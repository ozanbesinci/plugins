# Kılıç Sözleşme Yönetimi

**0.1.2 otomatik Windows kurulumu:** ChatGPT Work için 30 sözleşme becerisi ve ayrı Windows kurulumu. Plugin/beceriler 0.1.2, çekirdek 0.2.1, P6 sonuç p6-1.2. Güncelleyici becerisi ve gömülü güncelleyici motoru kaldırıldı.

Business üyeleri Windows'ta tek EXE ile kullanıcı alanına kurulum yapar, ardından Work içinde doğal dilde çalışır. Kurucu Python'u ve 13 sabit paketi içinde taşır; mevcut Python veya PATH'i değiştirmez. Work bütün iş komutlarını aynı kayıtlı ortamda yürütür. Webden devam, desteklenen ve çevrimiçi Windows bağlantısına bağlıdır. Kullanıcıdan terminal veya Python komutu beklenmez.

Kurucu kaynakları [kurulum](kurulum/README.md), ajan protokolü [runtime-integration](plugins/kilic-sozlesme-yonetimi/references/runtime-integration.md). [Kararlı 0.1.2 paketi](https://github.com/ozanbesinci/plugins/releases/tag/kilic-sozlesme-yonetimi-v0.1.2) 22.10.2026'da GitHub ve Kılıç Holding Business'ta yayımlandı. Ana daldaki ürünün 263 dosyası bu ZIP ile aynı baytları taşır. Kurucu imzasızdır; SmartScreen ve ikinci gerçek Windows cihazında kurulum kabulü açık kalır. Önceki dev.2 aynı bilgisayarda Work masaüstü/Bulut ve web bağlantı kontrolünü geçti; bu sonuç yeni baytların host testi olarak sunulmaz.

Kaynak depo [ozanbesinci/plugins](https://github.com/ozanbesinci/plugins), proje kilic-sozlesme-yonetimi/, ürün plugins/kilic-sozlesme-yonetimi/. Kurulu eski paket veya başka eklentinin kabul sonucu bu yeni adayın kabulü sayılmaz. Eski yerel geliştirme kaynakları ayrı korunur.

K29 yalnız sohbet içinde yazışma taslağıdır. Mail gönderme/mailbox taslağı yoktur. Normal üretim Word kapısı CONFIG_REQUIRED olarak kalır. Teknik başarı, iş/uzman/şirket onayı değildir. Kaynak hash'i, vaka revizyonu, erişim ve bağlam kapanımı kontrolleri geçerlidir.

Ürün testleri gerçek Windows/DuckDB/OS kilidiyle izole sentetik ortamda çalışır. Native kurucu testleri ayrıca ayrı USERPROFILE klasöründe yürütülür. Test makbuzu kaynak/manifest SHA, ortam ve gerçek sonucu taşır; başka baytların eski PASS'i güncel kabul sayılmaz. [Test stratejisi](plugins/kilic-sozlesme-yonetimi/references/product-test-strategy.md), [bileşen kimliği](plugins/kilic-sozlesme-yonetimi/references/component-identity.md), [bilinen sınırlar](plugins/kilic-sozlesme-yonetimi/KNOWN_LIMITATIONS.md).

Önceki 0.1.0 sürümünün 2026-10-15 yayın kararı tarihseldir. 0.1.1, ayrı Windows kurulumuna geçen sürümdür. Yayın kaydı, üyelerin gerçek iş denemesi ve ikinci cihaz kabulünden ayrıdır. Gerçek şirket belgeleri, kişisel kayıtlar ve erişim anahtarları açık test/kurulum paketine konulmaz.

0.1.2 ilk kullanımda eksik Windows ortamını otomatik indirip kurar; kurucu sabit hash/boyutla doğrulanır ve aynı talebe yalnız gerçek native READY sonrası dönülür. Kullanıcıya indirme bağlantısı veya kurulum görevi verilmez; kişisel izin istenmez. Windows ortamı ve uyumlu 0.1.1 kurucusu değiştirilmedi.
