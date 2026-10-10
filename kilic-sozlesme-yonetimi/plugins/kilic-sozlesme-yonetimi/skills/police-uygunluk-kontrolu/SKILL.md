---
name: police-uygunluk-kontrolu
description: "Poliçe Uygunluk Kontrolü: Poliçe/zeyil yeterli mi. Teklifi düzenlenmiş poliçe sayma."
metadata:
  catalog_id: K13
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Poliçe Uygunluk Kontrolü

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Poliçe Uygunluk Kontrolü skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.5**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K13 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Talep edilen kapsamı gerçek poliçe ve zeyillerle karşılaştır.
- Saha/faaliyet, lehtar, limit, muafiyet, tarih ve istisnaları göster; teklif düzenlenmiş poliçe değildir.

Girdi: Talep edilen kapsam, poliçeler, zeyiller. Çıktı: Boşluk, çakışma ve düzeltme talebi. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K13 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Teklifi düzenlenmiş poliçe sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
