"""Technical conformance of every effective scenario definition (E01-E40).

Synthetic sources only. Each scenario is routed and run with sufficient,
missing-annex and written-versus-statement conflict variants. These tests check
mechanical must-not-do boundaries; domain quality and expected business output
remain expert/model evaluation (NOT_RUN), never accepted here.
"""
import unittest
from uuid import uuid4

import test_business as fixtures
import test_context
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.catalog import effective_test_scope
from sozlesme_cekirdek.safety import hash_file
from sozlesme_cekirdek.workflows import evaluate

SCENARIOS = [row["effective"] for row in effective_test_scope()["records"] if row["original_id"].startswith("E")]
NOT_READY = {"K19": "BILGI_GEREKLI", "K20": "BILGI_GEREKLI", "K21": "UZMAN_GORUSU_GEREKLI"}


class ScenarioConformanceTests(unittest.TestCase):
    setUp = fixtures.BusinessTests.setUp; rev = fixtures.BusinessTests.rev; document = fixtures.BusinessTests.document
    fact_spec = fixtures.BusinessTests.fact_spec; fact = fixtures.BusinessTests.fact
    obligation_spec = fixtures.BusinessTests.obligation_spec; obligation = fixtures.BusinessTests.obligation
    link = test_context.ContextTests.link

    def req(self, skill, roots=(), **extra):
        return dict({"request_id": str(uuid4()), "case_id": self.case, "skill_id": skill, "intent": "Sentetik senaryo uygunluğu",
                     "context_version": self.rev(), "selected_versions": list(self.versions), "root_ids": list(roots),
                     "max_context_bytes": 1048576, "policy_version": "1", "requested_output": "CHAT"}, **extra)

    def assert_closed_side_effects(self, result, skill):
        self.assertEqual(skill, result["skill_id"])
        self.assertNotEqual("TAMAMLANDI", result["status"])
        self.assertEqual([], result["output_ids"]); self.assertEqual([], result["updates"])
        self.assertEqual("DISABLED", result["action_execution"]); self.assertEqual("NOT_VERIFIED", result["authority"])
        self.assertFalse(result["critical_analysis_allowed"])
        self.assertTrue(result["chat_response"].startswith(result["startup_message"]))

    def check(self, scenario):
        skill = scenario["skill_ids"][0]
        before = hash_file(self.path)
        # Routing: the explicit scenario selects exactly its effective target skill.
        routed = evaluate(self.store, self.req("K00", scenario_id=scenario["scenario_id"]))
        self.assertEqual(scenario["skill_ids"], routed["selected_skills"])
        # Sufficient source: provenance-bound partial context, never completion or authority.
        result = evaluate(self.store, self.req(skill, [self.node]))
        self.assert_closed_side_effects(result, skill)
        self.assertEqual(NOT_READY.get(skill, "KISMI"), result["status"])
        if scenario["scenario_id"] == "S-20":  # Company-own policy scope remains an open business choice.
            pending = evaluate(self.store, self.req(skill, [self.node], scenario_id="S-20"))["open_questions"]
            self.assertTrue(any("kendi poliçe satınalması" in question for question in pending))
        finding = result["findings"][0]
        self.assertEqual((self.versions[0], before), (finding["provenance"]["version_id"], finding["provenance"]["source_sha256"]))
        # Missing annex: no findings, the concrete reference is asked, nothing assumed.
        annex, _ = self.document("Ek 3 teslim istisnalarını düzenler.")
        reference = scenario["id"] + " Ek 3 eki bulunamadı"
        self.link(annex, relation="ANNEX", unresolved_reference=reference)
        missing = evaluate(self.store, self.req(skill, [annex]))
        self.assert_closed_side_effects(missing, skill)
        self.assertEqual("UZMAN_GORUSU_GEREKLI" if skill == "K21" else "BILGI_GEREKLI", missing["status"])
        self.assertEqual([], missing["findings"]); self.assertIn("INCOMPLETE_DEPENDENCIES", missing["limitations"])
        self.assertTrue(any("“" + reference + "”" in question for question in missing["open_questions"]))
        # Conflict: written term and user position stay on separate planes; unknown party/date are not invented.
        self.fact(); self.fact("36", node=self.statement, plane="USER_POSITION"); self.obligation()
        conflict = evaluate(self.store, self.req(skill, [self.node], business_context={"as_of": "2026-11-02", "scope_keys": ["main"]}))
        self.assert_closed_side_effects(conflict, skill)
        overview = conflict["business_overview"]
        comparison = next(row for row in overview["comparisons"] if row["field"] == "warranty")
        self.assertEqual(("VALUE_MISMATCH", {"WRITTEN", "USER_POSITION"}), (comparison["status"], set(comparison["planes"])))
        self.assertFalse(comparison["contract_amended"]); self.assertFalse(comparison["authorized_decision"])
        obligation = overview["obligations"][0]
        self.assertEqual((None, None, "UNRESOLVED", False, False), (obligation["obligated_party"], obligation["due_date"],
                         obligation["date_position"], obligation["closed"], obligation["close_allowed"]))
        self.assertEqual("NOT_GRANTED", overview["business_approval"])
        # Delivery and sending stay closed without an explicit production gate.
        document = evaluate(self.store, self.req(skill, requested_output="DOCX"))
        self.assertEqual("TEKNIK_ENGEL", document["status"]); self.assertEqual([], document["output_ids"])
        with self.assertRaises(CoreError) as caught:
            evaluate(self.store, self.req(skill, requested_output="EMAIL_SEND"))
        self.assertEqual("EPOSTA_GONDERIM_KALDIRILDI", caught.exception.code)
        self.assertEqual(before, hash_file(self.path))
        self.assertEqual([], list(self.store.root.rglob("*.docx")))

    def test_unreadable_attachment_is_not_counted_as_read(self):
        path = self.sources / "bozuk ek İı.docx"
        path.write_bytes(b"PK\x03\x04 bozuk ek")
        document = self.store.create_document(self.case, "Bozuk ek", expected_revision=self.rev())
        version = self.store.ingest(self.case, document, path, expected_revision=self.rev())["version_id"]
        with self.assertRaises(CoreError):
            self.store.read_document(self.case, version, format="DOCX")
        row = next(row for row in self.store.context_source_map(self.case)["versions"] if row["version_id"] == version)
        self.assertEqual(("NOT_READ_FOR_CURRENT_PROFILE", []), (row["reading_status"], row["readings"]))
        self.link(self.node, relation="ANNEX", unresolved_reference="Ek 2 okunamadı")
        result = evaluate(self.store, self.req("K03", [self.node], selected_versions=self.versions + [version]))
        self.assertEqual(("BILGI_GEREKLI", []), (result["status"], result["findings"]))
        self.assertIn("“Ek 2 okunamadı”", result["open_questions"][0])


def scenario_test(scenario):
    def test(self):
        self.check(scenario)
    test.__doc__ = scenario["id"] + " " + scenario["scenario_id"] + " " + scenario["title"]
    return test


for row in SCENARIOS:
    setattr(ScenarioConformanceTests, "test_" + row["id"] + "_" + row["scenario_id"].replace("-", "") + "_" + row["skill_ids"][0],
            scenario_test(row))


if __name__ == "__main__":
    unittest.main()
