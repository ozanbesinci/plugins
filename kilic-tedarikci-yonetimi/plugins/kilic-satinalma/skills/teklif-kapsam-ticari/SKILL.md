---
name: teklif-kapsam-ticari
description: Kaynak bağlı teklif kalemlerini şartname, kapsam, miktar/birim, ödeme, teslim ve ticari risk açısından değerlendirir. Ana teklif akışında kapsam veya ticari belirsizlik çözümlerken kullan; fiyat aritmetiği ve rapor ihracı yapmaz.
---

# Kapsam ve Ticari Koşullar — 5.1.1
## Kullanıcı kanıtı önceliği

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir.

Açık kullanıcı miktar, para birimi, ödeme, garanti ve geçerlilik teyitlerini firma/alan kapsamıyla esas al; yalnız belgede bulunmadığı için aynı teyidi yeniden isteme.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](../../USER-EVIDENCE-POLICY.md) bütün aşamalarda uygulanır.

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill teklif-kapsam-ticari` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

Ana giriş [Teklif Değerlendirme](../teklif-degerlendirme/SKILL.md). Doğrudan çağrılmışsan önce onu oku ve aynı run'a bağlan; ikinci prepare/DB açma. Mevcut run/task/context yoksa ana başlangıca dön. [Ortak sözleşme](../teklif-degerlendirme/references/module-contract.md) kimlik, strict şema, kanıt, soru, makbuz ve yetki sınırlarını belirler. Model alt görevinde yeni alt ajan açma.

## Sorumluluk

Kararı etkileyen kaynak veya iş belirsizliğinde [Kaynak ve soru](../teklif-degerlendirme/references/analysis-quality-workflow.md#kaynak-ve-soru) yöntemini uygula; soru kapsamını ve hangi bağlı hesabın beklediğini görünür tut.

Belge bölümünden gelen kanonik olgu/locator ve varsa bağımsız şartnameyle çalış. Kapsam sınıfı ile evidence_status ve cost_role ayrı alanlardır. Dahil kalem fiyatı toplamda zaten varsa yeniden eklenmez; incremental_adjustment yalnız kendi doğrulanmış tutar/para kanıtıyla hesap bölümüne gider. Tüm firmalarda ortak boşluk ile tek firmaya özel eksik farklıdır.

Ödeme süresi hangi olaydan başlıyor, teslim neye bağlı, fiyat birim mi satır mı, KDV dahil mi, para birimi/miktar/birim aynı mı açık olmalı. “60 gün” metninden fatura veya teklif tarihini seçme. Kullanıcının bir firmaya cevabını tüm firmalara yayma. Eksik finans/iş parametresini tahmin etme. İş belirsizliğini kaynak+alan+karar etkisiyle hemen ana ajana ilet.

Kullanıcı fiyatları vadeyle karşılaştırmak isterse [Maliyet Hesabı](../teklif-maliyet/SKILL.md) talimatını da yükle. Yalnız bir firmanın başlangıç olayına odaklanıp aynı aşamada bilinen finans yöntemi/parametre açığını sonraya bırakma. Tek kısa blokta eksik başlangıç olayı ile değerlendirme yöntemini sor: nominal bedel ve vade ayrı gösterilecek mi, yoksa vade etkisi tutara çevrilecek mi? İkinci yol için ortak değerleme tarihi, EUR'ya uygun kaynaklı/kullanıcı verilen efektif iskonto ve gerekiyorsa fatura tarihi gerekir. Kullanıcının vermediği yöntemi veya oranı seçme; belirsiz tarih yerine teklif tarihini kullanma. Bilinen profil/miktar/birim/para/kapsamı yeniden sorma.

Şartname yoksa “şartname yok, uygunluk değerlendirmesi yapılmadı” ayrı yazılır. Doğrulanmış zorunlu uygunsuzluk puandan önce eleme kapısına gider; yorum veya model eminliği belge teyidi değildir. requirement_assessment, technical_exception ve contract_exception mevcut strict şemalarıyla çalış. Uzman yorumuyla sayısal kaynak değerini değiştirme.

## Dönüş

comparison_contract/grain/data_quality kontrolü ile ortak kapsam bazını kur; sıralama yetkisini Maliyet ve bağımsız kapılara bırak. Açık ticari soru bağlı hesabı bekletir; teknik tutarsızlık ayrı BLOCKED'dır. Kullanıcı cevaplarını yetkisi/revizyonu ve firma kapsamıyla ana ajana döndür.

İlgili kurallar: [procurement-invariants](../teklif-degerlendirme/references/procurement-invariants.md), [decision-gates](../teklif-degerlendirme/references/decision-gates.md). Ekipman/ithalat kurallarını yalnız gerekirse [legacy-v4 dizininden](../teklif-degerlendirme/references/legacy-v4/README.md) yükle.
