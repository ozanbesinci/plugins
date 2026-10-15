# Kılıç Sözleşme Yönetimi

Kaynaklı Türkçe sözleşme desteği için 30 iş becerisi ve Güncelleyici 2.3.0. **Kararlı sürüm 0.1.0** (2026-10-15): satınalma ve ithalat personelinin sözleşme ön incelemesi için yayımlandı. Mail gönderimi yok; Word çıktısı 0.1.0'da kapalı, cevaplar sohbette verilir.

Kurulum notları:

- Claude Code yerel katalogdan kurulan eklentiyi kapalı başlatır; kurulumdan sonra `claude plugin enable kilic-sozlesme-yonetimi@<katalog>` gerekir.
- Codex'te aynı adlı eski bir deneme adayı kuruluysa, eski sürümün becerisi seçilmesin diye önce o kaldırılır.
- Codex korumalı alanda vaka klasörüne erişim için bir kez kullanıcı onayı isteyebilir.

Güncel sürüm hazırlığı için tek giriş: [kararlı sürüme geçiş yapısı](release/README.md).
`tools/release.py status` ürünün mevcut baytlarına bağlı makbuzları doğrular;
`tools/release.py test` aynı test manifestini çakışmasız gruplarla yürütür.
Geliştirme/kabul aracı ürün paketinin dışında, özel kanıtlar deponun dışında kalır.
Tarihsel faz raporları güncel durumun yerine kullanılmaz.

Plugin ve30 beceri0.1.0, çekirdek0.2.0, ortak sonuç şemasıp6-1.2; Güncelleyici2.3.0 değişmedi. Bileşen/build kimlikleri ayrı tutulur. Beceri başlangıcında gerçek ad, sürüm ve Kılıç Satınalma Departmanı geliştirici bildirimi görünür. Depo sahibi Ozan Beşinci'dir.

## Kaynak ve kurulum kaydı

Güncel depo [ozanbesinci/plugins](https://github.com/ozanbesinci/plugins), proje alt dizini `kilic-sozlesme-yonetimi/`, ürün paketi `plugins/kilic-sozlesme-yonetimi/`. Proje pazar yeri tanımı `.claude-plugin/marketplace.json` dosyasında bulunur. Eski bağımsız depo adı ve hareketli `main` ref'i bu adayın kurulum kanıtı değildir.

Kurulum/kabul kaydı, onaylanmış40 karakterli commit SHA'sını veya hash'i doğrulanmış değişmez paket kimliğini, gerçek host/sürümü ve test makbuzunu taşımalıdır. Bu çalışma ağacında değişiklikler commit/release/host kurulumuna bağlanmadı; kurulu kaynak commit'i bilinmiyorsa kimlikte null/UNVERIFIED kalır. Bu README kurulum veya yayın başarısı iddia etmez.

Yerel motor Windows ve izinli native Python yürütümü gerektirir. Shell bulunmayan cloud host'ta bağımlılık/kurulum veya Windows motoru çalıştı sayılmaz. Eksik kaynak ve yapılandırmada kapalı ret verilir. Gerçek ChatGPT/Claude host kabulü ayrı ve henüz NOT_RUN'dır.

## Ürün sınırları

- K29 yalnız sohbet içinde yazışma taslağıdır. E-posta gönderimi, mailbox taslağı veya başka connector ile gönderim yoktur.
- Normal üretim Word yazıcı/kimlik/QA kapıları CONFIG_REQUIRED ile kapalıdır. Sentetik Word testleri üretim yetkisi değildir.
- Kaynak baytları korunur; case/sürüm/CAS, erişim, locator ve son hash kontrolleri yeniden uygulanır. Tarihsel kaynak güncel karar kanıtına yükseltilmez.
- Teknik SUCCEEDED/COMPLETED, iş tamamlanması veya şirket onayı değildir. İş durumu ve NOT_GRANTED kabulü ayrı gösterilir.

## Güncel test ve kabul

Ürün testleri gerçek Windows/DuckDB/OS kilidiyle, kurulum yapmadan izole sentetik staging'de yürütülür. Her koşu kaynak/manifest SHA, ortam, test kimliği ve gerçek terminal sonucu taşır. Kaynak değişince eski PASS yeni kabul değildir. Çalıştırılmayan testler NOT_RUN; yarım/timeout koşusu tam PASS değildir.

Önceki345/345 kod testi,90/90 paket kontrolü,214/214 beceri kontrolü ve120/296 senaryo sayıları **tarihsel faz kayıtlarıdır**. Bu adayın güncel test başarısı veya gerçek ekip kabulü olarak kullanılmaz. Eski219 dosyalı ZIP/hash de bu değişmiş kaynak için paket kabulü değildir.

Test koşucusu ve kapsam: [ürün test stratejisi](plugins/kilic-sozlesme-yonetimi/references/product-test-strategy.md). Bileşenler: [kimlik sözleşmesi](plugins/kilic-sozlesme-yonetimi/references/component-identity.md). Sınırlar: [KNOWN_LIMITATIONS](plugins/kilic-sozlesme-yonetimi/KNOWN_LIMITATIONS.md).

Kararlı kabul; aynı aday üzerinde güncel teknik kanıtların yanı sıra gerçek iş denemesi ve ilgili bağımsız uzman kabulü tamamlandığında verilir. 0.1.0 için bu kayıtlar yayın kararından önce aynı ürün baytlarına bağlandı. Gerçek şirket belgeleri, kişisel kayıtlar ve erişim anahtarları açık kaynak test/release paketine konulmaz.
