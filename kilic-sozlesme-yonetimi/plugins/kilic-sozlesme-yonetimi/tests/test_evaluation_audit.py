import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch

from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.safety import hash_value
from sozlesme_cekirdek.workflows import evaluate
import test_context as fixtures

ROOT=Path(__file__).resolve().parents[1]


class EvaluationAuditTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def request(self):
        return {'request_id':str(uuid4()),'case_id':self.case,'skill_id':'K03','intent':'Audit synthetic',
                'context_version':self.rev(),'selected_versions':[],'root_ids':[],
                'max_context_bytes':65536,'policy_version':'1','requested_output':'CHAT'}

    def events(self):
        with self.store._db() as db:
            return [(name,json.loads(value)) for name,value in db.execute("SELECT event,details FROM islem_olaylari WHERE case_id=? AND event LIKE 'SKILL_EVALUATION_%' ORDER BY occurred_at",[self.case]).fetchall()]

    def test_success_correlates_start_terminal_build_and_result_without_semantic_bump(self):
        before=self.rev();request=self.request();operation=str(uuid4())
        result=evaluate(self.store,request,operation_id=operation)
        events=self.events();self.assertEqual(2,len(events))
        start=next(value for name,value in events if name=='SKILL_EVALUATION_STARTED')
        final=next(value for name,value in events if name=='SKILL_EVALUATION_TERMINAL')
        self.assertEqual(operation,start['operation_id']);self.assertEqual(operation,final['operation_id'])
        self.assertEqual(hash_value(request),final['request_digest'])
        self.assertEqual(hash_value(result),final['result_digest'])
        self.assertEqual(start['components'],final['components'])
        self.assertEqual('SUCCEEDED',final['technical_status'])
        self.assertEqual(result['status'],final['business_status'])
        self.assertEqual('NOT_GRANTED',final['business_acceptance'])
        self.assertNotIn('intent',start);self.assertEqual(before,self.rev())

    def test_context_conflict_has_real_blocked_terminal(self):
        request=self.request();request['context_version']+=1
        with self.assertRaises(CoreError) as error:evaluate(self.store,request)
        self.assertEqual('SURUM_CAKISMASI',error.exception.code)
        final=next(value for name,value in self.events() if name=='SKILL_EVALUATION_TERMINAL')
        self.assertEqual('BLOCKED',final['technical_status']);self.assertEqual('NOT_RUN',final['business_status'])
        self.assertEqual('SURUM_CAKISMASI',final['error_code'])

    def test_native_crash_leaves_start_only_without_completion(self):
        request=self.request()
        code='import json,os,sys\nsys.path.insert(0,sys.argv[5])\nfrom process_fixtures import abrupt_exit\nfrom sozlesme_cekirdek import Store\nimport sozlesme_cekirdek.workflows as w\ns=Store(sys.argv[1],source_roots=[sys.argv[2]],output_root=sys.argv[3])\nw._evaluate=lambda *args: abrupt_exit(91)\nw.evaluate(s,json.loads(sys.argv[4]))'
        run=subprocess.run([sys.executable,'-c',code,str(self.store.root),str(self.sources),str(self.store.output_root),json.dumps(request),str(ROOT/"tests")],env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,timeout=30)
        self.assertEqual(91,run.returncode,run.stderr)
        self.assertEqual(['SKILL_EVALUATION_STARTED'],[name for name,_ in self.events()])

    def test_invalid_schema_has_no_fabricated_evaluation(self):
        request=self.request();request['authority']='APPROVED'
        with self.assertRaises(CoreError):evaluate(self.store,request)
        self.assertEqual([],self.events())
