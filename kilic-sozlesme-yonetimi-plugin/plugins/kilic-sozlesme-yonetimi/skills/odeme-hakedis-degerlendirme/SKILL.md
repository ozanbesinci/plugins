---
name: odeme-hakedis-degerlendirme
description: "Ödeme ve Hakediş Değerlendirme: Ödeme planı/hakediş uygun mu. Eksik matrah/tarihi tahmin etme; ödeme yapma."
metadata:
  catalog_id: K05
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Ödeme ve Hakediş Değerlendirme

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Ödeme ve Hakediş Değerlendirme skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.5**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K05 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Matrah, para birimi, vergi, oran, vade başlangıcı ve kabul olayını açık seç.
- Decimal hesabı ve ödeme karşılığı teminat/kabul bağını göster; eksik matrahı tahmin etme.

Girdi: Matrah, vade, vergi, para birimi, kabul. Çıktı: Hesap, ödeme karşılığı ve risk. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K05 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Eksik matrah/tarihi tahmin etme; ödeme yapma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
