"""Real Windows files/process exits; write/flush/move failures are injected at IO boundaries."""
import json
from pathlib import Path
import tempfile
import unittest

from test_request_receipts import quote


class ReceiptFaultMatrixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cs-receipt-fault-')
        self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name)
        self.claim=self.area/'request.json';self.final=self.area/'request.final.json'
        self.foreign=self.area/'foreign.tmp';self.foreign.write_bytes(b'foreign owner')
        self.effect=self.area/'effects.log'
        root=Path(__file__).resolve().parents[1]
        self.prefix='. '+quote(root/'scripts/beceri-baslat.ps1')+' -SkillId K03 -LibraryOnly; $ErrorActionPreference="Stop"; '
    def ps(self,code):
        import subprocess
        return subprocess.run(['powershell.exe','-NoProfile','-Command',self.prefix+code],capture_output=True,
                              text=True,encoding='utf-8',errors='replace',timeout=30)
    def claim_code(self):
        return f'$lock=New-ContractRequestClaim {quote(self.claim)} @{{status="STARTED";request_id="r"}};$lock.Dispose();'
    def final_code(self):
        return f'Write-ContractFinalReceipt {quote(self.final)} @{{status="COMPLETED";business_acceptance="NOT_GRANTED"}};'
    def effect_code(self):
        return f'[IO.File]::AppendAllText({quote(self.effect)},"effect`n");'
    def no_replay(self):
        before=self.claim.read_bytes()
        result=self.ps(f'try{{{self.claim_code()}{self.effect_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertEqual(before,self.claim.read_bytes())
        if self.effect.exists():self.assertEqual(['effect'],self.effect.read_text().splitlines())
    def preserved_foreign(self):self.assertEqual(b'foreign owner',self.foreign.read_bytes())
    def test_serialization_failure_occurs_before_claim_creation(self):
        result=self.ps('function ConvertTo-Json {throw "injected serialization failure"};'
                       f'try{{{self.claim_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.claim.exists());self.assertFalse(self.effect.exists());self.preserved_foreign()
    def test_partial_claim_write_failure_consumes_claim_and_never_runs_effect(self):
        adapter='function Write-ContractReceiptBytes($Stream,$Bytes){$Stream.Write($Bytes,0,5);$Stream.Flush($true);throw "injected write failure"};'
        result=self.ps(adapter+f'try{{{self.claim_code()}{self.effect_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertEqual(5,self.claim.stat().st_size);self.assertFalse(self.effect.exists())
        self.no_replay();self.preserved_foreign()
    def test_claim_flush_failure_leaves_consumed_claim_without_effect(self):
        adapter='function Flush-ContractReceiptStream($Stream){throw "injected flush failure"};'
        result=self.ps(adapter+f'try{{{self.claim_code()}{self.effect_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertTrue(self.claim.exists());self.assertFalse(self.effect.exists());self.no_replay()
    def test_native_exit_immediately_after_exclusive_claim_creation_blocks_replay(self):
        adapter='function Write-ContractReceiptBytes($Stream,$Bytes){[Environment]::Exit(21)};'
        result=self.ps(adapter+self.claim_code()+self.effect_code())
        self.assertEqual(21,result.returncode,result.stdout+result.stderr)
        self.assertEqual(0,self.claim.stat().st_size);self.assertFalse(self.final.exists())
        self.assertFalse(self.effect.exists());self.no_replay()
    def test_native_exit_during_partial_claim_write_blocks_replay(self):
        adapter='function Write-ContractReceiptBytes($Stream,$Bytes){$Stream.Write($Bytes,0,5);$Stream.Flush($true);[Environment]::Exit(22)};'
        result=self.ps(adapter+self.claim_code()+self.effect_code())
        self.assertEqual(22,result.returncode,result.stdout+result.stderr)
        self.assertEqual(5,self.claim.stat().st_size);self.assertFalse(self.final.exists())
        self.assertFalse(self.effect.exists());self.no_replay()
    def test_final_write_failure_cleans_owned_temp_keeps_claim_and_single_effect(self):
        adapter='function Write-ContractReceiptBytes($Stream,$Bytes){$Stream.Write($Bytes,0,5);throw "injected write failure"};'
        result=self.ps(self.claim_code()+self.effect_code()+adapter+f'try{{{self.final_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.final.exists());self.assertEqual([],list(self.area.glob('request.final.json.*.tmp')))
        self.assertEqual('STARTED',json.loads(self.claim.read_text())['status']);self.no_replay();self.preserved_foreign()
    def test_final_flush_failure_cleans_temp_without_replaying_effect(self):
        adapter='function Flush-ContractReceiptStream($Stream){throw "injected flush failure"};'
        result=self.ps(self.claim_code()+self.effect_code()+adapter+f'try{{{self.final_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.final.exists());self.assertEqual([],list(self.area.glob('request.final.json.*.tmp')));self.no_replay()
    def test_final_move_failure_cleans_temp_without_modifying_claim(self):
        adapter='function Move-ContractFinalReceipt($Temporary,$Path){throw "injected move failure"};'
        result=self.ps(self.claim_code()+self.effect_code()+adapter+f'try{{{self.final_code()}exit 9}}catch{{exit 0}}')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.final.exists());self.assertEqual([],list(self.area.glob('request.final.json.*.tmp')));self.no_replay()
    def test_native_exit_after_final_temp_flush_keeps_valid_temp_but_no_final(self):
        adapter='function Move-ContractFinalReceipt($Temporary,$Path){[Environment]::Exit(23)};'
        result=self.ps(self.claim_code()+self.effect_code()+adapter+self.final_code())
        self.assertEqual(23,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.final.exists());temps=list(self.area.glob('request.final.json.*.tmp'))
        self.assertEqual(1,len(temps));self.assertEqual('COMPLETED',json.loads(temps[0].read_text())['status'])
        self.no_replay();self.preserved_foreign()
    def test_native_exit_during_final_partial_write_keeps_only_owned_partial_temp(self):
        adapter='function Write-ContractReceiptBytes($Stream,$Bytes){$Stream.Write($Bytes,0,5);$Stream.Flush($true);[Environment]::Exit(25)};'
        result=self.ps(self.claim_code()+self.effect_code()+adapter+self.final_code())
        self.assertEqual(25,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.final.exists());temps=list(self.area.glob('request.final.json.*.tmp'))
        self.assertEqual(1,len(temps));self.assertEqual(5,temps[0].stat().st_size)
        self.no_replay();self.preserved_foreign()
    def test_native_exit_after_atomic_move_preserves_parseable_final_and_single_effect(self):
        adapter='function Move-ContractFinalReceipt($Temporary,$Path){[IO.File]::Move($Temporary,$Path);[Environment]::Exit(24)};'
        result=self.ps(self.claim_code()+self.effect_code()+adapter+self.final_code())
        self.assertEqual(24,result.returncode,result.stdout+result.stderr)
        final=json.loads(self.final.read_text());self.assertEqual('COMPLETED',final['status'])
        self.assertEqual('NOT_GRANTED',final['business_acceptance']);self.assertEqual([],list(self.area.glob('request.final.json.*.tmp')))
        self.no_replay();self.preserved_foreign()
