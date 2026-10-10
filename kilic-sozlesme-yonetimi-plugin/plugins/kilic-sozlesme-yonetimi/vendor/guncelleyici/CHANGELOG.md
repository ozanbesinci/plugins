# Sürüm Geçmişi — guncelleyici

Sürümleme: büyük sürüm akış değişikliklerini, küçük sürüm yeni aşama ve
kontrolleri, yama sürümü düzeltmeleri belirtir. Yayımlanmamış değişiklikler
yerel geliştirme durumundadır.

## v2.3.0 — 2026-10-04 — Bağımsız güncelleyici ve pnpm native düzeltmesi

- 2026-10-04: Ortak'ın talimatıyla teklif-değerlendirme sürüm kontrolü, kurulum/güncelleme/doğrulama yolu ve ilgili araç/talimatlar kaldırıldı. Ana tablo altı program bileşeni içerir; PDF destekleyen kaynakta isteğe bağlı yedinci satır korunur.

- pnpm 12+ yerel (`pnpm.exe`) kurulumları Node ile betik gibi çalıştırıldığı için sürümsüz/yönetilmeyen görünüyordu; yerel ikili artık doğrudan sorgulanır. Kurulu pnpm "Yüklü değil" olarak raporlanmaz; engelli satırlar gerekçesiz kalmaz.
- pnpm 12+ güncellemesi: `@pnpm/exe.win32-x64` tarball'ı ve SHA-512'si taramada plana bağlanır; uygulamada iki paket de doğrulanır, scriptler/isteğe bağlı bağımlılıklar kapalı kalır, ikili doğrulanmış paketten çıkarılıp shim'ler doğrudan ona bağlanır. Offline/ignore-scripts koruması kaldırılmadı; başlatıcı çalıştırılmadığı için ikinci indirmeye gerek kalmaz.
- Test düzeneği: `test_scan.ps1` fixture kökü 8.3 kısa TEMP yolundan (`OZANBE~1`) kanonik uzun yola çevrildi; Power BI kontrolü gevşetilmedi. pnpm regresyonları bağımsız koşabilen `tests/test_pnpm.ps1` girişine taşındı ve `test_windows.ps1` tarafından da çağrılır.
- Gerçek pnpm 12.9.1 geçici kurulumu: ana/ikili tarball SHA-512, offline npm kurulumu, native probe ve CMD/PowerShell shim'leri dahil altı kontrol PASS. Kullanıcının canlı pnpm kurulumu değiştirilmedi.
- Windows PowerShell 5.1: genel47 + pnpm29 + tarama21 PASS. Python78 PASS/2 NOT_RUN. DuckDB1.5.6 PDF6535c81 imzalı LOAD ve sentetik metin smoke testi PASS.
- Bağımsız ZIP için deterministik paketleyici ve güncel manifest eklendi. Plugin kurulumundan bağımsız kaynak/paket yayınıdır. `production_approved=false`; kalan gerçek istemci/Excel/kurtarma matrisi ve personel pilotu açık.

## v2.2.1 — 2026-10-04 — Windows düzeltmeleri ve plugin paketi

- Gerçek PowerShell5.1 atomik JSON yazımında null yedek yolu düzeltildi; otomatik Bypass kaldırıldı.
- Python/Node release dizilerinin JSON açılması, sabit kütüphane setinin korunması, Power BI home değişkeni ve tr-TR pnpm sürüm karşılaştırması düzeltildi.
- Python kurucusu sınırlı bekleme900→1200 saniye; yalnız kendi süreç ağacı ve kalıcı kurtarma mekanizmaları korundu.
- pypdf yoksa isteğe bağlı PDF fixture NOT_RUN; bozuk fixture FAIL kalır.29 yeni scan regresyon kontrolü eklendi.
- Native normal kullanıcı PS5.1 x64: Python/Node/DuckDB/PBI server gerçek kurulum ve ayrı verify PASS;108 Python PASS/2 NOT_RUN,42Windows+29scan PASS.
- pnpm staging FAIL, teklif TLS BLOCKED, Excel yokluğu FAIL ve gerçek istemci/kalan matris NOT_RUN açık tutulur. Kurtarma kapısı PASS; production_approved=false.
- Kaynak2.2.1 ve Kılıç Satınalma plugin1.1.4 ZIP/SHA-256/manifest hazırlanır. Yayın ve canlı kurulum ayrı yetkilerdir.

## v2.2.0 — 2026-10-04 — Pro denetimi, Work/Codex sohbet yüzeyi ve kontrollü PDF

- GitHub Release `v2.2.0`, doğrulanmış `skill.zip` ve `skill.zip.sha256` varlıklarıyla yayımlandı; bu işlem `production_approved=false` durumunu değiştirmez ve native Windows kabulü yerine geçmez.
- Son kullanıcı yüzeyi ChatGPT Desktop Work/Codex sohbeti olarak sabitlendi; kullanıcıdan Terminal/PowerShell açması, komut kopyalaması veya script çalıştırması istenmez. Teknik PowerShell örnekleri ajan-içi yerel yürütme komutları olarak işaretlendi.
- Power BI MCP ertelenmiş bağlama akışı terminal talimatı vermek yerine istemciyi kapatıp sohbette bağlamayı yeniden istemeye çevrildi; Work/Codex `-BindOnly` bakım adımını yerel araçla yürütür.


- Windows PowerShell 5.1 kabulünde bulunan parser hatası düzeltildi: PowerShell tipografik `’` karakterini string sonlandırıcısı olarak yorumladığı için `core.ps1` içindeki `hash’i` ifadesi güvenli ASCII metne çevrildi. Tüm `.ps1` dosyalarında tipografik tırnak yasağı ve UTF-8 BOM regresyon kontrolleri eklendi.
- Uygulama girişine ayrıca `-ConfirmApply` zorunluluğu eklendi; seçim düzenleme artık kod seviyesinde de uygulama yetkisi sayılmaz.
- Plan çıktısı seçili bileşen yan etkilerini makine-okunur `effects` kayıtlarıyla taşır; sabit Python setindeki gerçek paket düşürmeleri ad/sürüm bazında onay öncesi görünür. Operasyonel referans/config dosyaları da plan kod parmak izine bağlandı.
- Pro ikinci denetimi sonrası Windows amd64/64-bit çalışma sözleşmesi bütün ana girişlerde erken doğrulanır; farklı mimaride indirme veya kurulum başlatılmaz.
- Kaynak sürüm `2.2.0` olarak yayımlandı. GitHub kaynak yayını, native Windows kabulü veya personel genel dağıtım onayı değildir; tamamlanmamış kabul adımları `BUILD.json` içinde açık tutulur.
- Sohbet orkestrasyonu core.ps1, ortak program yardımcıları program-ortak.ps1 olarak ayrıldı. Eski grafik panelin doğrudan çalıştırılması kapatıldı.
- Seçim değiştirme ile uygulama onayı ayrıldı. Plan; tam hedef, paket hash'i, yorumlayıcı/yerel durum, kullanıcı/bilgisayar/kod hash'i ve süre sınırına bağlandı. Kilit altında yeniden gözlem eklendi; uygulamada yeni latest seçimi kaldırıldı.
- Program kurucuları yalnız onaylı hedef dosyası/hash ile çalışır. Python doğrudan doğrulanan python.org kurucusunu kullanır; farklı winget artefaktı ve otomatik sözleşme kabulü kullanılmaz.
- Codex/Claude Desktop alan koruma, exact-byte yedek, atomik yazım/semantik kontrol; Claude Code'un kendi CLI'sıyla basit kayıt güncelleme/geri dönüş eklendi. Açık istemcide bağlama ertelenir.
- Node/pnpm son konum kontrolü ve eski sürüm yedeği; PBI ayrı ve doğrulanmış sürüm klasörü; teklif/PDF işlem günlüğü ve doğrulanan eski duruma dönüş geliştirildi.
- Sürüm ve sağlık ayrıldı; NOT_RUN/FAIL/WARNING görünür, açık verify/repair yolu eklendi. Paket hatasında sonraki belirsiz değişiklikler engellenir.
- Scan kurulum/sağlık kaydı yazmaz. Session planı, seçilenler, temizleme notları, nihai yerel gözlem ve kurtarma gereği kalıcı sonuçta bulunur.
- Sabit 12 Python paketi ayrı JSON kilidine taşındı. Ortak --user ortamı sessizce venv'e taşınmadı; bakım kontrolü ve kısmi pip hatasında recovery_required davranışı eklendi.
- DuckDB PDF ayrı, varsayılan seçili olmayan satırdır. Sürüm/platform/ikili hash'i sabitlenir; native imza ve golden metin testi için kod eklendi. Native PDF ve Türkçe OCR/tablo kabulü bu oturumda çalıştırılmadı.
- Yeni çevrimdışı Python regresyon testleri ve Windows PowerShell parser/orkestrasyon test koşucusu eklendi. Çalıştırılan ve çalıştırılmayan testler raporda ayrı tutulur.
- Bu paket, değişmeden kalan bir kurulum klonu değil, kaynakları revize edilmiş tam `2.2.0` sürüm paketidir. Native kabul ve kalan riskler `references/degisiklik-haritasi.md` ile `BUILD.json` içinde açıklanır.

## v2.1.0 — 2026-09-28

- Masaüstü Work ve Codex için sürüm seçimi sohbet tablosuna taşındı; PowerShell penceresi açılmadan `scan` ve açık kullanıcı seçiminden sonra `apply` çalışır.
- Tarama parmak iziyle sürüm değişikliği kontrolü, seçilemeyen satır reddi ve sıralı sonuç kaydı eklendi.
- DuckDB salt okuma taraması sonuç dosyası veya hata raporu yazmadan `@@SONUC` döndürür.
- Eski skill temizliği salt okuma taramasından çıkarılıp açık **Güncelle** seçiminin uygulama aşamasına taşındı.

## v2.0.0 — 2026-09-27

- Program ve teklif değerlendirme skill güncellemesi tek `guncelleyici` skill'i altında birleştirildi.
- Eski program öz güncellemesi kaldırıldı. Önceki Release paketi birleşik skill'in üzerine kurulmaz.
- `teklif-degerlendirme` güncellemesi yalnız hedef skill ağacını değiştirir; eski güncelleyici ağacını kurmaz.
- Windows seçim paneli eklendi. Panel yüklü ve güncel sürümleri karşılaştırır, her bileşen için seçim kutusu ve tek **Güncelle** düğmesi sunar.
- Yalnız seçilen bileşenler sıralı işlenir; sonuçlar sohbet tablosuna aktarılmak üzere yapılandırılmış çıktı olarak döndürülür.
- Eksik bileşenler “Yüklü değil” gösterilir; yükleme veya güncelleme gereken satırlar varsayılan işaretli gelir.
- Bütün bileşenlerin güncelliği doğrulanırsa tablo açılmadan “Güncelsiniz.” sonucu verilir.
- Güncelle düğmesine basıldığında seçim penceresi kapanır; seçili işlemler tamamlanana kadar süreç çalışmaya devam eder.
- Eski `program-guncelle` / `program-guncelleme` kullanıcı skill kurulumları panel açılışında kaldırılır. Junction hedefleri korunur; doğrulanmış fiziksel kurulumlar kullanıcı alanındaki karantinaya taşınır.
- Teklif değerlendirme sürümü, kararlı GitHub Release paketinin SHA-256 doğrulaması yapılan manifestinden okunur.
- Teklif sürümü sorgusu ve paket indirmesi, geçici bağlantı hatasında bir kez yeniden denenir; paket doğrulama hataları yine işlemi durdurur.
- Ağ erişimi engeli sürüm tablosunda açıklanır; kontrol edilemeyen satırların nedeni sonuç kaydında korunur.
- Teklif paketi SHA-256 kontrolü, PowerShell modülünün otomatik yüklenmesine bağlı kalmadan yapılır.
- Yüklü sürüm kararlı yayından ilerideyse tablo bunu ayrı durum olarak gösterir.
- Panel alt süreçlerinde UTF-8 çıktı, boşluk/tırnak içeren argümanlar ve çıkış kodları doğrulanır; eksik veya başarısız sonuçlar tamamlandı olarak gösterilmez.
- Kurulum sırası sabittir; seçim penceresinin kapanması işlemleri kesmez. Sonuçlarda hata, uyarı, rapor ve hedef sürüm doğrulaması korunur.
- Aynı kullanıcının birden çok panel üzerinden eşzamanlı kurulum başlatması engellenir.
- Teklif kontrolü ve kurulumu paket etiketinden bağımsız bileşen sürümünü karşılaştırır; doğrulanan paket kurulumda yeniden kullanılır.
- Yüklü sürümün tespit edilememesi, kurulum yokluğundan ayrı gösterilir. Python paket setinin sabit doğrulanmış sürümler kullandığı tabloda belirtilir.
- Panel seçim/bağımlılık testleri ile teklif geri dönüş ve program kurulum koruma testleri birleşik skill'in test dizininde genişletildi.

## v1.1.0 — 2026-09-26

- Kurulum veya kontrolü engelleyen kullanıcı programları önce normal, gerektiğinde zorla kapatılır; aynı aşama bir kez yeniden denenir ve sonuç raporlanır.
- Node.js sonrasına pnpm aşaması eklendi. Kararlı `latest` sürümü npm kayıt deposundan alınır ve kullanıcı alanında doğrulanır.
- pnpm için Node.js uyumluluk kontrolü, PATH kaydı ve başarısız güncellemede önceki kuruluma dönüş iyileştirildi.
- pnpm ikilisinin geçici Windows dosya kilitleri için sınırlı yeniden deneme eklendi.
- Python kurulumu başarısız olduğunda Python'a bağımlı aşamalar atlanır; bağımsız aşamalar devam eder.
- Node.js ve Power BI güncellemelerinde önceki çalışır kurulumun korunması ve karantina davranışı iyileştirildi.
- Power BI sunucusu ayarlara bağlanmadan önce sınanır.
- Ön kontrolün Excel süreç takibi ve ağ kaynakları güncellendi.
- Git Bash üzerinden başlatılan PowerShell işlemlerinde çalışan sürümün modül yolu kullanılır.

## v1.0.0 — 2026-09-24

- Satınalma yapay zekâ projeleri için kullanıcı alanında Python, 12 doğrulanmış Python paketi, Node.js, DuckDB ve Power BI Modeling MCP kurulumu sağlandı.
- Python kurulumunda desteklenen serinin son kararlı yaması; Node.js için son LTS; DuckDB için uyumlu son PyPI sürümü kullanılır.
- İndirilen paketlerin SHA-256 özetleri ve uygun kaynak imzaları doğrulanır.
- Python kütüphaneleri gerçek işle, Excel otomasyonu ve örnek dosya açma senaryolarıyla sınanır.
- Power BI MCP kurulumu isteğe bağlıdır; bağlama başarısız olursa önceki ayar korunur. Proxy kimlik bilgileri çıktı ve raporlarda gizlenir.
- İlk yerel doğrulamada Python kurulumu, 12 paket kurulumu ve 18 işlev kontrolü tamamlandı. Yöneticisiz personel bilgisayarında pilot doğrulama beklemektedir.
