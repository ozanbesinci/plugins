---
name: sozlesme-yonlendirici
description: "Sözleşme Yönlendirici: Sözleşmeyle ilgili her doğal dil talebi. Tüm skill'leri çalıştırma; işlem izni üretme."
metadata:
  catalog_id: K00
  implementation: "DRAFT_PROTOCOL_WITH_COMMON_SOURCE_GATES"
---

# Sözleşme Yönlendirici

<!-- startup-message:start -->
Her çağrının başında, araçları çalıştırmadan önce, kullanıcı sohbetinde şu satırı aynen göster:

**Sözleşme Yönlendirici skilli Ozan Beşinci tarafından geliştirilmiştir. Sürüm: 0.1.0-dev.3**

Bu satır gerçek beceri adı ve sürümünü gösterir. Kurulum sırasında başka beceri çalışırsa onun başlangıç satırını da göster.
<!-- startup-message:end -->

Önce [ortak çalışma protokolünü](../../references/skill-runtime.md) oku. Bu beceri K00 sözleşmesini uygular; yalnız gerekli kaynakları yükle.

- Amaç, seçilmiş dosya ve host yeteneğini belirle; bütün skill ailesini çağırma.
- Senaryo kimliğinden hedef skill seç; belirsiz doğal dilde mevcut bağlamı kontrol et, yalnız gerekli soruyu sor.

Girdi: Amaç, dosya, yüzey ve yetenek kaydı. Çıktı: Hedef dosya, gerekli skill ve sınırlı iş planı. Varsayılan sohbet yanıtı; aynı izin kapsamını gereksiz tekrar sorma.

Ortak çekirdekte `skill-evaluate` isteğini skill_id=K00 ile kullan; katalogdaki senaryo varsa scenario_id alanına koy. Kaynak kapanımı eksik/eskiyse TAMAMLANDI üretme. Türetilen yorumları aday tut, gerçek şirket kararı yaratma.

Sınır: Tüm skill'leri çalıştırma; işlem izni üretme. Host/connector/üretim yazıcı yoksa teknik engeli belirt; mevcut kaynaklı sohbet desteğini sürdür.
