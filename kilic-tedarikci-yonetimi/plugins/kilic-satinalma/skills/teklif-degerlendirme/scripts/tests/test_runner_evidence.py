"""A killed/empty/stale child can never turn an exit-zero process into PASS."""
import json
from pathlib import Path
import tempfile
import unittest
from run_tests import validate_child_report


class RunnerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "report.json"
        self.report = {"run_id":"fresh", "requested_engine":"sqlite", "status":"PASS",
                       "executed":2, "passed":2, "discovered":2, "source_unchanged_during_run":True,
                       "failed":0,"errors":0,"skipped":0,"expected_failures":0,"unexpected_successes":0,
                       "observed_connections":{"sqlite:sqlite3.Connection":3}}

    def tearDown(self):
        self.tmp.cleanup()

    def save(self):
        self.path.write_text(json.dumps(self.report), encoding="utf-8")

    def test_zero_exit_without_report_is_not_pass(self):
        self.assertEqual(validate_child_report(self.path, "sqlite", "fresh", 0), 1)

    def test_old_pass_report_cannot_be_reused(self):
        self.save()
        self.assertEqual(validate_child_report(self.path, "sqlite", "new_run", 0), 1)

    def test_wrong_motor_or_incomplete_result_cannot_pass(self):
        for key, value in (("observed_connections", {"duckdb:_duckdb.DuckDBPyConnection":1}),
                           ("source_unchanged_during_run", False), ("executed", 0), ("passed", 1),
                           ("status", "NOT_RUN_TERMINATED")):
            with self.subTest(key=key):
                original = self.report[key]
                self.report[key] = value
                self.save()
                self.assertEqual(validate_child_report(self.path, "sqlite", "fresh", 0), 1)
                self.report[key] = original

    def test_only_fresh_complete_evidence_and_successful_exit_pass(self):
        self.save()
        self.assertEqual(validate_child_report(self.path, "sqlite", "fresh", 0), 0)
        self.assertEqual(validate_child_report(self.path, "sqlite", "fresh", 1), 1)

    def test_pass_label_with_contradictory_or_untyped_counts_is_rejected(self):
        original=dict(self.report)
        for key in ('failed','errors','skipped','expected_failures','unexpected_successes'):
            for value in (1,-1,None,False,'0'):
                with self.subTest(key=key,value=value):
                    self.report={**original,key:value};self.save()
                    self.assertEqual(validate_child_report(self.path,'sqlite','fresh',0),1)
        for key,value in (('discovered',True),('executed',2.0),('passed','2'),('observed_connections',{'sqlite:sqlite3.Connection':True})):
            self.report={**original,key:value};self.save()
            self.assertEqual(validate_child_report(self.path,'sqlite','fresh',0),1)
