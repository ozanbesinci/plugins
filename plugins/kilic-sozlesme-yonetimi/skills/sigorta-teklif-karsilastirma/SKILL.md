---
name: sigorta-teklif-karsilastirma
description: "Sigorta Teklif Karşılaştırma: Sigorta tekliflerini karşılaştır. Salt ucuz primle seçme; şirket poliçesi kapsam tercihini teyitli tut."
metadata:
  catalog_id: K12
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sigorta Teklif Karşılaştırma

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sigorta Teklif Karşılaştırma skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K12 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Prim, para, dönem, limit, kapsam ve muafiyetleri karşılaştırılabilir zemine getir.
- En düşük primi tek seçim ölçütü yapma; şirket portföyü S-20 kapsam tercihi açıksa bunu koru.

Girdi: Karşılaştırılabilir prim, limit, kapsam ve muafiyet. Çıktı: Fark tablosu ve uzman teyit soruları. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K12 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Salt ucuz primle seçme; şirket poliçesi kapsam tercihini teyitli tut. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
