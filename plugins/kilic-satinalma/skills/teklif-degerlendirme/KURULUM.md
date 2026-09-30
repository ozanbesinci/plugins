# Kurulum ve dağıtım — ana skill v4.0.5 / birleşik güncelleyici

**4.0.5 kararlı dağıtım sürümüdür.** Kullanıcının 2026-09-30 tarihli açık
yayın kararıyla 4.0.3 sonrasındaki model/efor ve başlangıç düzeltmelerini içerir.
Excel/PDF doğrulaması ile uçtan uca canlı analiz kabulü ayrı kayıtlardır;
kararlı yayın, bütün canlı analiz senaryolarının kabul edildiği anlamına gelmez.
Resmî dağıtım deposu:
[ozanbesinci/teklif-degerlendirme](https://github.com/ozanbesinci/teklif-degerlendirme).

## Paket

Yeni teklif paketi yalnız ana skill'i içerir; birleşik `guncelleyici` ayrı
kalır. Paket manifesti şema 3'tür. Eski şema 1/2 paketleri güncelleyici
tarafından okunur, içlerindeki eski güncelleyici klasörü kurulmaz.

```text
skills/
  teklif-degerlendirme/
    SKILL.md
    VERSION
    requirements.txt
    config/
    references/
    scripts/
```

Paketin çalışma modülleri ve requirements.txt eksik/boşsa v4 kurulumu reddedilir;
`ajan_yonetimi.py` girişine ek olarak `ajan_v4.py` ve `kayit_temeli.py` de
zorunlu modül listesine dahildir.
Yalnız metadata/sürüm dosyası içeren bir arşiv çalışan eski ağacın yerine geçemez.
Kaynak depo ZIP'i, doğrulanmış dağıtım ZIP'iyle aynı kurulum biçimi sayılmaz.

## Gereksinimler

- Windows, yerel Codex masaüstü / ChatGPT Work, model/efor seçebilen yerleşik alt ajanlar.
- Çalıştırılarak doğrulanmış Python **3.14**; Store kısayolu yeterli değildir.
- `requirements.txt` içindeki tam sürümler: openpyxl, pypdf, pdfplumber,
  pypdfium2 ve pywin32. Sürüm kaynağı `guncelleyici` paket listesidir.
- Masaüstü Microsoft Excel; Python + pywin32 ile görünmez bağımsız örnekte gerçek
  yeniden hesaplama ve temiz kapanış.
- Gerçek güncel araç kataloğunda erişilebilir GPT-6.1 (`gpt-6.1-sol`) ve High eforu.
  Ana koordinatör ve bütün alt roller bu model/eforu kullanır; başka sürüme geçilmez.
- Gerçek oturum JSONL kayıtlarına, model/efora ve token sayaçlarına erişim.

Python/kütüphane eksikliği `guncelleyici` program akışının işidir. Python kurucusu veya wheel
dosyaları teklif paketine gömülmez; bu skill ikinci pip/winget kurulum yolu açmaz.
Katalog, efor, Excel veya telemetri yoksa “tam doğrulanmış v4” denmez.

## İlk kurulum ve güncelleme

Komutların güncel kaynağı `../guncelleyici/references/teklif-paketi.md` ve
`../guncelleyici/scripts/teklif-guncelle.py --help` çıktısıdır.

```text
python "<teklif-guncelle.py>" check --root "<fiziksel-skills>"
python "<teklif-guncelle.py>" update --root "<fiziksel-skills>"
python "<teklif-guncelle.py>" verify --root "<fiziksel-skills>"
```

“Sürümü kontrol et” yalnız okuma; “güncelle” yalnız ana skill ağacını yenileme
yetkisidir. Normal çevrimiçi güncelleme resmî kararlı Release'i kullanır.
Henüz yayımlanmamış yerel adayı GitHub'dan indirmeye çalışma.

Paket doğrulanmadan mevcut kurulum değiştirilmez. Ana skill ağacı dosyalar üst üste
eklenmeden tamamen değiştirilir; işlem hatasında önceki ağaç geri konur.
Windows geçici kilitleri sınırlı yeniden denemeye tabidir; kalıcı hata gizlenmez.
İşlem günlüğü, kurtarma ve kilit kontrolleri atlanmaz.

Yönetimsiz/değiştirilmiş eski kurulum otomatik silinmez. Yayımlanmış sürüm içeriği
değiştirilmez. Eski eşleştirilmiş paket kaydı yalnız ana skill'in dosya özetleri
eşleşiyorsa yeni tek skill kaydına alınır.
Doğrulanmış yerel aday `teklif-guncelle.py register --archive ... --sha256 ...`
ile kaydedilebilir; komut yalnız manifestle birebir eşleşen mevcut dosyaları
envantere alır, paket kurmaz.

Ortak fiziksel skill kökü ve mevcut junction düzeni korunur. Başka skill'ler, global
model/ajan ayarları ve kullanıcı dosyaları değiştirilmez. Yeni skill sonraki turda
keşfedilir; kullanıcıya görünmesi başarılı analiz koşusunun kanıtı değildir.

## Analizi başlatma

1. Personel ana sohbet için **GPT-6.1 / High** seçer; bütün alt görevler aynı model/eforu kullanır.
2. `$teklif-degerlendirme` ile kaynak dosyaları/klasörü verir.
3. Skill otomatik `guncelleyici` çağrısını atlar; ilk olarak aktif oturumun gerçek
   model/efor kaydını `oturum_kontrol.py` ile kontrol eder. GPT-6.1/High değilse
   kullanıcıdan ikisini de değiştirmesini ister. Her yeni yanıtta kontrol ve
   gerekiyorsa uyarı tekrarlanır; yalnız `READY` sonucuyla analize geçilir.
4. Skill envanter ve öneriyi gösterir; personel hızlı, standart veya yüksek güvence seçer.
5. Gerçek katalog ve ana oturum sayacıyla `prepare` değişmez koşu kopyasını oluşturur.
6. Sonraki işlemler manifestin `runner` yoluyla yürür. `task` yalnız görev kaydıdır;
   model yerleşik alt ajan aracıyla açık model/efor kullanılarak çağrılır.
7. Gerçek model/efor makbuzları, kod QA, bağımsız kaynak okuma, hakem, karar özeti
   ve Excel kontrolü tamamlandığında `verify` / `close` çalışır.

Komut yaşam döngüsü: `references/ajan-calistirma.md`.
Model talimatını yazmak aktif sohbet modelini değiştirmez. CLI model yürütme veya
oturum devamıyla düzeltme kullanılmaz. Tam sohbet her alt ajana aktarılmaz.

Hazırlanmış analiz sabit kopyasından yürür; sonraki ortak kurulum değişikliği bu
kopyayı değiştirmez. Güncelleme kilidinde yeni snapshot alınmaz. Eski global analiz
kilidi veya yarım işlem kilidi otomatik silinmez. Kaynak değişirse yeni revizyon koşusu gerekir.

## Yerel kontrol ve canlı kabul

- Paketlenen ana skill'in VERSION, SKILL metadata ve CHANGELOG'u eşleşmelidir.
- Hesap örnekleri, merkezi veri, model çözümü, oturum kanıtı, bütçe, Excel ve
  güncelleme testleri çalıştırılır. Sadece başlık/metin eşleşmesi yeterli değildir.
- Gerçek Excel yeniden hesaplama, bağımsız motor mutabakatı ve parametreyi geri alma
  testi, formül XML'ine cache yazmaktan farklıdır; fiilen çalıştırılmalıdır.
- Gerçek kullanıcı verili canlı kabul ayrı kayıttır. Hızlı: 8M/25 dk; standart:
  25M/60 dk; yüksek güvence: 50M/120 dk. Bunlar tavan, süre tahmini değildir.
- Kabulte kaynak bulguları, açık konular, doğru son birikimli sayaçlar ve süre kaydedilir.
  Sentetik birim testleri gerçek model davranışı veya tasarruf oranı kanıtlamaz.
- 4.0.2 kullanıcının açık kararıyla kararlı sürüm olarak yayımlanır. Uçtan uca
  canlı analiz kabulünün durumu ayrıca izlenir; yapılmamış kontrol geçti sayılmaz.

## Paket hazırlama ve yayın

`scripts/paket_olustur.py` yalnız ana skill'in izinli kaynak dosyalarını alır.
Paket doğrulayıcısı için aynı fiziksel `skills/` kökünde `guncelleyici` bulunmalıdır.
Çıktı skill ağacının dışında olmalıdır. requirements.txt pakete girer; şirket
teklifleri, fiyatlar, raporlar, sohbet/oturum/hafıza, kimlik bilgileri ve gerçek test
verileri girmez. Paket hash'i bütünlüğü doğrular; bağımsız yayıncı imzası değildir.

Release etiketi ve paket version alanı aynı olmalıdır.
Yerel kurulum, commit/push/tag/Release/yükleme yetkisi değildir. Kullanıcı yayın
talep etmeden yayın yapılmaz; yerel durum ile yayımlanmış durum ayrı raporlanır.

Eski ortak 3.0.1 güncelleyici yeni paketi okuyamaz. Böyle bir kurulumdan ilk geçiş
birleşik güncelleyicinin doğrulanmış kaynak kopyasıyla yapılır.

v4 bu ortam için tasarlanır; Claude Teams ve diğer web istemcileri doğrulanmış
çalışma kapsamı dışındadır. İş kılavuzlarını okuyabilmeleri aynı model/araç/Excel
doğrulama yeteneğine sahip olduklarını göstermez.
