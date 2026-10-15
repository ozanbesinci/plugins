import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def quote(path):
    return "'" + str(path).replace("'", "''") + "'"


class RequestReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cs-receipt-')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.prefix = '. ' + quote(ROOT/'scripts/beceri-baslat.ps1') + ' -SkillId K03 -LibraryOnly; $ErrorActionPreference="Stop"; '

    def ps(self, code):
        return subprocess.run(['powershell.exe', '-NoProfile', '-Command', self.prefix+code],
                              capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)

    def test_claim_stays_immutable_after_separate_final_publication(self):
        claim, final = self.area/'request.json', self.area/'request.final.json'
        code = f'$lock=New-ContractRequestClaim {quote(claim)} @{{status="STARTED";request_id="r"}}; $lock.Dispose(); $before=Get-ContractBootstrapSha {quote(claim)}; Write-ContractFinalReceipt {quote(final)} @{{status="COMPLETED";business_acceptance="NOT_GRANTED"}}; if($before -cne (Get-ContractBootstrapSha {quote(claim)})){{exit 8}}'
        run = self.ps(code)
        self.assertEqual(0, run.returncode, run.stdout+run.stderr)
        self.assertEqual('STARTED', json.loads(claim.read_text(encoding='utf-8'))['status'])
        self.assertEqual('COMPLETED', json.loads(final.read_text(encoding='utf-8'))['status'])
        self.assertEqual([], list(self.area.glob('*.tmp')))

    def test_existing_final_cannot_be_overwritten_and_owned_temp_is_cleaned(self):
        final = self.area/'request.final.json'
        final.write_bytes(b'{"original":true}')
        run = self.ps(f'try{{Write-ContractFinalReceipt {quote(final)} @{{status="COMPLETED"}};exit 9}}catch{{exit 0}}')
        self.assertEqual(0, run.returncode, run.stdout+run.stderr)
        self.assertEqual(b'{"original":true}', final.read_bytes())
        self.assertEqual([], list(self.area.glob('*.tmp')))

    def test_native_crash_leaves_consumed_claim_and_no_final_no_replay(self):
        claim, final = self.area/'request.json', self.area/'request.final.json'
        code = self.prefix+f'$lock=New-ContractRequestClaim {quote(claim)} @{{status="STARTED"}}; Start-Sleep -Seconds 30'
        child = subprocess.Popen(['powershell.exe', '-NoProfile', '-Command', code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic()+15
            while (not claim.exists() or claim.stat().st_size == 0) and time.monotonic()<deadline:
                time.sleep(.02)
            self.assertTrue(claim.exists())
        finally:
            child.kill(); child.wait(timeout=10)
        self.assertEqual('STARTED', json.loads(claim.read_text(encoding='utf-8'))['status'])
        self.assertFalse(final.exists())
        before = claim.read_bytes()
        run = self.ps(f'try{{$lock=New-ContractRequestClaim {quote(claim)} @{{status="STARTED"}};$lock.Dispose();exit 9}}catch{{exit 0}}')
        self.assertEqual(0, run.returncode, run.stdout+run.stderr)
        self.assertEqual(before, claim.read_bytes())
