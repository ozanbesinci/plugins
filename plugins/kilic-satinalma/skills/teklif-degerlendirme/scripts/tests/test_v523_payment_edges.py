"""Final-review payment edge regressions; all fixtures are local/unit-only.

Synthetic recorder metadata below exists only because the public recorder API
requires receipt fields. No model was called; this is not LLM acceptance.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import json_text
from db import connect, init_db
from comparison_contract import assess
from independent_recompute import run as independent_recompute
from procurement_engine import calculate_costs
from procurement_math import present_value_days
from record_results import record_task_result


SCRIPTS = Path(__file__).resolve().parents[1]


class V523PaymentEdgeContracts(unittest.TestCase):
    """Two final-review edge cases, intended for native SQLite and DuckDB runs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v523-payment-edges-")
        self.root = Path(self.tmp.name)
        self.run_no = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _new_run(self, name: str | None = None) -> Path:
        self.run_no += 1
        run = self.root / (name or f"run-{self.run_no}")
        init_db(run, SCRIPTS.parent)
        return run

    def test_present_value_rejects_nonfinite_amount_and_rate_with_value_error(self):
        bad_inputs = [
            (float("nan"), 60, 0.1),
            (float("inf"), 60, 0.1),
            (100, 60, float("nan")),
            (100, 60, float("inf")),
        ]
        for amount, days, rate in bad_inputs:
            with self.subTest(amount=amount, days=days, rate=rate):
                try:
                    present_value_days(amount, days, rate)
                except ValueError:
                    continue
                except Exception as exc:
                    self.fail(f"non-finite input leaked {type(exc).__name__}; expected ValueError: {exc}")
                self.fail("present_value_days accepted a non-finite amount/rate; expected ValueError")

    def test_nonfinite_discount_rate_keeps_real_cost_unverified_without_pv(self):
        for rate in (float("nan"), float("inf")):
            with self.subTest(rate=rate):
                run = self._new_run()
                con = connect(run)
                try:
                    for oid, amount in (("A", 100.0), ("B", 110.0)):
                        con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES (?,?, 'confirmed')", [oid, oid])
                        con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES (?,?, 'active','[]')", [oid, oid])
                        for field, number, text, unit, normalized in [
                            ("total", amount, None, None, {}),
                            ("currency", None, "EUR", None, {}),
                            ("payment", None, "%100 60 gün", None, {"payment_schedule": [{"ratio": 1.0, "days": 60}]}),
                        ]:
                            con.execute(
                                "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,unit,evidence_status,critical,extraction_path,normalized_json,updated_at) VALUES (?,?,?,?,?,?,?,'verified',true,'unit_fixture',?, '2026-10-07')",
                                [f"{oid}/{field}", oid, oid, field, number, text, unit, json_text(normalized)],
                            )
                    financial = {"base_currency": "EUR", "base_date": "2026-10-07", "discount_rates": {"EUR": {"annual_effective_rate": rate}}}
                    con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('financial_parameters',?)", [json_text(financial)])
                    try:
                        calculate_costs(con, financial)
                    except Exception as exc:
                        self.fail(f"calculate_costs leaked {type(exc).__name__} for non-finite PV rate: {exc}")
                    if hasattr(con, "commit"):
                        con.commit()
                    costs = [json.loads(row[0]) for row in con.execute("SELECT result_json FROM calculations WHERE calculation_type='cost_summary' ORDER BY offer_id").fetchall()]
                    self.assertEqual(len(costs), 2)
                    for result in costs:
                        self.assertFalse(result["complete"], result)
                        self.assertIsNone(result.get("acquisition_present_value"), result)
                finally:
                    con.close()
                comparison = assess(run)
                self.assertFalse(comparison["ranking_allowed"], comparison)
                independent = independent_recompute(run)
                self.assertEqual(independent["status"], "UNVERIFIED", independent)

    def _payment_run(self, task_id: str, day: int, amount: float, payment_quote: str) -> tuple[Path, dict]:
        run = self._new_run(task_id)
        source_text = f"Offer total 100 EUR. Delivery 30 days. Payment: {payment_quote}."
        source_path = run / f"{task_id}.txt"
        source_path.write_text(source_text, encoding="utf-8")
        from common import sha256_file

        con = connect(run)
        try:
            con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES ('A','Supplier A','confirmed')")
            con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('A','A','active','[\"doc-A\"]')")
            con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,offer_id,sha256,size_bytes,parse_status,active) VALUES ('doc-A',?,?, 'text','offer','A','A',?,?, 'read',true)",
                        [source_path.name, source_path.name, sha256_file(source_path), len(source_text.encode("utf-8"))])
            con.execute("INSERT INTO document_units(unit_id,document_id,unit_type,unit_index,locator_json,text_content,structured_json,content_sha256) VALUES ('unit-A','doc-A','text_block',1,?,?,?,?)",
                        [json_text({"page": 1}), source_text, json_text({}), sha256_file(source_path)])
            for evidence_id, quote, locator in (("ev-total", "100 EUR", "A1"), ("ev-currency", "100 EUR", "A1"), ("ev-delivery", "30 days", "B1")):
                con.execute("INSERT INTO evidence(evidence_id,document_id,locator_json,quote,evidence_status,extraction_path,confidence,source_sha256) VALUES (?,'doc-A',?,?,'verified','unit_source_fixture',1.0,?)",
                            [evidence_id, json_text({"cell": locator}), quote, sha256_file(source_path)])
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at) VALUES ('A/total','A','A','total',100,NULL,'verified',true,'ev-total','unit_source_fixture','{}','2026-10-07')")
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at) VALUES ('A/currency','A','A','currency','EUR','verified',true,'ev-currency','unit_source_fixture','{}','2026-10-07')")
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at) VALUES ('A/delivery','A','A','delivery','30 days','verified',true,'ev-delivery','unit_source_fixture','{}','2026-10-07')")
            con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at,offer_id) VALUES (?, 'EXTRACT','semantic_extraction','offer_semantic_fields',?,1,true,'pending',0,'now','A')",
                        [task_id, json.dumps({"offer_id": "A", "fields": ["payment"], "document_ids": ["doc-A"]})])
            con.commit()
        finally:
            con.close()
        result = {
            "facts": [{"offer_id": "A", "field_key": "payment", "value_text": payment_quote, "evidence_status": "verified", "evidence_client_id": "ev-payment",
                       "normalized": {"payment_schedule": [{"amount": amount, "days": day}]}}],
            "evidence": [{"client_id": "ev-payment", "document_id": "doc-A", "locator": {"cell": "C1"}, "quote": payment_quote, "evidence_status": "verified"}],
        }
        return run, result

    @staticmethod
    def _canonical_counts(run: Path) -> tuple[list[int], str]:
        con = connect(run)
        try:
            counts = [con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("facts", "scope_items", "evidence", "model_receipts")]
            status = con.execute("SELECT status FROM task_queue WHERE task_id=?", [run.name]).fetchone()[0]
            return counts, status
        finally:
            con.close()

    def test_amount_only_payment_is_bound_to_delivery_relative_source_and_rejects_tampering(self):
        # Keep the existing percentage-form quote as a control and add the
        # critical amount-only literal, whose normalized day is delivery-relative.
        cases = [
            ("%100 60 days after delivery", 90, 100.0, True),
            ("%100 60 days after delivery", 60, 100.0, False),
            ("%100 60 days after delivery", 600, 100.0, False),
            ("%100 60 days after delivery", 90, 90.0, False),
            ("100 EUR, 60 days after delivery", 90, 100.0, True),
            ("100 EUR, 60 days after delivery", 60, 100.0, False),
            ("100 EUR, 60 days after delivery", 600, 100.0, False),
            ("100 EUR, 60 days after delivery", 90, 90.0, False),
        ]
        for index, (quote, day, amount, should_accept) in enumerate(cases):
            task_id = f"payment-source-{index}"
            with self.subTest(quote=quote, day=day, amount=amount, accepted=should_accept):
                run, result = self._payment_run(task_id, day, amount, quote)
                before, status_before = self._canonical_counts(run)
                self.assertEqual(status_before, "pending")
                if should_accept:
                    try:
                        recorded = record_task_result(run, task_id, result,
                                                      model_name="unit-test-fixture-no-model-call",
                                                      reasoning_effort="fixture",
                                                      input_tokens=0, output_tokens=0)
                    except Exception as exc:
                        self.fail(f"recorder rejected expected source-bound payment: {type(exc).__name__}: {exc}")
                    self.assertEqual(recorded["status"], "completed")
                    con = connect(run)
                    try:
                        saved = json.loads(con.execute("SELECT normalized_json FROM facts WHERE offer_id='A' AND field_key='payment'").fetchone()[0])
                        self.assertEqual(saved["payment_schedule"], [{"amount": 100.0, "days": 90}])
                        self.assertEqual(con.execute("SELECT count(*) FROM evidence").fetchone()[0], before[2] + 1)
                        self.assertEqual(con.execute("SELECT count(*) FROM model_receipts").fetchone()[0], 1)
                    finally:
                        con.close()
                else:
                    try:
                        record_task_result(run, task_id, result,
                                           model_name="unit-test-fixture-no-model-call",
                                           reasoning_effort="fixture",
                                           input_tokens=0, output_tokens=0)
                    except ValueError:
                        pass
                    except Exception as exc:
                        self.fail(f"source/payment rejection leaked {type(exc).__name__}; expected ValueError: {exc}")
                    else:
                        self.fail(f"recorder accepted unsupported payment source semantics: quote={quote!r}, days={day}, amount={amount}")
                    after, status_after = self._canonical_counts(run)
                    self.assertEqual(after, before, "rejected payment must not commit facts/scope/evidence/model receipt")
                    self.assertEqual(status_after, "pending")


if __name__ == "__main__":
    unittest.main()
