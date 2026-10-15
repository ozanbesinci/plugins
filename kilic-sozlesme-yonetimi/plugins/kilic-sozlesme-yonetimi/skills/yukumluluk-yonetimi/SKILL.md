---
name: yukumluluk-yonetimi
description: "Yükümlülük Yönetimi: Görevleri ve tarihleri çıkar. Atanmayan sorumluyu uydurma; otomatik izleme varsayma."
metadata:
  catalog_id: K23
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Yükümlülük Yönetimi

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Yükümlülük Yönetimi skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K23 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Hüküm, olay başlangıcı, açık süre kuralı ve gerçek sorumlu atamasını bağla.
- Atanmayan sorumluyu veya süreyi uydurma; izleme adaptörü yoksa otomatik takip vaat etme.

Girdi: Hükümler, olaylar ve atamalar. Çıktı: Kaynaklı yükümlülük ve vade kaydı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K23 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Atanmayan sorumluyu uydurma; otomatik izleme varsayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
