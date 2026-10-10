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
