# Sürüm Geçmişi — guncelleyici

Sürümleme: büyük sürüm akış değişikliklerini, küçük sürüm yeni aşama ve
kontrolleri, yama sürümü düzeltmeleri belirtir. Yayımlanmamış değişiklikler
yerel geliştirme durumundadır.

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
