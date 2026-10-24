---
name: kurumsal-emsal-arastirma
description: "Kurumsal Emsal Araştırma: Benzer görüş/şirket standardı var mı. Tek emsali kurala çevirme."
metadata:
  catalog_id: K20
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Kurumsal Emsal Araştırma

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Kurumsal Emsal Araştırma skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.2**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K20 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Yalnız izinli kurumsal kaynakları şirket/tarih/kapsam bağında getir.
- Benzerlik ve farkı, geçerlilik ve onay kaynağını göster; tek emsal şirket standardı değildir.

Girdi: İzinli şirket kaynakları ve somut soru. Çıktı: Benzerlik/farklar, geçerlilik ve kapsam. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K20 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Tek emsali kurala çevirme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
