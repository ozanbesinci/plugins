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

**Portföy Değerlendirme skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K27 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- İzinli örneklemde ortak riskleri ve veri kalitesini kaynaklarıyla çıkar.
- Nicel hesap ile yorum/iyileştirme önerisini ayır; erişilemeyen dosyayı kapsama sayma.

Girdi: Yetkili erişimli dosya kümesi. Çıktı: Örneklem sınırı belli bulgu ve ölçüm. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K27 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Birden fazla dosyayı karşılaştırmak için `portfolio-overview --request <izinli-kökte-JSON>` kullan (`schemas/portfolio_request.schema.json`). Yalnız kullanıcının açıkça adlandırdığı ve erişimi olan case'leri, her biri için güncel revizyon ve seçili sürümlerle listele; bütün şirketi veya listelenmemiş dosyaları tarama. Sonuçtaki `coverage` ve her metriğin pay/paydasını aynen göster. EXCLUDED case'i nedeniyle birlikte söyle, ölçüme katma ve içeriğini tahmin etme. Case'lerin kaynaklarını birbirine karıştırma; ayrıntı gerekiyorsa ilgili case için ayrı `skill-evaluate` çağır. Ortak sorun yorumu ve iyileştirme önerisi senin taslak değerlendirmendir; ölçüm `interpretation=NOT_RUN` ve onay vermez.

Sınır: Erişilemeyen dosyayı kapsama dahil sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
