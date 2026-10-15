"""Release orchestration tests use synthetic receipts, not product acceptance."""
import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.digest = release.product_runner(release.PACKAGE).digest
        self.current = {"src/core.py": "abc"}
        self.found = {"sample.C.test_a": "sample.C", "sample.C.test_b": "sample.C", "sample.C.test_old": "sample.C"}
        self.manifest = {"classes": ["sample.C"], "excluded": {"sample.C.test_old": "historical fixture"}}
        self.receipt = {"schema": "contract-product-test-receipt/v1", "receipt_phase": "FINAL",
                        "status": "PASS", "exit_code": 0, "failures": 0, "errors": 0, "skipped": 0,
                        "source_before": self.current, "source_after": self.current,
                        "source_unchanged": True, "original_source_unchanged": True,
                        "source_digest": self.digest(self.current), "manifest_digest": self.digest(self.manifest),
                        "classes": ["sample.C"], "classes_not_run": {}, "methods_run": 2,
                        "suite": "full", "test_selection": [], "unselected_not_run": [],
                        "platform": "Windows-test", "python": "3.14.8", "python_abi": "cpython-314",
                        "dependencies": {"duckdb": "1.5.6"},
                        "records": [{"test_id": "sample.C.test_a", "status": "PASS"},
                                    {"test_id": "sample.C.test_b", "status": "PASS"},
                                    {"test_id": "sample.C.test_old", "status": "NOT_RUN"}]}

    def verify(self, receipts):
        return release.verify_receipts(receipts, self.current, self.manifest, self.found, self.digest)

    def test_unchanged_final_evidence_reuses_without_new_run_or_release_approval(self):
        result = self.verify([self.receipt])
        self.assertEqual("PASS", result["status"])
        self.assertFalse(result["new_product_test_run"])
        self.assertEqual("NOT_GRANTED", result["release_acceptance"])

    def test_child_only_or_failed_or_timed_out_cannot_pass(self):
        for key, value in [("receipt_phase", "CHILD_TERMINAL_ONLY"), ("status", "NOT_RUN"),
                           ("exit_code", 124), ("errors", 1), ("skipped", 1), ("original_source_unchanged", False)]:
            with self.subTest(key=key):
                changed = dict(self.receipt, **{key: value})
                self.assertEqual("BLOCKED", self.verify([changed])["status"])

    def test_source_or_manifest_drift_invalidates_old_pass(self):
        for key in ("source_before", "source_after", "source_digest", "manifest_digest"):
            with self.subTest(key=key):
                changed = dict(self.receipt, **{key: "changed"})
                self.assertEqual("BLOCKED", self.verify([changed])["status"])

    def test_no_receipts_or_missing_test_does_not_pass(self):
        self.assertEqual("BLOCKED", self.verify([])["status"])
        changed = copy.deepcopy(self.receipt)
        changed["records"].pop(0)
        changed["methods_run"] = 1
        self.assertEqual(["sample.C.test_a"], self.verify([changed])["missing_tests"])

    def test_disjoint_partials_cover_complete_scope(self):
        shards = []
        for record in self.receipt["records"][:2]:
            name = record["test_id"]
            shards.append(dict(self.receipt, methods_run=1, records=[record], test_selection=[name],
                               unselected_not_run=sorted(set(self.found) - {name})))
        self.assertEqual("PASS", self.verify(shards)["status"])
        self.assertEqual("BLOCKED", self.verify(shards[:1])["status"])

    def test_duplicate_tests_across_or_within_receipts_do_not_inflate_coverage(self):
        self.assertEqual("BLOCKED", self.verify([self.receipt, self.receipt])["status"])
        changed = copy.deepcopy(self.receipt)
        changed["records"].append(changed["records"][0])
        changed["methods_run"] += 1
        self.assertEqual("BLOCKED", self.verify([changed])["status"])

    def test_unknown_or_failed_record_and_fake_count_block(self):
        for key, value in [("test_id", "other.C.test_a"), ("status", "FAIL")]:
            changed = copy.deepcopy(self.receipt)
            changed["records"][0][key] = value
            self.assertEqual("BLOCKED", self.verify([changed])["status"])
        self.assertEqual("BLOCKED", self.verify([dict(self.receipt, methods_run=1000)])["status"])

    def test_historical_exclusion_is_never_promoted_to_pass(self):
        changed = copy.deepcopy(self.receipt)
        changed["records"][-1]["status"] = "PASS"
        self.assertEqual("BLOCKED", self.verify([changed])["status"])

    def test_partition_keeps_each_class_together_covers_each_effective_test_once(self):
        found = {f"sample.C{i}.test_{j}": f"sample.C{i}" for i in range(7) for j in range(i + 1)}
        excluded = {"sample.C0.test_0"}
        groups = release.partition(found, excluded, 4)
        names = [name for group in groups for name in group]
        self.assertEqual(set(found) - excluded, set(names))
        self.assertEqual(len(names), len(set(names)))
        for cls in set(found.values()) - {"sample.C0"}:
            self.assertEqual(1, sum(any(found[name] == cls for name in group) for group in groups))

    def test_observation_requires_exact_hash_and_values_and_scope(self):
        with tempfile.TemporaryDirectory() as area:
            base = Path(area)
            path = base / "host.json"
            path.write_text(json.dumps({"source_digest": "current", "result": {"request": "one", "ready": True}}), encoding="utf-8")
            row = {"id": "host", "title": "Host", "scope": "K01 only", "source_digest": "current",
                   "artifacts": [{"path": "host.json", "sha256": release.sha(path),
                                  "checks": [{"pointer": "/result/request", "equals": "one"},
                                             {"pointer": "/source_digest", "equals": "current"}]}]}
            self.assertEqual("RECORDED", release.observation(row, base, "current")["status"])
            self.assertEqual("STALE_SOURCE", release.observation(row, base, "new")["status"])
            row["artifacts"][0]["checks"][0]["equals"] = "other"
            self.assertEqual("INVALID_EVIDENCE", release.observation(row, base, "current")["status"])
            row["artifacts"][0]["sha256"] = "wrong"
            self.assertEqual("INVALID_EVIDENCE", release.observation(row, base, "current")["status"])
            path.unlink()
            self.assertEqual("INVALID_EVIDENCE", release.observation(row, base, "current")["status"])

    def test_empty_observation_cannot_pass(self):
        row = {"id": "expert", "title": "Expert", "scope": "none", "source_digest": "current", "artifacts": []}
        self.assertEqual("INVALID_EVIDENCE", release.observation(row, Path.cwd(), "current")["status"])

    def test_old_artifact_cannot_be_relabelled_as_a_new_candidate(self):
        with tempfile.TemporaryDirectory() as area:
            base = Path(area)
            path = base / "host.json"
            path.write_text('{"source_digest": "old"}', encoding="utf-8")
            row = {"id": "host", "title": "Host", "scope": "K01", "source_digest": "new",
                   "artifacts": [{"path": "host.json", "sha256": release.sha(path),
                                  "checks": [{"pointer": "/source_digest", "equals": "old"}]}]}
            result = release.observation(row, base, "new")
            self.assertEqual("INVALID_EVIDENCE", result["status"])
            self.assertIn("SOURCE_DIGEST_NOT_BOUND_TO_ARTIFACT", result["issues"])

    def test_pointer_handles_arrays_and_escaped_keys(self):
        self.assertEqual(2, release.pointer({"a/b": [{"~": 2}]}, "/a~1b/0/~0"))

    def test_inconsistent_classes_selection_or_unselected_list_cannot_pass(self):
        for key, value in [("classes", []), ("suite", "unknown"), ("test_selection", ["sample.C.test_a"]),
                           ("test_selection", ["sample.C.test_a", "sample.C.test_a"]),
                           ("unselected_not_run", ["sample.C.test_b"])]:
            with self.subTest(key=key, value=value):
                self.assertEqual("BLOCKED", self.verify([dict(self.receipt, **{key: value})])["status"])

    def test_shards_from_different_runtime_environments_are_not_merged(self):
        first = dict(self.receipt, methods_run=1, records=[self.receipt["records"][0]],
                     test_selection=["sample.C.test_a"], unselected_not_run=["sample.C.test_b", "sample.C.test_old"])
        second = dict(self.receipt, methods_run=1, records=[self.receipt["records"][1]],
                      test_selection=["sample.C.test_b"], unselected_not_run=["sample.C.test_a", "sample.C.test_old"])
        self.assertEqual("PASS", self.verify([first, second])["status"])
        for key, value in [("python", "3.15"), ("python_abi", "cpython-315"),
                           ("dependencies", {"duckdb": "different"}), ("platform", "Windows-other")]:
            with self.subTest(key=key):
                self.assertEqual("BLOCKED", self.verify([first, dict(second, **{key: value})])["status"])

    def test_missing_environment_or_boolean_counters_are_rejected(self):
        for key, value in [("python_abi", None), ("dependencies", {}), ("exit_code", False),
                           ("failures", False), ("methods_run", True)]:
            with self.subTest(key=key):
                self.assertEqual("BLOCKED", self.verify([dict(self.receipt, **{key: value})])["status"])

    def test_short_status_and_saved_reports_block_invalid_or_stale_observations(self):
        for state in ["INVALID_EVIDENCE", "STALE_SOURCE"]:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as area:
                report = {"source_digest": "synthetic", "technical": self.verify([self.receipt]),
                          "observations": [{"status": state, "title": "Host", "scope": "K01"}]}
                stream = io.StringIO()
                with contextlib.redirect_stdout(stream):
                    folder = release.save(Path(area), report)
                self.assertEqual("BLOCKED", json.loads(stream.getvalue())["status"])
                self.assertEqual("BLOCKED", release.read(folder / "result.json")["status"])
                self.assertIn("Kanıt bütünlüğü: **BLOCKED**", (folder / "DURUM.md").read_text(encoding="utf-8"))

    def test_missing_or_changed_evidence_blocks_overall_success(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "receipt.json"
            path.write_text('{"result": 1}', encoding="utf-8")
            _, ref = release.read_evidence(path)
            self.assertEqual([], release.changed_evidence([ref]))
            path.write_text('{"result": 2}', encoding="utf-8")
            issues = release.changed_evidence([ref])
            self.assertTrue(issues)
            self.assertEqual("BLOCKED", release.overall_status({"technical": {"status": "PASS"}, "evidence_issues": issues}))
            path.unlink()
            self.assertTrue(release.changed_evidence([ref]))

    def test_decoded_receipt_is_bound_to_the_bytes_that_were_hashed(self):
        with tempfile.TemporaryDirectory() as area:
            path = Path(area) / "receipt.json"
            path.write_text('{"result": 1}', encoding="utf-8")
            original_hash = release.sha(path)
            original_read = Path.read_bytes
            def read_then_replace(p):
                data = original_read(p)
                p.write_text('{"result": 2}', encoding="utf-8")
                return data
            with patch.object(Path, "read_bytes", read_then_replace):
                value, ref = release.read_evidence(path, original_hash)
            self.assertEqual(1, value["result"])
            self.assertEqual(original_hash, ref["sha256"])
            self.assertTrue(release.changed_evidence([ref]))
            with self.assertRaises(ValueError):
                release.read_evidence(path, original_hash)

    def test_complete_single_group_uses_short_native_full_command(self):
        names = ["sample.C.test_" + str(i) + "x" * 100 for i in range(514)]
        command = release.group_command(release.PACKAGE, names, Path("output"), 0, 120, set(names))
        self.assertNotIn("--test", command)
        self.assertIn("full", command)
        partial = release.group_command(release.PACKAGE, names[:1], Path("output"), 0, 120, set(names))
        self.assertIn("--test", partial)
        with self.assertRaisesRegex(ValueError, "Windows command limit"):
            release.group_command(release.PACKAGE, names, Path("output"), 0, 120)

    def test_private_evidence_is_refused_inside_project_or_git_checkout(self):
        checkout = release.owning_checkout()  # Project root itself when no Git metadata exists.
        report = {"source_digest": "synthetic", "technical": self.verify([self.receipt]), "observations": []}
        for inside in [release.PACKAGE / "x", release.PROJECT / "release" / "x", checkout / "evidence", checkout]:
            with self.subTest(path=inside):
                with self.assertRaisesRegex(ValueError, "outside the product and its Git repository"):
                    release.save(inside, report)
                with self.assertRaisesRegex(ValueError, "outside the product and its Git repository"):
                    release.run_groups(release.PACKAGE, [["a"]], inside, 1, 60, "synthetic")
                self.assertFalse(inside.exists() and inside != checkout)
        with tempfile.TemporaryDirectory() as area:
            self.assertEqual(Path(area).resolve(), release.outside_repository(area))

    def test_malformed_evidence_index_reports_blocked_json_not_traceback(self):
        import subprocess, sys
        with tempfile.TemporaryDirectory() as area:
            index = Path(area) / "index.json"
            index.write_text(json.dumps({"schema": "contract-release-evidence/v1"}), encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", "-X", "utf8", str(Path(release.__file__)), "status",
                                  "--evidence", str(index), "--output-root", str(Path(area) / "out")],
                                 capture_output=True, text=True, encoding="utf-8", timeout=300)
            self.assertEqual(1, run.returncode)
            self.assertNotIn("Traceback", run.stderr)
            self.assertEqual("BLOCKED", json.loads(run.stderr.strip().splitlines()[-1])["status"])

    def test_empty_or_duplicate_group_never_falls_back_to_running_everything(self):
        for names in [[], ["a", "a"]]:
            with self.assertRaises(ValueError):
                release.group_command(release.PACKAGE, names, Path("output"), 0, 120)


if __name__ == "__main__":
    unittest.main(verbosity=2)
