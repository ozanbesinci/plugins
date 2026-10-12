# Kılıç Satınalma eklentisi

**Plugin 1.3.2**, **Teklif Değerlendirme 5.1.2** ve bağımsız **Güncelleyici 2.3.0** içerir. Kılıç Satınalma Departmanı tarafından geliştirilmiştir.

Her analiz profilinde tek çok sekmeli formüllü XLSX ve çok sayfalı PDF üretilir. Şartname uygunsuzluğu, eksik veri, tek firma veya elenmiş teklifler gerekçeli raporu engellemez. Kaynak ve kullanıcı varsayımları ayrıdır; bilinmeyen maliyet sıfır olmaz. Atomik çift teslim, şartname matrisi, yıl bazlı giderler, çok adımlı ödeme ve ayrı tarihli/para birimli nakit senaryoları desteklenir. Senaryo puanı veya nakit NBD şirket onayı ve rekabetçi firma sıralaması değildir.

Güncel kapsam ve yayın kabulü: [5.1.2 kabul sözleşmesi](plugins/kilic-satinalma/skills/teklif-degerlendirme/references/RELEASE_ACCEPTANCE_5.1.2.md). Gerçek sonuç JSON/logları sürüme bağlı release kanıtlarıdır; önceki sürüm test sayıları bu sürümün sonucu değildir.

Teklif akışı bir ana beceri ve beş alt beceriden oluşur. Kaynak kanıtı, kapsam, maliyet, ticari koşullar ve riskleri değerlendirir; gerekli kullanıcı cevaplarını işler; gerekçeli satınalma önerisi ile Excel/PDF üretir. Güncelleyici2.3.0motoru `vendor/guncelleyici` altında tutulur; beceri girişi bu motoru çağırır. Motor çalışma kodu, testler, konfigürasyon ve sürüm önceki yayından korunmuştur; iki dokümantasyon dosyası kabul adayındaki kurumsal dil düzenlemelerini taşır.

Ayrıntı ve kabul kapsamı: [Plugin bilgileri](plugins/kilic-satinalma/README.md).

Marketplace plugin kaynağı `./plugins/kilic-satinalma` olarak korunur. Release ZIP'i bu plugin klasörünü içerir; birlikte verilen SHA256 dosyası indirme bütünlüğünü doğrulamak için kullanılır.
