"""Real subprocess faults; explicit fixtures do not constitute native Excel QA."""
import json
from pathlib import Path
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch
from common import sha256_file
from db import init_db
from office_execution import execute_office,_stop_owned_excel

FIXTURE='''import argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser()
for k in ('operation','input','output','result','receipt','attempt'):p.add_argument('--'+k)
a=p.parse_args()
MODE
'''

class OfficeDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        init_db(self.root/'run')
        self.input=self.root/'input.xlsx';self.input.write_bytes(b'original isolated test bytes')
        self.worker=self.root/'fixture.py'
    def tearDown(self):self.tmp.cleanup()
    def execute(self,code,seconds=3):
        self.worker.write_text(FIXTURE.replace('MODE',code),encoding='utf-8')
        with patch('office_execution.platform.system',return_value='Windows'):
            return execute_office('recalculate',self.input,timeout_seconds=seconds,_worker=self.worker)
    def test_hung_worker_only_changes_disposable_copy(self):
        original=sha256_file(self.input);start=time.monotonic()
        result=self.execute("Path(a.input).write_bytes(b'unfinished worker copy');time.sleep(30)",0.4)
        self.assertFalse(result['available']);self.assertEqual(result['reason'],'native_office_timeout')
        self.assertEqual(sha256_file(self.input),original);self.assertLess(time.monotonic()-start,8)
        self.assertEqual(result['owned_process_cleanup'],'NOT_PROVEN_NO_RECEIPT')
        # No Office application was created by this fixture. Its killed Python
        # subprocess cannot continue writing to the explicitly recorded temp copy.
        work=Path(result['isolated_copy']).resolve()
        self.assertEqual(work.parent,Path(tempfile.gettempdir()).resolve());self.assertTrue(work.name.startswith('kilic-office-'))
        shutil.rmtree(work)
    def test_wrong_attempt_cannot_replace_original(self):
        original=sha256_file(self.input)
        result=self.execute("Path(a.input).write_bytes(b'candidate');Path(a.result).write_text(json.dumps({'available':True,'attempt':'wrong','operation':a.operation}))")
        self.assertEqual(result['reason'],'native_office_result_identity_mismatch');self.assertEqual(sha256_file(self.input),original)
    def test_failed_worker_cannot_publish_even_with_success_json(self):
        original=sha256_file(self.input)
        result=self.execute("Path(a.result).write_text(json.dumps({'available':True,'attempt':a.attempt,'operation':a.operation}));raise SystemExit(2)")
        self.assertEqual(result['worker_exit_code'],2);self.assertFalse(result['available']);self.assertEqual(sha256_file(self.input),original)
    def test_successful_worker_atomically_replaces_only_requested_file(self):
        result=self.execute("Path(a.input).write_bytes(b'completed explicit unit fixture');Path(a.result).write_text(json.dumps({'available':True,'attempt':a.attempt,'operation':a.operation,'scope':'UNIT_FIXTURE_NOT_EXCEL'}))")
        self.assertTrue(result['available']);self.assertEqual(self.input.read_bytes(),b'completed explicit unit fixture')
        self.assertEqual(result['scope'],'UNIT_FIXTURE_NOT_EXCEL')
    def test_preexisting_process_receipt_is_never_terminated(self):
        receipt=self.root/'owner.json'
        receipt.write_text(json.dumps({'attempt':'ours','pid':1,'identity':{'created_100ns':116444736000000000,'image':'EXCEL.EXE'}}),encoding='utf-8')
        self.assertEqual(_stop_owned_excel(receipt,'ours',time.time_ns()),'NOT_PROVEN_PREEXISTING_PROCESS')
    def test_invalid_deadline_rejects_before_spawning(self):
        for seconds in (0,-1,121,True,float('nan')):
            with self.assertRaises(ValueError):execute_office('recalculate',self.input,timeout_seconds=seconds)
