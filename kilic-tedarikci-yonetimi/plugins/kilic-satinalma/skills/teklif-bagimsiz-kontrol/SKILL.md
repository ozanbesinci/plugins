---
name: teklif-bagimsiz-kontrol
description: Teklif kanıtı, uygun küme, kritik hesap ve sıralamayı ayrı kanıt/formül yoluyla denetler; yalnız kalan farkları hakeme taşır. Ana teklif akışında bağımsız doğrulama gerektiğinde kullan; ana hesabı tekrar çağırarak onay vermez.
---

# Bağımsız Kontrol — 5.1.3
## Sorunun yanıtına bağlı bekleme

[Kullanıcı yanıtı bekleme kuralı](../../USER-EVIDENCE-POLICY.md#sorunun-yanıtına-bağlı-bekleme) zorunludur. Yalnız sorunun cevabına bağlı ajan ve işler durur; soru anında çalışan bağımsız ajanlar devam eder. Bekleyen ajan cevap gelene kadar araç/model çağrısı, okuma, hesap, yazma, rapor veya kontrol yapmaz; süre sınırı ve periyodik sorgulama yoktur. Soru kimliği/kapsamı ve bağımlı görev/ajan kimliklerini gösterimden önce kaydet. Yalnız ilgili yeterli yanıt bu bağımlılığı açar; “devam”, sessizlik veya seçili varsayılan cevap/onay değildir. Cevaplanmış soruyu sebepsiz tekrarlama.

## Kullanıcı kanıtı önceliği

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir.

Beklenen hesabı aynı geçerli kullanıcı girdisi ve özgün belge iziyle ayrı kur; belge–kullanıcı farkının açıkça çözülmüş olması ile teknik hesap hatasını ayır.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](../../USER-EVIDENCE-POLICY.md) bütün aşamalarda uygulanır.

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill teklif-bagimsiz-kontrol` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

Ana giriş [Teklif Değerlendirme](../teklif-degerlendirme/SKILL.md). Doğrudan çağrılmışsan önce onu oku ve aynı run'a bağlan; ikinci prepare/DB açma. Mevcut run/task/context yoksa ana başlangıca dön. [Ortak sözleşme](../teklif-degerlendirme/references/module-contract.md) kimlik, strict şema, kanıt, soru, makbuz ve yetki sınırlarını belirler. Model alt görevinde yeni alt ajan açma.

## Sorumluluk

Kontrole başlarken [Bağımsız kontrol ve iz](../teklif-degerlendirme/references/analysis-quality-workflow.md#bağımsız-kontrol-ve-iz) yöntemini ve üyelik farkı varsa [Analiz birimi ve üyelik](../teklif-degerlendirme/references/analysis-quality-workflow.md#analiz-birimi-ve-üyelik) bölümünü uygula.

Ana hesap önerisini doğru varsayma. Güncel aktif teklifler, doğrulanmış hard-gate kaynakları, fact/evidence, kapsam, izinli finans girdileri ve input hash'lerinden beklenen fiyat/ağırlıklı üyeliği ayrı kur. Aynı adette farklı üye, tam kaynakta kayıp hesap satırı, gerçek eksik kaynak ve meşru karşılaştırma bastırması ayrı denetlenir.

Deterministik kontrol ana skill'in scripts/independent_recompute.py dosyasıyla ayrı formül kullanır; procurement_math/ana hesap helper'ına ikinci çağrı bağımsız teyit değildir. Mevcut independent_calculations kayıtları ve qa/independent_recompute.json kontrol ürünüdür. FAIL veya UNVERIFIED kritikse kesin karar kapısı geçmez. Parser karşılaştırmasını önce kodla yap; eşleşene ikinci tam model okuması verme.

independent_fact_review görevinde yalnız izinli ham kanıt/dar şema; merkezi öneriyi verme. Aynı görüntüye ikinci bakış bağımsız dış teyit yerine geçmez. Salt aynı tutar/filename teyit ilişkisi değildir. Semantik fark çözülemezse canonical adjudicate_differences paketi, iki tarafın kanıtı ve main/independent/corrected/open sonucu kullanılır. Açık kritik fark cevapsızsa karar bekler; teknik arıza hakem tahminiyle kapatılmaz.

## Dönüş

Gözlenen üyelik, kalem/kanıt bağı veya hesap değeri beklenenle çelişiyorsa bulgu teknik `FAIL`, teslim durumu `BLOCKED` olur. Henüz yapılmamış bağımsız kontrol ayrıca `UNVERIFIED` kalabilir; bu, gösterilmiş tutarsızlığı belirsizliğe çevirmez. Yalnız eksik ticari bilgi için kullanılan `PRELIMINARY_ONLY` etiketini teknik arızaya verme. Kritik kaynak yokluğu ile kaynak mevcutken kayıt/hesapta kaybolması ayrı bulgulardır.

Kod kontrolü kendi mevcut tablolarına/makbuzuna, model kontrolü kendi task-specific JSON'una döner; iki biçimi karıştırma. Fark listesi/etkilenen kimlikler/input hash'leri ana koordinatöre gider. Kullanıcı iş sorularını yalnız ana kanal sorar. Değişen kaynak/yanıt karşısında eski bağımsız PASS/QA'yı kör taşıma.

Sınırlar: [validation-and-trust](../teklif-degerlendirme/references/validation-and-trust.md) ve [agent-routing](../teklif-degerlendirme/references/agent-routing.md). Ayrı formül/kayıt sözleşmesi ortak referansta.
