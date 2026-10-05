---
name: sozlesme-degisiklik-yonetimi
description: "Sözleşme Değişiklik Yönetimi: Süre/fiyat/kapsam değişti. Teminat/sigorta/ceza etkisini atlama."
metadata:
  catalog_id: K24
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sözleşme Değişiklik Yönetimi

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sözleşme Değişiklik Yönetimi skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K24 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Süre/fiyat/kapsam talebini mevcut kaynak sürüm ve ticari pozisyondan ayır.
- Teminat/sigorta/ceza/kabul zincir etkisini incele; ek protokol içeriği taslaktır.

Girdi: Değişiklik talebi ve bağlı hükümler. Çıktı: Zincirleme etki ve ek protokol içeriği. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K24 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Teminat/sigorta/ceza etkisini atlama. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
