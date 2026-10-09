# Kılıç Satınalma 1.2.0

Teklif Değerlendirme **5.0.29** ve bağımsız Güncelleyici **2.3.0** içerir. Kılıç Satınalma Departmanı tarafından geliştirilmiştir.

| Beceri | Görev | Sürüm |
|---|---|---|
| teklif-degerlendirme | Ana giriş; teklif değerlendirme akışını ve kalite kapılarını yönetir. | 5.0.29 |
| teklif-belge-kaynak | Belgeleri, kaynak kimliğini, revizyonu ve kanıtı değerlendirir. | 5.0.29 |
| teklif-kapsam-ticari | Kapsam ve ticari koşulları karşılaştırır; gerekli soruları oluşturur. | 5.0.29 |
| teklif-maliyet | Kanıtlı miktar, fiyat, maliyet köprüsü ve satır hesaplarını yönetir. | 5.0.29 |
| teklif-bagimsiz-kontrol | Bağımsız inceleme ve hesap doğrulama kapılarını yönetir. | 5.0.29 |
| teklif-karar-rapor | Gerekçeli öneri, aynı inceleme kaydına bağlı Excel/PDF ve çıktı kontrollerini yönetir. | 5.0.29 |
| guncelleyici | Windows programlarını açık seçim/onayla kontrol eder ve günceller. | 2.3.0 |

Her beceri başlatıldığında gerçek adı ve sürümüyle Kılıç Satınalma Departmanı geliştirme bildirimi gösterilir. Ana giriş `teklif-degerlendirme` becerisidir; alt beceriler aynı değerlendirme koşusuna bağlanır.

Kullanıcının ilgili firma ve alana ilişkin doğrudan teyit veya düzeltmesi geçerli değerlendirme kanıtıdır. Özgün belge ve değişiklik izi korunur. Bilinmeyen değerler uydurulmaz; cevaplanan alanlar tekrar sorulmaz. Kararı etkileyen belirsizlikler kullanıcıya sorulur. Kaynak, sayı, hesap ve görsel kalite kontrolleri kendi gerçek sonuçlarıyla kaydedilir.

Hesaplar ve Excel/PDF aynı dondurulmuş inceleme kaydından üretilir. Rapor dosyasının oluşması kabul tamamlandığı anlamına gelmez: gerekli son kalite ve kapanış kontrolleri tamamlanmalıdır. Satınalma önerisi, satınalma onayı veya sözleşme imzası değildir.

## Doğrulama kapsamı

5.0.29-dev.10 kabul adayının çalışma kodu ve konfigürasyonu kararlı paketle birebir aynıdır; yalnız sürüm ve yayın dokümantasyonu değiştirilmiştir. Aynı üç gerçek XLSX/33 fiyat satırıyla yüksek güvence kabulü, gerçek Excel/PDF ve95sayfa görsel inceleme tamamlanmıştır; nihai sonuç VERIFIED. Mevcut tek belirsizlikli sentetik soru–cevap örneği de VERIFIED. Kabul adayında SQLite ve nativeDuckDB399/399PASS. Ayrıntı: [Kabul raporu](skills/teklif-degerlendirme/references/RELEASE_ACCEPTANCE_5.0.29.md), [yayın manifesti](release-manifest.json).

Bu kanıt, incelenen belge seti ve test kapsamı içindir. Her satınalmada kaynak doğrulaması, gerekli sorular ve kalite kontrolleri yeniden uygulanır. Finansal girdiler verilmeden kur, iskonto oranı veya finansman maliyeti türetilmez; şartname yoksa uygunluk değerlendirmesi yapılmadığı açıkça belirtilir.

Güncelleyici2.3.0motoru `vendor/guncelleyici` altında tutulur; `skills/guncelleyici` kabul adayındaki giriş yönergesidir. Önceki 1.1.5 yayınının 43 motor dosyasından 40'ı bayt bayt aynıdır; SKILL.md ve CHANGELOG.md yalnız kabul adayındaki kurumsal dil düzenlemelerini taşır. MANIFEST.sha256.json içinde bu iki belgenin hash kayıtları güncellenmiştir. Çalışma kodu, testler, konfigürasyon ve sürüm değişmemiştir. Kabul adayının Güncelleyici giriş/vendor 45 dosyasından 44'ü kararlı paketle birebir aynıdır; tek fark bu yayın bütünlüğü metadatasıdır. Güncelleyici teklif becerisini güncellemez. DuckDB PDF desteği isteğe bağlıdır. Güncelleyicinin kendi kabul kapsamı ve sınırlamaları, korunmuş BUILD.json ve test raporlarında belirtilir.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](USER-EVIDENCE-POLICY.md) ve [Kurumsal Dil ve Yayın Standardı](EDITORIAL-POLICY.md) bütün teklif becerilerine uygulanır.
