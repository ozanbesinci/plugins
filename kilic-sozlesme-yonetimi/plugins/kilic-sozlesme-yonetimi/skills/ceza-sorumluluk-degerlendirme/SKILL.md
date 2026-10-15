---
name: ceza-sorumluluk-degerlendirme
description: "Ceza ve Sorumluluk Değerlendirme: Ceza ve sorumluluk sınırı ne anlama gelir. Hesap doğruluğunu hukuken uygulanabilirlik sayma."
metadata:
  catalog_id: K10
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Ceza ve Sorumluluk Değerlendirme

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Ceza ve Sorumluluk Değerlendirme skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K10 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Ceza matrahı, kesir oranı, dönem ve tavanı Decimal ile hesapla.
- Sorumluluk istisnaları ile ekonomik senaryoyu birlikte göster; uygulanabilirlik Hukuk görüşü ister.

Girdi: İhlal, matrah, oran, üst sınır, istisnalar. Çıktı: Ekonomik senaryolar, risk ve Hukuk soruları. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K10 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Hesap doğruluğunu hukuken uygulanabilirlik sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
