"""Python components, simulated CLI recovery, and plan-source contracts.

Static PowerShell source assertions are NOT PowerShell execution tests.
"""
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'scripts';sys.path.insert(0,str(S))
import duckdb_pdf as pdf
import claude_bagla as cc
import islem_guvencesi as g

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,S/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
libs=load('libtest','kurulum-testi.py');duck=load('ducktest','python-paket-kur.py');fixture=load('fixture','islev-testi.py')

class PackageTests(unittest.TestCase):
    def test_twelve_valid_locked_packages(self):
        p=libs.package_set();self.assertEqual(len(p),12);self.assertEqual(len({x['name'] for x in p}),12)
        self.assertTrue(all(len(h)==64 for x in p for h in x['hashes']))
    def test_lock_hash_and_python_in_target(self):
        t=libs.target_info();self.assertEqual(t['version'],g.digest_bytes(libs.LOCK_PATH.read_bytes()));self.assertEqual(t['python'],sys.executable)
    def test_invalid_lock_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'lock.json';p.write_text(json.dumps({'schema':'guncelleyici-package-set/v1','packages':[{'name':'x','version':'1','hashes':['bad']}]*12}))
            with patch.object(libs,'LOCK_PATH',p),self.assertRaises(g.SafetyError):libs.package_set()
    def test_pip_environment_source_override_removed(self):
        with patch.dict(os.environ,{'PIP_EXTRA_INDEX_URL':'https://bad.invalid','PIP_TRUSTED_HOST':'bad.invalid','PIP_CERT':'fixture-ca','HTTPS_PROXY':'https://proxy.invalid'}):
            e=libs.pip_environment();self.assertNotIn('PIP_EXTRA_INDEX_URL',e);self.assertNotIn('PIP_TRUSTED_HOST',e)
            self.assertEqual(e['PIP_CERT'],'fixture-ca');self.assertEqual(e['HTTPS_PROXY'],'https://proxy.invalid')
    def test_target_run_token_and_hash(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'GUNCELLEYICI_RUN_TOKEN':'fixture'}):
            p=Path(td)/'target.json';p.write_text(json.dumps({'key':'libraries','run_token':'fixture','target':{'a':1}}));h=g.digest_bytes(p.read_bytes())
            self.assertEqual(libs.read_target(p,h,'libraries'),{'a':1})
            with self.assertRaises(g.SafetyError):libs.read_target(p,'0'*64,'libraries')
            with self.assertRaises(g.SafetyError):libs.read_target(p,h,'duckdb')
    def test_linux_installer_rejected_before_pip(self):
        if os.name=='nt':self.skipTest('Linux guard case')
        with patch.object(libs,'run',side_effect=AssertionError('pip must not run')):
            with self.assertRaises(g.SafetyError):libs.install(libs.target_info())
    def test_wheel_plan_sources_and_hashes(self):
        good={'name':'duckdb','version':'1.2.3','sha256':'a'*64,'url':'https://files.pythonhosted.org/test.whl'}
        self.assertEqual(duck.validate_wheels([good]),[good])
        for key,value in (('url','http://files.pythonhosted.org/test.whl'),('url','https://evil.test/test.whl'),('sha256','bad'),('version','1.2.3rc1')):
            bad={**good,key:value}
            with self.subTest(key=key,value=value),self.assertRaises(g.SafetyError):duck.validate_wheels([bad])
    def test_duck_test_rejects_nonzero_even_with_pass_json(self):
        p=subprocess.CompletedProcess([],2,'{"status":"PASS","version":"1.2.3"}','fixture failure')
        with patch.object(duck.base,'run',return_value=p),self.assertRaises(g.SafetyError):duck.smoke()
    def test_failed_package_install_records_recovery(self):
        proc=subprocess.CompletedProcess([],1,'','fixture pip failure')
        with patch.object(libs,'ensure_runtime'),patch.object(libs,'run',return_value=proc):
            result=libs.install(libs.target_info())
        self.assertEqual(result['ozet'],'ENGEL');self.assertTrue(result['recovery_required'])
    @unittest.skipUnless(importlib.util.find_spec("pypdf") is not None, "optional pypdf dependency is not installed")
    def test_pdf_fixture_is_readable(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.pdf';fixture.pdf_fixture(p)
            reader=PdfReader(p);self.assertEqual(len(reader.pages),1);self.assertIn('12345',reader.pages[0].extract_text())

class PdfTests(unittest.TestCase):
    def test_platform_version_url(self):
        self.assertEqual(pdf.source_url('1.2.3','windows_amd64'),'https://community-extensions.duckdb.org/v1.2.3/windows_amd64/pdf.duckdb_extension.gz')
        for v,platform in (('1.2.3-dev','windows_amd64'),('1.2.3','linux_amd64'),('../1','windows_amd64')):
            with self.assertRaises(g.SafetyError):pdf.source_url(v,platform)
    def test_download_rejects_untrusted_before_network(self):
        with patch.object(pdf.urllib.request,'build_opener',side_effect=AssertionError('network')):
            for url in ('http://community-extensions.duckdb.org/x','https://evil.test/x','https://user:pass@community-extensions.duckdb.org/x'):
                with self.assertRaises(g.SafetyError):pdf.checked_download(url)
    def test_download_decompresses_and_bounds(self):
        class Opener:
            def open(self,*a,**kw):return io.BytesIO(gzip.compress(b'fixture-extension-bytes'))
        with patch.object(pdf.urllib.request,'build_opener',return_value=Opener()):
            self.assertEqual(pdf.checked_download('https://community-extensions.duckdb.org/x'),b'fixture-extension-bytes')
            with patch.object(pdf,'MAX_EXPANDED',2),self.assertRaises(g.SafetyError):pdf.checked_download('https://community-extensions.duckdb.org/x')
    def test_scan_never_loads_extension(self):
        local={'engine':'1.2.3','platform':'windows_amd64','destination':'fixture','version':None,'sha256':None}
        with tempfile.TemporaryDirectory() as td,patch.object(pdf,'worker_request',return_value=local) as worker,patch.object(pdf,'checked_download',return_value=b'fixture'):
            r=pdf.prepare(td);self.assertEqual(worker.call_args.args,('probe',));self.assertEqual(r['target']['sha256'],g.digest_bytes(b'fixture'))
            self.assertTrue(Path(r['target']['archive']).is_file());self.assertEqual(r['health'],'NOT_RUN')
    def test_worker_failure_is_not_success(self):
        proc=subprocess.CompletedProcess([],1,'{"status":"PASS"}','fixture crash')
        with patch.object(pdf.subprocess,'run',return_value=proc),self.assertRaises(g.SafetyError):pdf.worker_request('probe')

class ClaudeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/'claude.json';self.cli=self.root/'claude.exe';self.cli.touch();self.exe=self.root/'server.exe';self.exe.touch();self.calls=[]
    def runner(self,args):
        self.calls.append(args);obj=json.loads(self.path.read_text()) if self.path.exists() else {};servers=obj.setdefault('mcpServers',{})
        if args[1]=='remove':servers.pop(cc.NAME,None)
        else:servers[cc.NAME]={'type':'stdio','command':args[-2],'args':['--start']}
        self.path.write_text(json.dumps(obj))
    def test_new_cli_binding(self):
        r=cc.bind(self.path,self.cli,self.exe,self.runner);self.assertEqual(r['status'],'created');self.assertEqual(self.calls[0][0:2],['mcp','add'])
    def test_custom_entry_deferred_unchanged(self):
        old={'mcpServers':{cc.NAME:{'command':'old','args':['--start'],'env':{'SECRET':'keep'}}}}
        raw=json.dumps(old).encode();self.path.write_bytes(raw)
        r=cc.bind(self.path,self.cli,self.exe,self.runner);self.assertEqual(r['status'],'deferred');self.assertEqual(self.calls,[]);self.assertEqual(self.path.read_bytes(),raw)
    def test_other_server_preserved_and_backup_created(self):
        self.path.write_text(json.dumps({'mcpServers':{cc.NAME:{'command':'old','args':['--start']},'other':{'url':'https://example.invalid'}}}))
        raw=self.path.read_bytes();r=cc.bind(self.path,self.cli,self.exe,self.runner)
        self.assertEqual(Path(r['backup']).read_bytes(),raw);self.assertIn('other',json.loads(self.path.read_text())['mcpServers'])
    def test_add_failure_restores_old_via_cli(self):
        self.path.write_text(json.dumps({'mcpServers':{cc.NAME:{'command':'old','args':['--start']}}}))
        def failing(args):
            if args[1]=='add' and args[-2]==str(self.exe):raise g.SafetyError('fixture new binding fail')
            self.runner(args)
        r=cc.bind(self.path,self.cli,self.exe,failing);self.assertEqual(r['status'],'error');self.assertTrue(r['rollback_verified'])
        self.assertEqual(json.loads(self.path.read_text())['mcpServers'][cc.NAME]['command'],'old')
    def test_cmd_cli_rejected(self):
        cli=self.root/'claude.cmd';cli.touch()
        with self.assertRaises(g.SafetyError):cc.bind(self.path,cli,self.exe,self.runner)

class SourceContractTests(unittest.TestCase):
    def text(self,n):return (S/n).read_text(encoding='utf-8-sig')
    def test_core_post_lock_revalidation_and_no_rolling_resolve_in_apply(self):
        s=self.text('core.ps1');apply=s.split('function Apply-Plan',1)[1].split('function Verify-Selected',1)[0]
        self.assertLess(apply.index('Enter-Guard'),apply.index('Get-Observation $component.key -LocalOnly'))
        self.assertNotIn('Build-Plan',apply);self.assertIn('component.target.version',apply)
    def test_old_panel_no_mutations(self):
        s=self.text('panel.ps1');self.assertNotIn('Remove-LegacySkill',s);self.assertNotIn('ShowDialog',s)
    def test_pnpm_pinned_hash_and_no_install_scripts(self):
        s=self.text('pnpm-kur.ps1');self.assertIn('$target.integrity',s);self.assertIn("'--offline'",s);self.assertIn("'--ignore-scripts'",s)
    def test_pdf_unsigned_disabled_and_no_bulk_update(self):
        s=self.text('duckdb_pdf.py');self.assertIn('"allow_unsigned_extensions": False',s);self.assertNotIn('UPDATE EXTENSIONS;',s)
    def test_all_installers_require_explicit_target(self):
        for name in ('python-kur.ps1','node-kur.ps1','pnpm-kur.ps1','powerbi-mcp-kur.ps1'):
            with self.subTest(name=name):self.assertIn('Read-Target',self.text(name))
    def test_core_and_wrapper_verify_defined(self):
        self.assertIn('function Verify-Selected',self.text('core.ps1'));self.assertIn('Verify-Selected $selected',self.text('sohbet.ps1'))
    def test_windows_amd64_guard_is_enforced_at_entrypoints(self):
        shared=self.text('program-ortak.ps1');self.assertIn('function Assert-SupportedPlatform',shared);self.assertIn("$arch -ne 'AMD64'",shared)
        for name in ('python-kur.ps1','node-kur.ps1','pnpm-kur.ps1','powerbi-mcp-kur.ps1','sohbet.ps1'):
            with self.subTest(name=name):self.assertIn('Assert-SupportedPlatform',self.text(name))
    def test_apply_requires_confirmation_and_plan_exposes_effects(self):
        core=self.text('core.ps1');chat=self.text('sohbet.ps1')
        self.assertIn('if(-not $Confirmed)',core);self.assertIn('global_effects=$globalEffects',core)
        self.assertIn('effects=$effects',core);self.assertIn("action='downgrade'",core)
        self.assertIn('[switch]$ConfirmApply',chat);self.assertIn('([bool]$ConfirmApply)',chat)
    def test_operational_reference_files_are_bound_to_code_fingerprint(self):
        core=self.text('core.ps1')
        self.assertIn("$rel -like 'references\\*'",core);self.assertIn("$rel -like 'scripts\\*'",core)
        self.assertIn("'BUILD.json'",core);self.assertIn("'agents\\openai.yaml'",core)
    def test_no_automatic_global_upgrade_or_eula(self):
        for name in ('python-kur.ps1','node-kur.ps1','pnpm-kur.ps1'):
            self.assertNotIn('--accept-package-agreements',self.text(name));self.assertNotIn('InstallAllUsers=1',self.text(name))

if __name__=='__main__':unittest.main()