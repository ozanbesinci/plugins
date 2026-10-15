import copy
import json
import subprocess
import sys
import unittest
from uuid import uuid4

import test_business as fixtures
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.safety import hash_file


class PortfolioTests(unittest.TestCase):
    """Explicit-case K27 measurement; synthetic cases only, never company-wide."""
    setUp = fixtures.BusinessTests.setUp; rev = fixtures.BusinessTests.rev; document = fixtures.BusinessTests.document
    fact_spec = fixtures.BusinessTests.fact_spec; fact = fixtures.BusinessTests.fact; error = fixtures.BusinessTests.error
    obligation_spec = fixtures.BusinessTests.obligation_spec; obligation = fixtures.BusinessTests.obligation

    def add_case(self, title):
        """Build another case in the same store with its own source and statement."""
        self.case = self.store.create_case(title)
        self.versions = []
        self.node, self.path = self.document(fixtures.CONTRACT)
        statement = self.store.add_statement(self.case, fixtures.POSITION, expected_revision=self.rev())
        self.statement = self.store.register_context_node(self.case, spec={"node_kind": "USER_STATEMENT", "title": "Pozisyon", "record_id": statement}, expected_revision=self.rev())["node_id"]
        self.texts[self.statement] = fixtures.POSITION
        return self.case

    def entry(self, case=None, versions=None):
        return {"case_id": case or self.case, "expected_revision": self.store.case_revision(case or self.case),
                "selected_versions": list(versions if versions is not None else self.versions)}

    def request(self, entries):
        return {"request_id": str(uuid4()), "purpose": "Sentetik portföy ortak risk ölçümü", "as_of": "2026-11-02",
                "scope_keys": ["main"], "policy_version": "1", "cases": entries}

    def two_cases(self):
        first, first_versions, first_path = self.case, list(self.versions), self.path
        self.fact()
        self.fact("36", node=self.statement, plane="USER_POSITION")
        due = self.fact("2026-10-31", field="due_date", method="DATE_ISO", unit=None, unit_literal=None)
        self.obligation(date_fact=due)
        self.obligation()
        first_entry = self.entry()
        second = self.add_case("Sentetik ikinci dosya")
        self.fact()
        second_entry = self.entry()
        return (first, first_versions, first_path, first_entry), (second, list(self.versions), self.path, second_entry)

    def metric(self, result, key):
        row = next(row for row in result["metrics"] if row["id"] == key)
        return row["numerator"], row["denominator"]

    def test_listed_cases_are_measured_separately_with_numerator_and_denominator(self):
        (first, _, first_path, a), (second, _, _, b) = self.two_cases()
        before = hash_file(first_path)
        result = self.store.portfolio_overview(self.request([a, b]))
        self.assertEqual("COMPLETE_LISTED_SCOPE", result["status"])
        self.assertEqual({"method": "EXPLICIT_CASE_LIST_ONLY", "requested_cases": 2, "included_cases": 2,
                          "excluded_cases": 0, "company_wide": False, "sampling_inference": "NOT_RUN"}, result["coverage"])
        self.assertEqual((1, 2), self.metric(result, "cases_with_value_mismatch"))
        self.assertEqual((1, 2), self.metric(result, "obligations_past_due_candidate"))
        self.assertEqual((1, 2), self.metric(result, "obligations_unresolved_due"))
        self.assertEqual((2, 2), self.metric(result, "obligations_unknown_party"))
        rows = {row["case_id"]: row for row in result["cases"]}
        self.assertEqual(1, rows[first]["measures"]["value_mismatches"])
        self.assertEqual(0, rows[second]["measures"]["obligations"])
        kinds = {item["kind"] for item in rows[first]["attention"]}
        self.assertEqual({"PAST_DUE_CANDIDATE", "UNRESOLVED_DUE", "VALUE_MISMATCH"}, kinds)
        self.assertEqual([], rows[second]["attention"])
        self.assertFalse(result["cross_case_source_mixing"])
        self.assertEqual("NOT_RUN", result["interpretation"])
        self.assertEqual("NOT_GRANTED", result["business_acceptance"])
        self.assertEqual(before, hash_file(first_path))

    def test_inaccessible_case_is_excluded_with_reason_and_never_counted(self):
        (first, _, first_path, a), (second, _, _, b) = self.two_cases()
        first_path.unlink()
        result = self.store.portfolio_overview(self.request([a, b]))
        self.assertEqual("PARTIAL_LISTED_SCOPE", result["status"])
        rows = {row["case_id"]: row for row in result["cases"]}
        self.assertEqual(("EXCLUDED", "ERISIM_YOK", None), (rows[first]["status"], rows[first]["error_code"], rows[first]["measures"]))
        self.assertEqual(1, result["coverage"]["included_cases"])
        self.assertEqual((0, 1), self.metric(result, "cases_with_value_mismatch"))
        self.assertEqual((0, 0), self.metric(result, "obligations_past_due_candidate"))

    def test_changed_revision_or_foreign_version_excludes_only_that_case(self):
        (first, first_versions, _, a), (second, second_versions, _, b) = self.two_cases()
        self.store.add_statement(second, "Yeni beyan", expected_revision=self.store.case_revision(second))
        foreign = dict(a, selected_versions=second_versions)
        result = self.store.portfolio_overview(self.request([foreign, b]))
        rows = {row["case_id"]: row for row in result["cases"]}
        self.assertEqual("KAYNAK_KAPSAMI", rows[first]["error_code"])
        self.assertEqual("SURUM_CAKISMASI", rows[second]["error_code"])
        self.assertEqual("NO_INCLUDED_CASE", result["status"])
        self.assertTrue(all(row["denominator"] == 0 for row in result["metrics"]))

    def test_unknown_case_is_excluded_not_invented(self):
        result = self.store.portfolio_overview(self.request([self.entry(), {"case_id": str(uuid4()), "expected_revision": 0,
                                                                            "selected_versions": self.versions}]))
        self.assertEqual("PARTIAL_LISTED_SCOPE", result["status"])
        self.assertEqual("KAYNAK_YOK", result["cases"][1]["error_code"])

    def test_duplicate_case_bad_date_extra_or_authority_fields_are_rejected(self):
        request = self.request([self.entry(), dict(self.entry(), expected_revision=self.rev() + 1)])
        self.error("GECERSIZ_GIRDI", lambda: self.store.portfolio_overview(request))
        request = self.request([self.entry()]); request["as_of"] = "2026-02-30"
        self.error("TARIH_KURALI", lambda: self.store.portfolio_overview(request))
        for key, value in [("sql", "SELECT * FROM dosyalar"), ("approved", True), ("company_wide", True)]:
            request = self.request([self.entry()]); request[key] = value
            self.error("SEMA_HATASI", lambda: self.store.portfolio_overview(request))
        request = self.request([]); self.error("SEMA_HATASI", lambda: self.store.portfolio_overview(request))
        request = self.request([dict(self.entry(), selected_versions=[])])
        self.error("SEMA_HATASI", lambda: self.store.portfolio_overview(request))

    def test_attention_is_bounded_and_truncation_is_reported(self):
        for number in range(20):  # Identical specs are deduplicated by the Store.
            spec = dict(self.obligation_spec(), description=f"Teslim adayı {number}")
            self.store.register_obligation(self.case, spec=spec, expected_revision=self.rev())
        row = self.store.portfolio_overview(self.request([self.entry()]))["cases"][0]
        self.assertEqual(16, len(row["attention"]))
        self.assertEqual(4, row["attention_truncated"])
        self.assertEqual(20, row["measures"]["obligations_unresolved_due"])

    def test_real_cli_is_read_only_and_confines_request_path(self):
        self.fact()
        before = self.rev()
        path = self.sources / "portföy İı.json"
        path.write_text(json.dumps(self.request([self.entry()])), encoding="utf-8")
        args = [sys.executable, "-X", "utf8", "-m", "sozlesme_cekirdek", "--workspace", str(self.store.root),
                "--output-root", str(self.area), "--source-root", str(self.sources), "portfolio-overview", "--request", str(path)]
        run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        envelope = json.loads(run.stdout)
        self.assertEqual("READ_ONLY", envelope["retry_safety"])
        self.assertEqual("COMPLETE_LISTED_SCOPE", envelope["result"]["status"])
        self.assertEqual(before, self.rev())
        outside = self.area / "outside.json"; outside.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        args[-1] = str(outside)
        self.assertNotEqual(0, subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=60).returncode)


if __name__ == "__main__":
    unittest.main()
