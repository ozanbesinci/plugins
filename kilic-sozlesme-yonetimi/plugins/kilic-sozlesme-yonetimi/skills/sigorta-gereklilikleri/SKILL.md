---
name: sigorta-gereklilikleri
description: "Sigorta Gereklilikleri: Hangi sigorta, limit ve muafiyet. All Risk adını istisnasız teminat sayma."
metadata:
  catalog_id: K11
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sigorta Gereklilikleri

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sigorta Gereklilikleri skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.2**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K11 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Faaliyet/saha/kişiler/varlık ve zarar senaryosu üzerinden sigorta gereksinimini kur.
- Limit, muafiyet ve istisna boşluklarını ayır; All Risk adını istisnasız koruma kabul etme.

Girdi: Faaliyet, saha, kişiler, varlık ve zarar senaryosu. Çıktı: Risk-sigorta eşleştirmesi ve şart içeriği. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K11 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: All Risk adını istisnasız teminat sayma. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
