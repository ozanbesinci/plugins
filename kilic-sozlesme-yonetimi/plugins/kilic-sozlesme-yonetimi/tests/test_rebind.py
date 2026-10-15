import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_context as fixtures
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.safety import hash_file

NEW_POLICY = "2"  # A different policy yields a different reader profile for the same bytes.


class RebindTests(unittest.TestCase):
    """Exact-text move of stale source nodes; synthetic sources only."""
    setUp = fixtures.ContextTests.setUp; rev = fixtures.ContextTests.rev; error = fixtures.ContextTests.error
    document = fixtures.ContextTests.document; spec = fixtures.ContextTests.spec; node = fixtures.ContextTests.node
    register = fixtures.ContextTests.register; link = fixtures.ContextTests.link; four = fixtures.ContextTests.four

    def pack(self, roots, policy=NEW_POLICY):
        return self.store.context_pack(self.case, request={"root_ids": roots, "purpose": "Taşınan bağlamı incele",
            "max_context_bytes": 1048576, "policy_version": policy, "include_related": False})["result"]

    def rebind(self, **kwargs):
        return self.store.rebind_context(self.case, expected_revision=self.rev(), policy_version=NEW_POLICY, **kwargs)

    def test_stale_graph_moves_with_exact_text_and_complete_closure(self):
        clause, definition, exception, annex = self.four()
        before = hash_file(self.path)
        self.assertEqual("NEEDS_REVIEW", self.pack([clause])["status"])
        result = self.rebind()
        mapping = {row["old_node_id"]: row["new_node_id"] for row in result["mapping"]}
        self.assertEqual({clause, definition, exception, annex}, set(mapping))
        self.assertTrue(set(mapping.values()).isdisjoint(mapping))
        self.assertEqual((3, 0, 0), (result["relations"]["created"], result["relations"]["superseded"], result["relations"]["reused"]))
        current = self.pack([mapping[clause]])
        self.assertEqual("COMPLETE_REGISTERED_SCOPE", current["status"])
        self.assertEqual(sorted(mapping.values()), current["included"])
        old = {row["node_id"]: row for row in self.pack([clause], policy="1")["context"]["entries"]}
        new = {row["node_id"]: row for row in current["context"]["entries"]}
        for source, target in mapping.items():
            self.assertEqual(old[source]["content"]["excerpt"], new[target]["content"]["excerpt"])
        self.assertEqual("NEEDS_REVIEW", self.pack([clause])["status"])  # History is kept, not repaired in place.
        self.assertEqual(before, hash_file(self.path))
        self.assertEqual(result["final_revision"], self.rev())

    def test_missing_annex_reference_is_carried_not_resolved(self):
        clause = self.node()
        self.link(clause, relation="ANNEX", unresolved_reference="Ek 7 bulunamadı")
        result = self.rebind()
        new = result["mapping"][0]["new_node_id"]
        report = self.pack([new])
        self.assertEqual("INCOMPLETE_DEPENDENCIES", report["status"])
        self.assertEqual("Ek 7 bulunamadı", report["missing_dependencies"][0]["reference"])

    def test_rerun_reuses_every_record_without_revision_change(self):
        self.four()
        first = self.rebind()
        revision = self.rev()
        second = self.rebind()
        self.assertEqual([row["new_node_id"] for row in first["mapping"]], [row["new_node_id"] for row in second["mapping"]])
        self.assertTrue(all(row["reused"] for row in second["mapping"]))
        self.assertEqual(0, second["relations"]["created"]); self.assertEqual(revision, self.rev())

    def test_incoming_edge_from_current_statement_is_superseded_to_new_target(self):
        clause = self.node()
        statement = self.store.add_statement(self.case, "Bu madde teslimle ilgili", expected_revision=self.rev())
        source = self.register({"node_kind": "USER_STATEMENT", "title": "Beyan", "record_id": statement})
        self.link(source, clause, "EVIDENCE")
        result = self.rebind()
        self.assertEqual(1, result["relations"]["superseded"])
        report = self.pack([source])
        self.assertEqual("COMPLETE_REGISTERED_SCOPE", report["status"])
        self.assertIn(result["mapping"][0]["new_node_id"], report["included"])

    def test_changed_source_text_or_missing_unit_is_reported_not_registered(self):
        clause, definition = self.node(), self.node("Teslim tarihi:", "DEFINITION")
        self.link(clause, definition)
        original = self.store.read_document
        def altered(case, version, **kwargs):
            reading = copy.deepcopy(original(case, version, **kwargs))
            units = reading["result"]["units"]
            for unit in units:
                if unit["views"]["RAW"].startswith("Teslim tarihi:"):
                    unit["views"]["RAW"] = unit["views"]["RAW"].replace("kabul", "sevk")
            reading["result"]["units"] = [unit for unit in units if not unit["views"]["RAW"].startswith("Ceza,")]
            return reading
        before = self.rev()
        with patch.object(self.store, "read_document", side_effect=altered):
            result = self.rebind()
        self.assertEqual([], result["mapping"])
        self.assertEqual({clause: "UNIT_NOT_IN_CURRENT_READING", definition: "TEXT_CHANGED_IN_CURRENT_READING"},
                         {row["node_id"]: row["reason"] for row in result["unmapped"]})
        self.assertEqual([], result["relations"]["unmapped"])  # The edge's start node never moved.
        self.assertEqual(before, self.rev())

    def test_changed_source_file_is_skipped_for_human_review(self):
        clause = self.node()
        self.path.write_bytes(fixtures.fixture_bytes("Teslim tarihi: sevk günüdür."))
        result = self.store.rebind_context(self.case, expected_revision=self.rev(), policy_version="1")
        self.assertEqual([], result["mapping"])
        self.assertEqual(clause, result["skipped"][0]["node_id"])
        self.assertIn("SOURCE_FILE_CHANGED", result["skipped"][0]["reasons"])

    def test_stale_revision_writes_nothing(self):
        self.four()
        revision = self.rev()
        self.error("SURUM_CAKISMASI", lambda: self.store.rebind_context(self.case, expected_revision=revision - 1, policy_version=NEW_POLICY))
        self.assertEqual(revision, self.rev())

    def test_real_cli_rebinds_and_reports_mapping(self):
        self.four()
        args = [sys.executable, "-X", "utf8", "-m", "sozlesme_cekirdek", "--workspace", str(self.store.root), "--output-root", str(self.area),
                "--source-root", str(self.sources), "context-rebind", "--case-id", self.case, "--expected-revision", str(self.rev()),
                "--policy-version", NEW_POLICY]
        run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        envelope = json.loads(run.stdout)
        self.assertEqual("NO_BLIND_RETRY", envelope["retry_safety"])
        self.assertEqual(4, len(envelope["result"]["mapping"]))


if __name__ == "__main__":
    unittest.main()
