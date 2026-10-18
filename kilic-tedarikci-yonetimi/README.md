# Kılıç Tedarikçi Yönetimi 1.4.0

Kaynak kanıtlı teklif değerlendirme, otomatik yerel hesap ve Excel/PDF raporlama. Altı teklif becerisi **5.2.0** sürümündedir. Güncelleyici becerisi paketten çıkarılmıştır; analiz hazır ortamı doğrular ve kullanır.

## Kurulum

1. [1.4.0 sürüm sayfasından](https://github.com/ozanbesinci/plugins/releases/tag/kilic-tedarikci-yonetimi-v1.4.0) **kilic-teklif-1.4.0-kurulum.zip** dosyasını indirin ve tamamını bir klasöre çıkarın.
2. `kurulum/Kur.cmd` dosyasını çift tıklayın. Kurulum kullanıcı profiline Python, kilitli paketler ve LibreOffice hesap motorunu hazırlar; yönetici yetkisi veya sistem PATH değişikliği gerektirmez.
3. ChatGPT Business çalışma alanındaki **Kılıç Tedarikçi Yönetimi** eklentisini seçerek Work görevini masaüstünden başlatın.

Yerel bilgisayar ve bağlı ChatGPT masaüstü açık kalmalıdır. Web'de aynı yerel erişime sahip mevcut Work görevi üzerinden devam edilir. Yeni bir web sohbetinin kendiliğinden bilgisayara bağlandığı varsayılmaz. Excel hesap kontrolü otomatik yürür; her analizde kullanıcıya ayrı hesap kontrolü yaptırılmaz.

Eklenti yöneticisi için **kilic-tedarikci-yonetimi-1.4.0.zip** yalnız eklenti paketidir. Python kurucusu ayrı ZIP içindedir. Kurumsal çalıştırma politikası kurulumu engelliyorsa kurucu bunu bildirir; politika değiştirilmez.

## Doğrulama

Kabul edilmiş yürütülebilir kodda SQLite 669 + gerçek DuckDB 669 = **1.338 test** geçti. Microsoft Excel referansı 16.136 formülde karşılaştırıldı; gerçek Work çıktısındaki 2.288 formül de ayrı Excel kopyasıyla eşleşti. Python olmayan, yönetici olmayan temiz Windows Sandbox hesabında kurulum geçti. Gerçek Work, aynı sohbet web devamı ve özgün Excel/PDF/manifest ZIP teslimi doğrulandı.

[Ayrıntılı kabul kapsamı](plugins/kilic-satinalma/skills/teklif-degerlendirme/references/RELEASE_ACCEPTANCE_5.2.0.md) · [Kurulum ayrıntısı](kurulum/README.md) · [Değişiklikler](plugins/kilic-satinalma/skills/teklif-degerlendirme/CHANGELOG.md).

Bilinemeyen fiyat, vergi, kur veya teknik veri uydurulmaz; kaynakla doğrulanan hesaplar ve kullanıcı senaryoları ayrı tutulur. Özgün dosyalar ZIP içinde teslim edilir; tekil Library PDF önizlemesi metadata nedeniyle farklı dosya baytları taşıyabilir.
