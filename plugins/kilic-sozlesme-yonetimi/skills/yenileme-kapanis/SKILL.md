---
name: yenileme-kapanis
description: "Yenileme ve Kapanış: Yenileyelim mi, kapanışta ne var. Devam eden yükümlülüğü kapatma."
metadata:
  catalog_id: K26
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Yenileme ve Kapanış

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Yenileme ve Kapanış skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.5**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K26 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Yalnız izinli ve güncel case kapsamını, erişilemeyen dosyaları ve eksikleri belirle.
- Portföy ölçümünün pay/payda ve kapsama sınırını göster; keyfi SQL ya da bütün şirket erişimi yok.

Girdi: Süre, performans, garanti ve açık talepler. Çıktı: Yenileme/kapanış kontrolü. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K26 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Devam eden yükümlülüğü kapatma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
