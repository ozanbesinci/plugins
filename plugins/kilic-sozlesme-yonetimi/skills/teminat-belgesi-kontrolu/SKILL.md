---
name: teminat-belgesi-kontrolu
description: "Teminat Belgesi Kontrolü: Bu mektup uygun mu. Metni okumayı bankaca teyit sayma."
metadata:
  catalog_id: K07
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Teminat Belgesi Kontrolü

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Teminat Belgesi Kontrolü skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K07 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Talep şartı ile mektubun lehtar, tutar, para, vade ve çağrı metnini karşılaştır.
- Okuma sonucu ile banka gerçeklik/teyit durumunu ayrı tut; farkı kaynak konumuyla göster.

Girdi: Kararlaştırılan şartlar ve gerçek mektup. Çıktı: Uyum farkları ve banka teyit ihtiyacı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K07 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Metni okumayı bankaca teyit sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
