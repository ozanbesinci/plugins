"""Read-only compatibility diagnostics; terminal records never grant business acceptance."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from test_request_receipts import quote


class RequestReceiptInspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cs-receipt-inspect-');self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name);self.request_id=str(uuid4());self.sha='a'*64
        self.claim=self.area/(self.request_id+'.json');self.final=self.area/(self.request_id+'.final.json')
    def write(self,path,value):path.write_text(json.dumps(value),encoding='utf-8')
    def base(self):return {'request_id':self.request_id,'request_sha256':self.sha,'skill_id':'K03','status':'STARTED'}
    def inspect(self):
        import subprocess
        root=Path(__file__).resolve().parents[1]
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.area.iterdir() if p.is_file()}
        command='. '+quote(root/'scripts/beceri-baslat.ps1')+' -SkillId K03 -LibraryOnly; '
        command+=f'Get-ContractRequestReceiptState {quote(self.area)} {quote(self.request_id)} {quote(self.sha)} K03 | ConvertTo-Json -Compress'
        run=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,timeout=30)
        self.assertEqual(0,run.returncode,run.stderr.decode('utf-8',errors='replace'))
        result=json.loads(run.stdout.decode('utf-8-sig'))
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.area.iterdir() if p.is_file()})
        self.assertFalse(result['resume_allowed']);self.assertFalse(result['repair_performed'])
        self.assertEqual('NOT_VERIFIED',result['authority']);self.assertEqual('NOT_GRANTED',result['business_acceptance'])
        return result
    def test_unclaimed_and_orphan_final_never_offer_automatic_resume(self):
        self.assertEqual('UNCLAIMED',self.inspect()['state'])
        self.write(self.final,{'status':'COMPLETED'});self.assertEqual('ORPHAN_FINAL_UNVERIFIED',self.inspect()['state'])
    def test_legacy_started_and_completed_are_read_without_rewriting_claim(self):
        for status,expected in [('STARTED','RECOVERY_REQUIRED'),('COMPLETED','LEGACY_TERMINAL_RECORD'),('FAILED','LEGACY_TERMINAL_RECORD')]:
            self.write(self.claim,dict(self.base(),status=status));self.assertEqual(expected,self.inspect()['state'])
    def test_modern_missing_final_and_completed_final_remain_no_business_acceptance(self):
        self.write(self.claim,dict(self.base(),schema='contract-request-claim/v1'))
        self.assertEqual('FINAL_MISSING',self.inspect()['reason'])
        self.write(self.final,{'schema':'contract-request-final/v1','status':'COMPLETED','request_id':self.request_id,'request_sha256':self.sha,'business_acceptance':'NOT_GRANTED'})
        self.assertEqual('TERMINAL_RECORD',self.inspect()['state'])
    def test_partial_or_invalid_utf8_claim_is_consumed_recovery_required(self):
        for payload in [b'',b'{"st',b'\xff\xfe\x00']:
            self.claim.write_bytes(payload);self.assertEqual('RECOVERY_REQUIRED',self.inspect()['state'])
    def test_mismatched_final_or_false_authority_is_not_terminal_success(self):
        self.write(self.claim,dict(self.base(),schema='contract-request-claim/v1'))
        final={'schema':'contract-request-final/v1','status':'COMPLETED','request_id':self.request_id,'request_sha256':self.sha,'business_acceptance':'NOT_GRANTED'}
        for changes in [{'request_sha256':'b'*64},{'request_id':str(uuid4())},{'business_acceptance':'GRANTED'}]:
            self.write(self.final,dict(final,**changes));self.assertEqual('RECOVERY_REQUIRED',self.inspect()['state'])
    def test_legacy_modern_mixture_and_foreign_claim_binding_are_closed(self):
        self.write(self.claim,dict(self.base(),status='COMPLETED'));self.write(self.final,{'status':'COMPLETED'})
        self.assertEqual('RECOVERY_REQUIRED',self.inspect()['state'])
        self.write(self.claim,dict(self.base(),request_sha256='b'*64));self.assertEqual('RECOVERY_REQUIRED',self.inspect()['state'])
