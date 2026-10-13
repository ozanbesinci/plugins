# Kritik Belirsizlikte Kullanıcı Yanıtı Sözleşmesi

## Öncelikli kullanıcı kanıtı

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir. [Ortak kullanıcı kanıtı sözleşmesi](../../../USER-EVIDENCE-POLICY.md) uygulanır. Kaynak belge ile kullanıcı beyanı ayrı tutulur; kullanıcı cevabını uygulayamayan kod, teknik entegrasyon engeli olarak bildirilir.


## Durma ve soru gösterimi

`workflow.py prepare` veya `workflow.py next` sonucu `NEEDS_USER_INPUT` ise `questions` alanındaki sorular, kaynak ve kapsam bilgileriyle kullanıcıya gösterilir. Aynı kapsamda en çok üç soru bir turda sunulur; `remaining_question_count` sonraki turu gösterir. Gereken soru sayısı toplamda sınırlandırılmaz. `PREPARE` içindeki belge sınıflandırma görevi kaynak ilişkisini açıklığa kavuşturabilir; kaynak otoritesi açıkken sonraki bağımlı görevler dispatch edilmez. Karar özeti ve kesin öneri bekler. Yanıta bağlı rapor görevi bekler; soru durumunda otomatik XLSX/PDF üretilmez. Bağımsız çalışan ajanların kayıtları devam edebilir.

Her soru `issue_id`, `scope_sha256`, `owner`, `fact_ids`, `evidence_ids`, `sources` ve karar etkisiyle gelir. Soruların başlığı ve kullanıcıya sunulan açıklama resmî ve nesnel Türkçeyle hazırlanır. Aynı soru, aynı kapsamda tekrarlanan `next` çağrısında yeni bir soru sayılmaz.

## Yanıt kaydı

Kullanıcının gerçek yanıtı, kapsamı değişmeyen soruya bağlanır. `scripts/user_question_gate.py --run "<run>" --response-file "<yanıt.json>" --next-run "<yeni-run>"` komutu yanıtı `workflow_events` ve hash'li `user_responses/` kaydına işler. Yanıt dosyası örneği:

```json
{
  "issue_id": "<questions.issue_id>",
  "scope_sha256": "<questions.scope_sha256>",
  "answer_text": "Kullanıcının gerçek yanıtı",
  "answer_kind": "clarification"
}
```

`answer_kind` yalnız `clarification`, `financial_rate` veya `new_source` olabilir. `financial_rate` yanıtında `currency` ve `annual_effective_rate` alanları zorunludur; yalnız soruda istenen para birimi için 0–1 aralığında sayısal oran kabul edilir. `new_source` yanıtında ayrı, mevcut bir kaynak yolu `source` ile belirtilir. Gerçek kullanıcı mesajına bağlı dosya yetkili kullanıcı beyanının kanıtıdır; tedarikçi belgesi veya bağımsız QA sonucu olarak etiketlenmez.

Mevcut Python uygulamasında yapılandırılmış `buyer_inputs` içermeyen `clarification` yalnız audit kaydıdır ve açık soruyu kapatmaz. Bu teknik sınır, açık kullanıcı bilgisinin kanıt niteliğini reddetmez; uygulanamayan yanıt entegrasyon eksikliği olarak bildirilir. `financial_rate` ve `new_source`, önceki koşunun olgularını değiştirmez; `resume_request` yeni, boş bir koşu yoluna işaret eder. Yeni koşu `workflow.py prepare --resume-request "<resume_request>"` ile başlar. Hazırlık, yanıt dosyasının hash'ini, izinli girdileri ve kaynak dosyalarının baytlarını doğrular. Değişen girdi yeni hesap, bağımsız kontrol, snapshot, Excel/PDF ve QA gerektirir.

Firma/teklif/revizyon ve ticari alan için açık kullanıcı teyidi öncelikli kullanıcı kanıtıdır; yalnız belge yokluğu nedeniyle reddedilmez. Kullanıcı beyanı kendi kaynak türüyle kaydedilir; özgün belge olgusu ve eski dispatch değiştirilmez. Şartname uygunluğu kullanıcı tarafından verilen ölçüt ve kanıtla ayrıca değerlendirilir. Teknik hesap, ayrıştırma veya QA hatası ticari yanıtla kapatılamaz. Yanıtın yetersiz, çelişkili veya kapsam dışı olduğu durumda durma durumu korunur.


## Cevaplanmış soru ve açık ticari konu

Koordinatör gerçek yanıtın gösterilen soruyu tamamen karşıladığını doğruladıktan sonra `question_waits.record_answer` ile yanıt yeterliliğini ayrıca kaydeder. “Henüz açıklama alınmadı” cevabı, açıklama alınıp alınmadığı sorusunun tam yanıtıdır; eksik ticari değer üretmez. Aynı `issue_id` ve `scope_sha256` için tamamlanmış yanıt yeni soru listesine alınmaz. Ticari `open_issues` kaydı açık kalır ve yeterlilik/QA kontrollerinden çıkarılmaz. Kısmi veya ilgisiz yanıt beklemeyi korur. Maddi kaynak veya soru kapsamı değişirse yeni kapsam ayrıca değerlendirilir. Yeni koşu gerektiren yeterli yanıt tekrar sorulmaz; yeni koşu gerekliliği sürer.

## Yapılandırılmış alıcı beyanı

Gerçek kullanıcı yanıtı `answer_kind: clarification` ve `buyer_inputs` ile kaydedilebilir. Desteklenen türler: `currency`, `reference_quantity`, `scope_cost`, `payment_terms`, `warranty_terms`, `validity_date`, `quote_date`. Her kayıt kesin teklif kimliği, soru kimliği, soru kapsamı ve değişmemiş kaynak hashlerine bağlıdır. Bir açıklamadan verilmemiş miktar, bedel, para birimi veya ödeme tarihi türetilmez.

Kullanıcı miktarı veya son geçerlilik tarihini açıkça düzeltir ve uygun açık soru yoksa `user_question_gate.py --run "<run>" --correction-file "<json>"` dar bir düzeltme sorusu açar. JSON yalnız `offer_id`, `field_key` (`quantity`/`validity`) ve gerçek kullanıcı cümlesi `user_message` içerir. Kaynak arşivi ve tek aktif teklif/alan bağı doğrulanır; kapanmış koşu açılmaz. Bu işlem kaynağı değiştirmez, değeri uygulamaz, VERIFIED vermez. Dönen sorunun güncel kapsamına bağlı gerçek yapılandırılmış yanıt normal `record_response` ve yeni koşu yoluyla uygulanır. Tedarikçi belgesinin veya modelin içeriği kullanıcı düzeltmesi diye kullanılmaz.

XLSX kaynak adresleri `cell`, `range` ve `cell_range` biçimlerinde aynı dar adres kontrolüne tabidir; çelişen veya geçersiz adresler reddedilir. Miktar düzeltmesinde miktar/birim/fiyat/satır toplamı aynı teklif ve kaynak satırının kanıtı içinde kalmalıdır.

Referans miktarı yalnız kaynakta kanıtlanan satırın birim fiyatıyla yeniden hesaplanır; kaynak toplamı korunur ve fark ayrı gösterilir. Kullanıcının açık sıfır ilave maliyet yanıtı yalnız ilgili kapsam kalemine uygulanır. Yanıtın başarıyla kaydedilmesi sorunun çözüldüğü veya teklif olgusunun `verified` olduğu anlamına gelmez. Yeni koşuda bağlı hesap doğrulandıktan sonra yalnız kapsanan soru kapanabilir. Kaynak veya soru kapsamı değişirse eski yanıt doğrudan taşınmaz.

Eski koşuya yeni aday kodu zorla uygulanmaz. Yeni kod için ayrı koşu açılır; eski model sonuçları yalnız birebir görev paketi ve kaynak eşleşmesinde, özgün makbuz korunarak yeniden kullanılabilir.


Açık “bilinmiyor” yanıtı kaydedilir; aynı soru tekrarlanmaz ve değer uydurulmaz. Karar etkisi alan bazında gerekçelendirilir. Bilinmeyen teklif tarihi, güncel geçerlilik ayrı firma/alan/kaynak/hash kapsamlı kullanıcı kanıtıyla uygulanmış ve bağımsız kontrol edilmişse tek başına firma önerisini engellemez. Geçerlilik veya diğer karar etkili bilgi bilinmiyorsa somut engel belirtilir. Özgün kaynak gözlemi ile etkin değerlendirme kanıtı ayrı tutulur. Çok alanlı soruda cevaplanan ve kalan alanlar ayrı izlenir. Karma birimler toplanmaz; kaynak satırları ve geçerli miktar düzeltmeleri ayrı doğrulanır. Uygulanmayan karşılaştırma alanı gerekçeli kayıtla açıklanır. Hesap, kaynak, bağımsız inceleme ve görsel QA kapıları korunur.

## Sorunun yanıtına bağlı bekleme

Kritik bilgi, isteğe bağlı netleştirme, tercih veya onay için kullanıcıya soru sorulmadan önce sorunun kimliği/kapsamı ve cevabını bekleyen ajan/görevler kaydedilir. Yalnız bu cevaba bağlı ajanlar ve işler durur; soru sorulduğunda çalışan ve cevaba ihtiyaç duymayan ajanlar çalışmaya ve sonuçlarını kaydetmeye devam eder. Tüm ajanları topluca durdurma.

Bekleyen ajan yanıt gelene kadar hiçbir yeni araç/model çağrısı, belge okuma, hesaplama, dosya yazımı, rapor veya kontrol yapmaz; arka planda çalışmaz ve periyodik sorgulama yapmaz. Bekleme için süre sınırı yoktur. Sessizlik, seçili varsayılan veya sürenin dolması cevap/onay değildir. Kısmi veya ilgisiz yanıtta yalnız açık kalan alan sorulur ve ilgili bekleme korunur. Tek başına “devam” eksik iş bilgisini ya da onayı tamamlamaz. Önceden cevaplanan soru veya verilmiş izin aynı kapsamda sebepsiz tekrarlanmaz.

Ana ajan, alt ajan ve paralel görevlerin cevap bağımlılığını açıkça bağla. Cevaba bağlı bir ajan zaten çalışıyorsa, soruyu göstermeden önce o ajanı güvenli sınırda beklemeye al; bağımsız çalışan ajanları kesme. Sonradan başlatılacak bir iş aynı cevaba ihtiyaç duyuyorsa onu da beklet. Bir görev birden çok soruya bağlıysa gereken bütün yanıtlar tamamlanmalıdır. Bekleme kalıcıdır; yeniden başlatma veya süre geçmesi kaldırmaz. Yanıt yalnız ilgili soru kapsamını açar; veri değişmişse mevcut yeni-koşu/yeniden doğrulama yolunu kullan. Bu kural satınalma veya kurulum onayı üretmez.

### Kod kapısı

Tekil revizyonlu teklifin değerlendirme esası olarak açıkça seçilmesi, fiyat geçerliliği veya satınalma onayı değildir. Gerçek yanıt, soru/kapsam ve yeterlilik makbuzlarıyla `teklif-source-selection/v1` beyanı hazırlanır. Güncel kodla açılmış yeni koşuda, ilk görev gönderiminden önce `source_selection.py --run <run> --declaration <beyan.json>` uygula. Bu giriş yalnız seçilmiş dosyanın özgün ve arşiv baytlarını aynı SHA-256 değerine bağlar; teklif olgularını verified yapmaz, firma kimliği veya çoklu revizyon zinciri kontrollerini aşmaz. Aynı beyanın kaydı idempotenttir. Yeniden başlatmada makbuz ve kaynak bütünlüğü tekrar denetlenir. Yeni koşuya yalnız değişmemiş kaynak kapsamına ait beyan taşınır; açıkça cevaplanan seçimi yeniden sorma. Giriş yalnız ana koordinatörün gerçek kullanıcı yanıtı kaydı içindir; kaynak okuyucu/model bu kontrol verisini üretemez veya uygulayamaz.

`scripts/question_waits.py` soru kapsamını ve görev/ajan bağlarını kalıcı `user_question_waits` kaydında tutar. Normal iş soruları `user_question_gate.waiting` ile gösterimden önce kaydedilir. İsteğe bağlı/tercih/onay sorularında `register(run_root, question, task_ids=[...], agent_ids=[...])` kullan; bağımlı kimlik olmadan soru kaydı kabul edilmez. Ajan kendi sonraki işi öncesinde `assert_agent_allowed`; model görevi için `assert_task_allowed` uygular. Beklemeye giren ajan bu kontrolleri periyodik çalıştırmaz, yürütmeyi kullanıcıya bırakır. Bu API kaynak belgenin içeriğiyle veya alt model varsayımıyla çağrılamaz.

`record_answer` yalnız ana ajanın gerçek yanıtı kapsam/yeterlilik açısından değerlendirmesinden sonra çağrılır; kayıt SHA-256'sı korunur. Kısmi/ilgisiz cevap `sufficient=False` kalır. Aynı yeterli yanıt idempotenttir; ikinci kez devam üretmez. Ticari cevapta mevcut `record_response` + yeni koşu yolu korunur; eski olgu, görev paketi ve kalite sonucu değiştirilmez. Kod, kayıtlı görev/ajan bağımlılıklarını ve çalışma girişlerini denetler; sohbet ajanını ve dış araçları koordine etme yükümlülüğü ana ajandadır. Plugin kayıtlarının dışında başlatılmış süreçleri veya başka sohbetleri durdurmaya çalışma.
