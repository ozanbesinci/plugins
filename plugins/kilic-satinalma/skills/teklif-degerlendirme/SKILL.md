---
name: teklif-degerlendirme
description: Satınalma tekliflerini kaynak, kapsam, ticari koşul, deterministik maliyet ve bağımsız kontrol üzerinden değerlendirir; aynı doğrulanmış veriden karar önerisi ve Excel/PDF üretimini yönetir. Teklif karşılaştırma, şartname uygunluğu ve satınalma karar desteğinde ana giriş olarak kullan.
---

# Teklif Değerlendirme — 5.0.29

## Kullanıcı kanıtı önceliği

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir.

Önce mevcut kullanıcı beyanlarını değerlendir; belgedeki boşluğu yeniden kullanıcı eksikliği olarak sorma. Yanıtın motora taşınamaması teknik entegrasyon engelidir.

[Kullanıcı Kanıtı ve Değerlendirme Önceliği](../../USER-EVIDENCE-POLICY.md) bütün aşamalarda uygulanır.

## Kurumsal dil

[Kurumsal Dil ve Yayın Standardı](../../EDITORIAL-POLICY.md) uygulanır. Kullanıcı soruları ve bütün çıktı metinleri resmî ve nesnel dille hazırlanır; kişisel hitap ve sohbet geçmişine atıf kullanılmaz.

## Her çağrıda başlangıç bildirimi

Bu beceri fiilen çalışmaya başladığında, ilk kullanıcı mesajında ortak okuyucunun ürettiği satırı aynen göster. Kendi paketindeki `../../scripts/skill_startup.py --skill teklif-degerlendirme` komutunu kendi fiziksel skill klasöründen çalıştır; başka plugin'in aynı adlı skill'ini genel adla çağırma. Okuyucu gerçek beceri adını ve o çağrıdaki VERSION dosyasını kullanır:

**[Beceri adı] skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: [gerçek sürüm]**

Köşeli alanlar yalnız şablondur; kullanıcıya gösterilmez. Ad veya sürüm kaynağı eksik/bozuk/çelişkiliyse hatayı bildir ve becerinin asıl işlemini başlatma. Plugin sürümünü skill sürümü yerine yazma.

Ana akış bir alt skill'in görevini başlatacaksa ana ajan o alt skill'in gerçek satırını kullanıcı kanalında **görev dispatch'ından önce** gösterir. Alt ajan kullanıcıya ayrı mesaj göndermez ve görev JSON'una bildirim öneki eklemez. Yalnız bir referansı okumak veya sıradaki adım olarak bir skill'den bahsetmek bildirim gerektirmez. Başka bir gerçek çağrı başladığında tekrar göster.

Bu beceri tek ana giriş noktasıdır. Kullanıcıya bütünleşik bir akış sunulur; ilgili alt beceri ihtiyaç doğrultusunda yüklenir. Bir alt skill'i yüklemek yeni model çağrısı veya yeni analiz koşusu açmak değildir. Nihai satınalma onayı yetkili kullanıcıya aittir. Analiz belgelerinde resmî, nesnel ve somut Türkçe kullanılır; kişisel hitaba yer verilmez.

## Başlangıç ve ortak sınır

1. Ortamı `scripts/environment_check.py --strict --output "<run>/environment.json"` ile kontrol et. `READY` olmadan analiz başlatma. Eksikleri gereken/kurulu sürüm ve nedenle tek tabloda göster. Güncelleyici otomatik çağrılmaz; paket kurulmaz. Geliştirme veya sürüm sorusu bir teklif analizi değildir.
2. Yalnız yeni boş run için `scripts/workflow.py prepare --source "<source>" --run "<run>" --profile <profil>` kullan. Kaynak salt okunur; arşiv kopyası hash eşit olmalı. Var olan koşuya prepare uygulama. Kullanıcı profil/girdi vermişse tekrar sorma.
3. Envanteri dosya/format/rol/firma/revizyon/okunabilirlik olarak tek tabloda göster. Kaynak klasör adı kullanıcı tarafından firma olarak belirtilmişse bu ilişkiyi kaydet; diğer adlardan sessiz firma/revizyon seçimi yapma.
4. [Ortak çalışma sözleşmesini](references/module-contract.md) oku. Tek run/DB, mevcut şema/context, task ID, kaynak/hash/evidence ve gerçek model makbuzu bütün bölümlerde korunur. Normal otomatik keşif açıktır; doğrudan alt skill çağrısı da bu ana akışa bağlanır.

## Bölüm seçimi

| İhtiyaç / mevcut görev | Yüklenecek alt skill |
|---|---|
| Dosya/envanter, okuma, firma/revizyon/kaynak otoritesi, document_classification, requirements_extraction, offer_semantic_fields, visual_source_review | [Belge ve Kaynak](../teklif-belge-kaynak/SKILL.md) |
| Şartname/kapsam/miktar/ödeme/teslim/garanti; requirement_assessment, technical_exception, contract_exception | [Kapsam ve Ticari Koşullar](../teklif-kapsam-ticari/SKILL.md) |
| Deterministik tutar, kalem, indirim, kur/vergi/PV/TCO, cost bridge | [Maliyet Hesabı](../teklif-maliyet/SKILL.md) |
| Ayrı hesap ve üyelik kontrolü, parser farkı, independent_fact_review, adjudicate_differences | [Bağımsız Kontrol](../teklif-bagimsiz-kontrol/SKILL.md) |
| decision_summary, claim/snapshot, Excel/PDF, artifact_visual_review, validate_run | [Karar ve Rapor](../teklif-karar-rapor/SKILL.md) |

Bir görevde birincil sorumlu tek bölüm olsun. Ödeme metnini Belge çıkarır, Kapsam ticari anlamını çözer, Maliyet yalnız doğrulanmış girdiyi hesaplar; Bağımsız Kontrol ayrı doğrular. Karar/Rapor hesap veya eksik kaynak üretmez. Beş bölümü peşinen bağlama alma.

## Belirsizlikte tek kullanıcı kanalı

[Kritik Belirsizlikte Kullanıcı Yanıtı Sözleşmesi](references/user-input-gate.md) uygulanır. `NEEDS_USER_INPUT` döndüğünde kaynaklı sorular kullanıcıya gösterilir; bağlı karar özeti ve Excel/PDF görevi ilerletilmez. Gerçek yanıt yalnız soru/kaynak kapsamıyla kayıt altına alınır; mevcut koşudaki model veya çıktı onayı doğrudan devralınmaz.

Her aşamada karar/hesap etkili belirsizlik görülür görülmez sor; sadece final RFI yeterli değildir. Önce mevcut belge/önceki yanıtı kontrol et, bilinen bilgiyi tekrar isteme. Alt görevler aynı soruyu ana ajana mevcut şemanın issue/difference alanıyla iletir; kullanıcıya ayrı mesaj göndermez. Aynı aşamadaki ilişkili soruları kısa blokta birleştir; farklı firmaların cevap kapsamını birleştirme.

Soruda firma/dosya/locator, belirsiz alan ve karara etkisi görünür olsun; kullanıcıya teknik hata çözümü veya gereksiz uygulama tercihi sorma. Örneğin: “Batu teklifindeki 60 günlük ödeme süresi hangi olaydan başlıyor: teslim, fatura veya başka bir tarih?” Seçeneği varsayılan cevap yapma.

Cevap yok/kısmi/çelişkiliyse bağlı hesap, sıralama, karar ve karar Excel/PDF üretimini beklet. Bağımsız envanter işi devam edebilir. Bilinmeyeni sıfır yapma; kullanıcı susması veya “devam” demesi iş girdisi değildir. Gereken takip soruları sayı sınırı olmadan sürer; aynı cevaplanmış soru sebepsiz tekrarlanmaz. Model retry/bütçe sınırları korunur.

Yanıtı firma/teklif/alan/kaynak revizyonu ve soru kapsamında tut. Açık kullanıcı iş beyanı ilgili alan için öncelikli kullanıcı kanıtıdır; özgün belge teyidi ve teknik QA sonuçları ayrı kayıtlardır. Pinned görev context'ini ezme; yeni veri bağlı kontrolleri/hesap/snapshot/QA'yı yeniden doğrulatır. Mevcut uyumluluk kuralları yeni run gerektiriyorsa eski koşuyu koru.

## Motor ile çalışma

Mevcut sıra `PREPARE → INGEST → REQUIREMENTS → EXTRACT → NORMALIZE → SUFFICIENCY → REVIEW → ADJUDICATE → REPORT → QA → COMPLETE`. Sırayı Python belirler; alt skill yeni aşama yaratmaz. Açık iş sorusuna bağlı bir sonraki çağrıyı çalıştırmadan kullanıcıya dön. `NEEDS_LLM` için yalnız listelenen bounded context + görev şeması + listelenen görselleri ver; strict JSON ve gerçek model/efor/token ile `record_results.py` kayıt kapısını uygula.

**Bu geliştirme adayının yürütme sınırı:** `workflow.py prepare/next`, açık kritik iş sorularında `NEEDS_USER_INPUT` döndürür; `user_question_gate.py` yanıtı soru/kaynak kapsamıyla kaydeder ve değişen girdi için yeni koşu talebi üretir. Açık soru varken karar özeti veya ön Excel/PDF teslimi yapılmaz. Yanıt kaynak olgularını doğrudan `verified` yapmaz. Bu geliştirme adayı gerçek belge kabulü ve son iki motorlu test tamamlanmadan üretim kabulü almış sayılmaz.

Teknik parser/şema/hesap/QA hatası kullanıcı ticari cevabıyla PASS olmaz. `PASS/SKIPPED/BLOCKED` aşamalarını ayrı bildir. Tamamlanan analiz tek gerekçeli ana satınalma eylemi önerisiyle kapanır: doğrulanmış firma/kapsam/bedel/koşul/risk ve sonraki adım. Yeterli kanıt yoksa somut teyit/yenileme talebi veya mevcut şartlarda alımı önermeme kararı ver; zorla firma seçme. Teknik BLOCKED başarılı karar teslimi değildir.

## Gerektikçe ayrıntı

[Kalite yöntemi](references/analysis-quality-workflow.md) kaynak/soru, analiz birimi, bağımsız iz ve görünür çıktı için ortak ayrıntıyı taşır. İlgili alt beceri yalnız kendi bölümünü yükler; aynı kontrolü farklı adlarla yeniden başlatma.

- [Mevcut yürütme protokolü](references/execution-protocol-v5024.md): eski algoritma, CLI, modeller, cache, pin ve teslim kontrolleri. Belirsizlikte otomatik ön Excel/PDF talimatı yerine yukarıdaki yeni kullanıcı bekleme kuralı uygulanır; sürüm ve kullanıcı sorusu kapsamlarında bu ana dosya önceliklidir.
- [Mimari](references/architecture.md) ve [ajan sınırları](references/agent-routing.md): yalnız teknik geçiş veya dar görev gerektiğinde.
- [Satınalma değişmezleri](references/procurement-invariants.md): bütün profillerde; şartname bulunmadığında teknik uygunluk sonucu üretilmez; tek tedarikçiye karşılaştırmalı puan verilmez.

Kurulum/güncelleme/yayın ayrı yetkidir; analiz sırasında skill dosyalarını değiştirme.


Açık “bilinmiyor” yanıtı kaydedilir; aynı soru tekrarlanmaz ve değer uydurulmaz. Karar etkisi alan bazında gerekçelendirilir. Bilinmeyen teklif tarihi, güncel geçerlilik ayrı firma/alan/kaynak/hash kapsamlı kullanıcı kanıtıyla uygulanmış ve bağımsız kontrol edilmişse tek başına firma önerisini engellemez. Geçerlilik veya diğer karar etkili bilgi bilinmiyorsa somut engel belirtilir. Özgün kaynak gözlemi ile etkin değerlendirme kanıtı ayrı tutulur. Çok alanlı soruda cevaplanan ve kalan alanlar ayrı izlenir. Karma birimler toplanmaz; kaynak satırları ve geçerli miktar düzeltmeleri ayrı doğrulanır. Uygulanmayan karşılaştırma alanı gerekçeli kayıtla açıklanır. Hesap, kaynak, bağımsız inceleme ve görsel QA kapıları korunur.
