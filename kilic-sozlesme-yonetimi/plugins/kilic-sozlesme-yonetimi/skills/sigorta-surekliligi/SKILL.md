---
name: sigorta-surekliligi
description: "Sigorta Sürekliliği: İş uzadı, sigorta yeterli mi. Kanıt olmadan poliçe uzatıldı deme."
metadata:
  catalog_id: K14
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sigorta Sürekliliği

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sigorta Sürekliliği skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.5**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K14 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- İş süresi/bedeli/faaliyeti/saha değişikliğini poliçe dönem ve kapsamına bağla.
- Gerekli zeyil/uzatma teyidini göster; gerçekleşmiş uzatma iddiası yalnız belgeyle.

Girdi: İş, bedel, faaliyet, saha değişikliği. Çıktı: Zeyil/uzatma ve teyit gereksinimleri. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K14 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kanıt olmadan poliçe uzatıldı deme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
