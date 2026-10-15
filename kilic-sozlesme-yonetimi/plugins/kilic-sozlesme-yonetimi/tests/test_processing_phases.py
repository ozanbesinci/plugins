import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.__main__ import inventory
import test_context as fixtures

ROOT=Path(__file__).resolve().parents[1]


class ProcessingPhaseTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def process(self, extractor):
        return self.store.process(self.case,self.version,tool='phase-test',tool_version='1',settings={},
                                  validation_version='1',policy_version='1',extractor=extractor)

    def count(self):
        with self.store._db() as db:
            return db.execute("SELECT count(*) FROM isleme_calismalari WHERE case_id=? AND tool='phase-test'",[self.case]).fetchone()[0]

    def test_native_other_process_can_write_while_parser_runs_and_old_cas_is_rejected(self):
        before=self.rev();path=self.sources/'statement.json'
        path.write_text(json.dumps({'text':'Parser çalışırken gelen gerçek yeni beyan (sentetik)'}),encoding='utf-8')
        def extractor(data):
            command=[sys.executable,'-m','sozlesme_cekirdek','--workspace',str(self.store.root),'--output-root',str(self.store.output_root),
                     '--source-root',str(self.sources),'statement-register','--case-id',self.case,'--request',str(path),'--expected-revision',str(before)]
            run=subprocess.run(command,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(0,run.returncode,run.stdout+run.stderr)
            return inventory(data)
        with self.assertRaises(CoreError) as error:self.process(extractor)
        self.assertEqual('SURUM_CAKISMASI',error.exception.code)
        self.assertEqual(before+1,self.rev());self.assertEqual(0,self.count())

    def test_source_edit_during_parser_cannot_publish_stale_result(self):
        def extractor(data):
            self.path.write_bytes(b'changed-during-parser')
            return inventory(data)
        with self.assertRaises(CoreError) as error:self.process(extractor)
        self.assertEqual('KAYNAK_DEGISTI',error.exception.code);self.assertEqual(0,self.count())

    def test_parser_failure_has_no_partial_processing_record(self):
        def extractor(data):raise RuntimeError('synthetic parser failure')
        with self.assertRaises(RuntimeError):self.process(extractor)
        self.assertEqual(0,self.count())

    def test_two_native_parsers_share_one_cache_record_after_both_run_outside_lock(self):
        code='''import json,os,sys,time
from pathlib import Path
from sozlesme_cekirdek import Store
from sozlesme_cekirdek.__main__ import inventory
s=Store(sys.argv[1],source_roots=[sys.argv[2]],output_root=sys.argv[3],lock_timeout=60)
area=Path(sys.argv[3]);token=sys.argv[6]
def extract(data):
 (area/('parser-ready-'+token)).write_bytes(b'1')
 deadline=time.monotonic()+30
 while len(list(area.glob('parser-ready-*')))<2:
  if time.monotonic()>deadline:raise RuntimeError('parsers overlapped DB lock')
  time.sleep(.02)
 return inventory(data)
r=s.process(sys.argv[4],sys.argv[5],tool='phase-test',tool_version='1',settings={},validation_version='1',policy_version='1',extractor=extract)
print(json.dumps({'processing_id':r['processing_id'],'reused':r['reused']}))
'''
        children=[subprocess.Popen([sys.executable,'-c',code,str(self.store.root),str(self.sources),str(self.store.output_root),self.case,self.version,str(i)],
                                   env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(2)]
        rows=[]
        try:
            for child in children:
                out,err=child.communicate(timeout=90)
                self.assertEqual(0,child.returncode,err.decode('utf-8',errors='replace'))
                rows.append(json.loads(out))
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.wait(timeout=10)
        self.assertEqual(rows[0]['processing_id'],rows[1]['processing_id'])
        self.assertEqual([False,True],sorted(row['reused'] for row in rows));self.assertEqual(1,self.count())
