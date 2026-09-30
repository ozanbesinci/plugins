"""Startup gate behavior; synthetic sessions, no model calls or installations."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from oturum_kontrol import check_session


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root/'main.jsonl'
        self.path.write_text(json.dumps({'type':'session_meta','payload':{'id':'main','cwd':str(self.root)}})+'\n',encoding='utf-8')

    def context(self, model='gpt-6.1-sol', effort='high'):
        with self.path.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps({'type':'turn_context','payload':{'model':model,'effort':effort}})+'\n')

    def test_ready_requires_real_model_and_high_without_usage_counter(self):
        self.context()
        result=check_session(self.path,'main')
        self.assertEqual(result['status'],'READY')
        self.assertEqual(result['observed'],result['required'])

    def test_wrong_model_or_effort_blocks(self):
        for model,effort in [('gpt-6-sol','high'),('gpt-6.1-sol','medium'),('gpt-6.1-sol','xhigh'),('gpt-6-sol','medium')]:
            with self.subTest(model=model,effort=effort):
                self.context(model,effort)
                self.assertEqual(check_session(self.path,'main')['status'],'WAITING_FOR_SELECTION')

    def test_repeated_checks_keep_warning_and_do_not_write_files(self):
        self.context(effort='medium')
        before=self.path.read_bytes()
        first=check_session(self.path,'main'); second=check_session(self.path,'main')
        self.assertEqual(first['status'],'WAITING_FOR_SELECTION')
        self.assertEqual(first,second)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual(list(self.root.iterdir()),[self.path])

    def test_latest_correction_allows_continuation(self):
        self.context('gpt-6-sol','medium')
        self.assertEqual(check_session(self.path,'main')['status'],'WAITING_FOR_SELECTION')
        self.context()
        self.assertEqual(check_session(self.path,'main')['status'],'READY')

    def test_model_only_correction_still_waits_for_high(self):
        self.context('gpt-6-sol','medium'); self.context(effort='medium')
        self.assertEqual(check_session(self.path,'main')['status'],'WAITING_FOR_SELECTION')
        self.context()
        self.assertEqual(check_session(self.path,'main')['status'],'READY')

    def test_other_session_cannot_pass(self):
        self.context()
        self.assertEqual(check_session(self.path,'other')['status'],'UNVERIFIED')

    def test_missing_session_log_cannot_pass(self):
        self.assertEqual(check_session(self.root/'missing.jsonl','main')['status'],'UNVERIFIED')

    def test_unavailable_effort_cannot_pass(self):
        self.context(effort=None)
        self.assertEqual(check_session(self.path,'main')['status'],'UNVERIFIED')

    def test_cli_runs_without_site_packages(self):
        self.context()
        completed=subprocess.run([sys.executable,'-S',str(Path(__file__).with_name('oturum_kontrol.py')),
                                  '--main-log',str(self.path),'--session-id','main'],capture_output=True,encoding='utf-8')
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(json.loads(completed.stdout)['status'],'READY')

    def test_cli_returns_waiting_status_until_corrected(self):
        self.context(effort='medium')
        command=[sys.executable,'-S',str(Path(__file__).with_name('oturum_kontrol.py')),
                 '--main-log',str(self.path),'--session-id','main']
        for _ in range(2):
            completed=subprocess.run(command,capture_output=True,encoding='utf-8')
            self.assertEqual(completed.returncode,2)
            self.assertEqual(json.loads(completed.stdout)['status'],'WAITING_FOR_SELECTION')
        self.context()
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,0)


if __name__=='__main__':
    unittest.main()
