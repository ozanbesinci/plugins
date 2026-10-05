---
name: teslim-kabul-garanti
description: "Teslim, Kabul ve Garanti: Kabul/performans/garanti nasıl. Teslimi otomatik kesin kabul sayma."
metadata:
  catalog_id: K09
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Teslim, Kabul ve Garanti

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Teslim, Kabul ve Garanti skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K09 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Teslim, geçici/kesin kabul ve performans testini ayrı olaylar olarak ele al.
- Garanti başlangıcı, koşul/istisna ve sorumlu atamasını kaynakla bağla.

Girdi: Teknik kriterler, aşamalar ve sorumlular. Çıktı: Kriterler, başlangıç olayları ve süreler. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K09 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Teslimi otomatik kesin kabul sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
