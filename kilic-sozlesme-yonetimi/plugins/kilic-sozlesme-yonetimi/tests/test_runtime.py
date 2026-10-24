"""Read-only runtime policy and real isolated Windows installer/Work entry tests."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import test_context as fixtures
from sozlesme_cekirdek.skill_metadata import skill_metadata
from sozlesme_cekirdek.workflows import catalog
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import runtime_registry as runtime
import runtime_launcher as launcher

class RuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="cs-policy-")
        self.addCleanup(self.temp.cleanup);self.area=Path(self.temp.name).resolve()
        self.env=patch.dict(os.environ,{"USERPROFILE":str(self.area)});self.env.start();self.addCleanup(self.env.stop)

    def test_all_30_visible_messages_use_real_name_version_author(self):
        self.assertEqual(30,len(catalog()))
        for skill in catalog():
            meta=skill_metadata(skill)
            self.assertIn(meta["name"]+" skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir.",meta["startup_message"])
            self.assertIn("Sürüm: "+meta["version"],meta["startup_message"])
            self.assertIn(meta["startup_message"],(ROOT/"skills"/meta["slug"]/"SKILL.md").read_text(encoding="utf-8"))

    def test_exact_thirteen_pins_and_profile_lock_match(self):
        self.assertEqual(13,len(runtime.requirements()))
        self.assertEqual(runtime.requirements(),runtime.profile()["packages"])
        self.assertEqual([3,14,8],runtime.profile()["python_version"])
        self.assertEqual("OPTIONAL_NOT_REQUIRED",runtime.probe()["pdf_extension"])

    def test_missing_runtime_never_creates_or_installs_anything(self):
        with self.assertRaises(runtime.RuntimeErrorDetail) as found:runtime.current()
        self.assertEqual("SETUP_REQUIRED",found.exception.code)
        self.assertFalse((self.area/"KilicPython").exists())

    def test_duplicate_registry_keys_are_rejected(self):
        path=self.area/"duplicate.json";path.write_text('{"schema":"a","schema":"b"}')
        with self.assertRaises(ValueError):runtime.read_json(path)

    def test_wrong_profile_record_blocks_without_mutation(self):
        home=runtime.user_root();home.mkdir()
        path=home/"sozlesme-runtime.json";path.write_text('{"schema":"unknown"}')
        before=path.read_bytes()
        with self.assertRaises(runtime.RuntimeErrorDetail):runtime.current()
        self.assertEqual(before,path.read_bytes())

    def test_developer_mode_is_explicit_and_cannot_claim_acceptance(self):
        with patch.dict(os.environ,{"SOZLESME_DEVELOPMENT":"1"}):
            result=runtime.entry_gate()
        self.assertEqual("DEVELOPMENT",result["execution_profile"])
        self.assertEqual("NOT_GRANTED",result["business_acceptance"])

    def test_state_override_cannot_change_canonical_claim_location(self):
        roots=launcher.state_roots(self.area/"legacy")
        self.assertEqual(runtime.user_root()/"sozlesme-state",roots[0])
        self.assertIn(self.area/"legacy",roots)

    def request(self):
        path=self.area/"request.json";identifier=str(uuid4())
        path.write_text(json.dumps({"request_id":identifier,"skill_id":"K03"}))
        args=type("Args",(),{"request":str(path),"skill":"K03","source_root":[str(self.area)],
             "workspace":str(self.area/"case"),"output_root":str(self.area/"output"),"state_root":None})()
        return args,path,identifier

    def test_child_failure_preserves_claim_and_prevents_retry(self):
        args,path,identifier=self.request()
        with patch.object(launcher,"run_core",side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):launcher.request_run(args,{"runtime_id":"a"*32,"lock_sha256":"b"*64})
        claim=runtime.user_root()/"sozlesme-state/requests"/(identifier+".json")
        self.assertTrue(claim.is_file());self.assertFalse(claim.with_name(identifier+".final.json").exists())
        with patch.object(launcher,"run_core") as child:
            with self.assertRaises(runtime.RuntimeErrorDetail):launcher.request_run(args,{"runtime_id":"a"*32,"lock_sha256":"b"*64})
            child.assert_not_called()

    def test_legacy_record_blocks_even_with_new_state_override(self):
        args,path,identifier=self.request()
        args.state_root=str(self.area/"old-state")
        ledger=Path(args.state_root)/"requests";ledger.mkdir(parents=True)
        (ledger/(identifier+".json")).write_text("{}")
        with patch.object(launcher,"run_core") as child:
            with self.assertRaises(runtime.RuntimeErrorDetail) as failure:launcher.request_run(args,{"runtime_id":"a"*32,"lock_sha256":"b"*64})
            self.assertEqual("RECOVERY_REQUIRED",failure.exception.code);child.assert_not_called()
        self.assertFalse((runtime.user_root()/"sozlesme-state").exists())

    def test_same_bound_core_claim_is_consumed_only_once(self):
        args,path,identifier=self.request()
        ledger=runtime.user_root()/"sozlesme-state/requests";ledger.mkdir(parents=True)
        claim=ledger/(identifier+".json")
        claim.write_text(json.dumps({"schema":"contract-request-claim/v1","status":"STARTED","request_id":identifier,
            "request_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"skill_id":"K03","runtime_id":"a"*32,
            "workspace":args.workspace,"output_root":args.output_root,"source_roots":args.source_root}))
        data=json.loads(path.read_text())
        with patch.dict(os.environ,{"SOZLESME_REQUEST_CLAIM":str(claim)}):
            runtime.claim_execution(path,data,{"runtime_id":"a"*32},args.workspace,args.output_root,args.source_root)
            with self.assertRaises(FileExistsError):runtime.claim_execution(path,data,{"runtime_id":"a"*32},args.workspace,args.output_root,args.source_root)

    def test_request_change_is_rejected_before_core_claim_consumption(self):
        args,path,identifier=self.request()
        ledger=runtime.user_root()/"sozlesme-state/requests";ledger.mkdir(parents=True)
        claim=ledger/(identifier+".json")
        claim.write_text(json.dumps({"schema":"contract-request-claim/v1","status":"STARTED","request_id":identifier,
            "request_sha256":"0"*64,"skill_id":"K03","runtime_id":"a"*32,
            "workspace":args.workspace,"output_root":args.output_root,"source_roots":args.source_root}))
        with patch.dict(os.environ,{"SOZLESME_REQUEST_CLAIM":str(claim)}):
            with self.assertRaises(runtime.RuntimeErrorDetail):runtime.claim_execution(path,json.loads(path.read_text()),{"runtime_id":"a"*32},args.workspace,args.output_root,args.source_root)
        self.assertFalse((ledger/(identifier+".invoked")).exists())

class NativeStartupTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp;rev=fixtures.ContextTests.rev;document=fixtures.ContextTests.document
    spec=fixtures.ContextTests.spec;node=fixtures.ContextTests.node;register=fixtures.ContextTests.register

    @classmethod
    def setUpClass(cls):
        installer=os.environ.get("SOZLESME_TEST_INSTALLER")
        if not installer:raise unittest.SkipTest("NOT_RUN: explicit built installer path required")
        cls.installer=Path(installer);cls.profile_temp=tempfile.TemporaryDirectory(prefix="csw-")
        cls.addClassCleanup(cls.profile_temp.cleanup)
        cls.profile=Path(cls.profile_temp.name).resolve()
        cls.native_env=dict(os.environ,USERPROFILE=str(cls.profile),PATH=str(Path(os.environ["SystemRoot"])/"System32"))
        cls.native_env.pop("SOZLESME_DEVELOPMENT",None)
        process=subprocess.run([str(cls.installer),"--quiet"],env=cls.native_env,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=300)
        logs="\n".join(p.read_text(encoding="utf-8")[-5000:] for p in cls.profile.rglob("verification.log"))
        if process.returncode:raise AssertionError(process.stderr+"\n"+logs)
        cls.entry=cls.profile/"KilicPython/launcher/sozlesme.exe"

    def gate(self,*args,env=None):
        return subprocess.run([str(self.entry),"--plugin-root",str(ROOT),*map(str,args)],env=env or self.native_env,
            capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120)

    def request(self):
        data={"request_id":str(uuid4()),"case_id":self.case,"skill_id":"K03","intent":"Sentetik sohbet incelemesi",
            "context_version":self.rev(),"selected_versions":[self.version],"root_ids":[],
            "max_context_bytes":65536,"policy_version":"1","requested_output":"CHAT"}
        path=self.sources/"request.json";path.write_text(json.dumps(data),encoding="utf-8");return path,data

    def run_args(self,path):
        return ["run","--skill","K03","--request",path,"--workspace",self.store.root,
                "--output-root",self.store.output_root,"--source-root",self.sources,"--state-root",self.area/"legacy"]

    def final(self,result):
        lines=[x[8:] for x in result.stdout.splitlines() if x.startswith("@@SONUC ")]
        self.assertTrue(lines,result.stdout+result.stderr)
        return json.loads(lines[-1])

    def test_actual_windows_prepare_is_ready_and_visible_without_installation(self):
        result=self.gate("prepare","--skill","K23")
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        final=self.final(result);self.assertEqual("READY",final["status"]);self.assertTrue(final["resume_allowed"])
        self.assertEqual("REGISTERED",final["execution_profile"])
        self.assertTrue(all(p["status"]=="PASS" for p in final["packages"]))
        self.assertIn(skill_metadata("K23")["startup_message"],result.stdout)

    def test_actual_installer_reentry_keeps_runtime_id_and_no_extra_environment(self):
        record=self.profile/"KilicPython/sozlesme-runtime.json";before=record.read_bytes()
        process=subprocess.run([str(self.installer),"--quiet"],env=self.native_env,capture_output=True,timeout=180)
        self.assertEqual(0,process.returncode,process.stderr);self.assertEqual(before,record.read_bytes())
        self.assertEqual(1,len(list((self.profile/"KilicPython/sozlesme-envs").iterdir())))

    def test_missing_profile_blocks_native_entry_without_case_creation(self):
        profile=self.area/"empty-profile";profile.mkdir()
        result=self.gate("prepare","--skill","K23",env=dict(self.native_env,USERPROFILE=str(profile)))
        self.assertEqual(2,result.returncode);self.assertEqual("SETUP_REQUIRED",self.final(result)["error"])
        self.assertFalse((profile/"KilicPython").exists())

    def test_native_runtime_tamper_is_rejected_before_execution(self):
        record=json.loads((self.profile/"KilicPython/sozlesme-runtime.json").read_text())
        code=Path(record["environment_root"])/"setup_runtime.py";before=code.read_bytes()
        try:
            code.write_bytes(before+b"\n# synthetic tamper")
            result=self.gate("prepare","--skill","K23")
            self.assertEqual(2,result.returncode);self.assertIn("REPAIR_REQUIRED",result.stdout)
        finally:code.write_bytes(before)

    def test_actual_run_same_request_hash_and_one_use_then_no_replay(self):
        path,data=self.request();before=path.read_bytes()
        result=self.gate(*self.run_args(path));self.assertEqual(0,result.returncode,result.stdout+result.stderr)
        final=self.final(result);self.assertEqual("COMPLETED",final["status"]);self.assertEqual(before,path.read_bytes())
        self.assertEqual("REGISTERED",final["result"]["components"]["execution_profile"])
        self.assertTrue(final["result"]["result"]["chat_response"].startswith(skill_metadata("K03")["startup_message"]))
        receipt=self.profile/"KilicPython/sozlesme-state/requests"/(data["request_id"]+".json")
        self.assertEqual("STARTED",json.loads(receipt.read_text())["status"])
        terminal=receipt.with_name(data["request_id"]+".final.json")
        self.assertEqual("NOT_GRANTED",json.loads(terminal.read_text(encoding="utf-8"))["business_acceptance"])
        replay=self.gate(*self.run_args(path));self.assertEqual(2,replay.returncode);self.assertFalse(self.final(replay)["resume_allowed"])

    def test_unlisted_python_file_blocks_native_entry(self):
        record=json.loads((self.profile/"KilicPython/sozlesme-runtime.json").read_text(encoding="utf-8"))
        extra=Path(record["environment_root"])/"Lib/site-packages/unlisted_synthetic.py"
        try:
            extra.write_text("raise RuntimeError('must not import')",encoding="utf-8")
            result=self.gate("prepare","--skill","K23")
            self.assertEqual(2,result.returncode);self.assertIn("REPAIR_REQUIRED",result.stdout)
        finally:extra.unlink(missing_ok=True)

    def test_actual_changed_case_after_request_is_blocked_without_replay(self):
        path,data=self.request();self.store.add_statement(self.case,"Yeni bilgi",expected_revision=self.rev())
        result=self.gate(*self.run_args(path));self.assertEqual(2,result.returncode,result.stdout+result.stderr)
        self.assertFalse(self.final(result)["resume_allowed"])

    def test_actual_wrong_skill_request_and_outside_root_block(self):
        path,data=self.request();data["skill_id"]="K28";path.write_text(json.dumps(data))
        result=self.gate(*self.run_args(path));self.assertEqual(2,result.returncode);self.assertIn("Request id/skill mismatch",result.stdout)
        data["skill_id"]="K03";path.write_text(json.dumps(data))
        outside=self.area/"outside.json";outside.write_bytes(path.read_bytes())
        result=self.gate(*self.run_args(outside));self.assertEqual(2,result.returncode);self.assertIn("Request outside allowed source roots",result.stdout)

    def test_actual_unfinished_install_blocks_skill_even_if_dependencies_ready(self):
        state=self.area/"legacy";state.mkdir();(state/"active-install.json").write_text("{}")
        result=self.gate("prepare","--skill","K23","--state-root",state)
        self.assertEqual(2,result.returncode);self.assertIn("Unfinished runtime transaction",result.stdout)

    def test_cli_cannot_bypass_request_claim(self):
        result=self.gate("cli","--","skill-evaluate")
        self.assertEqual(2,result.returncode);self.assertEqual("REQUEST_ENTRY_REQUIRED",self.final(result)["error"])

    def test_cli_and_direct_wrapper_bind_the_same_registered_runtime(self):
        args=["--workspace",str(self.area/"new-case"),"--output-root",str(self.area),"--source-root",str(self.sources),"case-create","--title","synthetic"]
        good=self.gate("cli","--",*args)
        self.assertEqual(0,good.returncode,good.stdout+good.stderr)
        self.assertEqual("REGISTERED",json.loads(good.stdout)["components"]["execution_profile"])
        bad=subprocess.run([sys.executable,"-B",str(ROOT/"scripts/contract_cli.py"),*args],env=self.native_env,capture_output=True,text=True,encoding="utf-8",timeout=60)
        self.assertEqual(2,bad.returncode);self.assertIn("RUNTIME_MISMATCH",bad.stdout)
