---
name: belge-hazirlama-duzenleme
description: "Belge Hazırlama ve Düzenleme: Word/PDF/Excel oluştur; Word'e işle. Kaynak ezme; izinsiz dosya üretme; QA yoksa nihai teslim yok."
metadata:
  catalog_id: K28
  implementation: "INTERNAL_DRAFT_WITH_STRUCTURAL_NATIVE_VISUAL_QA"
---

# Belge Hazırlama ve Düzenleme

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Belge Hazırlama ve Düzenleme skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: 0.2.0**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K28 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Açık çıktı talebi, kesin hedef, kaynak hash ve değişiklik/iç-dış nüsha planını belirle.
- İç çalışma taslağı için [iki aşamalı Word üretimini](../../references/internal-drafts.md) uygula. Bütün sayfaları görmeden son dosya verme. Orijinal korunur. Kurumsal onay/imza ve P5 revizyon/dış nüsha eylemleri bu ayrı yoldan açılmaz.

Girdi: Açık istek, kaynak sürüm, içerik/değişiklik planı. Çıktı: Doğrulanmış yeni dosya ve sürüm kaydı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K28 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Kaynak ezme; izinsiz dosya üretme; QA yoksa nihai teslim yok. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
