import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import error_log as log
import workflow
from common import json_text, sha256_file
from evidence_confirmation import confirm
from test_v520_scope_confirmation import ScopeConfirmation


class LoggingAndElevenFieldConfirmation(ScopeConfirmation):
    """RC22 regressions. Inherited fixture helpers, but only local tests run here."""

    def setUp(self):
        super().setUp()
        self._old_log_count = log._COUNT
        log._COUNT = 0
        self.log_root = tempfile.TemporaryDirectory()
        self._localappdata = patch.dict(os.environ, {"LOCALAPPDATA": self.log_root.name})
        self._localappdata.start()

    def tearDown(self):
        self._localappdata.stop()
        log._COUNT = self._old_log_count
        self.log_root.cleanup()
        super().tearDown()

    def events(self):
        return [
            json.loads(line)
            for path in Path(self.log_root.name).rglob("*.jsonl")
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def eleven_field_sources(self, *, vat_fact="excluded", vat_source="hariç", vat_extra=None):
        relation = super().confirmation_sources()
        source_hash = sha256_file(self.run / "sheet")
        target_hash = sha256_file(self.run / "image")
        added = {
            "vat": ("KDV", vat_fact, vat_source),
            "incoterms": ("Incoterm", "DDP", "DDP"),
            "warranty": ("Garanti", "24 months", "24 months"),
        }
        for offset, (field, (label, canonical, cited)) in enumerate(added.items(), 9):
            fact_id = f"o/field/{field}"
            evidence_id = f"pix-{field}"
            self.con.execute(
                "INSERT INTO evidence(evidence_id,document_id,locator_json,quote,evidence_status,extraction_path,source_sha256) "
                "VALUES (?,?, '{}',?,'requires_confirmation','vision',?)",
                [evidence_id, "image", f"{label}: {canonical}", target_hash],
            )
            self.con.execute(
                "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,evidence_id,extraction_path,normalized_json,critical) "
                "VALUES (?,?, 's',?,?,'requires_confirmation',?,'vision','{}',true)",
                [fact_id, "o", field, canonical, evidence_id],
            )
            cells = [
                {"cell": f"A{offset}", "formula_or_value": label},
                {"cell": f"B{offset}", "formula_or_value": cited},
            ]
            if field == "vat" and vat_extra is not None:
                cells.append({"cell": f"C{offset}", "formula_or_value": vat_extra})
            unit_row = json.loads(self.con.execute("SELECT structured_json FROM document_units WHERE unit_id='u'").fetchone()[0])
            unit_row["cells"].extend(cells)
            self.con.execute("UPDATE document_units SET structured_json=? WHERE unit_id='u'", [json_text(unit_row)])
        self.con.commit()
        if vat_extra is not None:
            from db import rows_as_dict
            from field_extract import _sheet_candidates
            unit = rows_as_dict(self.con, "SELECT * FROM document_units WHERE unit_id='u'")[0]
            self.assertEqual(len(_sheet_candidates(unit)["vat"]), 2)
        return relation

    def confirmation_issue(self, owner="IDARE", issue_type="independent_confirmation_required", *, extra=False, issue_id="rfi"):
        fact_ids = [f"o/field/{key}" for key in (
            "total", "currency", "quantity", "scope_signature", "quote_date", "payment",
            "delivery", "validity", "vat", "incoterms", "warranty",
        )]
        evidence_ids = [f"pix-{key}" for key in (
            "total", "currency", "quantity", "scope_signature", "quote_date", "payment",
            "delivery", "validity", "vat", "incoterms", "warranty",
        )]
        if extra:
            evidence_ids.append("unrelated-evidence")
        self.con.execute(
            "INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at) "
            "VALUES (?,?,'critical',?,'Confirm only cited values',?,?,'open','before')",
            [issue_id, owner, issue_type, json_text(fact_ids), json_text(evidence_ids)],
        )
        self.con.commit()

    def run_snapshot(self):
        return {
            "facts": self.con.execute("SELECT fact_id,evidence_status,evidence_id,normalized_json FROM facts ORDER BY fact_id").fetchall(),
            "evidence_count": self.con.execute("SELECT count(*) FROM evidence").fetchone()[0],
            "issues": self.con.execute("SELECT issue_id,status,resolved_at FROM open_issues ORDER BY issue_id").fetchall(),
        }

    def assert_audited_confirmation_issue(self, issue_id, expected_owner):
        from db import rows_as_dict

        fields = (
            "total", "currency", "quantity", "scope_signature", "quote_date", "payment",
            "delivery", "validity", "vat", "incoterms", "warranty",
        )
        expected_facts = {f"o/field/{field}" for field in fields}
        expected_originals = {f"pix-{field}" for field in fields}
        self.assertEqual(len(expected_facts), 11)
        self.assertEqual(len(expected_originals), 11)

        issue = rows_as_dict(self.con, "SELECT * FROM open_issues WHERE issue_id=?", [issue_id])[0]
        self.assertEqual(issue["status"], "resolved")
        self.assertEqual(issue["owner"], expected_owner)
        bound_facts = json.loads(issue["fact_ids_json"] or "[]")
        bound_originals = json.loads(issue["evidence_ids_json"] or "[]")
        self.assertEqual(len(bound_facts), len(set(bound_facts)))
        self.assertEqual(len(bound_originals), len(set(bound_originals)))
        self.assertEqual(set(bound_facts), expected_facts)
        self.assertEqual(set(bound_originals), expected_originals)

        audit = json.loads(self.con.execute(
            "SELECT value FROM run_meta WHERE key='independent_confirmation_issue_resolutions'"
        ).fetchone()[0])[issue_id]
        self.assertEqual(audit.get("owner"), expected_owner)
        self.assertEqual(set(audit["fact_ids"]), expected_facts)
        self.assertEqual(set(audit["original_evidence_ids"]), expected_originals)
        self.assertEqual(len(audit["fact_ids"]), 11)
        self.assertEqual(len(audit["original_evidence_ids"]), 11)
        self.assertEqual(len(audit["confirmation_ids"]), 11)
        self.assertEqual(len(set(audit["confirmation_ids"])), 11)
        self.assertEqual(len(audit["proofs"]), 11)
        self.assertEqual({p["fact_id"] for p in audit["proofs"]}, expected_facts)
        self.assertEqual(len({p["fact_id"] for p in audit["proofs"]}), 11)
        self.assertEqual({p["confirmation_id"] for p in audit["proofs"]}, set(audit["confirmation_ids"]))
        self.assertEqual(len({p["confirmation_id"] for p in audit["proofs"]}), 11)

        source_doc = rows_as_dict(self.con, "SELECT * FROM documents WHERE document_id='sheet'")[0]
        target_doc = rows_as_dict(self.con, "SELECT * FROM documents WHERE document_id='image'")[0]
        source_hash = sha256_file(Path(source_doc["source_path"]))
        target_hash = sha256_file(Path(target_doc["source_path"]))
        self.assertEqual(source_doc["sha256"], source_hash)
        self.assertEqual(target_doc["sha256"], target_hash)
        self.assertEqual(source_doc["offer_id"], "o")
        self.assertEqual(target_doc["offer_id"], "o")

        proof_fact_ids = []
        proof_confirmation_ids = []
        for item in audit["proofs"]:
            fact_id = item["fact_id"]
            fact = rows_as_dict(self.con, "SELECT * FROM facts WHERE fact_id=?", [fact_id])[0]
            proof = rows_as_dict(self.con, "SELECT * FROM fact_confirmations WHERE confirmation_id=?", [item["confirmation_id"]])[0]
            original = rows_as_dict(self.con, "SELECT * FROM evidence WHERE evidence_id=?", [proof["original_evidence_id"]])[0]
            confirmation = rows_as_dict(self.con, "SELECT * FROM evidence WHERE evidence_id=?", [proof["confirmation_evidence_id"]])[0]
            source_unit = rows_as_dict(self.con, "SELECT * FROM document_units WHERE unit_id=?", [confirmation["unit_id"]])[0]
            relation = rows_as_dict(self.con, "SELECT * FROM source_relations WHERE relation_id=?", [proof["relation_id"]])[0]
            pointer = json.loads(fact["normalized_json"] or "{}")["independent_confirmation"]
            expected_original_id = f"pix-{fact['field_key']}"
            expected_value = {key: fact.get(key) for key in ("value_text", "value_number", "value_date", "unit", "currency")}

            self.assertEqual(fact["offer_id"], "o")
            self.assertEqual(fact["extraction_path"], "vision")
            self.assertEqual(fact["evidence_status"], "verified")
            self.assertEqual(fact["evidence_id"], proof["confirmation_evidence_id"])
            self.assertEqual(pointer["confirmation_id"], proof["confirmation_id"])
            self.assertEqual(pointer["original_evidence_id"], expected_original_id)
            self.assertEqual(pointer["confirmation_evidence_id"], proof["confirmation_evidence_id"])
            self.assertEqual(pointer["relation_id"], proof["relation_id"])

            self.assertEqual(proof["fact_id"], fact_id)
            self.assertEqual(proof["original_evidence_id"], expected_original_id)
            self.assertEqual(proof["value_json"], json_text(expected_value))
            self.assertEqual(json.loads(proof["value_json"]), item["value"])
            self.assertEqual(item["confirmation_id"], proof["confirmation_id"])
            self.assertEqual(item["relation_id"], proof["relation_id"])
            self.assertEqual(item["original_sha256"], target_hash)
            self.assertEqual(item["confirmation_sha256"], source_hash)
            self.assertEqual(item["value"], expected_value)

            self.assertEqual(original["evidence_id"], expected_original_id)
            self.assertEqual(original["document_id"], "image")
            self.assertEqual(original["source_sha256"], target_hash)
            self.assertEqual(confirmation["document_id"], "sheet")
            self.assertEqual(source_unit["document_id"], "sheet")
            self.assertEqual(source_unit["unit_type"], "sheet")
            self.assertEqual(confirmation["source_sha256"], source_hash)
            self.assertEqual(confirmation["evidence_status"], "verified")
            self.assertEqual(confirmation["extraction_path"], "independent_structured_confirmation")

            self.assertEqual(relation["relation_type"], "corroborates")
            self.assertEqual(relation["source_document_id"], "sheet")
            self.assertEqual(relation["target_document_id"], "image")
            self.assertEqual(relation["source_sha256"], source_hash)
            self.assertEqual(relation["target_sha256"], target_hash)
            proof_fact_ids.append(fact_id)
            proof_confirmation_ids.append(proof["confirmation_id"])

        self.assertEqual(set(proof_fact_ids), expected_facts)
        self.assertEqual(len(set(proof_fact_ids)), 11)
        self.assertEqual(set(proof_confirmation_ids), set(audit["confirmation_ids"]))
        self.assertEqual(len(set(proof_confirmation_ids)), 11)
        return audit

    def test_actual_advance_budget_exhausted_keeps_boundary_and_sources_with_paired_report(self):
        self.confirmation_sources()
        before = self.run_snapshot()
        pending = [{"phase": "EXTRACT", "task_kind": "semantic_extraction", "task_id": "fixture-task", "attempts": 0}]
        boundary_result = []
        original_boundary = workflow._needs_llm_response

        def capture_boundary(*args, **kwargs):
            actual = original_boundary(*args, **kwargs)
            boundary_result.append(actual)
            return actual

        out = io.StringIO()
        with (
            patch("run_compatibility.assert_compatible"),
            patch.object(workflow, "_completed_verified_result", return_value=None),
            patch.object(workflow, "extract_fields"),
            patch.object(workflow, "normalize"),
            patch.object(workflow, "refresh_source_authority"),
            patch("evidence_confirmation.confirm"),
            patch.object(workflow, "_refresh_deterministic_controls"),
            patch.object(workflow, "generate_initial_tasks"),
            patch.object(workflow, "_pending_by_phase", return_value=pending),
            patch.object(workflow, "_token_budget", return_value={"hard_stop": True}),
            patch.object(workflow, "_task_contexts", return_value=[]),
            patch.object(workflow, "_needs_llm_response", side_effect=capture_boundary),
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(out),
        ):
            result = workflow.advance(self.run)
        for key, value in boundary_result[0].items():
            self.assertEqual(result[key], value)
        self.assertEqual(result["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(result["report_delivery_status"], "READY")
        self.assertTrue(result["deliverable_artifacts"])
        for kind in ("xlsx", "pdf"):
            self.assertTrue(Path(result["preliminary_report"][kind]).is_file())
        self.assertNotEqual(result["decision_assurance"], "VERIFIED")
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(self.run_snapshot(), before)
        self.assertEqual([event["status"] for event in self.events()], ["BUDGET_EXHAUSTED"])

    def test_normal_partial_workflow_result_is_not_logged(self):
        self.confirmation_sources()
        pending = [{"phase": "EXTRACT", "task_kind": "semantic_extraction", "task_id": "fixture-task", "attempts": 0}]
        with (
            patch("run_compatibility.assert_compatible"),
            patch.object(workflow, "_completed_verified_result", return_value=None),
            patch.object(workflow, "extract_fields"),
            patch.object(workflow, "normalize"),
            patch.object(workflow, "refresh_source_authority"),
            patch("evidence_confirmation.confirm"),
            patch.object(workflow, "_refresh_deterministic_controls"),
            patch.object(workflow, "generate_initial_tasks"),
            patch.object(workflow, "_pending_by_phase", return_value=pending),
            patch.object(workflow, "_token_budget", return_value={"hard_stop": False}),
            patch.object(workflow, "_task_contexts", return_value=[{"task_id": "fixture-task"}]),
        ):
            result = workflow.advance(self.run)
        self.assertEqual(result["status"], "NEEDS_LLM")
        self.assertEqual(self.events(), [])

    def test_all_eleven_fields_confirm_and_pure_linked_rfi_closes_with_audited_proofs(self):
        self.eleven_field_sources()
        self.confirmation_issue()
        result = confirm(self.run)
        self.assertEqual(len(result["confirmed"]), 11)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "resolved")
        audit = self.assert_audited_confirmation_issue("rfi", "IDARE")
        vat = self.con.execute("SELECT value_text,evidence_status FROM facts WHERE fact_id='o/field/vat'").fetchone()
        self.assertEqual(vat, ("excluded", "verified"))
        self.assertEqual(confirm(self.run)["confirmed"], [])

    def test_included_vat_alias_confirms_independently(self):
        self.eleven_field_sources(vat_fact="included", vat_source="dahil")
        result = confirm(self.run)
        self.assertIn("o/field/vat", result["confirmed"])

    def test_rate_bearing_vat_text_candidates_keep_stated_basis_in_turkish_and_english(self):
        from field_extract import _text_candidates
        from normalize import vat_basis

        def source_unit(text):
            return {
                "unit_id": "fixture-page",
                "document_id": "image",
                "unit_type": "page",
                "unit_index": 1,
                "locator_json": json_text({"page": 1}),
                "text_content": text,
                "structured_json": "{}",
                "content_sha256": "fixture-content-hash",
            }

        cases = (
            ("KDV %20 dahil", "included"),
            ("KDV %20 hariç", "excluded"),
            ("VAT 20% included", "included"),
            ("VAT 20% excluded", "excluded"),
        )
        self.assertEqual(vat_basis("VAT not included"), "excluded")
        self.assertEqual(vat_basis("KDV dahil değil"), "excluded")
        for line, expected in cases:
            with self.subTest(line=line):
                candidates = _text_candidates(source_unit(line))["vat"]
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0]["value_text"], expected)

    def test_rate_bearing_sheet_cell_confirms_all_fields_and_audits_excluded_vat(self):
        self.eleven_field_sources(vat_fact="excluded", vat_source="KDV %20 hariç")
        self.confirmation_issue()
        result = confirm(self.run)
        self.assertEqual(len(result["confirmed"]), 11)
        self.assert_audited_confirmation_issue("rfi", "IDARE")

    def test_negated_or_conflicting_rate_vat_stays_unknown_in_text_and_sheet_confirmation(self):
        from field_extract import _text_candidates

        def source_unit(text):
            return {
                "unit_id": "fixture-page",
                "document_id": "image",
                "unit_type": "page",
                "unit_index": 1,
                "locator_json": json_text({"page": 1}),
                "text_content": text,
                "structured_json": "{}",
                "content_sha256": "fixture-content-hash",
            }

        unknown_lines = ("KDV %20 hariç değil", "KDV %20 dahil ve %20 hariç")
        for line in unknown_lines:
            with self.subTest(line=line):
                candidates = _text_candidates(source_unit(line))["vat"]
                self.assertEqual(len(candidates), 1)
                self.assertNotIn(candidates[0]["value_text"], {"included", "excluded"})

        self.eleven_field_sources(vat_fact="excluded", vat_source=unknown_lines[0])
        self.confirmation_issue()
        result = confirm(self.run)
        self.assertNotIn("o/field/vat", result["confirmed"])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/vat'").fetchone()[0], "requires_confirmation")
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")

        unit = json.loads(self.con.execute("SELECT structured_json FROM document_units WHERE unit_id='u'").fetchone()[0])
        next(cell for cell in unit["cells"] if cell["cell"] == "B9")["formula_or_value"] = unknown_lines[1]
        self.con.execute("UPDATE document_units SET structured_json=? WHERE unit_id='u'", [json_text(unit)])
        self.con.commit()
        result = confirm(self.run)
        self.assertNotIn("o/field/vat", result["confirmed"])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/vat'").fetchone()[0], "requires_confirmation")
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")

    def test_negated_unknown_or_conflicting_vat_source_stays_unresolved(self):
        self.eleven_field_sources(vat_fact="excluded", vat_source="hariç değil")
        result = confirm(self.run)
        self.assertNotIn("o/field/vat", result["confirmed"])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/vat'").fetchone()[0], "requires_confirmation")

    def test_unknown_vat_source_stays_unresolved(self):
        self.eleven_field_sources(vat_fact="excluded", vat_source="sonradan bildirilecek")
        result = confirm(self.run)
        self.assertNotIn("o/field/vat", result["confirmed"])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/vat'").fetchone()[0], "requires_confirmation")

    def test_conflicting_vat_candidates_stay_unresolved(self):
        self.eleven_field_sources(vat_fact="excluded", vat_source="hariç", vat_extra="dahil")
        result = confirm(self.run)
        self.assertNotIn("o/field/vat", result["confirmed"])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/vat'").fetchone()[0], "requires_confirmation")

    def test_equivalent_known_vat_aliases_are_not_a_false_conflict(self):
        self.eleven_field_sources(vat_fact="excluded", vat_source="hariç", vat_extra="excluded")
        result = confirm(self.run)
        self.assertIn("o/field/vat", result["confirmed"])

    def test_correct_supplier_owner_closes_pure_confirmation_issue(self):
        self.eleven_field_sources(vat_fact="hariç", vat_source="hariç")
        supplier_name = self.con.execute("SELECT display_name FROM suppliers WHERE supplier_id='s'").fetchone()[0]
        supplier_id = self.con.execute("SELECT supplier_id FROM suppliers WHERE display_name=?", [supplier_name]).fetchone()[0]
        self.confirmation_issue(owner=f"FIRMA:{supplier_id}")
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "resolved")
        self.assert_audited_confirmation_issue("rfi", f"FIRMA:{supplier_id}")

    def test_all_suppliers_owner_closes_pure_confirmation_issue(self):
        self.eleven_field_sources(vat_fact="hariç", vat_source="hariç")
        self.confirmation_issue(owner="TUM_FIRMALAR")
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "resolved")
        self.assert_audited_confirmation_issue("rfi", "TUM_FIRMALAR")

    def test_wrong_firma_invalid_owner_and_business_approval_stay_open(self):
        self.eleven_field_sources(vat_fact="hariç", vat_source="hariç")
        self.confirmation_issue("FIRMA:wrong-supplier")
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")
        self.con.execute("UPDATE open_issues SET owner='NOT_A_VALID_OWNER' WHERE issue_id='rfi'")
        self.con.commit()
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")
        self.con.execute("UPDATE open_issues SET owner='FIRMA:s',issue_type='commercial_approval' WHERE issue_id='rfi'")
        self.con.commit()
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")

    def test_confirmed_rfi_spanning_two_active_offers_stays_open_for_every_owner(self):
        from db import rows_as_dict
        from evidence_confirmation import _resolve_confirmation_issues

        self.eleven_field_sources(vat_fact="hariç", vat_source="hariç")
        self.assertEqual(len(confirm(self.run)["confirmed"]), 11)

        self.con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES ('s2','Supplier Two','confirmed')")
        self.con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('o2','s2','active','[]')")
        self.con.execute("UPDATE facts SET offer_id='o2',supplier_id='s2' WHERE fact_id='o/field/warranty'")
        self.con.commit()

        confirmed_now = {}
        for fact in rows_as_dict(self.con, "SELECT * FROM facts WHERE fact_id LIKE 'o/field/%'"):
            pointer = json.loads(fact["normalized_json"])["independent_confirmation"]
            proof = rows_as_dict(self.con, "SELECT * FROM fact_confirmations WHERE confirmation_id=?", [pointer["confirmation_id"]])[0]
            confirmed_now[(proof["relation_id"], fact["fact_id"])] = {
                "original_sha256": proof["original_sha256"],
                "confirmation_sha256": proof["confirmation_sha256"],
                "target_document_id": "image",
                "source_document_id": "sheet",
            }

        owners = ("IDARE", "TUM_FIRMALAR", "FIRMA:s", "FIRMA:s2")
        for index, owner in enumerate(owners):
            issue_id = f"cross-offer-rfi-{index}"
            self.confirmation_issue(owner=owner, issue_id=issue_id)
            closed = _resolve_confirmation_issues(self.con, confirmed_now)
            self.assertNotIn(issue_id, closed)
            self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id=?", [issue_id]).fetchone()[0], "open")

    def test_extra_issue_evidence_keeps_pure_rfi_open(self):
        self.eleven_field_sources()
        self.confirmation_issue(extra=True)
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")

    def test_missing_issue_evidence_keeps_pure_rfi_open(self):
        self.eleven_field_sources()
        self.confirmation_issue()
        self.con.execute("UPDATE open_issues SET evidence_ids_json='[]' WHERE issue_id='rfi'")
        self.con.commit()
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")

    def test_stale_source_hash_keeps_pure_rfi_open(self):
        self.eleven_field_sources()
        confirm(self.run)
        self.confirmation_issue()
        self.con.execute("UPDATE documents SET sha256='stale' WHERE document_id='sheet'")
        self.con.commit()
        with self.assertRaisesRegex(ValueError, "hash changed"):
            confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0], "open")


def load_tests(loader, tests, pattern):
    own = [name for name, value in LoggingAndElevenFieldConfirmation.__dict__.items()
           if name.startswith("test_") and callable(value)]
    return unittest.TestSuite(LoggingAndElevenFieldConfirmation(name) for name in sorted(own))


if __name__ == "__main__":
    unittest.main()
