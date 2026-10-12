---
name: teklif-belge-kaynak
description: Teklif değerlendirmede dosya okuma, firma/teklif/revizyon ilişkisi, kaynak otoritesi ve locator bağlı olgu çıkarımını yürütür. Ana teklif akışının belge aşamasında veya belge/revizyon incelemesi istendiğinde kullan; maliyet hesabı ve nihai karar üretmez.
---

# Belge ve Kaynak — 5.1.1
## Kullanıcı kanıtı önceliği

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir.

Belgedeki özgün değer ayrı korunur; açık kullanıcı firma, revizyon veya alan düzeltmesi geçerli değerlendirme esasına bağlanır. Kullanıcı mesajını tedarikçi belgesi olarak etiketleme.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](../../USER-EVIDENCE-POLICY.md) bütün aşamalarda uygulanır.

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill teklif-belge-kaynak` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

Ana giriş [Teklif Değerlendirme](../teklif-degerlendirme/SKILL.md). Doğrudan çağrılmışsan önce onu oku ve aynı run'a bağlan; ikinci prepare/DB açma. Mevcut run/task/context yoksa ana başlangıca dön. [Ortak sözleşme](../teklif-degerlendirme/references/module-contract.md) kimlik, strict şema, kanıt, soru, makbuz ve yetki sınırlarını belirler. Model alt görevinde yeni alt ajan açma.

## Sorumluluk

Kaynaklar çeliştiğinde [Kaynak ve soru](../teklif-degerlendirme/references/analysis-quality-workflow.md#kaynak-ve-soru), kayıtları birleştirirken [Analiz birimi ve üyelik](../teklif-degerlendirme/references/analysis-quality-workflow.md#analiz-birimi-ve-üyelik) yöntemini uygula.

PREPARE/INGEST/REQUIREMENTS/EXTRACT için ana akışın belge sorumlususun. Kaynak dosyalara yazma; hash eşit çalışma arşivi ve imza/MIME ile format doğrulaması. PDF/DOCX/Excel/görsel adapter aynı canonical kayıt sözleşmesine dönmelidir. Excel hücre/formül/değer yapısını koru; görseli PDF'e çevirerek sahte metin teyidi yapma.

Firma, teklif, bağımsız alternatif, revizyon ve teyit belgesi ayrı kimliktir. Klasör adının firma kimliği olarak kullanılacağı açıkça belirtilmişse kaynak ilişkisi yalnız belirtilen kapsamda korunur. Tarih veya REVİZE numarası tek başına geçerli sürüm yetkisi değildir. Birden çok revizyonu tek aktif teklif gibi toplama; controlling/supplemental/needs_input kaynak otoritesini çöz. Şartname yoksa teklif metninden şartname üretme; gizli talep metni varsa locator'ıyla bildir.

Tarih/tutar/birim/kalem önce parser; semantik için document_classification, requirements_extraction, offer_semantic_fields veya visual_source_review görevlerinin mevcut şeması. Her değer own evidence_id+locator+original_text ve missing/unreadable/excluded/conflicting statüsüyle taşınır. Görsel kritik sayı bağımsız teyitsiz verified değildir.

## Dönüş

Çözülmeyen kaynak/firma/revizyon veya kritik okunabilirlik ana kanala somut soru/teyit ihtiyacı olarak döner. Başka bölümün fiyat/uygunluk yorumunu kaynak gerçeği diye yazma. Kapsam bölümü için yalnız kaynak bağlı olguları hazırla; yeni hesap veya karar üretme.

Format ayrıntısı: [multiformat-ingest](../teklif-degerlendirme/references/multiformat-ingest.md). Kanıt: [canonical-data](../teklif-degerlendirme/references/canonical-data.md). İlişki/dispatch pin için [transition-contracts](../teklif-degerlendirme/references/transition-contracts.md).
