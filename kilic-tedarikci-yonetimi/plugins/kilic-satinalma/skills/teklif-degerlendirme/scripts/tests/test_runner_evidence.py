"""A killed/empty/stale child can never turn an exit-zero process into PASS."""
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from run_tests import validate_child_report, source_fingerprint


class RunnerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "report.json"
        self.report = {"run_id":"fresh", "requested_engine":"sqlite", "status":"PASS",
                       "executed":2, "passed":2, "discovered":2, "source_unchanged_during_run":True,
                       "failed":0,"errors":0,"skipped":0,"expected_failures":0,"unexpected_successes":0,
                       "observed_connections":{"sqlite:sqlite3.Connection":3}}
        self.report['source_files'] = {'scripts/run_tests.py': hashlib.sha256(b'fixture source').hexdigest()}
        self.report['source_sha256'] = hashlib.sha256(json.dumps(self.report['source_files'], sort_keys=True).encode()).hexdigest()

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

    def test_output_ancestor_named_test_results_does_not_hide_runtime_source(self):
        root = Path(self.tmp.name) / 'test-results' / 'source-freeze' / 'plugin'
        (root / 'scripts').mkdir(parents=True)
        (root / 'scripts/run_tests.py').write_bytes(b'actual runtime')
        (root / '__pycache__').mkdir()
        (root / '__pycache__/generated.py').write_bytes(b'cache')
        (root / 'test-results').mkdir()
        (root / 'test-results/generated.json').write_bytes(b'result')
        with patch('run_tests.SOURCE_ROOT', root):
            result = source_fingerprint()
        self.assertEqual(result, {str(Path('scripts/run_tests.py')): hashlib.sha256(b'actual runtime').hexdigest()})

    def test_empty_or_invalid_source_map_cannot_support_pass(self):
        original = dict(self.report)
        invalid = ({}, None, [], {'scripts/run_tests.py': True}, {'scripts/run_tests.py': 'bad'},
                   {'../foreign.py': 'a' * 64}, {'/foreign.py': 'a' * 64})
        for source in invalid:
            with self.subTest(source=source):
                self.report = {**original, 'source_files': source,
                               'source_sha256': hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()}
                self.save()
                self.assertEqual(validate_child_report(self.path, 'sqlite', 'fresh', 0), 1)

    def test_source_hash_must_match_the_recorded_file_map(self):
        self.report['source_sha256'] = '0' * 64
        self.save()
        self.assertEqual(validate_child_report(self.path, 'sqlite', 'fresh', 0), 1)

    def test_parent_frozen_map_rejects_different_valid_child_source(self):
        self.save()
        same = dict(self.report['source_files'])
        other = {'scripts/run_tests.py': hashlib.sha256(b'other source').hexdigest()}
        self.assertEqual(validate_child_report(self.path, 'sqlite', 'fresh', 0, expected_source=same), 0)
        self.assertEqual(validate_child_report(self.path, 'sqlite', 'fresh', 0, expected_source=other), 1)
