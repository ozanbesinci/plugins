"""Native schema upgrades and pinned audit-code compatibility. No destructive downgrade."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import duckdb
from sozlesme_cekirdek import Store,CoreError
import sozlesme_cekirdek.store as store_module
from sozlesme_cekirdek.safety import hash_file
from reader_fixtures import docx_bytes

ROOT=Path(__file__).resolve().parents[1]
MIGRATIONS=ROOT/'src/sozlesme_cekirdek/migrations'
VERSIONS=['1.0','p2-verifier-1.0','p3-context-1.0','p4-guard-1.0','p5-docx-1.0','p6-business-1.0']


class MigrationFixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cs-migration-');self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name);self.sources=self.area/'sources';self.sources.mkdir()
        self.workspace=self.area/'work';self.database=self.workspace/'.sistem/sozlesme.duckdb'
        self.case,self.statement=str(uuid4()),str(uuid4())
    def fixture(self,count=5):
        self.database.parent.mkdir(parents=True)
        now=datetime(2026,10,14,tzinfo=timezone.utc)
        with duckdb.connect(str(self.database),config={'enable_external_access':False,'threads':1}) as db:
            for index in range(1,count+1):
                script=(MIGRATIONS/f'{index:03}.sql').read_text(encoding='utf-8');db.execute(script)
                db.execute('INSERT INTO sema_gecmisi VALUES(?,?,?,?)',[index,VERSIONS[index-1],hashlib.sha256(script.encode()).hexdigest(),now])
            db.execute('INSERT INTO dosyalar VALUES(?,?,?,?,?)',[self.case,'Sentetik eski dosya',2,'ACTIVE',now])
            db.execute('INSERT INTO kayitlar VALUES(?,?,?,?,?)',[self.case,self.statement,'STATEMENT',now,None])
            db.execute('INSERT INTO beyanlar VALUES(?,?,?,?,?,?,?)',[self.case,self.statement,'Kaynak beyanı İı',now,'session-ref','message-ref','UNVERIFIED_LOCAL_STATEMENT'])
    def open(self):return Store(self.workspace,source_roots=[self.sources],output_root=self.area)
    def logical(self):
        with duckdb.connect(str(self.database),read_only=True) as db:
            db.execute("SET TimeZone='UTC'")
            tables=sorted(r[0] for r in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall())
            # Preserve native values without an optional Python timezone adapter.
            return {name:sorted(r[0] for r in db.execute('SELECT to_json(t) FROM "'+name+'" t').fetchall()) for name in tables}
    def error(self,code,fn):
        with self.assertRaises(CoreError) as caught:fn()
        self.assertEqual(code,caught.exception.code)


class MigrationAcceptanceTests(MigrationFixture):
    def test_001_through_005_upgrade_preserves_case_statement_and_adds_only_006(self):
        self.fixture();before=self.logical();store=self.open();after=self.logical()
        self.assertEqual(2,store.case_revision(self.case));self.assertEqual(23,len(after))
        for table,rows in before.items():
            if table!='sema_gecmisi':self.assertEqual(rows,after[table],table)
        with store._db() as db:
            self.assertEqual(list(range(1,7)),[r[0] for r in db.execute('SELECT migration_no FROM sema_gecmisi ORDER BY migration_no').fetchall()])
            self.assertEqual('Kaynak beyanı İı',db.execute('SELECT excerpt FROM beyanlar').fetchone()[0])
    def test_reopening_clean_006_is_idempotent_without_new_history_or_records(self):
        self.fixture(6);before=self.logical();self.open();self.open();self.assertEqual(before,self.logical())
    def test_history_digest_drift_is_rejected_without_deleting_or_rewriting_rows(self):
        self.fixture()
        with duckdb.connect(str(self.database)) as db:db.execute('UPDATE sema_gecmisi SET change_digest=? WHERE migration_no=2',['0'*64])
        before=self.logical();self.error('SEMA_DRIFT',self.open);self.assertEqual(before,self.logical())
    def test_unknown_future_007_is_rejected_without_automatic_downgrade(self):
        self.fixture(6)
        with duckdb.connect(str(self.database)) as db:db.execute('INSERT INTO sema_gecmisi VALUES(7,?,?,?)',['future-7','f'*64,datetime.now(timezone.utc)])
        before=self.logical();self.error('SEMA_DRIFT',self.open);self.assertEqual(before,self.logical())
    def test_failed_006_ddl_rolls_back_all_new_tables_and_can_be_retried_fresh(self):
        self.fixture();before=self.logical();broken=self.area/'broken-006.sql'
        broken.write_text((MIGRATIONS/'006.sql').read_text(encoding='utf-8')+'\nSELECT * FROM missing_fault_fixture_table;',encoding='utf-8')
        with patch.object(store_module,'MIGRATION_BUSINESS',broken),self.assertRaises(duckdb.Error):self.open()
        self.assertEqual(before,self.logical());self.open();self.assertEqual(23,len(self.logical()))


class LegacyCompatibilityTests(MigrationFixture):
    def setUp(self):
        super().setUp()
        reference=os.environ.get('CONTRACT_AUDIT_REFERENCE_RECEIPT')
        if not reference:raise RuntimeError('NOT_RUN: pinned audit code was not materialized')
        self.reference=json.loads(Path(reference).read_text(encoding='utf-8'));self.legacy=Path(self.reference['root'])
        self.assertEqual('f5f739d867a0de701ee4adf20854941a7d3c331c',self.reference['commit'])
        for name,digest in self.reference['files'].items():self.assertEqual(digest,hash_file(self.legacy/name),name)
    def old(self,action,case=None,version=None):
        code='''import json,sys
from uuid import uuid4
from pathlib import Path
import sozlesme_cekirdek
from sozlesme_cekirdek import Store,CoreError
root=Path(sys.argv[1]);assert Path(sozlesme_cekirdek.__file__).resolve().is_relative_to(root.resolve())
try:
 s=Store(sys.argv[2],source_roots=[sys.argv[3]],output_root=sys.argv[4])
 result={'revision':s.case_revision(sys.argv[6]),'module':sozlesme_cekirdek.__file__}
 if sys.argv[5]=='read':result['source_text']=s.read_version(sys.argv[6],sys.argv[7]).decode('utf-8')
 if sys.argv[5]=='evaluate':
  from sozlesme_cekirdek.workflows import evaluate,checked
  request={'request_id':str(uuid4()),'case_id':sys.argv[6],'skill_id':'K30','intent':'Sentetik uyum kontrolü',
           'context_version':s.case_revision(sys.argv[6]),'selected_versions':[sys.argv[7]],'root_ids':[],
           'max_context_bytes':65536,'policy_version':'1','requested_output':'CHAT'}
  checked('p6_skill_request',request)
  evaluate(s,request)
 print(json.dumps({'status':'OPENED','result':result}))
except CoreError as exc:print(json.dumps({'status':'BLOCKED','error':exc.code}))
'''
        run=subprocess.run([sys.executable,'-B','-c',code,str(self.legacy),str(self.workspace),str(self.sources),str(self.area),action,case or self.case,version or ''],
                           env=dict(os.environ,PYTHONPATH=str(self.legacy/'src')),capture_output=True,timeout=40)
        self.assertEqual(0,run.returncode,run.stderr.decode('utf-8',errors='replace'))
        return json.loads(run.stdout)
    def test_real_audit_code_opens_current_db_and_reads_source_without_data_loss(self):
        self.sources.joinpath('kaynak.txt').write_text('Sentetik kaynak İı',encoding='utf-8')
        store=self.open();case=store.create_case('Uyum');doc=store.create_document(case,'Kaynak',expected_revision=0)
        version=store.ingest(case,doc,self.sources/'kaynak.txt',expected_revision=store.case_revision(case))['version_id']
        before=self.logical();old=self.old('read',case,version)
        self.assertEqual('OPENED',old['status']);self.assertEqual('Sentetik kaynak İı',old['result']['source_text'])
        self.assertEqual(before,self.logical());self.assertEqual('Sentetik kaynak İı',(self.sources/'kaynak.txt').read_text(encoding='utf-8'))
    def test_real_audit_code_rejects_future_db_without_downgrade_or_data_loss(self):
        self.fixture(6)
        with duckdb.connect(str(self.database)) as db:db.execute('INSERT INTO sema_gecmisi VALUES(7,?,?,?)',['future-7','f'*64,datetime.now(timezone.utc)])
        before=self.logical();self.assertEqual({'status':'BLOCKED','error':'SEMA_DRIFT'},self.old('open'))
        self.assertEqual(before,self.logical())
    def test_audit_p6_bug_prevents_using_old_code_as_stable_business_rollback(self):
        self.fixture(6);store=self.open();source=self.sources/'Sentetik.docx';source.write_bytes(docx_bytes())
        document=store.create_document(self.case,'Kaynak',expected_revision=store.case_revision(self.case))
        version=store.ingest(self.case,document,source,expected_revision=store.case_revision(self.case))['version_id']
        before=self.logical();result=self.old('evaluate',self.case,version)
        self.assertEqual({'status':'BLOCKED','error':'SEMA_HATASI'},result)
        self.assertEqual(before,self.logical())

