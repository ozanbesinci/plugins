# Kılıç Sözleşme Yönetimi

**Kararlı sürüm0.2.0:** ChatGPT Work için30 sözleşme becerisi, ayrı Windows ortamı ve iç çalışma taslağı Word üretimi. Plugin/beceriler0.2.0, çekirdek0.4.0, P6p6-1.4. [Kararlı paket ve SHA-256](https://github.com/ozanbesinci/plugins/releases/tag/kilic-sozlesme-yonetimi-v0.2.0).

K28, kullanıcının açık talebiyle yeni iç çalışma taslağı DOCX üretir. Kaynak alıntısı, kullanıcı beyanı ve taslak öneri ayrılır; eksik kaynaklar görünür kalır. Yapısal denetim, yerel Microsoft Word ile PDF/PNG üretimi ve bütün sayfaların ayrı görsel incelemesi tamamlanmadan son dosya teslim edilmez. [İki aşamalı Word akışı](plugins/kilic-sozlesme-yonetimi/references/internal-drafts.md).

Belge şirket imzası, kurumsal/hukuki onay veya imzaya hazır kararı değildir. P4/P5 genel üretim revizyon/dış nüsha eylemleri bu ayrı yoldan açılmaz. K29 yalnız sohbet içinde yazışma taslağı hazırlar; e-posta gönderimi ve mailbox taslağı yoktur.

Kaynak dosyaların üzerine yazılmaz. Kaynak erişimi/hash'i, vaka revizyonu, bağlam kapanımı ve bütün çıktı hashleri hazırlanırken ve teslimde denetlenir. Kesilen yayınlar kalıcı inceleme kaydı üzerinden aynı baytlarla uzlaştırılır.001–008 migration toplam26 tabloyu kapsar; eski çekirdek yeni veri şemasını kapalı retle karşılar.

Windows ortamı kullanıcı alanında,13 sabit paketle çalışır; mevcut Python/PATH değiştirilmez. Aynı hash/boyutla sabitlenmiş0.1.1 kurucusu korunur. Eksik ortamı ajan otomatik hazırlar, yalnız gerçek native READY sonrası devam eder. Word çıktısı için yerel Microsoft Word gerekir. Kullanıcıdan terminal/JSON/Python komutu beklenmez. Webden devam desteklenen ve çevrimiçi Windows bağlantısına bağlıdır. [Kurulum](kurulum/README.md) · [Ajan çalışma protokolü](plugins/kilic-sozlesme-yonetimi/references/runtime-integration.md).

Ürün testleri gerçek Windows/DuckDB/kilit üzerinde izole sentetik ortamda yürür; Office testlerinin kontrollü taklitleri gerçek Word denemesinin yerine geçmez. Kararlı paket son baytlarında660 etkin ürün testi ve24 araç testiyle doğrulanır.661 keşiften tek tarihsel P0 fixture testi açıkça kapsam dışıdır. Gerçek Word/native hazırlık, ayrı inceleme ve teslim kanıtı ayrıca tutulur. [Test stratejisi](plugins/kilic-sozlesme-yonetimi/references/product-test-strategy.md) · [Bilinen sınırlar](plugins/kilic-sozlesme-yonetimi/KNOWN_LIMITATIONS.md).

Kaynak depo [ozanbesinci/plugins](https://github.com/ozanbesinci/plugins); ürün `plugins/kilic-sozlesme-yonetimi/`, yerel geliştirme ayrı korunur. Gerçek şirket belgeleri, kişisel kayıtlar ve erişim anahtarları açık kaynak/test paketine konulmaz. Yayın kaydı kurum geneli saha kabulü değildir; imzasız kurucu, ikinci cihaz ve kaynak türlerine ait açık gerçek ortam sınırları korunur.
