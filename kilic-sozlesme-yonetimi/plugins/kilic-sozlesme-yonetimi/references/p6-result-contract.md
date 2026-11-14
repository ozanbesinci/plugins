# P6 sonuç sözleşmesi p6-1.4

Çalışma geliştiricisi `Kılıç Satınalma Departmanı`dır. Plugin author/developerName kimliği ayrı metadata semantiğidir. Sonuçta developer, skill_name, skill_version ve startup_message zorunludur. Yanlış geliştirici, bilinmeyen alan ve eski sonuç sürümü çalışma doğrulamasında reddedilir. İç taslak için K28/DOCX kapsamlı document_request ve document_review alanları birbirini dışlar; sonuçta ayrı internal_draft durum/manifesti bulunabilir.

Eski p6-1.1 sonuçların tarihsel okunması kendi sürüm şemasına bağlıdır; yeniden yürütüm veya güncel kabul yetkisi değildir. Bu değişiklik metadata üreticisini kişisel geliştirici değerine geri zorlamaz ve validator'ı devre dışı bırakmaz.

P6 KISMI, BILGI_GEREKLI, UZMAN_GORUSU_GEREKLI veya TEKNIK_ENGEL döndürebilir. Teknik CLI SUCCEEDED bu işin veya dosyanın tamamlandığı anlamına gelmez. Yalnız açık INTERNAL_DRAFT üretimi iki aşamalı yerel Word ve görsel QA ile açılır; kapsam belirtilmeyen DOCX ile kurumsal imza/onay ve P4/P5 genel eylemleri kapalıdır; K29 yalnız sohbet taslağıdır. SEND_EMAIL, EMAIL_SEND, MAILBOX_DRAFT ve başka connector'a gönderim devri kapsam dışıdır.

Ürün regresyonu `scripts/run_product_tests.py` ile gerçek Windows/Store/DuckDB/kilit üzerinde yalnız sentetik staging kopyasında çalışır. Metin/metadata testinin geçmesi gerçek Word/host/uzman/ekip kabulü değildir. Benzersiz koşu makbuzu kaynak, test manifesti, fixture, komut, ortam ve sonuç hash'lerini içerir; eski PASS dosyası yeni koşu sayılmaz.

K28 iç taslak sonucunda action_execution=INTERNAL_DRAFT_ONLY yalnız bu dosya yolunun çalıştığını bildirir. CHAT değerlendirmelerinde DISABLED sürer; kurumsal onay/iş eylemi yetkisi yaratılmaz.
