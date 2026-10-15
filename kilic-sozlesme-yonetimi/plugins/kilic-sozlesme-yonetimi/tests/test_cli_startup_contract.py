import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

import test_context as fixtures

ROOT=Path(__file__).resolve().parents[1]


class CLIStartupContractTests(unittest.TestCase):
    def test_actual_missing_site_dependencies_return_one_json_before_workspace_creation(self):
        with tempfile.TemporaryDirectory(prefix='cs-missing-dep-') as area:
            workspace=Path(area)/'must-not-exist'
            run=subprocess.run([sys.executable,'-S',str(ROOT/'scripts/contract_cli.py'),'--workspace',str(workspace),
                                '--output-root',area,'--source-root',area,'case-create','--title','synthetic'],
                               capture_output=True,text=True,encoding='utf-8',timeout=30)
            value=json.loads(run.stdout)
            self.assertEqual(2,run.returncode,run.stderr);self.assertEqual('CONFIG_REQUIRED',value['error_code'])
            self.assertEqual('NOT_RUN',value['business_status']);self.assertFalse(workspace.exists())

    def test_actual_invalid_arguments_return_one_structured_block(self):
        run=subprocess.run([sys.executable,str(ROOT/'scripts/contract_cli.py'),'--invalid-argument'],
                           capture_output=True,text=True,encoding='utf-8',timeout=30)
        value=json.loads(run.stdout)
        self.assertEqual(2,run.returncode);self.assertEqual('CLI_ARGUMENT_ERROR',value['error_code'])
        self.assertEqual('NOT_GRANTED',value['business_acceptance'])


class CLIBusinessStatusTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def test_exit_zero_does_not_promote_missing_info_or_closed_word_to_business_acceptance(self):
        for output in ('CHAT','DOCX'):
            request={'request_id':str(uuid4()),'case_id':self.case,'skill_id':'K03','intent':'Synthetic startup check',
                     'context_version':self.rev(),'selected_versions':[],'root_ids':[],
                     'max_context_bytes':65536,'policy_version':'1','requested_output':output}
            path=self.sources/'request.json';path.write_text(json.dumps(request),encoding='utf-8')
            run=subprocess.run([sys.executable,str(ROOT/'scripts/contract_cli.py'),'--workspace',str(self.store.root),
                                '--output-root',str(self.store.output_root),'--source-root',str(self.sources),'skill-evaluate','--request',str(path)],
                               env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,encoding='utf-8',timeout=30)
            value=json.loads(run.stdout);self.assertEqual(0,run.returncode,run.stderr)
            self.assertEqual('SUCCEEDED',value['technical_status'])
            self.assertEqual('BILGI_GEREKLI' if output=='CHAT' else 'TEKNIK_ENGEL',value['business_status'])
            self.assertEqual('NOT_GRANTED',value['business_acceptance'])
            self.assertEqual([],value['result']['output_ids'])
