"""Actual Store/evaluate contract regression, independent expected business limits."""
import copy
import unittest

import test_context as fixtures
from test_workflows import WorkflowTests
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.workflows import evaluate, checked
from sozlesme_cekirdek.safety import hash_file


class P6ResultContractTests(unittest.TestCase):
    setUp = fixtures.ContextTests.setUp
    rev = fixtures.ContextTests.rev
    document = fixtures.ContextTests.document
    req = WorkflowTests.req

    def test_real_store_connection_is_native_duckdb(self):
        with self.store._db() as connection:
            self.assertEqual("_duckdb", type(connection).__module__)
            self.assertEqual("DuckDBPyConnection", type(connection).__name__)
            self.assertEqual("v1.5.6", connection.execute("SELECT version()").fetchone()[0])

    def test_missing_metadata_cannot_bypass_developer_contract(self):
        result = evaluate(self.store, self.req())
        for field in ["developer", "skill_name", "skill_version", "startup_message"]:
            with self.subTest(field=field):
                bad = copy.deepcopy(result)
                del bad[field]
                with self.assertRaises(CoreError) as caught:
                    checked("p6_skill_result", bad)
                self.assertEqual("SEMA_HATASI", caught.exception.code)

    def test_wrong_developer_unknown_field_and_old_result_version_rejected(self):
        result = evaluate(self.store, self.req())
        for change in [{"developer": "Ozan Beşinci"}, {"developer": "unknown"},
                       {"schema_version": "p6-1.1"}, {"approved": True}]:
            with self.subTest(change=change):
                with self.assertRaises(CoreError) as caught:
                    checked("p6_skill_result", dict(result, **change))
                self.assertEqual("SEMA_HATASI", caught.exception.code)

    def test_business_overview_has_separate_budget_and_no_authority(self):
        request = self.req()
        request["business_context"] = {"as_of": "2026-10-13", "scope_keys": ["delivery"]}
        result = evaluate(self.store, request)
        self.assertIsNotNone(result["business_budget"])
        self.assertIsNone(result["business_budget"]["host_tokens"])
        self.assertEqual("NOT_VERIFIED", result["authority"])
        self.assertFalse(result["critical_analysis_allowed"])

    def test_docx_technical_block_is_a_valid_result_without_outputs(self):
        request = self.req("K28")
        request["requested_output"] = "DOCX"
        result = evaluate(self.store, request)
        self.assertEqual("TEKNIK_ENGEL", result["status"])
        self.assertIn("CONFIG_REQUIRED", result["chat_response"])
        self.assertEqual([], result["output_ids"])
        self.assertEqual([], list(self.store.root.rglob("*.docx")))


def skill_test(skill):
    def test(self):
        before = hash_file(self.path)
        result = evaluate(self.store, self.req(skill))
        self.assertEqual(skill, result["skill_id"])
        self.assertEqual("Kılıç Satınalma Departmanı", result["developer"])
        self.assertEqual("p6-1.2", result["schema_version"])
        self.assertEqual("UZMAN_GORUSU_GEREKLI" if skill == "K21" else "BILGI_GEREKLI", result["status"])
        self.assertTrue(result["chat_response"].startswith(result["startup_message"]))
        self.assertEqual([], result["output_ids"])
        self.assertEqual([], result["updates"])
        self.assertEqual("DISABLED", result["action_execution"])
        self.assertEqual("NOT_VERIFIED", result["authority"])
        self.assertFalse(result["critical_analysis_allowed"])
        self.assertEqual(before, hash_file(self.path))
    return test


for number in range(30):
    name = f"K{number:02d}"
    setattr(P6ResultContractTests, "test_actual_evaluate_" + name, skill_test(name))


if __name__ == "__main__":
    unittest.main()
