---
name: butunlesik-risk-degerlendirme
description: "Bütünleşik Risk Değerlendirme: Bütün şartları birlikte değerlendir. Güvenceleri otomatik birbirinin yerine koyma."
metadata:
  catalog_id: K16
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Bütünleşik Risk Değerlendirme

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Bütünleşik Risk Değerlendirme skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K16 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Ödeme, teminat, sigorta, ceza ve kabul korumalarını tek risk senaryosuna bağla.
- Bir güvencenin yerine diğerini otomatik koyma; paket taviz ve toplam kalan riski ayrı göster.

Girdi: Risk, ödeme, teminat, sigorta, ceza ve kabul. Çıktı: Koruma-kalan risk tablosu. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K16 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Güvenceleri otomatik birbirinin yerine koyma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
