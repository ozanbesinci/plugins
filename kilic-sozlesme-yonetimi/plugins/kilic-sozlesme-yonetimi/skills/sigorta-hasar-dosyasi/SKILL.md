---
name: sigorta-hasar-dosyasi
description: "Sigorta Hasar Dosyası: Hasar oldu, ne hazırlayalım. Kesin tazminat/teminat kararı verme; otomatik gönderme."
metadata:
  catalog_id: K15
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sigorta Hasar Dosyası

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sigorta Hasar Dosyası skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K15 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Olay kronolojisi, poliçe, bildirim başlangıcı ve süre kuralını kaynağıyla ayır.
- Kanıt/bildirim taslağı hazırla; kesin teminat/tazminat kararı veya otomatik gönderim yok.

Girdi: Olay, ilgili poliçe ve bildirim koşulları. Çıktı: Kronoloji, kanıt ve bildirim taslağı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K15 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kesin tazminat/teminat kararı verme; otomatik gönderme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
