---
name: ihlal-uyusmazlik-dosyasi
description: "İhlal ve Uyuşmazlık Dosyası: Yükümlülük yerine getirilmedi. Kendiliğinden ihtar/fesih/yaptırım yok."
metadata:
  catalog_id: K25
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# İhlal ve Uyuşmazlık Dosyası

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**İhlal ve Uyuşmazlık Dosyası skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K25 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Kronoloji, ihlal iddiası, kaynak hüküm, gerçekleşme kanıtı ve hukuk kaynağını ayır.
- Hukuka dosya ve seçenek üret; ihtar/fesih/yaptırım kendiliğinden yürütülmez.

Girdi: Kronoloji, kanıt, metin ve hukuk kaynakları. Çıktı: Hukuka dosya ve seçenekler. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K25 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kendiliğinden ihtar/fesih/yaptırım yok. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
