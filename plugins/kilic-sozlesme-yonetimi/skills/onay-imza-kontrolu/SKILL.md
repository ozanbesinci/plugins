---
name: onay-imza-kontrolu
description: "Onay ve İmza Kontrolü: Son nüsha imzaya hazır mı. İmza atma; yetki yoksa hazır kararı verme."
metadata:
  catalog_id: K21
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Onay ve İmza Kontrolü

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Onay ve İmza Kontrolü skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K21 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Son metin, önceki kararla farkı, bütün ekler ve açık onayları kaynakla kontrol et.
- Yetki/imza matrisi ve sürüme bağlı gerçek karar yoksa imzaya hazır sonucu verme.

Girdi: Son metin, kararlar, ekler ve yetki kaynağı. Çıktı: Hazırlık kontrolü, açık onaylar. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K21 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: İmza atma; yetki yoksa hazır kararı verme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
