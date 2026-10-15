"""Native crash/reopen tests. Synthetic Word evidence is never human acceptance."""
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from sozlesme_cekirdek import Store
from sozlesme_cekirdek.docx_revisions import SyntheticDocxBackend
from sozlesme_cekirdek.guard import SyntheticGuardRuntime
from sozlesme_cekirdek.safety import hash_file,hash_value
from guard_fixtures import Clock,Host,KEY
from reader_fixtures import docx_bytes
from process_fixtures import abrupt_exit
from test_docx import WHEN,edit_request,synthetic_evidence

ROOT=Path(__file__).resolve().parents[1]


class LoggedBackend(SyntheticDocxBackend):
    def __init__(self,area,crash=None):
        super().__init__(when=WHEN,evidence_provider=synthetic_evidence)
        self.area=Path(area);self.crash=crash
    def prepare_document(self,request,snapshots):
        with (self.area/'prepare.log').open('a',encoding='utf-8') as writer:
            writer.write(request['plan']['operation_id']+'\n');writer.flush();os.fsync(writer.fileno())
        return super().prepare_document(request,snapshots)
    def verify_document(self,request,data):
        if self.crash=='BEFORE_QA':abrupt_exit(27)
        return super().verify_document(request,data)


def reopen(area,case,req,crash=None):
    store=Store(Path(area)/'work',source_roots=[Path(area)/'sources'],output_root=area,lock_timeout=60)
    host=Host(case);host.authorize(req)
    backend=LoggedBackend(area,crash)
    runtime=SyntheticGuardRuntime(store,identity_provider=host,backend=backend,signing_key=KEY,clock=Clock())
    return store,host,backend,runtime


def native_execute(area,case,req,permission,crash):
    store,host,backend,runtime=reopen(area,case,req,crash)
    if crash=='AFTER_RENAME':
        original=runtime._stage
        def stage(db,case,operation,expected,state,**values):
            if state=='SIMULATION_COMMITTED':abrupt_exit(29)
            return original(db,case,operation,expected,state,**values)
        runtime._stage=stage
    runtime.execute(request=req,permission_id=permission)


def native_recover(area,case,req,spec,barrier,queue,crash=False):
    store,host,backend,runtime=reopen(area,case,req)
    if crash:
        original=store._event
        def event(db,case,event,details):
            if event=='SYNTHETIC_RECOVERY_STARTED':abrupt_exit(31)
            return original(db,case,event,details)
        store._event=event
    if barrier:barrier.wait(90)
    result=runtime.recover_document(spec=spec)
    if queue:queue.put(result)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'tests/.runtime';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='recovery-İı-',dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name);self.sources=self.area/'sources';self.sources.mkdir()
        self.path=self.sources/'kaynak.docx';self.path.write_bytes(docx_bytes())
        self.store=Store(self.area/'work',source_roots=[self.sources],output_root=self.area)
        self.case=self.store.create_case('Sentetik recovery')
        doc=self.store.create_document(self.case,'DOCX',expected_revision=0)
        self.version=self.store.ingest(self.case,doc,self.path,expected_revision=self.store.case_revision(self.case))['version_id']
        reading=self.store.read_document(self.case,self.version,format='DOCX')
        self.req=edit_request(self.path.read_bytes(),case=self.case,version=self.version,reading=reading['processing_id'])
        self.store,self.host,self.backend,self.runtime=reopen(self.area,self.case,self.req)
        self.permission=self.runtime.issue_permission(request=self.req,expected_revision=self.rev())['permission_id']
        self.operation=self.req['plan']['operation_id']
        self.final=self.store.root/self.req['plan']['parameters']['target_relative_path']
        self.capsule=self.store.system/'eylem-karantina'/self.operation/'capsule.json'
    def rev(self):return self.store.case_revision(self.case)
    def crash(self,mode='BEFORE_QA'):
        process=multiprocessing.get_context('spawn').Process(target=native_execute,args=(str(self.area),self.case,self.req,self.permission,mode))
        process.start();process.join(120)
        if process.is_alive():process.terminate();process.join();self.fail('native crash timeout')
        self.assertEqual(27 if mode=='BEFORE_QA' else 29,process.exitcode)
        self.assertTrue(self.capsule.is_file())
        self.store,self.host,self.backend,self.runtime=reopen(self.area,self.case,self.req)
    def spec(self):
        capsule=json.loads(self.capsule.read_text(encoding='utf-8'))
        return {'schema_version':'p4-recovery-request-1.0','case_id':self.case,'operation_id':self.operation,
                'permission_id':self.permission,'recovery_id':str(uuid4()),'context_version':self.rev(),
                'request_digest':hash_value(self.req),'artifact_sha256':capsule['artifact_sha256'],
                'requested_scope':'SYNTHETIC_TEST_ONLY'}
    def count(self):
        with self.store._db() as db:return db.execute('SELECT count(*) FROM docx_turevleri').fetchone()[0]
    def log_count(self):return len((self.area/'prepare.log').read_text(encoding='utf-8').splitlines())
    def blocked(self,result):
        self.assertEqual('BLOCKED',result['state']);self.assertFalse(result['production_ready'])
        self.assertFalse(result['delivery_confirmed']);self.assertEqual(0,self.count())
    def test_native_crash_restores_manifest_without_second_prepare(self):
        self.crash();result=self.runtime.recover_document(spec=self.spec())
        self.assertEqual('SIMULATION_COMMITTED',result['state']);self.assertFalse(result['existing_final_adopted'])
        self.assertFalse(result['backend_prepare_called']);self.assertEqual(1,self.log_count());self.assertEqual(1,self.count())
        self.assertEqual(result['artifact_sha256'],hash_file(self.final));self.assertEqual(hashlib.sha256(docx_bytes()).hexdigest(),hash_file(self.path))
        self.assertEqual('ALLOW',self.runtime.completion_gate(self.case,self.operation)['decision'])
        self.assertEqual('NOT_GRANTED',result['business_acceptance'])
    def test_after_native_publish_crash_adopts_same_final_without_rename(self):
        self.crash('AFTER_RENAME');identity=self.final.stat();digest=hash_file(self.final)
        with patch('sozlesme_cekirdek.recovery.os.rename',side_effect=AssertionError('must not republish')):
            result=self.runtime.recover_document(spec=self.spec())
        self.assertEqual('SIMULATION_COMMITTED',result['state']);self.assertTrue(result['existing_final_adopted'])
        self.assertEqual((identity.st_ino,identity.st_mtime_ns),(self.final.stat().st_ino,self.final.stat().st_mtime_ns))
        self.assertEqual(digest,hash_file(self.final));self.assertEqual(1,self.count());self.assertEqual(1,self.log_count())
    def test_second_recovery_and_original_execute_cannot_repeat_effect(self):
        self.crash();spec=self.spec();self.assertEqual('SIMULATION_COMMITTED',self.runtime.recover_document(spec=spec)['state'])
        self.assertEqual('BLOCKED',self.runtime.recover_document(spec=dict(spec,recovery_id=str(uuid4())))['state'])
        self.assertEqual('BLOCKED',self.runtime.execute(request=self.req,permission_id=self.permission)['state'])
        self.assertEqual(1,self.count());self.assertEqual(1,self.log_count())
    def test_native_recovery_claim_survives_crash_and_blocks_blind_retry(self):
        self.crash();spec=self.spec()
        process=multiprocessing.get_context('spawn').Process(target=native_recover,args=(str(self.area),self.case,self.req,spec,None,None,True))
        process.start();process.join(120)
        if process.is_alive():process.terminate();process.join();self.fail('recovery claim crash timeout')
        self.assertEqual(31,process.exitcode)
        self.store,self.host,self.backend,self.runtime=reopen(self.area,self.case,self.req)
        self.blocked(self.runtime.recover_document(spec=dict(spec,recovery_id=str(uuid4()))))
        self.assertFalse(self.final.exists());self.assertEqual(1,self.log_count())
        receipts=self.store.system/'recovery'
        self.assertTrue((receipts/(self.operation+'.claim.json')).exists());self.assertFalse((receipts/(self.operation+'.final.json')).exists())
    def test_two_native_recovery_processes_commit_only_once(self):
        self.crash();context=multiprocessing.get_context('spawn');barrier=context.Barrier(2);queue=context.Queue();spec=self.spec()
        processes=[context.Process(target=native_recover,args=(str(self.area),self.case,self.req,dict(spec,recovery_id=str(uuid4())),barrier,queue)) for _ in range(2)]
        for process in processes:process.start()
        for process in processes:
            process.join(120)
            if process.is_alive():process.terminate();process.join();self.fail('concurrent recovery timeout')
            self.assertEqual(0,process.exitcode)
        results=[queue.get(timeout=10) for _ in processes];queue.close()
        self.assertEqual(['BLOCKED','SIMULATION_COMMITTED'],sorted(r['state'] for r in results))
        self.assertEqual(1,self.count());self.assertEqual(1,self.log_count())
    def test_capsule_corruption_blocks_without_repreparation(self):
        self.crash();spec=self.spec();self.capsule.write_text('{}',encoding='utf-8')
        self.blocked(self.runtime.recover_document(spec=spec));self.assertFalse(self.final.exists());self.assertEqual(1,self.log_count())
    def test_quarantine_corruption_blocks_without_final(self):
        self.crash();spec=self.spec();self.capsule.with_name('artifact.bin').write_bytes(b'changed')
        self.blocked(self.runtime.recover_document(spec=spec));self.assertFalse(self.final.exists())
    def test_foreign_final_is_never_overwritten(self):
        self.crash();self.final.parent.mkdir(parents=True,exist_ok=True);self.final.write_bytes(b'foreign')
        self.blocked(self.runtime.recover_document(spec=self.spec()));self.assertEqual(b'foreign',self.final.read_bytes())
    def test_expired_permission_actor_epoch_and_source_drift_each_block(self):
        self.crash();spec=self.spec()
        self.runtime.clock.value+=timedelta(seconds=301);self.blocked(self.runtime.recover_document(spec=spec))
        self.runtime.clock.value-=timedelta(seconds=301)
        identity=self.host.identity;self.host.identity=replace(identity,identity_epoch='revoked')
        self.blocked(self.runtime.recover_document(spec=spec));self.host.identity=identity
        self.path.write_bytes(b'changed');self.blocked(self.runtime.recover_document(spec=spec));self.assertFalse(self.final.exists())
    def test_changed_build_blocks_same_backend_version(self):
        self.crash()
        with patch('sozlesme_cekirdek.recovery.component_identity',return_value={'source_digest':'0'*64}):
            self.blocked(self.runtime.recover_document(spec=self.spec()))
    def test_case_revision_and_request_bindings_are_explicit(self):
        self.crash();spec=self.spec()
        for changes in [{'case_id':str(uuid4())},{'request_digest':'0'*64},{'artifact_sha256':'0'*64},{'context_version':self.rev()+1},{'permission_id':str(uuid4())}]:
            self.blocked(self.runtime.recover_document(spec=dict(spec,**changes)))
        self.assertFalse(self.final.exists())
    def test_current_independent_test_qa_is_required(self):
        self.crash();self.backend.evidence_provider=None
        self.blocked(self.runtime.recover_document(spec=self.spec()));self.assertFalse(self.final.exists())
    def test_failed_qa_operation_cannot_be_promoted_to_recovery(self):
        self.backend.evidence_provider=None
        self.assertEqual('FAILED',self.runtime.execute(request=self.req,permission_id=self.permission)['state'])
        self.backend.evidence_provider=synthetic_evidence
        self.blocked(self.runtime.recover_document(spec=self.spec()));self.assertFalse(self.final.exists())
    def test_no_recovery_writer_is_available_on_store_or_agent_cli(self):
        self.assertFalse(hasattr(self.store,'recover_document'))
        text=(ROOT/'src/sozlesme_cekirdek/__main__.py').read_text(encoding='utf-8')
        self.assertNotIn('recover_document(',text)

