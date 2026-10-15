"""Synthetic tampered-package marker must never execute before verification."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('contract_bootstrap_integrity',ROOT/'scripts/bootstrap_integrity.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)


class BootstrapIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cs-integrity-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'package'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('.runtime','__pycache__'))
        self.vendor=self.root/'vendor/guncelleyici'

    def test_good_42_file_package_and_external_pin(self):
        proof=bootstrap.verify_vendor(self.vendor)
        self.assertEqual(42,proof['files_verified'])
        self.assertEqual('PACKAGE_SELF_CONSISTENCY_ONLY',proof['trust'])
        self.assertEqual('EXTERNAL_PIN_MATCHED',bootstrap.verify_vendor(self.vendor,proof['manifest_sha256'])['trust'])
        with self.assertRaises(bootstrap.BootstrapIntegrityError):bootstrap.verify_vendor(self.vendor,'0'*64)

    def test_python_tampered_helper_is_rejected_before_marker(self):
        marker=Path(self.temp.name)/'python-marker.txt'
        helper=self.vendor/'scripts/islem_guvencesi.py'
        helper.write_bytes(helper.read_bytes()+('\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("must-not-run")\n').encode())
        result=subprocess.run([sys.executable,'-B','-X','utf8',str(self.root/'scripts/runtime_kontrol.py'),'--action','verify-upstream'],
                              capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertNotEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn('PAKET_BUTUNLUK',result.stdout)
        self.assertFalse(marker.exists())

    def test_powershell_tampered_helper_is_rejected_before_dot_source(self):
        marker=Path(self.temp.name)/'ps-marker.txt'
        helper=self.vendor/'scripts/program-ortak.ps1'
        helper.write_bytes(helper.read_bytes()+('\n[IO.File]::WriteAllText(\''+str(marker).replace("'","''")+'\',\'must-not-run\')\n').encode('utf-8'))
        result=subprocess.run(['powershell.exe','-NoProfile','-File',str(self.root/'scripts/beceri-baslat.ps1'),'-SkillId','K23','-LibraryOnly'],
                              capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        self.assertNotEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn('PAKET_BUTUNLUK',result.stdout)
        self.assertFalse(marker.exists())

    def test_good_powershell_library_load_never_runs_an_installer(self):
        result=subprocess.run(['powershell.exe','-NoProfile','-File',str(self.root/'scripts/beceri-baslat.ps1'),'-SkillId','K23','-LibraryOnly'],
                              capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertNotIn('PAKET_BUTUNLUK',result.stdout)

    def test_extra_missing_and_traversal_files_are_rejected(self):
        extra=self.vendor/'unexpected-helper.py';extra.write_text('pass')
        with self.assertRaises(bootstrap.BootstrapIntegrityError):bootstrap.verify_vendor(self.vendor)
        extra.unlink()
        manifest=self.vendor/'MANIFEST.sha256.json';value=json.loads(manifest.read_text())
        old=next(iter(value['files']));value['files']['../outside']=value['files'].pop(old)
        manifest.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(bootstrap.BootstrapIntegrityError):bootstrap.verify_vendor(self.vendor)


if __name__=='__main__':unittest.main()
