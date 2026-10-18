# Mimari ve durum makinesi

## Amaç

Kontrolü LLM sohbetinden alıp deterministik iş akışına vermek; modeli yalnız kanıt yorumlama, çözülemeyen semantik fark ve karar metni üretiminde kullanmak.

## Katmanlar

1. **Inventory** — dosya imzası, hash, boyut, biçim, rol adayı, firma/revizyon ilişkisi.
2. **Adapters** — biçime özgü okuma; PDF/Excel/CSV/Word/görsel/e-posta.
3. **Trust/Authority** — dış kaynağı untrusted kabul et; `source_authority` ile controlling/supplemental/needs_input durumunu kodla.
4. **Canonical Store** — `analysis.duckdb`; belge, kanıt, fact, requirement, hesap, RFI, schema-validation, data-quality ve audit state.
5. **Integrity/Comparability** — `grain_integrity.py` + `comparison_contract.py`; grain/JOIN bütünlüğü ve karar için ortak karşılaştırma zemini.
6. **Deterministic Calculation** — ana procurement hesapları + `independent_recompute.py` ile ayrı yeniden hesaplama + `cost_bridge.py` residual mutabakatı.
7. **Bounded LLM** — yalnız `context_packet`; strict JSON Schema PASS olmadan DB'ye yazma.
8. **Adjudication** — yalnız unresolved difference; değişmeyen veri tekrar okunmaz; ham kaynak yerine fark paketi kullanılır.
9. **Decision Integrity** — `claim_registry.py` iddia desteğini, `scope_ledger.py` beklenen çalışma kapsamını doğrular.
10. **Reviewed Snapshot** — rapor öncesi doğrulanmış state immutable `reviewed_snapshot.json` olarak dondurulur; SHA-256 tüm çıktılara parent olur.
11. **Output/QA** — Excel/PDF/decision snapshot yalnız frozen snapshot'tan türetilir; `artifact_bindings`, formula audit, cross-output reconciliation, provenance survival, revision-aware coverage ve delta görsel QA uygulanır.

## Durumlar

| Phase | Giriş kapısı | Çıkış |
|---|---|---|
| PREPARE | kaynak erişilebilir | envanter + DB hazır |
| INGEST | adapter var | document_units yazıldı |
| REQUIREMENTS | şartname varsa | atomik requirements veya SKIPPED |
| EXTRACT | kaynak birimleri var | canonical facts |
| NORMALIZE | facts var | normalize değerler + hesaplar + comparability/integrity kontrolleri |
| SUFFICIENCY | kritik alanlar/bağımsız hesap kontrol edildi | SUFFICIENT veya PRELIMINARY_ONLY |
| REVIEW | profile göre gerekli | fark listesi |
| ADJUDICATE | açık kritik fark varsa | karar/open kayıtları |
| REPORT | claim/scope gate + reviewed snapshot PASS | aynı snapshot'tan Excel/PDF/özet |
| QA | artefakt + parent lineage var | VERIFIED/PRELIMINARY/BLOCKED |
| COMPLETE | close gate | immutable kapanış özeti |

`workflow.py next` yalnız DB durumuna göre geçiş önerir. Modelin serbest metin kararı transition kanıtı değildir.

## Pre-output freeze

Rapor öncesi sıralama zorunludur:

`source authority -> schema receipts -> data/grain quality -> comparability -> calculations -> independent recompute -> cost bridge -> claim support -> scope ledger -> reviewed snapshot freeze -> outputs`.

Frozen snapshot oluşturulduktan sonra çıktı katmanı canlı canonical tablolardan yeni değer çekmez. Snapshot içeriği değişecekse yeni snapshot/revision üret; eski parent hash'i yeni değere taşıma.

## İdempotency ve dependency

Cache anahtarı: `source_sha256 + parser_version + schema_version + extraction_mode`.

Ana zincir: `document -> unit -> evidence -> fact -> calculation/claim -> reviewed_snapshot -> artifact_binding/artifact -> QA`. Üst kaynak hash'i değişince yalnız bağlı alt zinciri invalidate et. Aynı PNG hash'li sayfa önceki görsel PASS'i taşıyabilir; ancak değişen fact/calculation/snapshot'a bağlı kontrol taşıyamaz.

## Kabul zinciri

`parse/build/save` başarısı acceptance değildir. Final zincir: `source authority -> LLM schema -> data/grain quality -> comparability -> deterministic + independent calculations -> cost bridge -> claim/scope gates -> reviewed snapshot -> output/provenance reconciliation -> coverage -> QA -> validate_run`. Kritik yapısal hata veya blocking coverage gap `VERIFIED` olamaz.

## v5.0.4 transaction ve immutable-source kurali

**Source Archive** ingest aninda exact source byte'larini SHA-256 ile run altinda korur. Model-result write tek transaction'dir: schema, evidence ownership/locator/quote ve telemetry receipt gecmeden canonical state mutate edilmez. Telemetry gercek olculmus model/efor/token veya host_unavailable + acik gerekcedir; bilinmeyen token NULL kalir, toplam butce tavaninin dogrulandigi soylenmez. Aciklanmamis eski eksik kayitlar engeldir. Reviewed snapshot ayni source revision icin idempotenttir; tamamlanmis run'a tekrar giris yeni snapshot veya workflow mutation uretmez.
