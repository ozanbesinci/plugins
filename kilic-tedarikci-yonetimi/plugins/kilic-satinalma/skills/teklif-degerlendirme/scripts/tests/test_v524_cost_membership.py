"""Independent cost-membership contracts for the RC25 5.0.24 candidate.

The expected IDs and source amounts here are handwritten from the fixture's
procurement rules. They are not obtained by calling the independent or main
scoring implementation to build the oracle.
"""
from __future__ import annotations

import json
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


class CostMembershipContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="v524-cost-membership-")
        self.root = Path(self.temp.name)
        self.case_number = 0

    def tearDown(self):
        self.temp.cleanup()

    def make_case(self, *, missing_total=()):
        """Create a clean real database with hand-authored A/B/C source facts."""
        self.case_number += 1
        run_root = self.root / f"run-{self.case_number}"
        init_db(run_root, SCRIPTS.parent)
        con = connect(run_root)
        try:
            # Fixture source contract: active A/B/C offers, 100/110/90 EUR.
            for offer_id, amount in (("A", 100), ("B", 110), ("C", 90)):
                con.execute(
                    "INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES (?,?,?)",
                    [offer_id, offer_id, "confirmed"],
                )
                con.execute(
                    "INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES (?,?, 'active','[]')",
                    [offer_id, offer_id],
                )
                if offer_id not in missing_total:
                    con.execute(
                        "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,evidence_status,critical,extraction_path,normalized_json) VALUES (?,?,?,?,?,'verified',true,'canonical_test','{}')",
                        [f"{offer_id}/total", offer_id, offer_id, "total", amount],
                    )
                con.execute(
                    "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,critical,extraction_path,normalized_json) VALUES (?,?,?,?,?,'verified',true,'canonical_test','{}')",
                    [f"{offer_id}/currency", offer_id, offer_id, "currency", "EUR"],
                )
            con.execute(
                "INSERT INTO requirements(requirement_id,category,text,critical) VALUES ('mandatory','mandatory','Required capability',true)"
            )
            gates = apply_hard_gates(con)
            calculate_costs(con, {})
            params = {"criteria": [{"id": "quality", "weight": 100,
                                    "scores": {"A": 8, "B": 9, "C": 7}}]}
            score = calculate_scoring(con, gates["eligible_offers"], params)
            con.commit()
        finally:
            con.close()
        return {"root": run_root, "eligible": gates["eligible_offers"], "score": score}

    @staticmethod
    def conn(case):
        return connect(case["root"])

    @classmethod
    def scoring_row(cls, con):
        rows = rows_as_dict(
            con,
            "SELECT calculation_id,inputs_json,result_json,status FROM calculations "
            "WHERE offer_id IS NULL AND calculation_type='scoring' "
            "ORDER BY updated_at DESC,calculation_id DESC LIMIT 1",
        )
        if not rows:
            raise AssertionError("fixture did not store a scoring calculation")
        return rows[0]

    @staticmethod
    def audit(case):
        con = connect(case["root"])
        try:
            rows = rows_as_dict(
                con,
                "SELECT status,expected_json,recomputed_json,detail_json "
                "FROM independent_calculations WHERE calculation_type='scoring'",
            )
            if not rows:
                raise AssertionError("independent scoring audit row missing")
            return rows[-1]
        finally:
            con.close()

    @staticmethod
    def ids(rows):
        return [row["offer_id"] for row in rows]

    def test_full_source_abc_control_passes_with_handwritten_cost_oracle(self):
        case = self.make_case()
        self.assertEqual(case["eligible"], ["A", "B", "C"])
        self.assertEqual(case["score"]["status"], "weighted_complete")
        self.assertEqual(recompute(case["root"])["status"], "PASS")
        rec = json.loads(self.audit(case)["recomputed_json"])
        self.assertEqual(rec["eligible_offers"], ["A", "B", "C"])
        self.assertEqual(self.ids(rec["price_scores"]), ["A", "B", "C"])
        self.assertEqual(rec["cost_ranking"], ["C", "A", "B"])
        self.assertEqual(self.ids(rec["weighted_scores"]), ["A", "B", "C"])

    def test_missing_cost_row_with_complete_canonical_source_must_fail(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            # Delete only C's derived row. Canonical total/currency facts remain.
            con.execute("DELETE FROM calculations WHERE offer_id='C' AND calculation_type='cost_summary'")
            prior = self.scoring_row(con)
            inputs = json.loads(prior["inputs_json"] or "{}")
            procurement_engine.calculate_scoring(con, inputs.get("eligible_offers", []),
                                                  inputs.get("scoring_params", {"criteria": [{"id": "quality", "weight": 100, "scores": {"A": 8, "B": 9, "C": 7}}]}))
            con.commit()
        finally:
            con.close()
        result = recompute(case["root"])
        # A/B/C are manually expected from active offers and verified source totals.
        self.assertEqual(result["status"], "FAIL")
        rec = json.loads(self.audit(case)["recomputed_json"])
        self.assertEqual(rec["eligible_offers"], ["A", "B", "C"])
        self.assertEqual(self.ids(rec["price_scores"]), ["A", "B", "C"])

    def test_false_complete_flag_with_full_source_must_not_shrink_membership(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            row = rows_as_dict(
                con,
                "SELECT calculation_id,result_json FROM calculations "
                "WHERE offer_id='C' AND calculation_type='cost_summary' "
                "ORDER BY updated_at DESC,calculation_id DESC LIMIT 1",
            )[0]
            result = json.loads(row["result_json"] or "{}")
            result["complete"] = False
            con.execute("UPDATE calculations SET result_json=?,status='incomplete' WHERE calculation_id=?",
                        [json.dumps(result), row["calculation_id"]])
            con.commit()
        finally:
            con.close()
        # The old scoring still says ABC; source facts also still say ABC.
        # An incomplete derived flag cannot authorize deleting C from the oracle.
        self.assertEqual(recompute(case["root"])["status"], "FAIL")
        rec = json.loads(self.audit(case)["recomputed_json"])
        self.assertEqual(rec["eligible_offers"], ["A", "B", "C"])

    def test_real_missing_c_total_keeps_weighted_abc_but_is_overall_unverified(self):
        case = self.make_case(missing_total=("C",))
        self.assertEqual(case["eligible"], ["A", "B", "C"])
        self.assertEqual(case["score"]["status"], "weighted_complete")
        result = recompute(case["root"])
        self.assertEqual(result["status"], "UNVERIFIED")
        rec = json.loads(self.audit(case)["recomputed_json"])
        self.assertEqual(rec["eligible_offers"], ["A", "B", "C"])
        self.assertEqual(self.ids(rec["price_scores"]), ["A", "B"])
        self.assertEqual(rec["cost_ranking"], ["A", "B"])
        self.assertEqual(self.ids(rec["weighted_scores"]), ["A", "B", "C"])
        self.assertEqual(set(rec["weighted_ranking"]), {"A", "B", "C"})

    def test_same_count_wrong_ac_result_fails_exact_membership(self):
        case = self.make_case()
        con = self.conn(case)
        try:
            row = self.scoring_row(con)
            result = json.loads(row["result_json"] or "{}")
            result["price_scores"] = [item for item in result["price_scores"] if item["offer_id"] in {"A", "C"}]
            result["cost_ranking"] = ["C", "A"]
            result["weighted_scores"] = [item for item in result["weighted_scores"] if item["offer_id"] in {"A", "C"}]
            result["weighted_ranking"] = ["A", "C"]
            con.execute("UPDATE calculations SET result_json=? WHERE calculation_id=?",
                        [json.dumps(result), row["calculation_id"]])
            con.commit()
        finally:
            con.close()
        self.assertEqual(recompute(case["root"])["status"], "FAIL")

    def test_independent_oracle_does_not_call_main_gate_cost_or_score(self):
        case = self.make_case()
        with patch.object(procurement_engine, "apply_hard_gates", side_effect=AssertionError("main gate called")), \
             patch.object(procurement_engine, "calculate_costs", side_effect=AssertionError("main costs called")), \
             patch.object(procurement_engine, "calculate_scoring", side_effect=AssertionError("main scoring called")):
            self.assertEqual(recompute(case["root"])["status"], "PASS")

    def test_missing_source_total_and_missing_derived_row_keep_aggregate_unverified(self):
        case = self.make_case(missing_total=("C",))
        # Genuine missing source total: price uses A/B, criterion scoring keeps A/B/C.
        self.assertEqual(case["score"]["status"], "weighted_complete")
        self.assertEqual(self.ids(case["score"]["price_scores"]), ["A", "B"])
        self.assertEqual(self.ids(case["score"]["weighted_scores"]), ["A", "B", "C"])
        con = self.conn(case)
        try:
            # Now remove the incomplete derived row too; source absence must remain visible.
            con.execute("DELETE FROM calculations WHERE offer_id='C' AND calculation_type='cost_summary'")
            con.commit()
        finally:
            con.close()
        result = recompute(case["root"])
        self.assertEqual(result["status"], "UNVERIFIED")
        self.assertEqual(self.audit(case)["status"], "pass")
        rec = json.loads(self.audit(case)["recomputed_json"])
        self.assertEqual(self.ids(rec["price_scores"]), ["A", "B"])
        self.assertEqual(self.ids(rec["weighted_scores"]), ["A", "B", "C"])


if __name__ == "__main__":
    unittest.main()
