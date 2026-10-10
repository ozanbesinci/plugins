# Kurulum ve calisma ortami - v5.0.17

This skill is designed for a local Windows procurement workflow, but deterministic tests also run cross-platform.

## Required runtime

- Python 3.11+; tested development code is compatible with Python 3.13.
- Packages in `requirements.txt`, including `jsonschema` for strict model-result gates.
- DuckDB is the production state/evidence database.
- The DuckDB `pdf` community extension is a required startup dependency in v5.0.17. `scripts/environment_check.py` verifies actual functions rather than assuming compatibility from a version string.
- The skill never installs or repairs dependencies and does not hand repair off to another skill. It checks, lists what is missing, and stops. Installation is done by an authorised person outside the skill; afterwards the preflight is re-run and the same request can resume.
- Microsoft Excel + pywin32 is required on Windows for real Excel recalculation and PDF export when those verification steps are required. No silent LibreOffice substitution is used.

## Preflight

Run:

```text
python scripts/environment_check.py --output environment.json
python scripts/run_tests.py
```

Any missing/out-of-range required Python package, missing DuckDB package, or unavailable DuckDB `pdf` extension returns `BLOCKED_ENVIRONMENT` (`--strict` exit code 3) with a concrete `missing_components` list (component, required, installed, reason) and a Turkish `user_message`. No package, extension or security setting is changed. Analysis continues only after `READY`. Test-only SQLite compatibility is enabled only by the test suite through `TEKLIF_TEST_SQLITE=1` and is not a production fallback.

## Analysis entrypoint

```text
python scripts/workflow.py prepare --source "<source-folder>" --run "<run-folder>" --profile standart
python scripts/workflow.py next --run "<run-folder>"
python scripts/workflow.py status --run "<run-folder>"
```

When `next` returns `NEEDS_LLM`, execute only the returned bounded task packets with an approved runtime model matching `config/policy.json`. Record strict JSON results together with the **actual** model and effort receipt:

```text
python scripts/record_results.py --run "<run-folder>" --task-id "<task-id>" --input "<result.json>" --model "<actual-model>" --effort "<actual-effort>" --response-id "<optional-response-id>" --input-tokens <required> --cached-input-tokens <optional> --output-tokens <required>
```

Each model result is schema-validated before it can enter the canonical store. `input_tokens` and `output_tokens` are mandatory for a successful model receipt; unknown usage is not treated as zero. Continue `workflow.py next` until VERIFIED/PRELIMINARY/BLOCKED. Final validation also requires source/data-quality controls, cross-output reconciliation and the revision-aware coverage record. Profile token caps are computed from recorded input-token receipts. At the hard cap no new model task is dispatched unless the user explicitly authorizes a run-level override with `workflow.py budget-override --run "<run-folder>" --allow true`.

## CLI durum kodlari

`workflow.py` ve `validate_run.py` JSON durumunu stdout'a yazar; otomasyon ayrıca exit code'u kontrol etmelidir. `VERIFIED/OK` başarıdır. `PRELIMINARY` (2) kontrollü eksik sonuçtur; `BLOCKED_ENVIRONMENT` (3) eksik bileşen listesiyle analizin hiç başlamadığını bildirir; `BLOCKED`, `MANUAL_REVIEW_REQUIRED` ve `BUDGET_EXHAUSTED` (4) başarılı teslim değildir. Bileşenler elle kurulduktan sonra devam parametreleri komut satırına dağılmaz; `resume_request.json` içinde source/run/profile/analysis-date/financial/scoring payload'ları birlikte korunur.

## v5.0.17 kabul kapilari

- Hesaplanmamış Excel formülleri, çözümlenmemiş veya çelişkili toplamlar, başka teklife ait ya da dayanağı bulunmayan kanıtlar ve geçersiz kaynak konumları `verified` olarak işaretlenemez.
- Ürün/kapsam ve miktar birimi doğrulanmadan ranking açılmaz; açık satır-toplam mutabakatsızlığı kritik bulgudur.
- Ödeme oranı/tutarı anaparaya mutabık değilse maliyet hesabı incomplete kalır ve karar kapısı `SUFFICIENT` olamaz.
- Final XLSX formula-free üretilir; yüksek güvence PDF'sinde kritik snapshot değerleri gerçek PDF metninde ayrıca doğrulanır.
- Gerçek DuckDB + DuckDB PDF extension ve Windows COM canlı kabulü ilgili üretim ortamında ayrıca yapılmalıdır; SQLite test modu bunların yerine geçmez.

## Release note

Do not replace an installed organizational version until controlled live acceptance has been completed on representative procurement files. Synthetic tests validate code paths, not real supplier-document accuracy or token consumption.
