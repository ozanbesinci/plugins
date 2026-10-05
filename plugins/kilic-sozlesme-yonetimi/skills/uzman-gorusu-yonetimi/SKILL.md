---
name: uzman-gorusu-yonetimi
description: "Uzman Görüşü Yönetimi: Hukuka/Finansa/Tekniğe soralım. Koşullu görüşü genel onay yapma."
metadata:
  catalog_id: K18
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Uzman Görüşü Yönetimi

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Uzman Görüşü Yönetimi skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K18 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Tartışmalı metin, ticari etki ve somut Hukuk/Finans/Teknik sorusunu sürüme bağla.
- Cevabın koşul/kapsam/tarih ve görüş sahibini koru; koşullu görüşü genel kabul yapma.

Girdi: Tartışmalı metin, etki, soru ve varsa cevap. Çıktı: Görüş talebi; sürüme bağlı görüş kaydı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K18 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Koşullu görüşü genel onay yapma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
