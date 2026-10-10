---
title: Kılıç Sözleşme Yönetimi plugin
created: 2026-10-04
modified: 2026-10-05
type: project
status: 🟡 devam ediyor
tags: [is, sozlesme, plugin]
---

# Kılıç Sözleşme Yönetimi


## Güncel geliştirme adayı: 0.1.0-dev.3

E-posta gönderimi kullanıcı kararıyla kaldırıldı. K29 **Yazışma Hazırlama**, yalnız sohbet içinde kaynaklı cevap taslağı hazırlar; gönderme ve mailbox taslağı yok. EML kaynak okuma, eski alıntı/alternatif gövde/ek ayrımı eklendi. İlgili kullanım sözleşmesi [EML okuma](references/eml-reading.md) ve [ortak beceri protokolü](references/skill-runtime.md) içindedir.

Dev.3 gerçek teknik kontrolleri: **345/345 test**, **90/90 paket kontrolü**, **214/214 YAML/başlangıç kontrolü**, **120 senaryo protokolü/296 kontrol PASS**. Tam koşu boyunca kaynaklar değişmedi. Bunlar mühendislik kontrolleridir; tam iş/üretim kabulü değildir.

Güncelleyici2.3.0,31 becerinin gerçek ad/sürüm/geliştirici bildirimi ve eksik ortamdan aynı talebe dönüş sürer. Üretim Word/kimlik/QA ve tam iş kabulü henüz tamamlanmadı; bu bir geliştirme adayıdır. Gönderime özgü üç regresyon son kullanıcı kararıyla kapsam dışındadır; kalan61 regresyon ve40 iş senaryosunun tam kabulü açık. Özgün katalog değişmez, güncel K29 kapsamı `references/skill-overrides.json` ile uygulanır.

Hedef ChatGPT Work/Codex ve Claude üzerinden bütün satınalma sözleşmeleri için Türkçe, sohbet öncelikli karar desteği. Bu klasör geliştirme kaynağıdır; kurulu veya üretime hazır ürün değildir.

Bağlayıcı baz: `D:\AI-PROJELER\📥 000-Inbox\Dump\sozlesme_yonetimi_codex_devir_v1_1`. Kaynak paketi değiştirilmedi. Son kullanıcı talimatı [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/docs/kullanici-gelistirme-talimati]] içindedir. K00–K29, 40 senaryo ve dört ortak altyapı bileşeni hedef kapsam olarak korunur.

## Önceki dev.2 kanıtı

Önceki geliştirme paketi **0.1.0-dev.2**:30 sözleşme becerisi ve **Güncelleyici2.3.0**. Her çağrının başında becerinin gerçek adı, sürümü ve “Ozan Beşinci tarafından geliştirilmiştir” satırı görünür. Eksik Python/kütüphane/DuckDB/PDF için yerel ön kontrol ve otomatik kurulumdan sonra aynı talebe dönüş uygulanır. Ortak paketler değiştirilmez; gerekirse özel Python ortamı hazırlanır.

Çalışan dilimler: P1 case/sürüm/hash ve DuckDB/kilit; P2 konumlu DOCX/PDF/XLSX okuma; P3 gerekli kanıt kapanımı/bütçe; P4 sentetik muhafız/izin; P5 gerçek Track Changes/yorum ve açık kararlı iç/dış taslak; P6 kaynaklı iş bilgisi/yükümlülük/olay ayrımı,30 ortak iş protokolü ve kesin hesap. **325/325 kod testi**, **90 paket kontrolü**, **214 YAML/başlangıç kontrolü PASS**. Boş Windows ortamında13 paket ve özel imzalı PDF eklentisinin gerçek kurulumu ile aynı request'e dönüş8/8PASS; mevcut ortak kurulumlar değişmedi. Python ana kurucusunun yeni kurulumu NOT_RUN. P5 native49 ve20 entegrasyon kontrolünün önceki kanıtı korunur.

P7 sekiz kısmi sentetik profilde 40 senaryo × üç varyantı yürüttü: 120 beceri akışı/296 kontrol PASS. **104 tam ürün kabulü NOT_RUN; yayın BLOCKED.** Üretim kimlik/yetki/QA ve uzman iş kabulü açık, genel sadakat PARTIAL ve anlamsal yeterlilik UNVERIFIED. Geliştirici **Ozan Beşinci**, ikon Kılıç Satınalma ile aynıdır. Yerel geliştirme paketi hazırlanır; GitHub ve Business yayını gerçekleşmedi.

- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/IMPLEMENTATION_STATUS|Uygulama ve faz durumu]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/TEST_STATUS|Gerçek test sonuçları]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/DECISIONS|Mimari kararlar ve sapmalar]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/DEPENDENCIES|Bağımlılıklar]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/KNOWN_LIMITATIONS|Bilinen sınırlar]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P2_READ_VERIFICATION|P2 okuma destek matrisi]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P2_CONTROL_RECORDS|P2 kontrol kayıtları ve sınırları]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P3_CONTEXT_PACKS|P3 kaynaklı bağlam ve bütçe]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P4_ACTION_GATES|P4 eylem muhafızı ve sentetik izin dilimi]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P5_DOCX_REVISIONS|P5 gerçek Word revizyonları ve destek matrisi]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P5_COMMENTS_COPIES|P5 yorum ve iç/dış taslaklar]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P6_BUSINESS_SKILLS|P6 ortak kaynak kontrollü iş becerileri]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P6_BUSINESS_LEDGER|Kaynaklı iş bilgisi ve yükümlülük kayıtları]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/RUNTIME_AND_STARTUP|Güncelleyici ve başlangıç akışı]]
- [[🏰 300-Projects/kilic-sozlesme-yonetimi-plugin/P7_RELEASE_CHECKS|P7 kabul ve yayın kapıları]]

`src/sozlesme_cekirdek/` ortak Python çekirdeğidir. `spec/` yalnız şema/katalog/test tanımlarının hash ile doğrulanan snapshot'ıdır; yeni ana şartname değildir. `reports/` gerçek çalıştırmaların kanıtıdır. `tests/.runtime/` yalnız sentetik ve git dışında kalan geçici veridir. CLI ajan ve geliştirici içindir; son kullanıcıya terminal işi bırakılmaz.
