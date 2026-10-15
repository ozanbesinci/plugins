"""Actual unittest process exit leaves unfinished/never-started methods NOT_RUN."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


class TestReceiptInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cs-test-crash-');self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name);self.report=self.area/'result.json'
        spec=importlib.util.spec_from_file_location('interruption_runner',ROOT/'scripts/run_product_tests.py')
        self.runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.runner)
    def test_native_unittest_exit_marks_started_and_never_started_methods_not_run(self):
        names=['__main__.Probe.test_1_pass','__main__.Probe.test_2_crash','__main__.Probe.test_3_never']
        self.report.with_suffix('.inventory.json').write_text(json.dumps({'tests':names}),encoding='utf-8')
        code='''import os,sys,unittest,importlib.util
from pathlib import Path
sys.path.insert(0,sys.argv[3])
from process_fixtures import abrupt_exit
spec=importlib.util.spec_from_file_location('probe_runner',sys.argv[1]);runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
runner.RecordedResult.event_path=Path(sys.argv[2])
class Probe(unittest.TestCase):
 def test_1_pass(self):self.assertEqual(2,1+1)
 def test_2_crash(self):abrupt_exit(37)
 def test_3_never(self):raise AssertionError('must not execute')
unittest.TextTestRunner(resultclass=runner.RecordedResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(Probe))
'''
        process=subprocess.run([sys.executable,'-B','-c',code,str(ROOT/'scripts/run_product_tests.py'),str(self.report.with_suffix('.events.jsonl')),str(ROOT/'tests')],capture_output=True,timeout=30)
        self.assertEqual(37,process.returncode)
        result=self.runner.interrupted_report(self.report,'CHILD_TERMINAL_RECEIPT_MISSING')
        self.assertEqual(['PASS','NOT_RUN','NOT_RUN'],[r['status'] for r in result['records']])
        self.assertEqual(2,result['methods_started']);self.assertEqual(1,result['methods_completed'])
        self.assertEqual('ERROR',result['status']);self.assertEqual('BLOCKED',result['release_acceptance'])
    def test_partial_event_tail_and_missing_inventory_never_become_pass(self):
        events=self.report.with_suffix('.events.jsonl')
        events.write_bytes(b'{"test_id":"a","status":"PASS"}\n{"test_id":')
        result=self.runner.interrupted_report(self.report,'MISSING')
        self.assertTrue(result['event_log_corrupt_or_partial']);self.assertFalse(result['discovery_complete'])
        self.assertEqual('ERROR',result['status']);self.assertEqual('NOT_GRANTED',result['full_product_acceptance'])

    def test_missing_git_is_not_fabricated_as_a_clean_commit(self):
        with patch.object(self.runner.shutil, 'which', return_value=None):
            result = self.runner.source_git_context(self.area)
        self.assertEqual('NOT_RUN', result['source_git_status'])
        self.assertEqual('GIT_UNAVAILABLE', result['source_git_reason'])
        self.assertIsNone(result['source_commit']); self.assertIsNone(result['dirty_source'])
        self.assertEqual('UNVERIFIED', result['source_commit_attestation'])

    def test_invalid_ancestor_git_marker_never_attests_package(self):
        (self.area / '.git').mkdir()
        package = self.area / 'package'; package.mkdir()
        (package / 'plugin.json').write_text('{}', encoding='utf-8')
        result = self.runner.source_git_context(package)
        self.assertIn(result['source_git_status'], ('ERROR', 'NOT_RUN'))
        self.assertIsNone(result['source_commit']); self.assertIsNone(result['dirty_source'])
        self.assertEqual('UNVERIFIED', result['source_commit_attestation'])

    def test_native_portable_runner_finishes_receipt_without_git_attestation(self):
        selected = 'test_reader_budget.ReaderBudgetTests.test_native_echo_preserves_bytes'
        area = self.area / 'portable-evidence'
        process = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ROOT / 'scripts/run_product_tests.py'),
                                  '--suite', 'budget', '--test', selected, '--output-root', str(area),
                                  '--label', 'portable-git', '--timeout-seconds', '60'],
                                 capture_output=True, encoding='utf-8', errors='replace', timeout=90)
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        paths = list(area.glob('portable-git-*/result.json')); self.assertEqual(1, len(paths))
        result = json.loads(paths[0].read_text(encoding='utf-8'))
        self.assertEqual('FINAL', result['receipt_phase']); self.assertEqual('PASS', result['status'])
        self.assertEqual(1, result['methods_run']); self.assertTrue(result['original_source_unchanged'])
        # The Windows user profile can itself contain an unrelated/corrupt .git.
        # A failed Git lookup is ERROR; an absent owning checkout is NOT_RUN.
        self.assertIn(result['source_git_status'], ('NOT_RUN', 'ERROR'))
        self.assertIsNone(result['source_commit'])
        self.assertIsNone(result['dirty_source']); self.assertEqual('UNVERIFIED', result['source_commit_attestation'])
        self.assertEqual('BLOCKED', result['release_acceptance'])
