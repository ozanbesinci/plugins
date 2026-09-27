"""Verification failure gates plus opt-in real Excel integration (--environment flag)."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from excel_uret import build, file_hash
from excel_dogrula import equal, verify
from test_excel_uret import fixture, scored_fixture, decision_fixture


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v4-verify-test-'); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'analysis.xlsx'; self.data = fixture()
        build(self.data, self.path, 'hizli')

    def test_empty_result_is_distinct_from_zero_and_bad_numeric_cache(self):
        self.assertTrue(equal('', None)); self.assertTrue(equal(None, None))
        self.assertFalse(equal(0, None)); self.assertFalse(equal('NOT_A_NUMBER', 1))
        self.assertFalse(equal(float('nan'), 1)); self.assertFalse(equal(True, 1))

    def test_missing_excel_returns_unverified_and_preserves_original(self):
        original = file_hash(self.path)
        with patch('excel_dogrula.subprocess.run', side_effect=OSError('Excel unavailable')):
            result = verify(self.path, self.data)
        self.assertEqual(result['status'], 'UNVERIFIED'); self.assertEqual(file_hash(self.path), original)
        self.assertFalse(result['checks']['recalculation'])

    def test_changed_data_fails_before_com(self):
        self.data['costs']['A']['events'][0]['amount'] = '999'
        with patch('excel_dogrula.subprocess.run', side_effect=AssertionError('COM must not start')):
            result = verify(self.path, self.data)
        self.assertEqual(result['status'], 'UNVERIFIED'); self.assertIn('eşleşmiyor', result['error'])

    def test_deadline_never_kills_user_excel_by_name(self):
        with patch('excel_dogrula.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', 1)), patch('excel_dogrula._stop_owned', return_value=False) as stop:
            result = verify(self.path, self.data, timeout=1)
        self.assertEqual(result['status'], 'UNVERIFIED'); stop.assert_called_once_with({})

    @unittest.skipUnless(os.environ.get('TEKLIF_TEST_EXCEL_COM') == '1', 'Real Excel is opt-in.')
    def test_real_excel_recalculation_restore_and_reuse(self):
        result = verify(self.path, self.data)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertTrue(all(result['checks'].values())); self.assertGreater(len(result['parameter_tests']), 4)
        with patch('excel_dogrula.subprocess.run', side_effect=AssertionError('Same artifact must not recalculate')):
            reused = verify(self.path, self.data)
        self.assertTrue(reused['reused'])

    @unittest.skipUnless(os.environ.get('TEKLIF_TEST_EXCEL_COM') == '1', 'Real Excel is opt-in.')
    def test_real_high_assurance_pdf_and_scoring(self):
        path = Path(self.temp.name) / 'high.xlsx'; data = scored_fixture(); decision = decision_fixture(data); build(data, path, 'yuksek_guvence', decision=decision)
        result = verify(path, data, decision=decision)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(file_hash(path.with_suffix('.pdf')), result['pdf_sha256'])
        self.assertIn('weight', {c['kind'] for c in result['parameter_tests']})


if __name__ == '__main__': unittest.main()
