import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import test_context as fixtures

ROOT=Path(__file__).resolve().parents[1]


class StatementCLITests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def cli(self, payload, *, revision=None, path=None):
        path=path or self.sources/'statement.json'
        path.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
        command=[sys.executable,'-m','sozlesme_cekirdek','--workspace',str(self.store.root),
                 '--output-root',str(self.store.output_root),'--source-root',str(self.sources),
                 'statement-register','--case-id',self.case,'--request',str(path),
                 '--expected-revision',str(self.rev() if revision is None else revision)]
        run=subprocess.run(command,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,encoding='utf-8',timeout=30)
        return run,json.loads(run.stdout)

    def test_real_cli_statement_preserves_user_text_refs_and_no_authority(self):
        before=self.rev();text='Kullanıcı beyanı: bilinmiyor; onay vermedim.'
        run,result=self.cli({'text':text,'session_ref':'synthetic-session','message_ref':'synthetic-message'})
        self.assertEqual(0,run.returncode,run.stderr)
        self.assertEqual('NOT_VERIFIED',result['result']['authority'])
        with self.store._db() as db:
            row=db.execute('SELECT excerpt,session_ref,message_ref,identity_status FROM beyanlar WHERE case_id=?',[self.case]).fetchone()
        self.assertEqual((text,'synthetic-session','synthetic-message','UNVERIFIED_LOCAL_STATEMENT'),row)
        self.assertEqual(before+1,self.rev())

    def test_unknown_authority_field_and_whitespace_are_rejected_without_write(self):
        before=self.rev()
        for value in [{'text':'beyan','authority':'APPROVED'},{'text':'   '}]:
            run,result=self.cli(value)
            self.assertEqual(2,run.returncode,run.stderr)
            self.assertEqual('BLOCKED',result['status'])
        self.assertEqual(before,self.rev())

    def test_stale_cas_and_outside_path_are_rejected_without_write(self):
        before=self.rev()
        run,result=self.cli({'text':'beyan'},revision=before+1)
        self.assertEqual(2,run.returncode);self.assertEqual('SURUM_CAKISMASI',result['error_code'])
        run,result=self.cli({'text':'beyan'},path=self.area/'outside.json')
        self.assertEqual(2,run.returncode)
        self.assertEqual(before,self.rev())

    def test_same_real_scoped_message_is_idempotent_without_revision_bump(self):
        payload={'text':'Bilinmiyor','session_ref':'session-1','message_ref':'message-1'}
        first,result1=self.cli(payload);revision=self.rev()
        second,result2=self.cli(payload)
        self.assertEqual(0,first.returncode);self.assertEqual(0,second.returncode)
        self.assertEqual(result1['result']['statement_id'],result2['result']['statement_id'])
        self.assertEqual(revision,self.rev())

    def test_same_reference_different_text_cannot_overwrite_statement(self):
        payload={'text':'Bilinmiyor','session_ref':'session-1','message_ref':'message-1'}
        first,_=self.cli(payload);revision=self.rev();payload['text']='Onaylandı'
        second,result=self.cli(payload)
        self.assertEqual(0,first.returncode);self.assertEqual(2,second.returncode)
        self.assertEqual('BEYAN_CAKISMASI',result['error_code']);self.assertEqual(revision,self.rev())
        with self.store._db() as db:
            self.assertEqual([('Bilinmiyor',)],db.execute('SELECT excerpt FROM beyanlar WHERE case_id=?',[self.case]).fetchall())
