# Kritik Belirsizlikte Kullanıcı Yanıtı Sözleşmesi

## Öncelikli kullanıcı kanıtı

Kullanıcının doğrudan verdiği olgu, teyit, düzeltme ve karar yetkili kullanıcı kanıtıdır; ilgili değerlendirme girdisinde belge, model çıkarımı ve önceki varsayımdan önceliklidir. [Ortak kullanıcı kanıtı sözleşmesi](../../../USER-EVIDENCE-POLICY.md) uygulanır. Kaynak belge ile kullanıcı beyanı ayrı tutulur; kullanıcı cevabını uygulayamayan kod, teknik entegrasyon engeli olarak bildirilir.


## Durma ve soru gösterimi

`workflow.py prepare` veya `workflow.py next` sonucu `NEEDS_USER_INPUT` ise `questions` alanındaki sorular, kaynak ve kapsam bilgileriyle kullanıcıya gösterilir. Aynı kapsamda en çok üç soru bir turda sunulur; `remaining_question_count` sonraki turu gösterir. Gereken soru sayısı toplamda sınırlandırılmaz. `PREPARE` içindeki belge sınıflandırma görevi kaynak ilişkisini açıklığa kavuşturabilir; kaynak otoritesi açıkken sonraki bağımlı görevler dispatch edilmez. Karar özeti, Excel/PDF ve teslim bekler.

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


## Yapılandırılmış alıcı beyanı

Gerçek kullanıcı yanıtı `answer_kind: clarification` ve `buyer_inputs` ile kaydedilebilir. Mevcut kodun desteklediği türler: `currency`, `reference_quantity`, `scope_cost`, `payment_terms`, `warranty_terms`. Tarih beyanlarının motora uygulanması henüz desteklenmemektedir; kullanıcı teyidi geçerlidir fakat bu entegrasyon tamamlanmış sayılmaz. Her kayıt kesin teklif kimliği, soru kimliği, soru kapsamı ve değişmemiş kaynak hashlerine bağlıdır. Bir açıklamadan verilmemiş miktar, bedel, para birimi veya ödeme tarihi türetilmez.

Referans miktarı yalnız kaynakta kanıtlanan satırın birim fiyatıyla yeniden hesaplanır; kaynak toplamı korunur ve fark ayrı gösterilir. Kullanıcının açık sıfır ilave maliyet yanıtı yalnız ilgili kapsam kalemine uygulanır. Yanıtın başarıyla kaydedilmesi sorunun çözüldüğü veya teklif olgusunun `verified` olduğu anlamına gelmez. Yeni koşuda bağlı hesap doğrulandıktan sonra yalnız kapsanan soru kapanabilir. Kaynak veya soru kapsamı değişirse eski yanıt doğrudan taşınmaz.

Eski koşuya yeni aday kodu zorla uygulanmaz. Yeni kod için ayrı koşu açılır; eski model sonuçları yalnız birebir görev paketi ve kaynak eşleşmesinde, özgün makbuz korunarak yeniden kullanılabilir.


Açık “bilinmiyor” yanıtı kaydedilir; aynı soru tekrarlanmaz ve değer uydurulmaz. Karar etkisi alan bazında gerekçelendirilir. Bilinmeyen teklif tarihi, güncel geçerlilik ayrı firma/alan/kaynak/hash kapsamlı kullanıcı kanıtıyla uygulanmış ve bağımsız kontrol edilmişse tek başına firma önerisini engellemez. Geçerlilik veya diğer karar etkili bilgi bilinmiyorsa somut engel belirtilir. Özgün kaynak gözlemi ile etkin değerlendirme kanıtı ayrı tutulur. Çok alanlı soruda cevaplanan ve kalan alanlar ayrı izlenir. Karma birimler toplanmaz; kaynak satırları ve geçerli miktar düzeltmeleri ayrı doğrulanır. Uygulanmayan karşılaştırma alanı gerekçeli kayıtla açıklanır. Hesap, kaynak, bağımsız inceleme ve görsel QA kapıları korunur.
