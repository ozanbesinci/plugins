"""Missing-dependency fault matrix and real Windows skill startup/resume tests."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from uuid import uuid4
import test_context as fixtures
from sozlesme_cekirdek.skill_metadata import skill_metadata
from sozlesme_cekirdek.workflows import evaluate, catalog

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('contract_runtime',ROOT/'scripts/runtime_kontrol.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

def fake_probe(ready=False):
    return {'status':'READY' if ready else 'DEPENDENCIES_REQUIRED','python':sys.executable,
        'runtime_ok':True,'packages':[{'name':'duckdb','status':'PASS' if ready else 'MISSING'}],
        'pdf':{'status':'PASS' if ready else 'DEFERRED','installed':ready},'pins_sha256':runtime.pin_hash()}

def resolution():
    return [{'metadata':{'name':name,'version':version},'download_info':{
        'url':'https://files.pythonhosted.org/packages/'+name+'.whl','archive_info':{'hashes':{'sha256':'a'*64}}}}
        for name,version in runtime.requirements().items()]

class RuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        short=ROOT/'tests/.runtime';short.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='runtime-',dir=short)
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.environment=patch.dict(os.environ,{},clear=False);self.environment.start();self.addCleanup(self.environment.stop)

    def test_updater_exact_230_all_upstream_hashes_match(self):
        runtime.verify_upstream()
        self.assertEqual('2.3.0',skill_metadata('guncelleyici')['version'])

    def test_all_31_visible_messages_use_real_name_version_author(self):
        for skill in list(catalog())+['guncelleyici']:
            meta=skill_metadata(skill)
            self.assertIn(meta['name']+' skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir.',meta['startup_message'])
            self.assertIn('Sürüm: '+meta['version'],meta['startup_message'])
            self.assertNotIn('...',meta['startup_message'])
            text=(ROOT/'skills'/meta['slug']/'SKILL.md').read_text(encoding='utf-8')
            self.assertIn(meta['startup_message'],text)

    def test_exact_thirteen_pinned_wheels_and_hashes_are_validated(self):
        self.assertEqual(13,len(runtime.validate_resolution(resolution(),runtime.requirements())))

    def test_long_windows_environment_path_blocks_before_mutation(self):
        with self.assertRaises(ValueError):runtime.validate_env_path(self.directory/('verylong'*40))
        runtime.validate_env_path(self.directory/'env')

    def test_mirror_http_credentials_unhashed_wrong_or_missing_wheel_blocks(self):
        for mutated in ('host','http','credentials','hash','version','missing','duplicate','source'):
            data=resolution()
            if mutated=='host': data[0]['download_info']['url']='https://evil.example/duckdb.whl'
            elif mutated=='http': data[0]['download_info']['url']='http://files.pythonhosted.org/duckdb.whl'
            elif mutated=='credentials': data[0]['download_info']['url']='https://user:secret@files.pythonhosted.org/duckdb.whl'
            elif mutated=='hash': data[0]['download_info']['archive_info']['hashes']['sha256']='fake'
            elif mutated=='version': data[0]['metadata']['version']='1.0.0'
            elif mutated=='missing': data.pop()
            elif mutated=='duplicate': data.append(data[0])
            else: data[0]['download_info']['url']='https://files.pythonhosted.org/duckdb.tar.gz'
            with self.subTest(mutated=mutated),self.assertRaises(ValueError):runtime.validate_resolution(data,runtime.requirements())

    def test_already_ready_does_not_create_environment_or_install(self):
        with patch.object(runtime,'probe',return_value=fake_probe(True)),patch.object(runtime.venv,'EnvBuilder') as env,patch.object(runtime,'child_json') as child:
            result=runtime.install_missing(self.directory)
        self.assertEqual('UNCHANGED',result['installation']);env.assert_not_called();child.assert_not_called()

    def test_missing_dependencies_get_new_private_environment_then_verified_pointer(self):
        with patch.object(runtime,'probe',return_value=fake_probe()),patch.object(runtime.venv,'EnvBuilder') as env,patch.object(runtime,'install_packages',return_value={}) as packages,patch.object(runtime,'child_json',side_effect=[{'status':'INSTALLED'},fake_probe(True)]):
            result=runtime.install_missing(self.directory)
        self.assertEqual('INSTALLED',result['installation'])
        python=packages.call_args.args[0]
        self.assertTrue(python.is_relative_to(self.directory/'environments'))
        self.assertFalse(env.call_args.kwargs['clear'])
        self.assertEqual(str(python),json.loads((self.directory/'active-runtime.json').read_text())['python'])
        self.assertFalse((self.directory/'active-install.json').exists())

    def test_pdf_only_missing_keeps_existing_packages_and_interpreter(self):
        before=fake_probe(True);before['status']='DEPENDENCIES_REQUIRED';before['pdf']={'status':'MISSING','installed':False}
        with patch.object(runtime,'probe',return_value=before),patch.object(runtime.venv,'EnvBuilder') as env,patch.object(runtime,'install_packages') as packages,patch.object(runtime,'child_json',side_effect=[{'status':'INSTALLED'},fake_probe(True)]):
            runtime.install_missing(self.directory)
        env.assert_not_called();packages.assert_not_called()
        self.assertEqual('REGISTERED_RUNTIME',json.loads((self.directory/'active-runtime.json').read_text())['mode'])

    def test_install_failure_preserves_journal_and_never_marks_ready(self):
        with patch.object(runtime,'probe',return_value=fake_probe()),patch.object(runtime.venv,'EnvBuilder'),patch.object(runtime,'install_packages',side_effect=ValueError('pip failure')):
            with self.assertRaises(ValueError): runtime.install_missing(self.directory)
        self.assertTrue((self.directory/'active-install.json').is_file());self.assertFalse((self.directory/'active-runtime.json').exists())
        with patch.object(runtime,'probe') as probe,self.assertRaises(ValueError):runtime.install_missing(self.directory)
        probe.assert_not_called()

    def test_failed_post_install_probe_blocks_selection_and_replay(self):
        with patch.object(runtime,'probe',return_value=fake_probe()),patch.object(runtime.venv,'EnvBuilder'),patch.object(runtime,'install_packages',return_value={}),patch.object(runtime,'child_json',side_effect=[{'status':'INSTALLED'},fake_probe()]):
            with self.assertRaises(ValueError): runtime.install_missing(self.directory)
        self.assertTrue((self.directory/'active-install.json').exists());self.assertFalse((self.directory/'active-runtime.json').exists())

    def test_existing_broken_pdf_is_not_repaired_or_overwritten(self):
        with patch.object(runtime,'pdf_probe',return_value={'status':'BROKEN','installed':True}),patch.object(runtime,'load_updater') as load:
            load.return_value.prepare=MagicMock()
            with self.assertRaises(ValueError):runtime.install_pdf(self.directory)
            load.return_value.prepare.assert_not_called()

    def test_pdf_appearing_after_plan_prevents_write(self):
        fake=MagicMock()
        fake.prepare.return_value={'local':{'binary':None},'target':{'sha256':'a'*64}}
        fake.worker_request.return_value={'binary':'new-other-extension'}
        with patch.object(runtime,'pdf_probe',return_value={'status':'MISSING','installed':False}),patch.object(runtime,'load_updater',return_value=fake):
            with self.assertRaises(ValueError):runtime.install_pdf(self.directory)
        fake.apply.assert_not_called()

    def test_child_nonzero_never_returns_ready_even_if_json_says_ready(self):
        failed=subprocess.CompletedProcess([],2,'@@SONUC {"status":"READY"}','')
        with patch.object(runtime.subprocess,'run',return_value=failed),self.assertRaises(ValueError):runtime.child_json(sys.executable,'probe')

class NativeStartupTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp;rev=fixtures.ContextTests.rev;document=fixtures.ContextTests.document
    spec=fixtures.ContextTests.spec;node=fixtures.ContextTests.node;register=fixtures.ContextTests.register

    def gate(self,*args,arch=...):
        env=dict(os.environ)
        if arch is None:env.pop('PROCESSOR_ARCHITECTURE',None)
        elif arch is not ...:env['PROCESSOR_ARCHITECTURE']=arch
        tmp=self.area/'gate-temp';tmp.mkdir(exist_ok=True)
        env['TEMP']=str(tmp);env['TMP']=str(tmp)
        return subprocess.run(['powershell.exe','-NoProfile','-File',str(ROOT/'scripts/beceri-baslat.ps1'),*map(str,args)],capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,timeout=120)

    def request(self):
        data={'request_id':str(uuid4()),'case_id':self.case,'skill_id':'K03','intent':'Sentetik sohbet incelemesi',
            'context_version':self.rev(),'selected_versions':[self.version],'root_ids':[],
            'max_context_bytes':65536,'policy_version':'1','requested_output':'CHAT'}
        path=self.sources/'request.json';path.write_text(json.dumps(data),encoding='utf-8');return path,data

    def run_args(self,path):
        return ['-Action','run','-SkillId','K03','-RequestFile',path,'-Workspace',self.store.root,
                '-OutputRoot',self.store.output_root,'-SourceRoot',self.sources,'-RuntimeStateRoot',self.area/'runtime']

    def test_actual_windows_prepare_is_ready_and_visible_without_installation(self):
        result=self.gate('-Action','prepare','-SkillId','K23','-RuntimeStateRoot',self.area/'runtime')
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        self.assertIn(skill_metadata('K23')['startup_message'],result.stdout)
        final=json.loads([x[8:] for x in result.stdout.splitlines() if x.startswith('@@SONUC ')][-1])
        self.assertEqual('READY',final['status']);self.assertTrue(final['resume_allowed'])
        self.assertTrue(all(p['status']=='PASS' for p in final['runtime']['packages']))

    def test_prepare_without_architecture_variable_reads_it_from_the_os(self):
        # CR-16: Codex sandbox starts PowerShell without PROCESSOR_ARCHITECTURE; prepare was BLOCKED "mimari: ".
        result=self.gate('-Action','prepare','-SkillId','K23','-RuntimeStateRoot',self.area/'runtime',arch=None)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        final=json.loads([x[8:] for x in result.stdout.splitlines() if x.startswith('@@SONUC ')][-1])
        self.assertEqual('READY',final['status'])

    def test_existing_architecture_value_is_never_overridden(self):
        result=self.gate('-Action','prepare','-SkillId','K23','-RuntimeStateRoot',self.area/'runtime',arch='ARM64')
        final=json.loads([x[8:] for x in result.stdout.splitlines() if x.startswith('@@SONUC ')][-1])
        self.assertEqual('BLOCKED',final['status']);self.assertIn('ARM64',final['message'])

    def test_actual_run_same_request_hash_and_one_use_then_no_replay(self):
        path,data=self.request();before=path.read_bytes()
        result=self.gate(*self.run_args(path))
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        final=json.loads([x[8:] for x in result.stdout.splitlines() if x.startswith('@@SONUC ')][-1])
        self.assertEqual('COMPLETED',final['status']);self.assertEqual(before,path.read_bytes())
        skill_result=final['result']['result'];self.assertTrue(skill_result['chat_response'].startswith(skill_metadata('K03')['startup_message']))
        receipt=self.area/'runtime/requests'/f"{data['request_id']}.json"
        self.assertEqual('STARTED',json.loads(receipt.read_text(encoding='utf-8'))['status'])
        terminal=receipt.with_name(f"{data['request_id']}.final.json")
        self.assertEqual('COMPLETED',json.loads(terminal.read_text(encoding='utf-8'))['status'])
        self.assertEqual('NOT_GRANTED',json.loads(terminal.read_text(encoding='utf-8'))['business_acceptance'])
        replay=self.gate(*self.run_args(path));self.assertEqual(2,replay.returncode)
        self.assertIn('"resume_allowed":false',replay.stdout)

    def test_actual_changed_case_after_request_is_blocked_without_replay(self):
        path,data=self.request()
        self.store.add_statement(self.case,'Yeni bilgi',expected_revision=self.rev())
        result=self.gate(*self.run_args(path));self.assertEqual(2,result.returncode,result.stdout+result.stderr)
        self.assertIn('"resume_allowed":false',result.stdout)
        receipt=self.area/'runtime/requests'/f"{data['request_id']}.json"
        self.assertEqual('STARTED',json.loads(receipt.read_text(encoding='utf-8'))['status'])

    def test_actual_wrong_skill_request_and_outside_root_block_before_probe(self):
        path,data=self.request();data['skill_id']='K28';path.write_text(json.dumps(data),encoding='utf-8')
        result=self.gate(*self.run_args(path));self.assertEqual(2,result.returncode)
        self.assertIn('Request id/skill mismatch',result.stdout)
        data['skill_id']='K03';path.write_text(json.dumps(data),encoding='utf-8')
        outside=self.area/'outside.json';outside.write_bytes(path.read_bytes())
        result=self.gate(*self.run_args(outside));self.assertEqual(2,result.returncode)
        self.assertIn('Request outside allowed source roots',result.stdout)

    def test_actual_unfinished_install_blocks_skill_even_if_dependencies_ready(self):
        state=self.area/'runtime';state.mkdir();(state/'active-install.json').write_text('{}')
        result=self.gate('-Action','prepare','-SkillId','K23','-RuntimeStateRoot',state)
        self.assertEqual(2,result.returncode);self.assertIn('Unfinished runtime transaction',result.stdout)

    def test_actual_powershell_request_mutation_is_detected(self):
        path,data=self.request();tmp=self.area/'gate-temp';tmp.mkdir()
        env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp))
        quote=lambda p:"'"+str(p).replace("'","''")+"'"
        code=f". {quote(ROOT/'scripts/beceri-baslat.ps1')} -SkillId K03 -LibraryOnly; $f=Get-ContractRequest {quote(path)} @({quote(self.sources)}) K03; [IO.File]::AppendAllText({quote(path)},' '); try{{Test-ContractRequestCurrent $f; exit 9}}catch{{exit 0}}"
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',code],capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    def test_actual_nonzero_dependency_result_blocks_even_if_json_claims_ready(self):
        tmp=self.area/'gate-temp';tmp.mkdir()
        env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp))
        quote=lambda p:"'"+str(p).replace("'","''")+"'"
        code=f". {quote(ROOT/'scripts/beceri-baslat.ps1')} -SkillId K03 -LibraryOnly; try{{Assert-ContractResult ([pscustomobject]@{{status='READY';process_exit_code=2;message='installation-failed'}}); exit 9}}catch{{if($_.Exception.Message -eq 'installation-failed'){{exit 0}}else{{exit 8}}}}"
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',code],capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
