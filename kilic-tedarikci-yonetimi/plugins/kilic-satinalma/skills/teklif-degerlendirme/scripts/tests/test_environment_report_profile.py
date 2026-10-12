import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from workflow import prepare
from report_model import build_preliminary


class EnvironmentReportProfileTests(unittest.TestCase):
    def check_profile(self, profile):
        with tempfile.TemporaryDirectory(prefix='teklif-profile-') as directory, patch.dict(os.environ):
            os.environ.pop('TEKLIF_TEST_SQLITE', None)
            source = Path(directory) / 'source'
            source.mkdir()
            run = Path(directory) / 'run'
            blocked = {'status': 'BLOCKED_ENVIRONMENT', 'missing_components': [],
                       'blocking_reasons': ['Synthetic missing dependency'], 'user_message': 'Test environment unavailable'}
            with patch('environment_check.check', return_value=blocked):
                result = prepare(source, run, profile)
            self.assertEqual(result['status'], 'BLOCKED_ENVIRONMENT')
            self.assertFalse(result['installation_performed'])
            self.assertFalse((run / 'analysis.duckdb').exists())
            self.assertFalse((run / 'analysis.test.sqlite').exists())
            self.assertFalse((run / 'inventory.json').exists())
            report = result['preliminary_report']
            self.assertEqual(report['delivery_status'], 'READY', report)
            self.assertEqual(report['profile'], profile)
            model = json.loads((Path(report['xlsx']).parent / 'report_model.json').read_text(encoding='utf-8'))
            self.assertEqual(model['profile'], profile)
            self.assertEqual(model['content_status'], 'SAFETY_NOTICE')
            self.assertEqual(model['decision_assurance'], 'BLOCKED_INTEGRITY')
            self.assertEqual(model['facts'], [])
            self.assertEqual(model['ranking'], [])
            self.assertEqual(json.loads((run / 'resume_request.json').read_text(encoding='utf-8'))['profile'], profile)

    def test_environment_failure_hizli_profile(self):
        self.check_profile('hizli')

    def test_environment_failure_standart_profile(self):
        self.check_profile('standart')

    def test_environment_failure_yuksek_guvence_profile(self):
        self.check_profile('yuksek_guvence')

    def check_invalid_request(self, content):
        with tempfile.TemporaryDirectory(prefix='teklif-invalid-profile-') as directory:
            run = Path(directory)
            (run / 'resume_request.json').write_text(content, encoding='utf-8')
            model = build_preliminary(run, 'Environment unavailable')
            self.assertEqual(model['profile'], 'UNKNOWN')
            self.assertEqual(model['content_status'], 'SAFETY_NOTICE')
            self.assertEqual(model['facts'], [])
            self.assertEqual(model['ranking'], [])
            self.assertFalse((run / 'analysis.duckdb').exists())

    def test_invalid_profile_is_not_claimed(self):
        self.check_invalid_request(json.dumps({'schema': 'teklif-resume/v1', 'profile': 'invented', 'run': 'other'}))

    def test_another_runs_profile_is_not_claimed(self):
        self.check_invalid_request(json.dumps({'schema': 'teklif-resume/v1', 'profile': 'hizli', 'run': 'other'}))

    def test_malformed_profile_record_does_not_prevent_safety_notice(self):
        self.check_invalid_request('{bad json')


if __name__ == '__main__':
    unittest.main()
