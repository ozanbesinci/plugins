from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from common import json_text
from db import connect, init_db
from comparison_contract import assess
from independent_recompute import run as independent_recompute
from procurement_engine import calculate_costs, calculate_scoring
from record_results import record_task_result
from llm_result_validate import ResultValidationError, validate_result


class V523StateFieldContracts(unittest.TestCase):
    """5.0.23 regression contracts, deliberately run against the frozen 5.0.22 copy."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v523-state-fields-")
        self.root = Path(self.tmp.name)
        self.run_no = 0

    def tearDown(self):
        self.tmp.cleanup()

    def case(self, *, amounts=(100, 100), changes=None, with_cost=True, extra_offer=False):
        self.run_no += 1
        run = self.root / f"run-{self.run_no}"
        init_db(run, SCRIPTS.parent)
        con = connect(run)
        try:
            offers = [("A", amounts[0]), ("B", amounts[1])]
            if extra_offer:
                offers.append(("C", 110))
            changes = changes or {}
            for oid, amount in offers:
                con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES (?,?, 'confirmed')", [oid, oid])
                con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES (?,?, 'active','[]')", [oid, oid])
                vals = {
                    "total": (amount, None, None), "currency": (None, "EUR", None),
                    "quantity": (10, None, "adet"), "scope_signature": (None, "Pompa X", None),
                    "payment": (None, "%100 60 gün", None), "incoterms": (None, "DDP", None),
                    "vat": (None, "excluded", None),
                }
                vals.update(changes.get(oid, {}))
                for field, value in vals.items():
                    number, text, unit = value
                    ev_status = "missing" if number is None and text is None and unit is None else "verified"
                    schedule = [{"ratio": 0.5, "days": 0}, {"ratio": 0.5, "days": 90}] if field == "payment" and text and "%50" in text else [{"ratio": 1.0, "days": 60}] if field == "payment" else None
                    con.execute(
                        "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,unit,evidence_status,critical,extraction_path,normalized_json,updated_at) VALUES (?,?,?,?,?,?,?, ?,true,'semantic_llm',?,'2026-10-07')",
                        [f"{oid}/{field}", oid, oid, field, number, text, unit, ev_status, json_text({"payment_schedule": schedule} if schedule else {})],
                    )
            if with_cost:
                calculate_costs(con, {})
                calculate_scoring(con, [x[0] for x in offers])
            con.commit()
        finally:
            con.close()
        return run

    @staticmethod
    def read_score(run):
        con = connect(run)
        try:
            row = con.execute("SELECT calculation_id,inputs_json,result_json,status FROM calculations WHERE offer_id IS NULL AND calculation_type='scoring' ORDER BY updated_at DESC,calculation_id DESC LIMIT 1").fetchone()
            return {"id": row[0], "inputs": json.loads(row[1] or "{}"), "result": json.loads(row[2] or "{}"), "status": row[3]}
        finally:
            con.close()

    def test_10_10_10_comparable_complete_cost_control_passes(self):
        run = self.case(amounts=(100, 105), extra_offer=True)
        contract = assess(run)
        result = independent_recompute(run)
        self.assertTrue(contract["ranking_allowed"])
        self.assertEqual(self.read_score(run)["result"]["status"], "cost_only")
        self.assertEqual(result["status"], "PASS", result)

    def test_10_10_20_complete_cost_is_legitimately_suppressed_and_independently_verified(self):
        run = self.case(amounts=(100, 105), changes={"C": {"quantity": (20, None, "adet")}}, extra_offer=True)
        before = self.read_score(run)["result"]
        self.assertEqual(before["status"], "cost_only")
        contract = assess(run)
        self.assertFalse(contract["ranking_allowed"])
        self.assertIn("quantity", contract["failed_dimensions"])
        qcheck = next(x for x in contract["checks"] if x["dimension"] == "quantity")
        self.assertEqual(json.loads(qcheck["observed_value"])["values"], {"A": 10.0, "B": 10.0, "C": 20.0})
        self.assertEqual(self.read_score(run)["result"]["status"], "suppressed_by_comparability")
        result = independent_recompute(run)
        self.assertEqual(result["status"], "PASS", result)

    def test_legitimate_suppression_dimensions_have_current_source_checks(self):
        cases = {
            "quantity": {"B": {"quantity": (20, None, "adet")}},
            "scope_identity": {"B": {"scope_signature": (None, "Pompa Y", None)}},
            "currency_basis": {"B": {"currency": (None, "USD", None)}},
            "payment_basis": {"B": {"payment": (None, "%50 bugün %50 90 gün", None)}},
            "incoterm_basis": {"B": {"incoterms": (None, "EXW", None)}},
            "vat_basis": {"B": {"vat": (None, "included", None)}},
        }
        for dimension, changes in cases.items():
            with self.subTest(dimension=dimension):
                run = self.case(changes=changes)
                contract = assess(run)
                self.assertIn(dimension, contract["failed_dimensions"])
                row = next(x for x in contract["checks"] if x["dimension"] == dimension)
                self.assertEqual(row["status"], "fail")
                self.assertTrue(json.loads(row["evidence_json"]), row)
                self.assertEqual(self.read_score(run)["result"]["status"], "suppressed_by_comparability")
                self.assertEqual(independent_recompute(run)["status"], "PASS")

    def test_missing_total_currency_and_incomplete_cost_remain_unverified_and_suppress(self):
        variants = {
            "missing_total_currency": {"B": {"currency": (None, None, None)}},
            "incomplete_cost": {"B": {"total": (None, None, None)}},
        }
        for label, changes in variants.items():
            with self.subTest(reason=label):
                run = self.case(changes=changes)
                contract = assess(run)
                self.assertFalse(contract["ranking_allowed"])
                expected = "currency" if label == "missing_total_currency" else "total"
                self.assertTrue({expected, "scope_basis"}.intersection(contract["failed_dimensions"]))
                self.assertEqual(self.read_score(run)["result"]["status"], "suppressed_by_comparability")
                self.assertEqual(independent_recompute(run)["status"], "UNVERIFIED")

    def test_suppressed_state_and_inputs_are_recomputed_not_trusted(self):
        mutations = {
            "fake_status": lambda r, i: r.update(status="cost_only"),
            "missing_failed_dimensions": lambda r, i: r.update(failed_dimensions=[]),
            "duplicate_failed_dimensions": lambda r, i: r.update(failed_dimensions=["quantity", "quantity"]),
            "extra_failed_dimensions": lambda r, i: r.update(failed_dimensions=["quantity", "foreign_dimension"]),
            "fake_ranking_allowed": lambda r, i: r.update(ranking_allowed=True),
            "fake_score_list": lambda r, i: r.update(price_scores=[{"offer_id": "A", "price_score_0_10": "10"}], cost_ranking=["A"]),
            "tampered_eligible_input": lambda r, i: i.update(eligible_offers=["A", "B", "GHOST"]),
        }
        for label, mutate in mutations.items():
            with self.subTest(tamper=label):
                run = self.case(changes={"B": {"quantity": (20, None, "adet")}})
                assess(run)
                con = connect(run)
                try:
                    score = self.read_score(run)
                    result, inputs = score["result"], score["inputs"]
                    mutate(result, inputs)
                    con.execute("UPDATE calculations SET result_json=?,inputs_json=? WHERE calculation_id=?", [json_text(result), json_text(inputs), score["id"]])
                    con.commit()
                finally:
                    con.close()
                self.assertEqual(independent_recompute(run)["status"], "FAIL")

    def test_all_compatible_offers_cannot_be_forged_as_suppressed(self):
        run = self.case(amounts=(100, 105), extra_offer=True)
        self.assertTrue(assess(run)["ranking_allowed"])
        score = self.read_score(run)
        forged = {"status": "suppressed_by_comparability", "ranking_allowed": False, "failed_dimensions": ["quantity"]}
        con = connect(run)
        try:
            con.execute("UPDATE calculations SET result_json=?,status='incomplete' WHERE calculation_id=?", [json_text(forged), score["id"]])
            con.commit()
        finally:
            con.close()
        self.assertEqual(independent_recompute(run)["status"], "FAIL")

    def test_zero_one_offer_and_legacy_missing_comparability_contract_preserve_statuses(self):
        run = self.case()
        self.assertEqual(independent_recompute(run)["status"], "PASS")
        con = connect(run)
        try:
            con.execute("DELETE FROM offers WHERE offer_id='B'")
            con.execute("DELETE FROM facts WHERE offer_id='B'")
            con.execute("DELETE FROM calculations WHERE offer_id='B' AND calculation_type='cost_summary'")
            one = calculate_scoring(con, ["A"])
            self.assertEqual(one["status"], "not_applicable")
            con.execute("DELETE FROM calculations WHERE calculation_type='scoring'")
            con.execute("UPDATE offers SET status='inactive' WHERE offer_id='A'")
            zero = calculate_scoring(con, [])
            self.assertEqual(zero["status"], "not_applicable")
            con.commit()
        finally:
            con.close()
        self.assertIsNone(self._meta(run, "comparability_contract"))
        self.assertEqual(independent_recompute(run)["status"], "PASS")

    @staticmethod
    def _meta(run, key):
        con = connect(run)
        try:
            row = con.execute("SELECT value FROM run_meta WHERE key=?", [key]).fetchone()
            return json.loads(row[0]) if row else None
        finally:
            con.close()

    def test_task_schema_requires_bounded_payment_schedule_and_rejects_alternates(self):
        skill_root = SCRIPTS.parent
        valid_ratio = {"facts": [{"offer_id": "A", "field_key": "payment", "evidence_status": "verified", "normalized": {"payment_schedule": [{"ratio": 1.0, "days": 60}]}}], "evidence": []}
        valid_amount = {"facts": [{"offer_id": "A", "field_key": "payment", "evidence_status": "verified", "normalized": {"payment_schedule": [{"amount": 100, "days": 60}]}}], "evidence": []}
        validate_result(skill_root, "offer_semantic_fields", valid_ratio)
        validate_result(skill_root, "offer_semantic_fields", valid_amount)
        invalid = [
            {"percentage": 100, "days": 60}, {"ratio": 1, "days": 60, "surprise": 1},
            {"ratio": 1, "days": 60.5}, {"ratio": -0.1, "days": 60},
            {"ratio": 1.1, "days": 60}, {"ratio": "1", "days": 60},
            {"ratio": 1, "days": "60"}, {},
        ]
        for item in invalid:
            with self.subTest(item=item):
                bad = {"facts": [{"offer_id": "A", "field_key": "payment", "evidence_status": "verified", "normalized": {"payment_schedule": [item]}}], "evidence": []}
                with self.assertRaises(ResultValidationError):
                    validate_result(skill_root, "offer_semantic_fields", bad)

    def _payment_task(self, run, task_id="pay-task"):
        con = connect(run)
        try:
            con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at,offer_id) VALUES (?, 'EXTRACT','semantic_extraction','offer_semantic_fields',?,1,true,'pending',0,'now','A')", [task_id, json.dumps({"offer_id": "A", "fields": ["payment"]})])
            con.commit()
            return [con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("facts", "scope_items", "model_receipts")]
        finally:
            con.close()

    def test_recorder_rejects_bad_payment_before_canonical_writes(self):
        run = self.case()
        before = self._payment_task(run)
        bad = {"facts": [{"offer_id": "A", "field_key": "payment", "value_text": "%100 60 gün", "evidence_status": "requires_confirmation", "normalized": {"payment_schedule": [{"percentage": 100, "days": 60}]}}], "evidence": []}
        with self.assertRaises(ResultValidationError):
            record_task_result(run, "pay-task", bad, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)
        con = connect(run)
        try:
            after = [con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("facts", "scope_items", "model_receipts")]
            self.assertEqual(after, before)
            self.assertEqual(con.execute("SELECT status FROM task_queue WHERE task_id='pay-task'").fetchone()[0], "pending")
        finally:
            con.close()

    def test_prompt_packet_exposes_the_same_schema_used_for_validation(self):
        from context_packet import task_packet
        from llm_result_validate import _bundle
        run = self.case()
        self._payment_task(run, "prompt-task")
        packet = task_packet(run, "prompt-task", max_units=10, max_chars=20000)
        schema = packet.get("result_schema") or packet.get("task_result_schema")
        self.assertIsInstance(schema, dict, packet)
        self.assertEqual(schema, _bundle(SCRIPTS.parent)["tasks"]["offer_semantic_fields"])
        valid = {"facts": [{"offer_id": "A", "field_key": "payment", "evidence_status": "requires_confirmation", "normalized": {"payment_schedule": [{"ratio": 1.0, "days": 60}]}}], "evidence": []}
        self.assertEqual(validate_result(SCRIPTS.parent, "offer_semantic_fields", json.loads(json.dumps(valid)))["status"], "PASS")

    def test_payment_ratio_and_amount_totals_are_semantically_checked_before_write(self):
        bad_schedules = [
            [{"ratio": 0.5, "days": 0}, {"ratio": 0.6, "days": 60}],
            [{"amount": 50, "days": 0}, {"amount": 40, "days": 60}],
        ]
        for index, schedule in enumerate(bad_schedules):
            with self.subTest(schedule=schedule):
                run = self.case()
                task_id = f"sum-task-{index}"
                before = self._payment_task(run, task_id)
                bad = {"facts": [{"offer_id": "A", "field_key": "payment", "evidence_status": "requires_confirmation", "normalized": {"payment_schedule": schedule}}], "evidence": []}
                with self.assertRaises(ValueError):
                    record_task_result(run, task_id, bad, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)
                con = connect(run)
                try:
                    after = [con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("facts", "scope_items", "model_receipts")]
                    self.assertEqual(after, before)
                    self.assertEqual(con.execute("SELECT status FROM task_queue WHERE task_id=?", [task_id]).fetchone()[0], "pending")
                finally:
                    con.close()

    def _source_task(self, run, task_id, fields, source_text="100 EUR"):
        source = run / f"{task_id}.txt"
        source.write_text(source_text, encoding="utf-8")
        from common import sha256_file
        con = connect(run)
        try:
            con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,offer_id,sha256,size_bytes,parse_status,active) VALUES ('doc-A',?,?,?,?, 'A','A',?,7,'read',true)", [source.name, source.name, "xlsx", "offer", sha256_file(source)])
            con.execute("INSERT INTO document_units(unit_id,document_id,unit_type,unit_index,locator_json,text_content,structured_json,content_sha256) VALUES ('unit-A','doc-A','xlsx_sheet',1,'{}',?,?, 'unit-hash')", [source_text, json_text({"cells": [{"cell": "A1", "value": source_text}]})])
            con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at,offer_id) VALUES (?, 'EXTRACT','semantic_extraction','offer_semantic_fields',?,1,true,'pending',0,'now','A')", [task_id, json.dumps({"offer_id": "A", "fields": fields, "document_ids": ["doc-A"]})])
            con.commit()
        finally:
            con.close()

    def test_verified_numeric_item_requires_semantically_matching_source_quote(self):
        for amount, should_pass in ((100, True), (101, False)):
            with self.subTest(amount=amount):
                run = self.case()
                self._source_task(run, f"item-{amount}", ["total"])
                result = {
                    "facts": [{"offer_id": "A", "field_key": "total", "evidence_status": "verified", "evidence_client_id": "ev-total", "normalized": {
                        "amount_basis": "stated_grand_total", "items": [{"item_id": "total-1", "amount": amount, "amount_basis": "stated_grand_total", "currency": "EUR", "evidence_refs": ["ev-total"], "evidence_status": "verified"}],
                    }}],
                    "evidence": [{"client_id": "ev-total", "document_id": "doc-A", "locator": {"cell": "A1"}, "quote": "100 EUR", "evidence_status": "verified"}],
                }
                before = self._table_counts(run)
                if should_pass:
                    receipt = record_task_result(run, f"item-{amount}", result, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)
                    self.assertEqual(receipt["status"], "completed")
                    con = connect(run)
                    try:
                        saved = json.loads(con.execute("SELECT normalized_json FROM facts WHERE fact_id='A/field/total'").fetchone()[0])
                        self.assertEqual(saved["items"][0]["amount"], 100)
                        self.assertTrue(saved["items"][0]["evidence_refs"])
                    finally:
                        con.close()
                else:
                    with self.assertRaises(ValueError):
                        record_task_result(run, f"item-{amount}", result, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)
                    self.assertEqual(self._table_counts(run), before)

    def test_scope_evidence_status_survives_recording_independently_of_cost_role(self):
        run = self.case()
        self._source_task(run, "scope-task", [])
        result = {
            "facts": [],
            "evidence": [{"client_id": "ev-scope", "document_id": "doc-A", "locator": {"cell": "A1"}, "quote": "100 EUR", "evidence_status": "verified"}],
            "scope_items": [
                {"scope_id": "included-verified", "offer_id": "A", "classification": "product", "description": "Priced pump", "status": "verified", "cost_role": "included_in_price", "evidence_ids": ["ev-scope"]},
                {"scope_id": "included-unconfirmed", "offer_id": "A", "classification": "product", "description": "Possible priced pump", "status": "requires_confirmation", "cost_role": "included_in_price", "evidence_ids": []},
            ],
        }
        record_task_result(run, "scope-task", result, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)
        con = connect(run)
        try:
            rows = con.execute("SELECT scope_id,status,cost_role FROM scope_items WHERE offer_id='A' ORDER BY scope_id").fetchall()
            self.assertEqual(rows, [("included-unconfirmed", "requires_confirmation", "included_in_price"), ("included-verified", "verified", "included_in_price")])
        finally:
            con.close()

    def test_scope_status_schema_rejects_cost_role_masquerading_as_evidence_state(self):
        valid = {"facts": [], "evidence": [], "scope_items": [{"offer_id": "A", "classification": "product", "description": "Pump", "status": "requires_confirmation", "cost_role": "included_in_price"}]}
        validate_result(SCRIPTS.parent, "offer_semantic_fields", valid)
        invalid = {"facts": [], "evidence": [], "scope_items": [{"offer_id": "A", "classification": "product", "description": "Pump", "status": "included_in_price", "cost_role": "included_in_price"}]}
        with self.assertRaises(ResultValidationError):
            validate_result(SCRIPTS.parent, "offer_semantic_fields", invalid)
        run = self.case()
        self._source_task(run, "bad-scope-task", [])
        before = self._table_counts(run)
        with self.assertRaises(ResultValidationError):
            record_task_result(run, "bad-scope-task", invalid, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)
        self.assertEqual(self._table_counts(run), before)

    def test_payment_day_offset_must_match_source_schedule(self):
        from normalize import _payment_schedule
        self.assertEqual(_payment_schedule("%100 teslimden 60 gün sonra", 30), [{"ratio": 1.0, "days": 90}])
        run = self.case()
        self._source_task(run, "day-offset-task", ["payment"], source_text="%100 teslimden 60 gün sonra")
        result = {
            "facts": [{"offer_id": "A", "field_key": "payment", "value_text": "%100 teslimden 60 gün sonra", "evidence_status": "verified", "evidence_client_id": "ev-payment", "normalized": {"payment_schedule": [{"ratio": 1.0, "days": 600}]}}],
            "evidence": [{"client_id": "ev-payment", "document_id": "doc-A", "locator": {"cell": "A1"}, "quote": "%100 teslimden 60 gün sonra", "evidence_status": "verified"}],
        }
        with self.assertRaises(ValueError):
            record_task_result(run, "day-offset-task", result, model_name="test", reasoning_effort="medium", input_tokens=1, output_tokens=1)

    def test_override_payment_schedule_rejects_coercion_unknown_keys_and_nonfinite_values(self):
        invalid = [
            [{"ratio": 1.0, "days": "60"}],
            [{"ratio": 1.0, "days": 60.5}],
            [{"ratio": 1.0, "days": True}],
            [{"ratio": 1.0, "days": 60, "percentage": 100}],
            [{"ratio": 1.0, "days": 60, "unexpected": 1}],
            [{"ratio": float("nan"), "days": 60}],
            [{"amount": float("inf"), "days": 60}],
        ]
        for schedule in invalid:
            with self.subTest(schedule=schedule):
                run = self.case(with_cost=False)
                calculate_costs_conn = connect(run)
                try:
                    try:
                        calculate_costs(calculate_costs_conn, {"discount_rates": {"EUR": 0.1}, "offer_parameters": {"A": {"payment_schedule": schedule}}})
                    except Exception as exc:
                        self.fail(f"payment schedule validator leaked {type(exc).__name__}: {exc}")
                    row = calculate_costs_conn.execute("SELECT result_json FROM calculations WHERE offer_id='A' AND calculation_type='cost_summary'").fetchone()
                    result = json.loads(row[0])
                    self.assertFalse(result["complete"], result)
                    self.assertIsNone(result["acquisition_present_value"], result)
                finally:
                    calculate_costs_conn.close()
        for schedule in ([{"ratio": 1.0, "days": 60}], [{"amount": 100, "days": 60}]):
            with self.subTest(valid_schedule=schedule):
                run = self.case(with_cost=False)
                con = connect(run)
                try:
                    calculate_costs(con, {"discount_rates": {"EUR": 0.1}, "offer_parameters": {"A": {"payment_schedule": schedule}}})
                    result = json.loads(con.execute("SELECT result_json FROM calculations WHERE offer_id='A' AND calculation_type='cost_summary'").fetchone()[0])
                    self.assertTrue(result["complete"], result)
                    self.assertEqual(result["payment_present_value_detail"][0]["days"], 60)
                finally:
                    con.close()

    @staticmethod
    def _table_counts(run):
        con = connect(run)
        try:
            return [con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("facts", "scope_items", "evidence", "model_receipts")]
        finally:
            con.close()

    def test_ratio_and_amount_payment_fields_drive_real_cost_calculation(self):
        for schedule in ([{"ratio": 1.0, "days": 60}], [{"amount": 100, "days": 60}]):
            with self.subTest(schedule=schedule):
                run = self.case(with_cost=False)
                con = connect(run)
                try:
                    con.execute("UPDATE facts SET normalized_json=? WHERE offer_id='A' AND field_key='payment'", [json_text({"payment_schedule": schedule})])
                    out = calculate_costs(con, {"discount_rates": {"EUR": 0.1}})
                    con.commit()
                    row = con.execute("SELECT result_json FROM calculations WHERE offer_id='A' AND calculation_type='cost_summary' ORDER BY updated_at DESC LIMIT 1").fetchone()
                    result = json.loads(row[0])
                    self.assertTrue(result.get("complete"), result)
                    self.assertIsNotNone(result.get("acquisition_present_value"), result)
                finally:
                    con.close()

    def test_scope_status_is_evidence_state_and_included_in_price_is_cost_neutral(self):
        run = self.case(with_cost=False)
        con = connect(run)
        try:
            for status in ("verified", "requires_confirmation"):
                con.execute("INSERT INTO scope_items(scope_id,offer_id,classification,description,status,amount,currency,evidence_ids_json,cost_role) VALUES (?,?,?,?,?,NULL,'EUR','[]','included_in_price')", [f"s-{status}", "A", "product", "Pump already priced", status])
            result = calculate_costs(con, {})
            rows = con.execute("SELECT status,cost_role FROM scope_items WHERE offer_id='A' ORDER BY scope_id").fetchall()
            self.assertEqual({r[0] for r in rows}, {"verified", "requires_confirmation"})
            self.assertEqual({r[1] for r in rows}, {"included_in_price"})
            cost = json.loads(con.execute("SELECT result_json FROM calculations WHERE offer_id='A' AND calculation_type='cost_summary' ORDER BY updated_at DESC LIMIT 1").fetchone()[0])
            self.assertEqual(float(cost["acquisition_cost_basis"]), 100.0)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()




