---
name: hukuka-sozlesme-hazirligi
description: "Hukuka Sözleşme Hazırlığı: Hukuka talep bilgilerini hazırla. Anlaşılmamış şartı mutabakat gibi yazma."
metadata:
  catalog_id: K02
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Hukuka Sözleşme Hazırlığı

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Hukuka Sözleşme Hazırlığı skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.2**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K02 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Taraf, kapsam, bedel/para, vergi, teslim-kabul ve sigorta/teminat eksiklerini ayrı çıkar.
- Mutabakat kaynağı ile öneriyi ayır; Hukuka talep taslağını sohbet içinde hazırla.

Girdi: Taraflar, ticari mutabakat, teknik kapsam. Çıktı: Sohbette talep paketi ve eksikler. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K02 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Anlaşılmamış şartı mutabakat gibi yazma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
