---
name: teklif-degerlendirme
description: Satınalma tekliflerini kaynak, kapsam, ticari koşul, deterministik maliyet ve bağımsız kontrol üzerinden değerlendirir; aynı doğrulanmış veriden karar önerisi ve Excel/PDF üretimini yönetir. Teklif karşılaştırma, şartname uygunluğu ve satınalma karar desteğinde ana giriş olarak kullan.
---

# Teklif Değerlendirme — 5.1.1
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

1. Ortamı `scripts/environment_check.py --strict --output "<run>/environment.json"` ile kontrol et. `READY` olmadan analiz başlatma. Eksikleri gereken/kurulu sürüm ve nedenle tek tabloda göster. DuckDB ikincil PDF okuyucusu isteğe bağlıdır; yokluğu uyarı olarak görünür, birincil okuma/rapor yeteneğiyle karıştırılmaz. Özel kabulde `--require-pdf-extension` kullanılabilir. Güncelleyici otomatik çağrılmaz; paket kurulmaz. Geliştirme veya sürüm sorusu bir teklif analizi değildir.
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

[Kritik Belirsizlikte Kullanıcı Yanıtı Sözleşmesi](references/user-input-gate.md) uygulanır. `NEEDS_USER_INPUT` döndüğünde kaynaklı sorular kullanıcıya gösterilir; bağlı karar özeti ve kesin öneri bekler. Her profilde tek çok sekmeli XLSX ve çok sayfalı PDF ön raporu üretilir; karar verilememe gerekçesi iki raporda bulunur. Gerçek yanıt yalnız soru/kaynak kapsamıyla kayıt altına alınır; mevcut koşudaki model veya çıktı onayı doğrudan devralınmaz.

Her aşamada karar/hesap etkili belirsizlik görülür görülmez sor; sadece final RFI yeterli değildir. Önce mevcut belge/önceki yanıtı kontrol et, bilinen bilgiyi tekrar isteme. Alt görevler aynı soruyu ana ajana mevcut şemanın issue/difference alanıyla iletir; kullanıcıya ayrı mesaj göndermez. Aynı aşamadaki ilişkili soruları kısa blokta birleştir; farklı firmaların cevap kapsamını birleştirme.

Soruda firma/dosya/locator, belirsiz alan ve karara etkisi görünür olsun; kullanıcıya teknik hata çözümü veya gereksiz uygulama tercihi sorma. Örneğin: “Batu teklifindeki 60 günlük ödeme süresi hangi olaydan başlıyor: teslim, fatura veya başka bir tarih?” Seçeneği varsayılan cevap yapma.

Cevap yok/kısmi/çelişkiliyse bağlı hesap, sıralama ve kesin karar bekler. Raporlar mevcut kaynakları, hesaplanamayan alanları ve gereken teyitleri gösterir. Bilinmeyeni sıfır yapma; kullanıcı susması veya “devam” demesi iş girdisi değildir. Gereken takip soruları sayı sınırı olmadan sürer; aynı cevaplanmış soru sebepsiz tekrarlanmaz. Model retry/bütçe sınırları korunur.

Yanıtı firma/teklif/alan/kaynak revizyonu ve soru kapsamında tut. Açık kullanıcı iş beyanı ilgili alan için öncelikli kullanıcı kanıtıdır; özgün belge teyidi ve teknik QA sonuçları ayrı kayıtlardır. Pinned görev context'ini ezme; yeni veri bağlı kontrolleri/hesap/snapshot/QA'yı yeniden doğrulatır. Mevcut uyumluluk kuralları yeni run gerektiriyorsa eski koşuyu koru.

## Motor ile çalışma

Tarihli kullanıcı nakit defteri `dated_costs` alanıyla aynı Excel/PDF içinde değerlendirilir. En çok 48 tekil `cost_id` kaydı; maliyet türü, kaynak tutar/para, nakit tarihi, aynı tarihli kur projeksiyonu ve dayanak gerekir. Satınalma, navlun, sigorta, gümrük, KDV ödeme/geri kazanımı, enerji, bakım, sarf, yenileme, diğer ve kalıntı türleri açıkça beyan edilmeden tam kapsam toplamı verilmez. Gerçek dışı sıfır varsayılmaz. KDV geri kazanımı ve kalıntı geri dönüşü negatif nakittir. Baz tarih ortak; kur yönü hedef/kaynak; nakit tarihine kullanıcı projeksiyonu uygulandıktan sonra hedef para biriminin 365 günlük efektif oranıyla NBD alınır. Gelecekteki yabancı para akışını spot kurla dönüştürmek bu modelde reddedilir. Kur varsayımı fiyat tahmini veya onaylı şirket politikası değildir. Bu bağımsız deftere diğer otomatik fiyat/ödeme/yıllık gider toplamları eklenmez; tek maliyet iki kez sayılmaz. Excel'den içe alma aynı izinli girdileri yeni rapor revizyonuna taşır; kaynak ve resmî karar korunur. Tarihler `YYYY-MM-DD` Gregoryen/1900–9999 aralığında olmalıdır.

Geliştirme adayında resmî rapor çifti ve karar JSON'u `output/revisions/<kimlik>/` altında birlikte doğrulanır; dosya revizyonu yayımlandıktan sonra artefaktlar ve aktif çift tek DB transaction'ında kaydedilir. Dosyanın bulunması tek başına teslim veya VERIFIED kanıtı değildir. `official_delivery.py` aktif grubun dosya/hash/snapshot/metadata bağını denetler; fiziksel arızada önceki çift korunur.

Excel kullanıcı varsayımları sekiz hesap grubuna ve beş finans sekmesine ayrılır. Çok adımlı ödeme, KDV geri kazanımı ve kalıntı NBD'si yalnız açık kullanıcı kur politikası ve yeterli girdilerle hesaplanır. Yaşam gideri modeli `CONSTANT_ANNUAL` sabit enerji/bakımı kapsar; diğer giderler kapsam dışıdır. `YEARLY_SCHEDULE` seçildiğinde en çok 100 yılın her biri için enerji/bakım/diğer gider ayrı ve hedef para biriminde, yıl sonu esasıyla girilir. Bilinen sıfır açıkça 0 yazılır; eksik yıl/kategori/model toplam TCO'yu hesaplanamadı bırakır. Sabit ve yıllık model girdileri karıştırılmaz; dönem dışındaki gider reddedilir. Kullanıcı varsayımları iki raporda da görünür. Mavi hücrelerdeki değişikliklerden yeni ön rapor çifti üretmek için `scenario_import.py --run <açık-koşu> --workbook <kullanıcı-kopyası.xlsx>` kullanılır. Kaynak/formül tahrifi veya değişmiş kaynak bazı reddedilir; kaynak facts ve resmî karar yazılmaz. Kapanmış koşu için yeni analiz gerekir. Eksik varsayım sıfır ve senaryo puanı resmî firma sıralaması olmaz.

Mevcut sıra `PREPARE → INGEST → REQUIREMENTS → EXTRACT → NORMALIZE → SUFFICIENCY → REVIEW → ADJUDICATE → REPORT → QA → COMPLETE`. Sırayı Python belirler; alt skill yeni aşama yaratmaz. Açık iş sorusuna bağlı bir sonraki çağrıyı çalıştırmadan kullanıcıya dön. `NEEDS_LLM` için yalnız listelenen bounded context + görev şeması + listelenen görselleri ver; strict JSON ve gerçek model/efor/token ile `record_results.py` kayıt kapısını uygula.

**Bu geliştirme adayının yürütme sınırı:** `workflow.py prepare/next`, açık kritik iş sorularında `NEEDS_USER_INPUT` döndürür; `user_question_gate.py` yanıtı soru/kaynak kapsamıyla kaydeder ve değişen girdi için yeni koşu talebi üretir. `report_delivery.py` karar güvencesinden ayrı, iki dosyalı ön rapor teslimini denetler. Kaynak bütünlüğü bozuksa teklif değerlerini yayımlamayan iki dosyalı güvenli bildirim denenir. İki dosya doğrulanmadan teslim READY olmaz. Senaryolar kullanıcı varsayımıdır; kaynaklar ve resmî karar hesabı değişmez. Native yeniden hesaplama yapılmamış senaryo VERIFIED değildir. Yanıt kaynak olgularını doğrudan `verified` yapmaz. Gerçek belge kabulü olmadan üretim kabulü verilmez.

Teknik parser/şema/hesap/QA hatası kullanıcı ticari cevabıyla PASS olmaz. `PASS/SKIPPED/BLOCKED` aşamalarını ayrı bildir. Tamamlanan analiz tek gerekçeli ana satınalma eylemi önerisiyle kapanır: doğrulanmış firma/kapsam/bedel/koşul/risk ve sonraki adım. Yeterli kanıt yoksa somut teyit/yenileme talebi veya mevcut şartlarda alımı önermeme kararı ver; zorla firma seçme. Teknik BLOCKED başarılı karar teslimi değildir.

## Gerektikçe ayrıntı

[Kalite yöntemi](references/analysis-quality-workflow.md) kaynak/soru, analiz birimi, bağımsız iz ve görünür çıktı için ortak ayrıntıyı taşır. İlgili alt beceri yalnız kendi bölümünü yükler; aynı kontrolü farklı adlarla yeniden başlatma.

- [Mevcut yürütme protokolü](references/execution-protocol-v5024.md): mevcut algoritma, CLI, modeller, cache, pin ve teslim kontrolleri. Kullanıcı sorusu bağlı kararı bekletir; zorunlu ön rapor çifti ve güvenli bildirim için bu ana dosyanın teslim kuralı önceliklidir.
- [Mimari](references/architecture.md) ve [ajan sınırları](references/agent-routing.md): yalnız teknik geçiş veya dar görev gerektiğinde.
- [Satınalma değişmezleri](references/procurement-invariants.md): bütün profillerde; şartname bulunmadığında teknik uygunluk sonucu üretilmez; tek tedarikçiye karşılaştırmalı puan verilmez.

Kurulum/güncelleme/yayın ayrı yetkidir; analiz sırasında skill dosyalarını değiştirme.


Açık “bilinmiyor” yanıtı kaydedilir; aynı soru tekrarlanmaz ve değer uydurulmaz. Karar etkisi alan bazında gerekçelendirilir. Bilinmeyen teklif tarihi, güncel geçerlilik ayrı firma/alan/kaynak/hash kapsamlı kullanıcı kanıtıyla uygulanmış ve bağımsız kontrol edilmişse tek başına firma önerisini engellemez. Geçerlilik veya diğer karar etkili bilgi bilinmiyorsa somut engel belirtilir. Özgün kaynak gözlemi ile etkin değerlendirme kanıtı ayrı tutulur. Çok alanlı soruda cevaplanan ve kalan alanlar ayrı izlenir. Karma birimler toplanmaz; kaynak satırları ve geçerli miktar düzeltmeleri ayrı doğrulanır. Uygulanmayan karşılaştırma alanı gerekçeli kayıtla açıklanır. Hesap, kaynak, bağımsız inceleme ve görsel QA kapıları korunur.
