"""program-guncelle — Asama 6 (DuckDB): en yeni surumle Python paketi.

python-kur.ps1'in buldugu/kurdugu Python ile, paket basina bir kez calistirilir:
  python python-paket-kur.py duckdb [--rapor RAPOR]
Yeni bir paket gerekirse PAKETLER sozlugune eklenir (asama adi, gorunen ad, PyPI dagitim adi, test).

Her paket icin: yuklu mu bakar; yuklu degilse kurar; yukluyse surumune bakar, bu Python icin PyPI'deki
en yeni surumun gerisindeyse gunceller; guncelse sonraki asamaya gecer (Ortak'in tanimi, 2026-09-24:
"her calistirmada en yeni"). En yeni surum her calistirmada pip'e cozdurulur (--dry-run --report);
cozulen dosyalar PyPI'nin yayimladigi SHA-256 ozetleriyle ve yalniz hazir derlenmis paket (wheel)
olarak kurulur (--require-hashes --only-binary). Kurulumdan sonra paket gercek bir isle denenir.

  duckdb -> DuckDB (duckdb paketi)
  (JEV / typesafe-sdk 2026-09-24'te Ozan'in karariyla cikarildi: API anahtari personelde tutulmayacak.)

Yalniz standart kutuphane kullanir. Guvenlik ayarlarini atlatmaya calismaz.
Cikti: son satir "@@SONUC {json}"; ayni JSON %LOCALAPPDATA%\\program-guncelle\\<paket>-kur-sonuc.json
durum: MEVCUT | KURULDU | GUNCELLENDI | ESKI (guncellenemedi, eski surum calisiyor) | BASARISIZ
--rapor verilirse sonuc kurulum testi raporunun sonuna eklenir.
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

KLASOR = os.path.dirname(os.path.abspath(__file__))
SKILL_KLASORU = os.path.dirname(KLASOR)
DURUM_KLASORU = os.path.join(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()), "program-guncelle")
INDEX = "https://pypi.org/simple"
# SKILL.md başlangıç mesajı, python-kur.ps1, node-kur.ps1 ve kurulum-testi.py ile aynı cümle.
AMAC = ("Satınalma Departmanının kullandığı yapay zekâ projelerinde gerekli olan programların "
        "personel bilgisayarına yüklenmesini sağlar.")
ALT_SUREC_ORTAMI = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
RENK = {"GEÇTİ": "\033[32m", "ENGEL": "\033[31m", "UYARI": "\033[33m", "BİLGİ": "\033[90m"}

# Gerçek iş testi: geçici klasörde çalışır, sonuç JSON olarak döner.
DUCKDB_TESTI = r"""
import json, os, sys, tempfile, duckdb
k = tempfile.mkdtemp(prefix="pg-duckdb-")
csv = os.path.join(k, "teklif.csv")
with open(csv, "w", encoding="utf-8") as f:
    f.write("tedarikci;tutar\nÇağ Ltd;1250,50\nİşçi A.Ş.;749,50\nÇağ Ltd;1000\n")
con = duckdb.connect(os.path.join(k, "test.duckdb"))
yol = csv.replace("'", "''")
con.execute(f"CREATE TABLE t AS SELECT * FROM read_csv('{yol}', delim=';', decimal_separator=',', header=true)")
satirlar = con.execute("SELECT tedarikci, SUM(tutar) FROM t GROUP BY 1 ORDER BY 1").fetchall()
con.close()
print(json.dumps({"surum": duckdb.__version__, "satirlar": [[a, float(b)] for a, b in satirlar]}, ensure_ascii=False))
"""
DUCKDB_BEKLENEN = [["Çağ Ltd", 2250.5], ["İşçi A.Ş.", 749.5]]

PAKETLER = {
    "duckdb": {"asama": "Aşama 7 — DuckDB", "ad": "DuckDB", "dagitim": "duckdb"},
}

sonuclar = []
aksiyonlar = []


def proxy_bilgisi_gizle(metin):
    return re.sub(r"(?i)\b(https?://)[^\s/]+@", r"\1***@", str(metin))


def ekle(ad, durum, ayrinti):
    ayrinti = proxy_bilgisi_gizle(ayrinti)
    sonuclar.append({"ad": ad, "durum": durum, "ayrinti": ayrinti})
    print(f"  {RENK.get(durum, '')}[{durum:<5}]\033[0m {ad}: {ayrinti}", flush=True)


def surum_oku():
    try:
        with open(os.path.join(SKILL_KLASORU, "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "?"


def sistem_proxy():
    try:
        p = urllib.request.getproxies()
        return p.get("https") or p.get("http")
    except Exception:  # noqa: BLE001
        return None


def pip_hatasini_yorumla(metin):
    m = metin.lower()
    if "do not match the hashes" in m or "hash mismatch" in m:
        return ("indirilen paket özeti tutmadı — dosya değişmiş ya da ağda araya giren var; kurulmadı", None)
    if "certificate verify failed" in m or "ssl" in m and "error" in m:
        return ("PyPI bağlantısında SSL doğrulaması başarısız (kurumsal SSL denetimi olabilir)",
                "PyPI (pypi.org, files.pythonhosted.org) için SSL denetimi istisnası ya da kurumsal kök "
                "sertifikanın Windows sertifika deposunda olduğunun teyidi.")
    if "407" in m or "proxy" in m:
        return ("proxy bağlantıyı reddetti ya da kimlik istiyor",
                "pip'in proxy üzerinden pypi.org ve files.pythonhosted.org'a çıkabilmesi.")
    if ("connection" in m or "timed out" in m or "getaddrinfo" in m or "no matching distribution" in m
            or "could not find a version" in m):
        return ("PyPI'ye erişilemedi ya da bu Python için paket dosyası yok",
                "pypi.org ve files.pythonhosted.org erişiminin açılması (yalnız HTTPS, yalnız okuma).")
    if "group policy" in m or "grup ilkesi" in m or "1260" in m:
        return ("program grup ilkesiyle engellendi",
                "Uygulama denetimi (AppLocker/WDAC): kullanıcının Python klasöründeki dosyalar için izin.")
    if "access is denied" in m or "erişim engellendi" in m or "permission" in m:
        return ("dosya yazma izni reddedildi (klasör izni ya da güvenlik yazılımı)",
                "Kullanıcının Python kütüphane klasörüne yazabilmesi; güvenlik yazılımı engelliyorsa "
                "o klasör için istisna.")
    return ("pip kurulumu başarısız", None)


def son_satirlar(metin, n=4):
    return " | ".join(s.strip() for s in proxy_bilgisi_gizle(metin).strip().splitlines()[-n:])[-500:]


def calistir(komut, sure):
    try:
        r = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=sure, env=ALT_SUREC_ORTAMI)
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", f"zaman aşımı ({sure} sn)"


def kurulu_surum(dagitim):
    # Ayrı süreçte bakılır: kurulumdan sonra bu sürecin paket bilgisi eskimiş olur.
    kod, out, _ = calistir([sys.executable, "-c",
                            f"import importlib.metadata as m\ntry: print(m.version({dagitim!r}))\nexcept Exception: print('')"], 60)
    return out.strip() or None if kod == 0 else None


def pypi_en_yeni(dagitim):
    """Bilgi amaçlı: PyPI'nin ilan ettiği en yeni sürüm (bu Python'a uymayabilir)."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{dagitim}/json", timeout=20) as y:
            return json.load(y)["info"]["version"]
    except Exception:  # noqa: BLE001
        return None


def pip_temel(sanal_ortam, proxy):
    k = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
         "--only-binary=:all:", "--index-url", INDEX, "--timeout", "60"]
    if not sanal_ortam:
        k.insert(4, "--user")
    if proxy:
        k += ["--proxy", proxy]
    return k


def coz(dagitim, sanal_ortam, proxy, calisma):
    """pip'e bu Python için en yeni sürümü ve eksik bağımlılıkları çözdürür; hiçbir şey kurmaz."""
    rapor = os.path.join(calisma, "cozum.json")
    komut = pip_temel(sanal_ortam, proxy) + ["--dry-run", "--quiet", "--report", rapor,
                                             "--upgrade", "--upgrade-strategy", "only-if-needed", dagitim]
    kod, out, err = calistir(komut, 300)
    if kod != 0 or not os.path.exists(rapor):
        return None, out + "\n" + err
    with open(rapor, encoding="utf-8") as f:
        kurulacaklar = json.load(f).get("install", [])
    liste = []
    for k in kurulacaklar:
        ai = (k.get("download_info") or {}).get("archive_info") or {}
        ozet = (ai.get("hashes") or {}).get("sha256") or (ai.get("hash", "").split("=", 1)[-1]
                                                          if ai.get("hash", "").startswith("sha256=") else "")
        if len(ozet) != 64:
            return None, f"{k['metadata']['name']} için PyPI özeti alınamadı; kurulmadı"
        liste.append({"ad": k["metadata"]["name"], "surum": k["metadata"]["version"], "sha256": ozet,
                      "istenen": bool(k.get("requested"))})
    return liste, ""


def kur(liste, sanal_ortam, proxy, calisma):
    istek = os.path.join(calisma, "requirements.txt")
    with open(istek, "w", encoding="utf-8") as f:
        for p in liste:
            f.write(f"{p['ad']}=={p['surum']} --hash=sha256:{p['sha256']}\n")
    # --no-deps: bağımlılıklar çözümde zaten listede; kurulacak küme tam olarak çözülen küme.
    komut = pip_temel(sanal_ortam, proxy) + ["--require-hashes", "--no-deps", "-r", istek]
    kod, out, err = calistir(komut, 1200)
    return kod == 0, out + "\n" + err


def test_et(anahtar):
    if anahtar == "duckdb":
        kod, out, err = calistir([sys.executable, "-c", DUCKDB_TESTI], 120)
        try:
            v = json.loads(out.strip().splitlines()[-1])
            if v["satirlar"] == DUCKDB_BEKLENEN:
                ekle("DuckDB işlev testi", "GEÇTİ", "Türkçe karakterli CSV okundu, veritabanı dosyasına yazıldı, "
                     "gruplu toplam doğru")
                return
            ekle("DuckDB işlev testi", "ENGEL", f"sonuç beklenen değil: {v['satirlar']}")
        except Exception:  # noqa: BLE001
            ekle("DuckDB işlev testi", "ENGEL", f"çalışmadı (kod {kod}): {son_satirlar(err or out)}")


def bagimlilik_denetimi():
    kod, out, err = calistir([sys.executable, "-m", "pip", "check", "--disable-pip-version-check"], 120)
    if kod == 0:
        return
    sorun = [s for s in proxy_bilgisi_gizle(out + "\n" + err).splitlines()
             if s.strip() and "No broken requirements" not in s]
    ekle("Bağımlılık uyumu", "UYARI", "pip check: " + " | ".join(sorun[:4])[-400:])


def bitir(anahtar, tanim, durum, kurulu_once, kurulu_son, hedef, pypi, neden, it_isi, kurulanlar, rapor_yolu, sure,
          kaydet=True):
    d = [s["durum"] for s in sonuclar]
    ozet = ("ENGEL" if durum == "BASARISIZ" or "ENGEL" in d else "UYARI" if durum == "ESKI" or "UYARI" in d
            else "BİLGİ" if durum == "YOK" else "GEÇTİ")
    sonuc = {"paket": anahtar, "dagitim": tanim["dagitim"], "durum": durum, "ozet": ozet,
             "kurulu_once": kurulu_once, "surum": kurulu_son, "hedef_surum": hedef, "pypi_en_yeni": pypi,
             "python": sys.executable, "neden": neden, "it_isi": it_isi, "kurulanlar": kurulanlar,
             "testler": sonuclar, "bilgisayar": os.environ.get("COMPUTERNAME", "?"),
             "zaman": dt.datetime.now().isoformat(timespec="seconds"), "sure_sn": round(sure)}
    s = ["", tanim["asama"].upper(), "-" * len(tanim["asama"]),
         f"[BİLGİ] Yüklü {tanim['ad']} (kurulumdan önce): {kurulu_once or 'yoktu'}",
         f"[BİLGİ] En yeni sürüm (bu Python için): {hedef or '?'}"
         + (f"; PyPI'de ilan edilen {pypi}" if pypi and pypi != hedef else ""),
         f"[{ozet:<5}] Durum: {durum}" + (f" — kullanılan {kurulu_son}" if kurulu_son else "")
         + (f"; {neden}" if neden else "")]
    if kurulanlar:
        s.append("[BİLGİ] Kurulan/güncellenen: " + ", ".join(f"{p['ad']} {p['surum']}" for p in kurulanlar)
                 + " (PyPI özetleriyle doğrulandı)")
    s += [f"[{x['durum']:<5}] {x['ad']}: {x['ayrinti']}" for x in sonuclar]
    if it_isi:
        s.append(f"IT'den gereken: {it_isi}")
    if kaydet and rapor_yolu and os.path.exists(rapor_yolu):
        with open(rapor_yolu, "a", encoding="utf-8") as f:
            f.write("\n".join(s) + "\n")
        sonuc["rapor"] = rapor_yolu
    elif kaydet and ozet == "ENGEL":
        masaustu = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        try:
            import ctypes.wintypes
            tampon = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, tampon) == 0:
                masaustu = tampon.value
        except Exception:  # noqa: BLE001
            pass
        if not os.path.isdir(masaustu):
            masaustu = DURUM_KLASORU
        yol = os.path.join(masaustu, f"{anahtar}-kurulumu-{os.environ.get('COMPUTERNAME', 'PC')}-"
                                     f"{dt.datetime.now():%Y%m%d-%H%M}.txt")
        bas = [f"GÜNCELLEYİCİ · sürüm {surum_oku()} — {tanim['ad'].upper()} KURULUMU", AMAC,
               f"Bilgisayar: {os.environ.get('COMPUTERNAME', '?')}  Kullanıcı: "
               f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}",
               f"Tarih: {dt.datetime.now():%d.%m.%Y %H:%M}"]
        with open(yol, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(bas + s) + "\n")
        sonuc["rapor"] = yol
    if kaydet:
        os.makedirs(DURUM_KLASORU, exist_ok=True)
        with open(os.path.join(DURUM_KLASORU, f"{anahtar}-kur-sonuc.json"), "w", encoding="utf-8") as f:
            json.dump(sonuc, f, ensure_ascii=False)
    print("@@SONUC " + json.dumps(sonuc, ensure_ascii=False), flush=True)
    sys.exit(0)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("paket", choices=sorted(PAKETLER))
    ap.add_argument("--rapor")
    ap.add_argument("--yalniz-bul", action="store_true", help="hiçbir şey kurmaz, yalnız bakar")
    args = ap.parse_args()
    tanim = PAKETLER[args.paket]
    dagitim = tanim["dagitim"]
    t0 = time.time()

    print(f"\n  Güncelleyici · sürüm {surum_oku()} — {tanim['ad']}\n  {AMAC}\n", flush=True)
    print(f"  {tanim['asama']}", flush=True)
    once = kurulu_surum(dagitim)
    print(f"  {tanim['ad']} yüklü: {once}" if once else f"  {tanim['ad']} yüklü değil; kurulacak.", flush=True)
    pypi = pypi_en_yeni(dagitim)

    sanal_ortam = sys.prefix != sys.base_prefix
    proxy = sistem_proxy()
    if proxy:
        ekle("Proxy", "BİLGİ", "sistem proxy'si kullanılıyor (adres gizlendi)")
    calisma = tempfile.mkdtemp(prefix="pg-paket-")
    try:
        liste, hata = coz(dagitim, sanal_ortam, proxy, calisma)
        if liste is None:
            neden, is_ = pip_hatasini_yorumla(hata)
            if once:
                ekle("En yeni sürüm", "UYARI", f"öğrenilemedi ({neden}); kurulu {once} kullanılıyor")
                bitir(args.paket, tanim, "ESKI", once, once, None, pypi, f"en yeni sürüm öğrenilemedi: {neden}",
                      is_, [], args.rapor, time.time() - t0, kaydet=not args.yalniz_bul)
            ekle("Kurulum", "ENGEL", f"{neden}. Son satırlar: {son_satirlar(hata)}")
            bitir(args.paket, tanim, "BASARISIZ", None, None, None, pypi, neden, is_, [], args.rapor, time.time() - t0,
                  kaydet=not args.yalniz_bul)
        hedefp = next((p for p in liste if p["ad"].lower().replace("_", "-") == dagitim), None)
        hedef = hedefp["surum"] if hedefp else once
        print(f"  En yeni sürüm (bu Python için): {hedef}", flush=True)

        if not liste:
            print(f"  {tanim['ad']} güncel, sonraki aşamaya geçiliyor.", flush=True)
            if not args.yalniz_bul:
                test_et(args.paket)
            bitir(args.paket, tanim, "MEVCUT", once, once, hedef, pypi, "", "", [], args.rapor, time.time() - t0,
                  kaydet=not args.yalniz_bul)
        if args.yalniz_bul:
            bitir(args.paket, tanim, "ESKI" if once else "YOK", once, once, hedef, pypi,
                  "yalnız bakıldı; kurulacaklar: " + ", ".join(f"{p['ad']} {p['surum']}" for p in liste),
                  "", [], args.rapor, time.time() - t0, kaydet=False)

        adlar = ", ".join(f"{p['ad']} {p['surum']}" for p in liste)
        print(f"  {'Güncelleniyor' if once else 'Kuruluyor'} (PyPI özetleriyle): {adlar}", flush=True)
        tamam, cikti = kur(liste, sanal_ortam, proxy, calisma)
        son = kurulu_surum(dagitim)
        if tamam and son == hedef:
            durum = "GUNCELLENDI" if once else "KURULDU"
            ekle("pip kurulumu", "GEÇTİ", f"{len(liste)} paket SHA-256 doğrulamasıyla kuruldu; "
                 f"{tanim['ad']} {(once + ' → ') if once else ''}{son}")
            bagimlilik_denetimi()
            test_et(args.paket)
            bitir(args.paket, tanim, durum, once, son, hedef, pypi, "", "", liste, args.rapor, time.time() - t0)
        neden, is_ = pip_hatasini_yorumla(cikti)
        if once and son:
            ekle("pip kurulumu", "UYARI", f"{neden}; kurulu {son} ile devam ediliyor. Son satırlar: {son_satirlar(cikti)}")
            test_et(args.paket)
            bitir(args.paket, tanim, "ESKI", once, son, hedef, pypi, f"{hedef} kurulamadı: {neden}", is_, [],
                  args.rapor, time.time() - t0)
        ekle("pip kurulumu", "ENGEL", f"{neden}. Son satırlar: {son_satirlar(cikti)}")
        bitir(args.paket, tanim, "BASARISIZ", once, son, hedef, pypi, neden, is_, [], args.rapor, time.time() - t0)
    finally:
        shutil.rmtree(calisma, ignore_errors=True)


if __name__ == "__main__":
    main()
