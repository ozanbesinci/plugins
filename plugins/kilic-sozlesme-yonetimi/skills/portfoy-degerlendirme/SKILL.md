---
name: portfoy-degerlendirme
description: "Portföy Değerlendirme: Ortak sorunları ve iyileştirmeleri göster. Erişilemeyen dosyayı kapsama dahil sayma."
metadata:
  catalog_id: K27
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Portföy Değerlendirme

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Portföy Değerlendirme skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K27 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- İzinli örneklemde ortak riskleri ve veri kalitesini kaynaklarıyla çıkar.
- Nicel hesap ile yorum/iyileştirme önerisini ayır; erişilemeyen dosyayı kapsama sayma.

Girdi: Yetkili erişimli dosya kümesi. Çıktı: Örneklem sınırı belli bulgu ve ölçüm. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K27 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Erişilemeyen dosyayı kapsama dahil sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
