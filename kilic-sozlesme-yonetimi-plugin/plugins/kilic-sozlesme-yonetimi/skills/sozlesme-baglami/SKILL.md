---
name: sozlesme-baglami
description: "Sözleşme Bağlamı: İşi anla; kaldığımız yerden devam et. Beyanı onay/hüküm sayma."
metadata:
  catalog_id: K01
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sözleşme Bağlamı

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sözleşme Bağlamı skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.5**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K01 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Planlanan ticari iş, sözleşmedeki hüküm ve gerçekleşen olayı ayrı göster.
- Kaynak haritası, kullanıcı beyanı ve açık konularla kaldığımız noktayı çıkar.

Girdi: Belgeler, beyanlar, açık konular. Çıktı: Süreç, bilinenler ve hedefli sorular. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K01 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Beyanı onay/hüküm sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
