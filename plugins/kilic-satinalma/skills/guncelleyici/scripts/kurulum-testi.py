"""program-guncelle — kutuphane kurulumu + kurulum testi.

python-kur.ps1'in buldugu/kurdugu Python ile calistirilir (desteklenen seri: DESTEK_SERI):
  1) 12 paketi PyPI'den sabit surum ve SHA-256 ozetiyle kullanici alanina kurar (--require-hashes).
  2) islev-testi.py ile her kutuphaneyi gercek bir isle dener; Excel'i Python'dan gorunmez acar.
  3) Masaustune rapor yazar; son satir "@@SONUC {json}".

Yalniz standart kutuphane kullanir. Guvenlik ayarlarini atlatmaya calismaz.

Kullanim: python kurulum-testi.py [--rapor-klasoru KLASOR] [--kurma]
  --kurma : paket kurmaz, yalniz mevcut kurulumu test eder.
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
# SKILL.md başlangıç mesajı ve python-kur.ps1 ile aynı cümle; birini değiştiren üçünü de değiştirir.
AMAC = ("Satınalma Departmanının kullandığı yapay zekâ projelerinde gerekli olan programların "
        "personel bilgisayarına yüklenmesini sağlar.")
ALT_SUREC_ORTAMI = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")

# Skill'in destekledigi Python serisi; python-kur.ps1'deki $DESTEK_SERI ile ayni olmali.
DESTEK_SERI = (3, 14)
# Sabit surumler ve PyPI'nin yayimladigi SHA-256 ozetleri (Windows 64-bit / CPython 3.14 ile
# uyumlu butun wheel dosyalari; pip hangisini secerse secsin ozeti listede olmali).
PAKETLER = [
    ("openpyxl", "3.1.5", ["5282c12b107bffeef825f4617dc029afaf41d0ea60823bbb665ef3079dc79de2"]),
    ("et-xmlfile", "2.0.0", ["7a91720bc756843502c3b7504c77b8fe44217c85c537d85037f0f536151b2caa"]),
    ("pypdf", "6.13.2", ["6eeb9e57693f29d41bd01255d02660cbbb41fd7fc818a982677389a35e4f2083"]),
    ("pdfplumber", "0.11.10", ["7741ea81bf165b474b153e6789d10d18e06b6ddcf3ec84289c3ef2fed6802580"]),
    ("pdfminer.six", "20260107", ["366585ba97e80dffa8f00cebe303d2f381884d8637af4ce422f1df3ef38111a9"]),
    ("charset-normalizer", "3.4.7", ["92a0a01ead5e668468e952e4238cccd7c537364eb7d851ab144ab6627dbbe12f", "3dce51d0f5e7951f8bb4900c257dad282f49190fdbebecd4ba99bcc41fef404d"]),
    ("cryptography", "48.0.0", ["5b012212e08b8dd5edc78ef54da83dd9892fd9105323b3993eff6bea65dc21d7", "16cd65b9330583e4619939b3a3843eec1e6e789744bb01e7c7e2e62e33c239c8"]),
    ("cffi", "2.0.0", ["203a48d1fb583fc7d78a4c6655692963b860a417c0528492a6bc21f1aaefab25"]),
    ("pycparser", "3.0", ["b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992"]),
    ("pillow", "12.2.0", ["4e6c62e9d237e9b65fac06857d511e90d8461a32adcc1b9065ea0c0fa3a28150"]),
    ("pypdfium2", "5.10.1", ["58da5b51fb7884c7d21a05062ab13edb011d1a08dfd9694f3d5d685df62796b9"]),
    ("pywin32", "312", ["a4dd3a848290ef724347b19f301045831d8e802fa4464f491b98b1e0a081432e"]),
]

K1 = "Kalem 1 - Python kurulumu"
K2 = "Kalem 2 - Kütüphane kurulumu"
K3 = "Kalem 3 - Excel otomasyonu"
RENK = {"GEÇTİ": "\033[32m", "ENGEL": "\033[31m", "UYARI": "\033[33m", "BİLGİ": "\033[90m"}

sonuclar = []
aksiyonlar = []


def proxy_bilgisi_gizle(metin):
    return re.sub(r"(?i)\b(https?://)[^\s/]+@", r"\1***@", str(metin))


def ekle(kalem, ad, durum, ayrinti):
    ayrinti = proxy_bilgisi_gizle(ayrinti)
    sonuclar.append({"kalem": kalem, "ad": ad, "durum": durum, "ayrinti": ayrinti})
    print(f"  {RENK.get(durum, '')}[{durum:<5}]\033[0m {ad}: {ayrinti}", flush=True)


def aksiyon(kalem, metin):
    if {"kalem": kalem, "metin": metin} not in aksiyonlar:
        aksiyonlar.append({"kalem": kalem, "metin": metin})


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
        return ("indirilen paket özeti tutmadı — dosya değişmiş ya da ağda araya giren var; kurulmadı",
                None)
    if "certificate verify failed" in m or "ssl" in m and "error" in m:
        return ("PyPI bağlantısında SSL doğrulaması başarısız (kurumsal SSL denetimi olabilir)",
                "PyPI (pypi.org, files.pythonhosted.org) için SSL denetimi istisnası ya da kurumsal kök "
                "sertifikanın Windows sertifika deposunda olduğunun teyidi.")
    if "407" in m or "proxy" in m:
        return ("proxy bağlantıyı reddetti ya da kimlik istiyor",
                "pip'in proxy üzerinden pypi.org ve files.pythonhosted.org'a çıkabilmesi.")
    if ("connection" in m or "timed out" in m or "getaddrinfo" in m or "no matching distribution" in m
            or "could not find a version" in m):
        return ("PyPI'ye erişilemedi",
                "pypi.org ve files.pythonhosted.org erişiminin açılması (yalnız HTTPS, yalnız okuma).")
    if "group policy" in m or "grup ilkesi" in m or "1260" in m:
        return ("program grup ilkesiyle engellendi",
                "Uygulama denetimi (AppLocker/WDAC): kullanıcının Python klasöründeki dosyalar için izin.")
    if "access is denied" in m or "erişim engellendi" in m or "permission" in m:
        return ("dosya yazma izni reddedildi (klasör izni ya da güvenlik yazılımı)",
                "Kullanıcının Python kütüphane klasörüne yazabilmesi; güvenlik yazılımı engelliyorsa "
                "o klasör için istisna.")
    return ("pip kurulumu başarısız", None)


def kutuphaneleri_kur():
    sanal_ortam = sys.prefix != sys.base_prefix
    istek = os.path.join(tempfile.mkdtemp(prefix="ksk-pip-"), "requirements.txt")
    with open(istek, "w", encoding="utf-8") as f:
        for ad, surum, ozetler in PAKETLER:
            f.write(f"{ad}=={surum} " + " ".join(f"--hash=sha256:{h}" for h in ozetler) + "\n")
    komut = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
             "--only-binary=:all:", "--require-hashes", "--index-url", INDEX, "--timeout", "60",
             "-r", istek]
    if not sanal_ortam:
        komut.insert(4, "--user")
    proxy = sistem_proxy()
    if proxy:
        komut += ["--proxy", proxy]
        ekle(K2, "Proxy", "BİLGİ", "sistem proxy'si kullanılıyor (adres gizlendi)")
    print("\n  Aşama 3 — Kütüphaneler", flush=True)
    print("  12 paket PyPI'den sabit sürüm ve özetle kuruluyor (yaklaşık 30 MB, birkaç dakika sürebilir)...",
          flush=True)
    t0 = time.time()
    try:
        r = subprocess.run(komut, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=1200, env=ALT_SUREC_ORTAMI)
    except subprocess.TimeoutExpired:
        ekle(K2, "pip kurulumu", "ENGEL", "20 dakikada tamamlanmadı (ağ çok yavaş ya da kesik)")
        aksiyon(K2, "pypi.org ve files.pythonhosted.org erişiminin açılması (yalnız HTTPS, yalnız okuma).")
        return False
    finally:
        shutil.rmtree(os.path.dirname(istek), ignore_errors=True)
    # Kimlik bilgisi kısaltmayla parçalanmadan önce tam çıktıda gizlenmeli.
    cikti = proxy_bilgisi_gizle((r.stdout or "") + "\n" + (r.stderr or ""))
    if r.returncode == 0:
        zaten = cikti.count("Requirement already satisfied")
        ek = f"; {zaten} paket zaten kuruluydu" if zaten else ""
        yer = "sanal ortam" if sanal_ortam else "kullanıcı alanı (--user)"
        ekle(K2, "pip kurulumu", "GEÇTİ",
             f"12 paket sabit sürüm + SHA-256 doğrulamasıyla kuruldu → {yer}; {time.time() - t0:.0f} sn{ek}")
        return True
    neden, is_ = pip_hatasini_yorumla(cikti)
    son = " | ".join(s.strip() for s in cikti.strip().splitlines()[-4:])[-500:]
    ekle(K2, "pip kurulumu", "ENGEL", f"{neden}. Son satırlar: {son}")
    if is_:
        aksiyon(K2, is_)
    return False


def islev_testi():
    print("\n  Aşama 4 — Test (kütüphaneler gerçek işle, ardından Excel otomasyonu)", flush=True)
    calisma = tempfile.mkdtemp(prefix="ksk-kurulum-testi-")
    try:
        r = subprocess.run([sys.executable, os.path.join(KLASOR, "islev-testi.py"), calisma],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
                           env=ALT_SUREC_ORTAMI)
        satirlar = [s for s in (r.stdout or "").splitlines() if s.startswith("@@T ")]
        for s in satirlar:
            t = json.loads(s[4:])
            ekle(t["kalem"], t["ad"], t["durum"], t["ayrinti"])
        if not satirlar or r.returncode != 0:
            son = " | ".join(proxy_bilgisi_gizle(r.stderr or "").strip().splitlines()[-4:])[-500:]
            ekle(K2, "İşlev testi", "ENGEL", f"test süreci beklenmedik biçimde bitti (kod {r.returncode}): {son}")
    except subprocess.TimeoutExpired:
        ekle(K3, "İşlev testi", "ENGEL", "5 dakikada tamamlanmadı (Excel yanıt vermiyor olabilir)")
    finally:
        shutil.rmtree(calisma, ignore_errors=True)


def aksiyonlari_turet():
    for s in sonuclar:
        if s["durum"] != "ENGEL":
            continue
        a = s["ayrinti"].lower()
        if s["kalem"] == K2 and ("dll load failed" in a or "yüklenemedi" in a or "importerror" in a):
            aksiyon(K2, "Kütüphane DLL/PYD dosyaları yüklenemiyor: güvenlik yazılımı (antivirüs/EDR) "
                        "ya da uygulama denetimi kullanıcının Python kütüphane klasörünü engelliyor — "
                        "o klasör için istisna.")
        if s["kalem"] == K3:
            if "excel" in s["ad"].lower() and ("class not registered" in a or "sınıf kayıtlı değil" in a
                                                or "invalid class string" in a):
                aksiyon(K3, "Masaüstü Excel kurulu değil ya da otomasyon kaydı bozuk: Microsoft 365 "
                            "masaüstü Excel kurulumu/onarımı.")
            elif "görünmez açma" in s["ad"].lower() or s["ad"] == "Excel otomasyonu":
                aksiyon(K3, "Excel COM otomasyonu engelli: güvenlik yazılımında python.exe'nin kullanıcı "
                            "oturumunda Excel'i görünmez başlatmasına izin.")
    for s in sonuclar:
        if s["ad"] == "İnternetten gelmiş dosyayı açma" and s["durum"] == "UYARI":
            aksiyon(K3, "Mailden gelen dosyalar otomasyonla açılamıyor: yapay zekâ çalışma klasörü Excel'de "
                        "Güvenilen Konum olarak tanımlanmalı.")


def en_kotu(kalem):
    d = [s["durum"] for s in sonuclar if s["kalem"] == kalem]
    for durum in ("ENGEL", "UYARI"):
        if durum in d:
            return durum
    return "GEÇTİ"


YORUM = {"ENGEL": "engel var — IT işlemi gerekli", "UYARI": "çalışıyor ama teyit gerekli",
         "GEÇTİ": "çalışıyor"}


def rapor_yaz(klasor, baslangic, kur_bilgisi):
    ad = f"python-kurulum-testi-{os.environ.get('COMPUTERNAME', 'PC')}-{baslangic:%Y%m%d-%H%M}.txt"
    yol = os.path.join(klasor, ad)
    s = []
    s.append(f"GÜNCELLEYİCİ · sürüm {surum_oku()} — KURULUM TESTİ RAPORU")
    s.append(AMAC)
    s.append("")
    s.append(f"Tarih        : {baslangic:%d.%m.%Y %H:%M}")
    s.append(f"Bilgisayar   : {os.environ.get('COMPUTERNAME', '?')}")
    s.append(f"Kullanıcı    : {os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}")
    s.append(f"Süre         : {(dt.datetime.now() - baslangic).seconds} sn")
    s.append("")
    s.append("ÖZET")
    s.append("----")
    for k in (K1, K2, K3):
        e = en_kotu(k)
        s.append(f"{k:<30} {e:<6} {YORUM[e]}")
    s.append("")
    s.append("IT'DEN GEREKEN İŞLEMLER")
    s.append("-----------------------")
    if aksiyonlar:
        s += [f"- [{a['kalem']}] {a['metin']}" for a in aksiyonlar]
    else:
        s.append("Yok — üç kalem de bu bilgisayarda çalışıyor.")
    for k in (K1, K2, K3):
        s.append("")
        s.append(k.upper())
        s.append("-" * len(k))
        s += [f"[{x['durum']:<5}] {x['ad']}: {x['ayrinti']}" for x in sonuclar if x["kalem"] == k]
    if kur_bilgisi and kur_bilgisi.get("denemeler"):
        s.append("")
        s.append("PYTHON KURULUM DENEMELERİ")
        s.append("-------------------------")
        s += [f"- {d.get('yol')}: {d.get('sonuc')} {d.get('ayrinti', '')}".rstrip() for d in kur_bilgisi["denemeler"]]
    s.append("")
    s.append("Not: Test dosyaları geçici klasörde oluşturuldu ve silindi. Kurulan kütüphaneler kullanıcının")
    s.append("Python alanında kalır; Satınalma yapay zekâ projeleri bunları kullanır.")
    with open(yol, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(s) + "\n")
    return yol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapor-klasoru")
    ap.add_argument("--kurma", action="store_true")
    args = ap.parse_args()
    baslangic = dt.datetime.now()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    os.system("")  # Windows konsolunda renk kodlarini etkinlestirir

    print(f"\n  Güncelleyici · sürüm {surum_oku()} — kurulum testi\n  {AMAC}\n", flush=True)

    # Kalem 1
    kur_bilgisi = None
    try:
        with open(os.path.join(DURUM_KLASORU, "python-kur-sonuc.json"), encoding="utf-8-sig") as f:
            kur_bilgisi = json.load(f)
    except (OSError, ValueError):
        pass
    surum = sys.version.split()[0]
    seri = f"{DESTEK_SERI[0]}.{DESTEK_SERI[1]}"
    if sys.version_info[:2] != DESTEK_SERI:
        ekle(K1, "Python", "ENGEL", f"bu test Python {seri} serisini ister, çalışan sürüm {surum} ({sys.executable})")
        return bitir(args, baslangic, kur_bilgisi)
    yol = sys.executable
    local = os.environ.get("LOCALAPPDATA", "")
    kapsam = ("kullanıcı alanı" if local and yol.lower().startswith(local.lower())
              else "Microsoft Store" if "\\windowsapps\\" in yol.lower() else "makine geneli")
    yontem = (kur_bilgisi or {}).get("yontem") or "bilinmiyor"
    print("  Aşama 1–2 — Python", flush=True)
    mevcut = (kur_bilgisi or {}).get("mevcut_pythonlar")
    if mevcut is not None:
        ekle(K1, "Aşama 1: yüklü Python", "BİLGİ", "; ".join(mevcut) if mevcut else "yoktu — kuruldu")
    bilgi = kur_bilgisi or {}
    hedef = bilgi.get("hedef_surum")
    hedef_metni = f"; son sürüm {hedef} ({bilgi.get('hedef_kaynagi')})" if hedef else ""
    if bilgi.get("durum") == "ESKI_YAMA" and hedef and hedef != surum:
        ekle(K1, "Aşama 2: Python son sürüm", "UYARI",
             f"{surum} çalışıyor ama son sürüm değil — {yol} ({kapsam}{hedef_metni}). {bilgi.get('neden', '')}")
        if kapsam == "makine geneli":
            aksiyon(K1, f"Makine geneline kurulu Python {surum}, son sürüme ({hedef}) güncellenmeli "
                        f"(yönetici yetkisi gerekir); ya da kaldırılırsa skill son sürümü kullanıcı alanına kurar.")
    else:
        ekle(K1, "Aşama 2: Python son sürüm", "GEÇTİ",
             f"{surum} çalışıyor — {yol} ({kapsam}; kurulum: {yontem}{hedef_metni})")
    if bilgi.get("yeni_seri_var"):
        ekle(K1, "Yeni Python serisi", "BİLGİ",
             f"Python {bilgi['yeni_seri_var']} yayımlandı; skill şimdilik {seri} serisini kuruyor "
             f"(kütüphaneler bu seriye göre doğrulandı). Seri, skill güncellemesiyle ilerletilecek.")
    if kapsam == "Microsoft Store":
        ekle(K1, "Python kaynağı", "UYARI", "Store sürümü klasör yönlendirmesi yapar; python.org sürümü önerilir")

    # Kalem 2 + 3
    if args.kurma:
        print("\n  Aşama 3 — Kütüphaneler", flush=True)
        ekle(K2, "pip kurulumu", "BİLGİ", "--kurma verildi; kurulum atlandı, mevcut kütüphaneler test ediliyor")
        islev_testi()
    elif kutuphaneleri_kur():
        islev_testi()
    else:
        ekle(K3, "Excel otomasyonu", "BİLGİ", "kütüphaneler kurulamadığı için denenmedi")
    return bitir(args, baslangic, kur_bilgisi)


def bitir(args, baslangic, kur_bilgisi):
    aksiyonlari_turet()
    klasor = args.rapor_klasoru
    if not klasor:
        try:
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY
            klasor = buf.value
        except Exception:  # noqa: BLE001
            klasor = None
    if not klasor or not os.path.isdir(klasor):
        klasor = DURUM_KLASORU
    os.makedirs(klasor, exist_ok=True)
    rapor = rapor_yaz(klasor, baslangic, kur_bilgisi)
    ozet = {k: en_kotu(k) for k in (K1, K2, K3)}
    print("\n  Özet:")
    for k, e in ozet.items():
        print(f"  {RENK[e]}{k:<30} {e:<6} {YORUM[e]}\033[0m")
    print(f"\n  Rapor: {rapor}\n")
    print("@@SONUC " + json.dumps({"ozet": ozet, "aksiyonlar": [a["metin"] for a in aksiyonlar],
                                   "rapor": rapor}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
