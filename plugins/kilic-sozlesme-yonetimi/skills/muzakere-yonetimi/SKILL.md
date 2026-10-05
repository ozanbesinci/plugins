---
name: muzakere-yonetimi
description: "Müzakere Yönetimi: Alternatif ver; açık maddeleri göster. Kullanıcı pozisyonunu yetkili onaya yükseltme."
metadata:
  catalog_id: K17
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Müzakere Yönetimi

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Müzakere Yönetimi skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K17 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Taraf pozisyonu, kaynak hükmü ve koşullu uzman görüşünü ayrı tut.
- Alternatif paket ve karar adaylarını açık maddelerle üret; pozisyon yetkili onay değildir.

Girdi: Taraf pozisyonları, görüşler, kurallar. Çıktı: Alternatif paket ve karar adayları. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K17 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kullanıcı pozisyonunu yetkili onaya yükseltme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
