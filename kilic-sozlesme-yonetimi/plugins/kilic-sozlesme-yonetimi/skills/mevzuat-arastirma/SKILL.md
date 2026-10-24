---
name: mevzuat-arastirma
description: "Mevzuat Araştırma: Türkiye hukuku açısından araştır. Kaynak yokken güncel mevzuat doğrulandı deme."
metadata:
  catalog_id: K19
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Mevzuat Araştırma

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Mevzuat Araştırma skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.2**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K19 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Somut olay tarihi, taraf niteliği ve hukuki soruyu belirle.
- Resmi kaynak, yürürlük/geçiş ve uygulanabilirliği teyit et; adaptör/kaynak yoksa güncel hüküm iddiası yok.

Girdi: Somut soru, taraf niteliği ve olay tarihi. Çıktı: Kaynaklı not ve doğrulama sınırı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K19 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kaynak yokken güncel mevzuat doğrulandı deme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
