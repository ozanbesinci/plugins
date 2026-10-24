---
name: ise-baslama-kontrolu
description: "İşe Başlama Kontrolü: Sahaya/ödemeye başlamadan ne eksik. Ödeme veya saha başlatma eylemi yok."
metadata:
  catalog_id: K22
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# İşe Başlama Kontrolü

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**İşe Başlama Kontrolü skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.2**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K22 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Başlama koşullarını ödeme, saha, kabul, teminat ve poliçe kaynaklarıyla listele.
- Gerçek belgelerde eksik ve teyitleri göster; ödeme/saha başlatma eylemi yok.

Girdi: Tanımlı ön koşullar ve gerçek belgeler. Çıktı: Eksik belge/teyit listesi. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K22 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Ödeme veya saha başlatma eylemi yok. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
