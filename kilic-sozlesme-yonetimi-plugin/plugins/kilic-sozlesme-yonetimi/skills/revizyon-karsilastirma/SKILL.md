---
name: revizyon-karsilastirma
description: "Revizyon Karşılaştırma: Ne değişmiş; etkisi ne. Fuzzy eşleşmeyle otomatik değişiklik uygulama."
metadata:
  catalog_id: K04
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Revizyon Karşılaştırma

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Revizyon Karşılaştırma skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K04 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Kullanıcının seçtiği eski/yeni sürümü ve kaynak hashlerini teyit et.
- Kesin fark ile belirsiz eşleşmeyi ayrı göster; değişen tanımın diğer hükümler üzerindeki etkisini incele.

Girdi: Seçilmiş eski/yeni sürüm ve ilişkili hükümler. Çıktı: Farklar, belirsiz eşleşmeler ve etki özeti. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K04 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Fuzzy eşleşmeyle otomatik değişiklik uygulama. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
