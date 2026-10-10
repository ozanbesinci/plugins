"""Regression contract for independent scoring eligibility, written against RC23 5.0.21."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import procurement_engine
from db import connect, init_db, rows_as_dict
from independent_recompute import run as recompute
from procurement_engine import apply_hard_gates, calculate_costs, calculate_scoring


class EligibleUniverseRegression(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="v522-eligible-")
        self.root = Path(self.temp.name)
        self.run_count = 0

    def tearDown(self):
        self.temp.cleanup()

    def make_case(self):
        """Every case is a fresh real DB initialized and calculated exactly once."""
        self.run_count += 1
        root = self.root / f"run-{self.run_count}"
        init_db(root, SCRIPTS.parent)
        con = connect(root)
        try:
            for oid, amount in (("A", 100000), ("B", 110000), ("C", 90000)):
                con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES (?,?,?)", [oid, oid, "confirmed"])
                con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES (?,?, 'active','[]')", [oid, oid])
                for field, number, text in (("total", amount, None), ("currency", None, "EUR")):
                    con.execute(
                        "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,evidence_status,critical,extraction_path,normalized_json) VALUES (?,?,?,?,?,?,'verified',true,'canonical_test','{}')",
                        [f"{oid}/{field}", oid, oid, field, number, text],
                    )
            con.execute("INSERT INTO requirements(requirement_id,category,text,critical) VALUES ('mandatory','mandatory','Required capability',true)")
            con.execute("INSERT INTO requirements(requirement_id,category,text,critical) VALUES ('optional','nonmandatory','Optional capability',false)")
            gates = apply_hard_gates(con)
            calculate_costs(con, {})
            scoring_params = {"criteria": [{"id": "quality", "weight": 100, "scores": {"A": 8, "B": 9, "C": 7}}]}
            scoring = calculate_scoring(con, gates["eligible_offers"], scoring_params)
            con.commit()
        finally:
            con.close()
        return {"root": root, "gates": gates, "scoring": scoring}

    @staticmethod
    def conn(case):
        return connect(case["root"])

    @classmethod
    def scoring_row(cls, con):
        rows = rows_as_dict(con, "SELECT calculation_id,inputs_json,result_json,status FROM calculations WHERE offer_id IS NULL AND calculation_type='scoring' ORDER BY updated_at DESC,calculation_id DESC LIMIT 1")
        if not rows:
            raise AssertionError("canonical fixture did not store a scoring calculation")
        return rows[0]

    def edit_scoring(self, case, *, input_edit=None, result_edit=None, result_status=None):
        con = self.conn(case)
        try:
            row = self.scoring_row(con)
            inputs = json.loads(row["inputs_json"] or "{}")
            result = json.loads(row["result_json"] or "{}")
            if input_edit:
                input_edit(inputs)
            if result_edit:
                result_edit(result)
            con.execute("UPDATE calculations SET inputs_json=?,result_json=?,status=? WHERE calculation_id=?", [json.dumps(inputs), json.dumps(result), result_status or row["status"], row["calculation_id"]])
            con.commit()
        finally:
            con.close()

    @staticmethod
    def insert_gate_fact(con, offer, req, value, evidence="verified"):
        con.execute(
            "INSERT INTO facts(fact_id,offer_id,supplier_id,requirement_id,field_key,value_text,evidence_status,critical,extraction_path,normalized_json) VALUES (?,?,?,?,?,?,?,true,'canonical_test','{}')",
            [f"{offer}/{req}/{value}/{evidence}", offer, offer, req, "requirement_assessment", value, evidence],
        )

    @classmethod
    def scoring_audit(cls, case):
        con = cls.conn(case)
        try:
            return rows_as_dict(con, "SELECT status,expected_json,recomputed_json,detail_json FROM independent_calculations WHERE calculation_type='scoring'")
        finally:
            con.close()

    @staticmethod
    def recompute(case):
        return recompute(case["root"])

    def test_all_eligible_control_recomputes_scoring(self):
        case = self.make_case()
        self.assertEqual(set(case["gates"]["eligible_offers"]), {"A", "B", "C"})
        self.assertEqual(case["scoring"]["status"], "weighted_complete")
        self.assertEqual(self.recompute(case)["status"], "PASS")

    def test_verified_mandatory_failure_aliases_are_excluded(self):
        for alias in ("noncompliant", "uygunsuz", "fail", "failed"):
            with self.subTest(alias=alias):
                case = self.make_case()
                con = self.conn(case)
                try:
                    self.insert_gate_fact(con, "C", "mandatory", alias)
                    gates = apply_hard_gates(con)
                    calculate_costs(con, {})
                    calculate_scoring(con, gates["eligible_offers"])
                    con.commit()
                finally:
                    con.close()
                self.assertEqual(set(gates["eligible_offers"]), {"A", "B"})
                self.assertEqual(self.recompute(case)["status"], "PASS")
                audit = self.scoring_audit(case)
                self.assertTrue(audit)
                self.assertEqual({x["offer_id"] for x in json.loads(audit[0]["recomputed_json"])["price_scores"]}, {"A", "B"})

    def test_weighted_scores_include_only_the_two_eligible_offers(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            self.insert_gate_fact(con, "C", "mandatory", "failed")
            gates = apply_hard_gates(con)
            calculate_costs(con, {})
            scoring = calculate_scoring(con, gates["eligible_offers"], {"criteria": [{"id": "quality", "weight": 100, "scores": {"A": 8, "B": 9, "C": 7}}]})
            con.commit()
        finally:
            con.close()
        self.assertEqual(gates["eligible_offers"], ["A", "B"])
        self.assertEqual(scoring["status"], "weighted_complete")
        self.assertEqual(self.recompute(case)["status"], "PASS")
        audit = self.scoring_audit(case)
        self.assertTrue(audit)
        weighted = json.loads(audit[0]["recomputed_json"])["weighted_scores"]
        self.assertEqual({x["offer_id"] for x in weighted}, {"A", "B"})
        self.assertEqual({x["offer_id"]: x["total_score_0_10"] for x in weighted}, {"A": "8.000", "B": "9.000"})

    def test_unverified_or_nonmandatory_failure_does_not_exclude(self):
        for req, evidence in (("mandatory", "requires_confirmation"), ("optional", "verified")):
            with self.subTest(requirement=req, evidence=evidence):
                case = self.make_case()
                con = self.conn(case)
                try:
                    self.insert_gate_fact(con, "C", req, "fail", evidence)
                    gates = apply_hard_gates(con)
                    calculate_costs(con, {})
                    calculate_scoring(con, gates["eligible_offers"])
                    con.commit()
                finally:
                    con.close()
                self.assertIn("C", gates["eligible_offers"])
                self.assertEqual(self.recompute(case)["status"], "PASS")

    def test_tampered_eligible_input_variants_fail(self):
        for bad in ("missing_valid", "extra_excluded", "unknown", "inactive", "duplicate", "nonstring", "not_list"):
            with self.subTest(input=bad):
                case = self.make_case()
                con = self.conn(case)
                try:
                    self.insert_gate_fact(con, "C", "mandatory", "fail")
                    con.commit()
                finally:
                    con.close()
                def edit(inputs):
                    if bad == "missing_valid": inputs["eligible_offers"] = ["A"]
                    elif bad == "extra_excluded": inputs["eligible_offers"] = ["A", "B", "C"]
                    elif bad == "unknown": inputs["eligible_offers"] = ["A", "B", "ghost"]
                    elif bad == "inactive":
                        c = self.conn(case)
                        try:
                            c.execute("UPDATE offers SET status='inactive' WHERE offer_id='C'"); c.commit()
                        finally: c.close()
                        inputs["eligible_offers"] = ["A", "B", "C"]
                    elif bad == "duplicate": inputs["eligible_offers"] = ["A", "B", "A"]
                    elif bad == "nonstring": inputs["eligible_offers"] = ["A", "B", 7]
                    else: inputs["eligible_offers"] = "A,B"
                self.edit_scoring(case, input_edit=edit)
                self.assertEqual(self.recompute(case)["status"], "FAIL")

    def test_price_and_weighted_result_ids_and_rankings_are_exact(self):
        variants = [(target, mutation) for target in ("price_scores", "cost_ranking", "weighted_scores", "weighted_ranking") for mutation in ("extra", "missing", "duplicate")]
        for target, mutation in variants:
            with self.subTest(target=target, mutation=mutation):
                case = self.make_case()
                def edit(result):
                    values = result.get(target, [])
                    if target.endswith("scores"):
                        if mutation == "extra": values.append({"offer_id": "ghost", "price_score_0_10": "1", "total_score_0_10": "1"})
                        elif mutation == "missing": values.pop()
                        else: values.append(dict(values[0]))
                    else:
                        if mutation == "extra": values.append("ghost")
                        elif mutation == "missing": values.pop()
                        else: values.append(values[0])
                    result[target] = values
                self.edit_scoring(case, result_edit=edit)
                self.assertEqual(self.recompute(case)["status"], "FAIL")

    def test_stale_exclusion_does_not_override_compliant_facts(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            con.execute("INSERT INTO exclusions(exclusion_id,offer_id,requirement_id,decision,reason,evidence_ids_json,status) VALUES ('old-exclusion','C','mandatory','exclude','stale fixture','[]','confirmed')")
            con.commit()
        finally:
            con.close()
        self.assertEqual(self.recompute(case)["status"], "PASS")

    def test_missing_legacy_eligible_input_still_checks_raw_and_result_membership(self):
        case = self.make_case()
        self.edit_scoring(case, input_edit=lambda inputs: inputs.pop("eligible_offers", None))
        self.assertEqual(self.recompute(case)["status"], "PASS")

    def test_missing_legacy_input_does_not_bypass_result_membership(self):
        case = self.make_case()
        def add_ghost(result): result["price_scores"].append({"offer_id": "ghost", "price_score_0_10": "9"})
        self.edit_scoring(case, input_edit=lambda inputs: inputs.pop("eligible_offers", None), result_edit=add_ghost)
        self.assertEqual(self.recompute(case)["status"], "FAIL")

    def test_zero_or_one_eligible_is_legitimate_not_applicable(self):
        for eligible_count in (0, 1):
            with self.subTest(eligible_count=eligible_count):
                case = self.make_case()
                con = self.conn(case)
                try:
                    for oid in ("A", "B", "C")[eligible_count:]:
                        self.insert_gate_fact(con, oid, "mandatory", "failed")
                    gates = apply_hard_gates(con)
                    scoring = calculate_scoring(con, gates["eligible_offers"])
                    con.commit()
                finally:
                    con.close()
                self.assertEqual(len(gates["eligible_offers"]), eligible_count)
                self.assertEqual(scoring["status"], "not_applicable")
                result = self.recompute(case)
                self.assertEqual(result["status"], "PASS")
                audit = self.scoring_audit(case)
                self.assertTrue(audit)
                self.assertEqual(audit[0]["status"], "pass")
                self.assertEqual(json.loads(audit[0]["recomputed_json"]).get("price_scores", []), [])

    def test_fake_cost_only_for_single_eligible_fails(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            for oid in ("B", "C"):
                self.insert_gate_fact(con, oid, "mandatory", "failed")
            gates = apply_hard_gates(con)
            calculate_scoring(con, gates["eligible_offers"])
            con.commit()
        finally:
            con.close()
        self.assertEqual(len(gates["eligible_offers"]), 1)
        self.edit_scoring(case, result_edit=lambda result: result.update(status="cost_only", price_scores=[], cost_ranking=[]))
        self.assertEqual(self.recompute(case)["status"], "FAIL")

    def test_two_or_more_eligible_with_zero_or_one_complete_cost_is_unverified(self):
        for complete_costs in (0, 1):
            with self.subTest(complete_costs=complete_costs):
                case = self.make_case()
                con = self.conn(case)
                try:
                    if complete_costs == 0:
                        con.execute("DELETE FROM facts WHERE offer_id IN ('A','B','C') AND field_key='total'")
                    else:
                        con.execute("DELETE FROM facts WHERE offer_id IN ('B','C') AND field_key='total'")
                    gates = apply_hard_gates(con)
                    calculate_costs(con, {})
                    scoring = calculate_scoring(con, gates["eligible_offers"])
                    con.commit()
                finally:
                    con.close()
                self.assertEqual(len(gates["eligible_offers"]), 3)
                self.assertEqual(scoring["status"], "incomplete")
                self.assertEqual(self.recompute(case)["status"], "UNVERIFIED")
                audit = self.scoring_audit(case)
                self.assertTrue(audit)
                self.assertEqual(audit[0]["status"], "unverified")
                recomputed = json.loads(audit[0]["recomputed_json"])
                self.assertEqual(recomputed.get("price_scores", []), [])
                self.assertEqual(recomputed.get("cost_ranking", []), [])

    def test_partial_costs_preserve_separate_price_and_weighted_grains(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            con.execute("DELETE FROM facts WHERE offer_id='C' AND field_key='total'")
            gates = apply_hard_gates(con)
            calculate_costs(con, {})
            scoring = calculate_scoring(con, gates["eligible_offers"], {"criteria": [{"id": "quality", "weight": 100, "scores": {"A": 8, "B": 9, "C": 7}}]})
            con.commit()
        finally:
            con.close()
        self.assertEqual(scoring["status"], "weighted_complete")
        self.assertEqual(self.recompute(case)["status"], "UNVERIFIED")
        audit = self.scoring_audit(case)
        self.assertTrue(audit)
        self.assertEqual(audit[0]["status"], "pass")
        recomputed = json.loads(audit[0]["recomputed_json"])
        self.assertEqual({x["offer_id"] for x in recomputed["price_scores"]}, {"A", "B"})
        self.assertEqual(recomputed["cost_ranking"], ["A", "B"])
        self.assertEqual({x["offer_id"] for x in recomputed["weighted_scores"]}, {"A", "B", "C"})
        self.assertEqual(set(recomputed["weighted_ranking"]), {"A", "B", "C"})

    def test_independent_recompute_never_calls_main_gate_or_cost_or_score_functions(self):
        case = self.make_case()
        with patch.object(procurement_engine, "apply_hard_gates", side_effect=AssertionError("main hard gate called")), \
             patch.object(procurement_engine, "calculate_costs", side_effect=AssertionError("main cost calculation called")), \
             patch.object(procurement_engine, "calculate_scoring", side_effect=AssertionError("main scoring called")):
            self.assertEqual(self.recompute(case)["status"], "PASS")

    def test_harness_observes_requested_database_engine(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            actual = f"{type(con).__module__}.{type(con).__name__}"
            if os.environ.get("TEKLIF_TEST_SQLITE") == "1":
                self.assertIsInstance(con, sqlite3.Connection)
                self.assertIn("sqlite3.Connection", actual)
            else:
                self.assertIn("duckdb", actual.casefold())
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
