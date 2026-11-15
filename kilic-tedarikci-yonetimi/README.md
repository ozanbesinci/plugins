# Kılıç Tedarikçi Yönetimi 1.4.1

Kaynak kanıtlı teklif değerlendirme, otomatik yerel hesap ve Excel/PDF raporlama. Altı teklif becerisi **5.2.1** sürümündedir. Güncelleyici becerisi paketten çıkarılmıştır; analiz hazır ortamı doğrular ve kullanır.

## Kurulum

ChatGPT Business çalışma alanındaki **Kılıç Tedarikçi Yönetimi** eklentisini seçerek yerel bilgisayara bağlı Work görevini başlatın. Eklenti `scripts/teklif.cmd` ile ortamı kontrol eder. Eksik Python veya hesap motoru varsa doğrulanmış kurulum paketini otomatik indirip çalıştırır; ardından aynı talebe devam eder. Kullanıcıdan geliştirici izni veya elle indirme istenmez. Yönetici yetkisi, PATH veya güvenlik ilkesi değiştirilmez; somut bir engel varsa bildirilir.

Yayımlanmış 1.4.0 kurucusunun Python ve hesap motoru kilitleri korunmuştur. Hazır ortamda tekrar kurulum yapılmaz. Yerel erişimi olmayan yeni web sohbetinde kurulum yapılmış gibi gösterilmez.

## Doğrulama

Önceki 1.4.0 sürümünün kabul edilmiş yürütülebilir kodunda SQLite 669 + gerçek DuckDB 669 = **1.338 test** geçti. Microsoft Excel referansı 16.136 formülde karşılaştırıldı; gerçek Work çıktısındaki 2.288 formül de ayrı Excel kopyasıyla eşleşti. Python olmayan, yönetici olmayan temiz Windows Sandbox hesabında kurulum geçti. Gerçek Work, aynı sohbet web devamı ve özgün Excel/PDF/manifest ZIP teslimi doğrulandı.

[Ayrıntılı kabul kapsamı](plugins/kilic-satinalma/skills/teklif-degerlendirme/references/RELEASE_ACCEPTANCE_5.2.0.md) · [Kurulum ayrıntısı](kurulum/README.md) · [Değişiklikler](plugins/kilic-satinalma/skills/teklif-degerlendirme/CHANGELOG.md).

Bilinemeyen fiyat, vergi, kur veya teknik veri uydurulmaz; kaynakla doğrulanan hesaplar ve kullanıcı senaryoları ayrı tutulur. Özgün dosyalar ZIP içinde teslim edilir; tekil Library PDF önizlemesi metadata nedeniyle farklı dosya baytları taşıyabilir.
