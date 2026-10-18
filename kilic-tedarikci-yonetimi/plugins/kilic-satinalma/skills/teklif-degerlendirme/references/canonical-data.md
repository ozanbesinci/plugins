# Kanonik veri ve kanıt sözleşmesi

## Amaç

Karar motorunu dosya formatından ayır. Her bulgu tek bir `fact` ve en az bir `evidence` zinciriyle temsil edilir.

## Fact kimliği

Önerilen desenler:

- `<offer_id>/field/<field_key>` — toplam, döviz, ödeme, teslim vb.
- `requirement/<requirement_id>` — şartname hükmü.
- `<offer_id>/requirement/<requirement_id>` — teklif uygunluğu.
- `<offer_id>/scope/<stable_key>` — kapsam dahil/hariç/eksik.

## Evidence locator

`locator_json` biçime göre değişir:

- PDF: `{page, bbox?}`
- XLSX/XLSM/XLS: `{sheet, cell|range}`
- CSV/TSV: `{row, column}`
- DOCX/DOC: `{paragraph?, table?, row?, column?}`
- Image: `{x1,y1,x2,y2}`
- EML: `{part: subject|body|attachment, index?}`

Karar motoru locator içeriğini yorumlamaz; yalnız kanıt zincirinin varlığını ve hash bağını doğrular.

## Kanıt durumları

- `verified`
- `missing`
- `excluded`
- `unreadable`
- `conflicting`
- `assumption`
- `requires_confirmation`

`missing` kayıt atlanması değildir. Kritik alan yoksa fact yine yazılır.

## Kritik ticari alanlar

Varsayılan kritik alanlar:

`total`, `currency`, `vat`, `quantity`, `quote_date`, `validity`, `delivery`, `payment`, `incoterms`, `warranty`.

Alım dalı ek kritik alan tanımlayabilir.

## Extraction path

Her evidence/fact `extraction_path` taşır:

- `deterministic`
- `python_primary`
- `duckdb_pdf_secondary`
- `vision`
- `semantic_llm`
- `adjudicated`

Bu alan model sonucuyla deterministik sonucu ayırmak için zorunludur.

## UNKNOWN prensibi

Bilinmeyen veya doğrulanmamış değer:

- `NULL` + uygun evidence_status olarak tutulur,
- hesapta otomatik `0` olmaz,
- toplam/TCO/puan sonucu gerekiyorsa incomplete olarak işaretlenir.

## RFI bağı

Her kritik unresolved fact en az bir `open_issues` kaydına bağlanır. Owner yalnız `FIRMA:<supplier_id>`, `TUM_FIRMALAR` veya `IDARE` sınıflarından biri olmalıdır.

## Source authority

Her aktif formal belge icin `source_authority` kaydi tut. `controlling`, `supplemental`, `superseded`, `candidate`, `needs_input`, `unusable` gibi durumlar karar motoruna kaynak seciminin nedenini tasir. Birden fazla formal revizyonda precedence dosya adi/tarihten otomatik cikmaz.

## Validation ve data-quality kayitlari

- `llm_result_validations`: task, schema version, canonical result hash, PASS/FAIL ve hata listesi.
- `data_quality_findings`: check id, entity, severity, confidence, evidence, risk ve remediation.
- `qa/coverage.json`: fact/requirement/artifact/claim bazinda revision-aware `passed/failed/unverified` kontrol kaydi.

Bu kayitlar final delivery gate'in girdisidir; rapor metni kendi basina kanit degildir.

## v5.0.4 karar ve çıktı kayıtları

- `comparability_checks`: karar için ortak baz boyutları ve PASS/FAIL kanıtı.
- `independent_calculations`: ana hesap ile bağımsız yeniden hesaplama, tolerans ve fark.
- `cost_bridges`: iki teklif arasındaki normalize fark, açıklanan bileşenler ve residual.
- `grain_checks`: intended grain/JOIN bütünlüğü ve revision hash'i.
- `claims`: claim türü, destek fact/calculation/evidence ID'leri, support status ve caveat.
- `scope_ledger`: beklenen/gerçekleşen kaynak, tedarikçi, analiz ve çıktı kapsamı.
- `reviewed_snapshots`: pre-output immutable snapshot kimliği, SHA-256, durum ve yol.
- `artifact_bindings`: çıktı component locator -> fact/requirement/calculation/claim -> snapshot hash bağı.

Çıktı katmanı bu kayıtların frozen snapshot görünümünü kaynak gerçek kabul eder. Live DB ile export arasında yeni bir hesap/fact oluşursa mevcut snapshot otomatik olarak yeni sonucu temsil etmez; yeni revision/snapshot gerekir.


## Kaynak kalem fiyat zinciri — 5.2.0-dev.7

Doğrulanmış `normalized.items` içindeki `amount_basis: unit_price` kalemi, `amount`, pozitif `quantity`, `currency` ve kendi `evidence_refs` alanlarını taşır. Fiyat koşulları ayrı `pricing` nesnesine yazılır:

```json
{"discounts":{"percentages":[10,5],"evidence_refs":["ev-iskonto1","ev-iskonto2"]},"vat":{"percent":20,"basis":"excluded","evidence_refs":["ev-kdv-oran","ev-fiyat-esasi"]},"stated_amounts":{"scope":"offer","net":{"amount":8550,"evidence_refs":["ev-net"]},"vat":{"amount":1710,"evidence_refs":["ev-kdv-tutar"]},"gross":{"amount":10260,"evidence_refs":["ev-brut"]}}}
```

Yüzde10, yüzde10 anlamındadır;0,10 değildir. `discounts` ve `vat` birlikte gereklidir; bilinmeyen fiyat koşulunda `pricing` atlanır, yerine sıfır yazılmaz. Açıkça sıfır iskonto ancak kendi kaynak kanıtıyla kabul edilir. Fiyatın100adet için verildiği doğrulanmışsa `price_unit: {"value":100,"evidence_refs":["ev-fiyat-birimi"]}` eklenir; belirtilmediğinde birim fiyat tanımı gereği bölen1'dir. `vat.basis` yalnız `included` veya `excluded` olur.

Birim fiyat, miktar ve para birimi kendi kaynaklarıyla doğrulanır. CSV oranları aynı kaynak veri satırından, doğru başlık/sütun rolünden ve bütün iskonto aşamaları kaynak sırasıyla alınır. Miktar hücresindeki10, iskonto%10 kanıtı değildir. KDV oranı hücresi KDV tutarı kanıtı değildir. Başka satır, başka teklif, eski hash veya yalnız görsel okuma kaynak oranı yerine geçmez. Metin kaynaklarında oran ve rol açık bağlamıyla desteklenir.

`stated_amounts.scope` satır veya teklif toplamını ayırır. Beyan genel toplamı hesaplanacak kalem listesine eklenmez. Motor `quantity × amount / price_unit × ∏(1-discount/100)` hesabını yapar; KDV esasından net/KDV/brüt türetip kaynak beyanıyla0,01 para birimi toleransında mutabakat kurar. `source_price_chain` ayrı hesap kaydıdır; kaynak net toplamına iskontoyu ikinci kez uygulamaz. Bağımsız yol kaynak kalemlerini yeniden okur. Bilinen fark kritik teyittir; eksik koşul tamamlanmış zincir değildir. KDV indirilebilirliği, alıcı düzeltmeleri, NBD/TCO ve kurum politikası ayrı girdiler ve kontroller gerektirir.

Excel/PDF aynı incelenen snapshot hesabını kullanır. Excel Kaynak Fiyat Zinciri sayfasının değer hücreleri hesap kimliği ve değer yoluna bağlıdır; kaynak kalem senaryoları teklif toplamı senaryosuyla toplanmaz.


## CSV teslim birimi adresi — 5.2.0

Tek veri satırında teslim aralığı `{"row":2,"start_column":17,"end_column":18}` veya `{"row":2,"column":17,"end_column":18}` biçiminde olabilir. İki başlangıç anahtarı birlikte varsa aynı sütunu göstermelidir. Aralıkta yalnız bir teslim-gün sütunu olmalı; değer, satır, birim başlığı, teklif/satıcı ve güncel kaynak hash'i doğrulanır. Gün sayısını yalnız normalleştirilmiş metadata'dan almak veya ödeme olayını peşin sözcüğünden dolayı sıfır gün saymak yasaktır.
