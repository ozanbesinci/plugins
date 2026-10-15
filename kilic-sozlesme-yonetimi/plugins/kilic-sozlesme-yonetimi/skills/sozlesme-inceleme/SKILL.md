---
name: sozlesme-inceleme
description: "Sözleşme İnceleme: Taslağı ve ekleri incele. Kritik eki atlayıp tam inceleme deme."
metadata:
  catalog_id: K03
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sözleşme İnceleme

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sözleşme İnceleme skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.1.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K03 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Ana sözleşme, ek ve atıf haritasını kur; tanım/istisna/olumsuzluğu gerekli kapanıma al.
- Her bulguya hüküm/konum, ticari etkisi, alternatif ve belirsizlik ekle; kritik okuma eksikse kapsamı daralt.

Girdi: Doğrulanmış belge birimleri ve iş bağlamı. Çıktı: Kaynaklı bulgu, alternatif ve kalan risk. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K03 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kritik eki atlayıp tam inceleme deme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
