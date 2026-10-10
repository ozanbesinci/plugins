---
name: teminat-takibi
description: "Teminat Takibi: Uzatma, azaltma, iade ne durumda. Teminat serbest bırakma eylemi yok."
metadata:
  catalog_id: K08
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Teminat Takibi

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Teminat Takibi skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K08 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Vade, uzatma, mahsup ve gerçekleşen kabul kanıtını ilişkilendir.
- Azaltma/iade için eksik kanıt ve risk süresini göster; serbest bırakma işlemi yapma.

Girdi: Teminat, vade, mahsup, gerçekleşme. Çıktı: Gerekçeli değerlendirme ve açık kanıt. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K08 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Teminat serbest bırakma eylemi yok. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
