---
name: teminat-yapilandirma
description: "Teminat Yapılandırma: Avans/kesin teminat nasıl olmalı. Kaynak olmadan sabit yüzdeyi şirket kuralı ilan etme."
metadata:
  catalog_id: K06
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Teminat Yapılandırma

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Teminat Yapılandırma skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K06 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Avans, mahsup ve risk bitiş olayını kaynaklarıyla eşleştir.
- Teminat tutarı/vadesi alternatiflerini gerekçelendir; sağlanmamış şirket oranını standarda dönüştürme.

Girdi: Avans, mahsup, kabul, risk süresi. Çıktı: Teminat türü, tutar/vade seçenekleri. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K06 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kaynak olmadan sabit yüzdeyi şirket kuralı ilan etme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
