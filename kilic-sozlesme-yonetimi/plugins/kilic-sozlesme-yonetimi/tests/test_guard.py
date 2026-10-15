import copy
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import duckdb
from sozlesme_cekirdek import Store, CoreError
from sozlesme_cekirdek.guard import SyntheticGuardRuntime, payload_digest, action_request, TestQA
from sozlesme_cekirdek.safety import canonical, hash_file, hash_value
from guard_fixtures import Backend, Clock, Host, KEY, request
from reader_fixtures import docx_bytes

ROOT = Path(__file__).resolve().parents[1]


def execution_worker(area, case, req, permission, barrier, queue, *, crash=False):
    def phase(name):
        if crash:
            with (Path(area)/"worker-phases.jsonl").open("a",encoding="utf-8") as stream:
                stream.write(json.dumps({"phase":name,"pid":os.getpid()})+"\n");stream.flush();os.fsync(stream.fileno())
    phase("TARGET_ENTERED")
    # Replay atomicity has a separate scope from the product's 5s busy policy.
    store = Store(Path(area) / "work", source_roots=[Path(area) / "sources"], output_root=area, lock_timeout=60)
    phase("STORE_OPENED")
    host, backend = Host(case), Backend(Path(area) / "prepare.log")
    host.authorize(req)
    backend.crash_after_prepare = crash
    backend.phase_log = Path(area)/"worker-phases.jsonl" if crash else None
    runtime = SyntheticGuardRuntime(store, identity_provider=host, backend=backend, signing_key=KEY, clock=Clock())
    if barrier:
        barrier.wait(90)
    phase("BEFORE_EXECUTE")
    result = runtime.execute(request=req, permission_id=permission)
    if queue:
        queue.put(result)


class GuardTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / "tests" / ".runtime"
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="muhafız-İı-", dir=root)
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.sources = self.area / "sources"
        self.sources.mkdir()
        self.path = self.sources / "Sentetik kaynak İı.txt"
        self.path.write_text("Sentetik hüküm, hiçbir şirket kuralı içermez. İ ı.", encoding="utf-8")
        self.sha = hash_file(self.path)
        self.store = Store(self.area / "work", source_roots=[self.sources], output_root=self.area)
        self.case = self.store.create_case("Sentetik P4")
        self.doc = self.store.create_document(self.case, "Sentetik", expected_revision=0)
        self.version = self.store.ingest(self.case, self.doc, self.path, expected_revision=self.rev())["version_id"]
        self.host, self.backend, self.clock = Host(self.case), Backend(), Clock()
        self.runtime = SyntheticGuardRuntime(self.store, identity_provider=self.host, backend=self.backend, signing_key=KEY, clock=self.clock)
        self.req = request(self.case, self.version, self.sha)

    def rev(self):
        return self.store.case_revision(self.case)
    def error(self, code, fn):
        with self.assertRaises(CoreError) as caught:
            fn()
        self.assertEqual(code, caught.exception.code)
    def issue(self, req=None, **kwargs):
        req = req or self.req
        self.host.authorize(req)
        return self.runtime.issue_permission(request=req, expected_revision=self.rev(), **kwargs)["permission_id"]
    def execute(self, permission, req=None):
        return self.runtime.execute(request=req or self.req, permission_id=permission)
    def no_output(self, req=None):
        req = req or self.req
        self.assertFalse((self.store.root / req["plan"]["parameters"].get("target_relative_path", "no-file")).exists())

    def test_agent_default_is_blocked_without_production_adapters(self):
        result = self.store.evaluate_action(request=self.req)
        self.assertEqual("BLOCK", result["decision"])
        self.assertIn("CONFIG_REQUIRED", result["reasons"])
        self.assertEqual("DISABLED", result["execution_scope"])
        self.assertEqual(0, self.backend.prepared)
        self.no_output()

    def test_four_decisions_keep_user_permission_and_corporate_authority_separate(self):
        self.assertEqual("REQUIRE_CONFIRMATION", self.runtime.evaluate(request=self.req)["decision"])
        self.host.authorize(self.req)
        self.assertEqual("ALLOW", self.runtime.evaluate(request=self.req)["decision"])
        mail = copy.deepcopy(self.req)
        mail["plan"]["purpose"] = "APPROVED_OUTPUT"
        self.host.authorize(mail)
        self.host.identity = replace(self.host.identity, corporate_authorized=False)
        self.assertEqual("ESCALATE", self.runtime.evaluate(request=mail)["decision"])
        self.host.identity = replace(self.host.identity, authenticated=False)
        self.assertEqual("BLOCK", self.runtime.evaluate(request=mail)["decision"])

    def test_explicit_trusted_request_does_not_require_a_second_confirmation(self):
        permission = self.issue()
        result = self.execute(permission)
        self.assertEqual("SIMULATION_COMMITTED", result["state"])
        self.assertEqual(1, self.backend.prepared)
        self.assertEqual(self.sha, hash_file(self.path))
        self.assertFalse(result["production_ready"])
        gate = self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])
        self.assertEqual("ALLOW", gate["decision"])
        self.assertEqual("NOT_VERIFIED_FOR_PRODUCTION", gate["authority"])

    def test_permission_issue_is_idempotent_without_semantic_feedback(self):
        permission = self.issue()
        revision = self.rev()
        duplicate = self.runtime.issue_permission(request=self.req, expected_revision=revision)
        self.assertEqual(permission, duplicate["permission_id"])
        self.assertTrue(duplicate["reused"])
        self.assertEqual(revision, self.rev())

    def test_model_cannot_mint_permissions_or_quality_via_json(self):
        for extra in [{"approved": True}, {"permission_id": str(uuid4())}, {"quality_ready": True}, {"corporate_authority": "VERIFIED"}]:
            bad = dict(self.req, **extra)
            self.assertEqual("BLOCK", self.runtime.evaluate(request=bad)["decision"])
            self.error("SEMA_HATASI", lambda: self.runtime.issue_permission(request=bad, expected_revision=self.rev()))
        with self.store._db() as db:
            self.assertEqual(0, db.execute("SELECT count(*) FROM islem_izinleri").fetchone()[0])

    def test_absolute_prohibitions_cannot_be_user_authorized(self):
        for action in ["SIGN_CONTRACT", "INITIATE_PAYMENT", "RELEASE_GUARANTEE", "ACCEPT_RISK", "APPROVE_AS_LEGAL", "OVERWRITE_SOURCE"]:
            bad = copy.deepcopy(self.req)
            bad["plan"]["action_type"] = action
            result = self.runtime.evaluate(request=bad)
            self.assertEqual(["ABSOLUTE_PROHIBITION"], result["reasons"])
            self.assertEqual("BLOCK", result["decision"])

    def test_source_change_after_permission_prevents_prepare(self):
        permission = self.issue()
        self.path.write_text("Değişmiş kaynak", encoding="utf-8")
        result = self.execute(permission)
        self.assertEqual("BLOCKED", result["state"])
        self.assertIn("KAYNAK_GUNCEL_DEGIL", result["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)
        self.no_output()

    def test_actor_policy_backend_epoch_changes_invalidate_old_scope(self):
        permission = self.issue()
        self.host.identity = replace(self.host.identity, identity_epoch="revoked-epoch")
        self.assertIn("IZIN_KAPSAMI_DEGISTI", self.execute(permission)["decision"]["reasons"])
        self.host.identity = replace(self.host.identity, identity_epoch="test-identity-1", policy_version="policy-2")
        self.assertIn("IZIN_KAPSAMI_DEGISTI", self.execute(permission)["decision"]["reasons"])
        self.host.identity = replace(self.host.identity, policy_version="test-policy-1")
        self.backend.version = "changed-backend"
        self.assertIn("IZIN_KAPSAMI_DEGISTI", self.execute(permission)["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)

    def test_case_semantic_change_requires_fresh_scope(self):
        permission = self.issue()
        self.store.add_statement(self.case, "Ticari mutabakat değişti", expected_revision=self.rev())
        self.assertIn("IZIN_KAPSAMI_DEGISTI", self.execute(permission)["decision"]["reasons"])
        self.no_output()



    def test_expiry_and_revocation_prevent_writes_and_automatic_renewal(self):
        permission = self.issue(ttl_seconds=1)
        self.clock.value += timedelta(seconds=2)
        self.assertIn("IZIN_SURESI", self.execute(permission)["decision"]["reasons"])
        self.error("YENI_ISLEM_GEREKLI", lambda: self.runtime.issue_permission(request=self.req, expected_revision=self.rev()))
        self.clock.value -= timedelta(seconds=2)
        self.runtime.revoke_permission(self.case, permission)
        self.assertIn("IZIN_TUKETILMIS", self.execute(permission)["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)

    def test_expiry_during_preparation_blocks_final_publish(self):
        permission = self.issue(ttl_seconds=1)
        self.backend.on_prepare = lambda: setattr(self.clock, "value", self.clock.value + timedelta(seconds=2))
        result = self.execute(permission)
        self.assertEqual("FAILED", result["state"])
        self.assertIn("IZIN_SURESI", result["decision"]["reasons"])
        self.no_output()

    def test_signed_permission_body_and_state_tampering_is_detected(self):
        permission = self.issue()
        with self.store._db() as db:
            body = json.loads(db.execute("SELECT payload FROM islem_izinleri WHERE record_id=?", [permission]).fetchone()[0])
            body["actor_id"] = "model-forged-actor"
            db.execute("UPDATE islem_izinleri SET payload=? WHERE record_id=?", [canonical(body), permission])
        result = self.execute(permission)
        self.assertIn("IZIN_BOZUK", result["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)

    def test_hmac_key_is_not_permission_or_corporate_authority(self):
        permission = self.issue()
        wrong = SyntheticGuardRuntime(self.store, identity_provider=self.host, backend=self.backend, signing_key=b"wrong-key-" * 4, clock=self.clock)
        self.assertIn("IZIN_BOZUK", wrong.execute(request=self.req, permission_id=permission)["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)
        self.host.identity = replace(self.host.identity, authenticated=False)
        self.assertEqual("BLOCK", self.runtime.evaluate(request=self.req)["decision"])

    def test_technical_guard_exception_and_audit_error_fail_closed(self):
        permission = self.issue()
        def broken():
            raise TimeoutError("Not emitted to model")
        with patch.object(self.runtime, "identity_provider", broken):
            self.assertEqual("BLOCKED", self.execute(permission)["state"])
        with patch.object(self.store, "_event", side_effect=RuntimeError("audit unavailable")):
            result = self.runtime.evaluate(request=self.req)
        self.assertEqual("BLOCK", result["decision"])
        self.assertFalse(result["audit_persisted"])
        self.assertEqual(0, self.backend.prepared)
        self.no_output()

    def test_lock_failure_cannot_write_or_send(self):
        permission = self.issue()
        with patch.object(self.store, "_db", side_effect=CoreError("KILIT_SINIRI", "synthetic")):
            result = self.execute(permission)
        self.assertEqual("BLOCKED", result["state"])
        self.assertFalse(result["decision"]["audit_persisted"])
        self.assertEqual(0, self.backend.prepared)

    def test_qa_failure_keeps_quarantine_and_source_but_never_delivers(self):
        permission = self.issue()
        self.backend.good_qa = False
        result = self.execute(permission)
        self.assertEqual("FAILED", result["state"])
        self.assertEqual("BLOCK", result["decision"]["decision"])
        self.no_output()
        self.assertTrue((self.store.system / "eylem-karantina" / self.req["plan"]["operation_id"] / "artifact.bin").exists())
        self.assertEqual(self.sha, hash_file(self.path))
        self.assertEqual("BLOCK", self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])["decision"])

    def test_source_or_identity_changes_during_qa_stop_publication(self):
        permission = self.issue()
        self.backend.on_qa = lambda: self.path.write_text("QA sırasında değişen kaynak", encoding="utf-8")
        result = self.execute(permission)
        self.assertEqual("FAILED", result["state"])
        self.no_output()






    def test_source_access_revocation_and_cross_case_permission_are_rejected(self):
        permission = self.issue()
        other = self.store.create_case("Başka case")
        altered = copy.deepcopy(self.req); altered["plan"]["case_id"] = other
        self.host.identity = replace(self.host.identity, case_ids=frozenset([self.case, other]))
        self.host.authorize(altered)
        self.assertEqual("BLOCKED", self.execute(permission, altered)["state"])
        self.host.authorize(self.req)
        denied = Store(self.area / "work", source_roots=[self.area / "other"], output_root=self.area)
        runtime = SyntheticGuardRuntime(denied, identity_provider=self.host, backend=self.backend, signing_key=KEY, clock=self.clock)
        self.assertIn("ERISIM_YOK", runtime.execute(request=self.req, permission_id=permission)["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)

    def test_output_traversal_ads_reserved_name_and_existing_target_are_rejected(self):
        for path in ["ciktilar/../source.docx", "ciktilar/CON.docx", "ciktilar/file.docx:stream", "ciktilar/dir\\file.docx", "ciktilar/file.docx."]:
            bad = copy.deepcopy(self.req); bad["plan"]["parameters"]["target_relative_path"] = path
            self.assertEqual("BLOCK", self.runtime.evaluate(request=bad)["decision"])
        target = self.store.root / self.req["plan"]["parameters"]["target_relative_path"]
        target.parent.mkdir(); target.write_bytes(b"existing")
        self.host.authorize(self.req)
        self.assertIn("HEDEF_MEVCUT", self.runtime.evaluate(request=self.req)["reasons"])
        self.assertEqual(b"existing", target.read_bytes())

    def test_racing_target_creation_never_overwrites_existing_file(self):
        permission = self.issue()
        target = self.store.root / self.req["plan"]["parameters"]["target_relative_path"]
        self.backend.on_qa = lambda: (target.parent.mkdir(exist_ok=True), target.write_bytes(b"racing-existing"))
        result = self.execute(permission)
        self.assertEqual("FAILED", result["state"])
        self.assertEqual(b"racing-existing", target.read_bytes())

    def test_publication_then_commit_failure_requires_reconciliation(self):
        permission = self.issue()
        original = self.runtime._stage
        def failing(db, case, operation, expected, state, **values):
            if state == "SIMULATION_COMMITTED":
                raise RuntimeError("synthetic commit failure after publication")
            return original(db, case, operation, expected, state, **values)
        with patch.object(self.runtime, "_stage", side_effect=failing):
            result = self.execute(permission)
        self.assertEqual("RECONCILE_REQUIRED", result["state"])
        self.assertTrue((self.store.root / self.req["plan"]["parameters"]["target_relative_path"]).exists())
        self.assertEqual("BLOCK", self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])["decision"])
        self.assertEqual("BLOCKED", self.execute(permission)["state"])

    def test_completion_rechecks_file_hash_and_current_source_without_rewriting_history(self):
        permission = self.issue()
        result = self.execute(permission)
        target = Path(result["output_path"])
        target.write_bytes(b"corrupt output")
        self.assertIn("QA_FAILED", self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])["reasons"])
        self.assertEqual("SIMULATION_COMMITTED", self.store.action_status(self.case, self.req["plan"]["operation_id"])["state"])

    def test_partial_read_quality_and_missing_backend_capability_do_not_allow_actions(self):
        self.host.authorize(self.req)
        self.host.identity = replace(self.host.identity, quality_ready=False)
        self.assertIn("SOURCE_QUALITY_UNVERIFIED", self.runtime.evaluate(request=self.req)["reasons"])
        self.host.identity = replace(self.host.identity, quality_ready=True, allowed_actions=frozenset())
        self.assertIn("TECHNICAL_CAPABILITY_UNAVAILABLE", self.runtime.evaluate(request=self.req)["reasons"])

    def test_completion_rechecks_live_case_access_identity_and_policy(self):
        self.execute(self.issue())
        original = self.host.identity
        for changes in [dict(case_ids=frozenset()), dict(authenticated=False), dict(allowed_actions=frozenset()),
                        dict(policy_version="changed-policy"), dict(identity_epoch="changed-epoch")]:
            self.host.identity = replace(original, **changes)
            gate = self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])
            self.assertEqual("BLOCK", gate["decision"], changes)
        self.host.identity = original
        self.assertEqual("ALLOW", self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])["decision"])

    def test_completed_effect_outlives_issuance_window_without_reopening_permission(self):
        permission = self.issue(ttl_seconds=1)
        self.execute(permission)
        self.clock.value += timedelta(minutes=16)
        self.assertEqual("ALLOW", self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])["decision"])
        self.assertEqual("BLOCKED", self.execute(permission)["state"])
        self.assertEqual(1, self.backend.prepared)

    def test_completed_document_is_not_current_when_original_source_changes(self):
        self.execute(self.issue())
        self.path.write_text("Source changed after completion", encoding="utf-8")
        gate = self.runtime.completion_gate(self.case, self.req["plan"]["operation_id"])
        self.assertIn("KAYNAK_GUNCEL_DEGIL", gate["reasons"])
        self.assertEqual("SIMULATION_COMMITTED", self.store.action_status(self.case, self.req["plan"]["operation_id"])["state"])

    def test_permission_invalidation_during_qa_blocks_publication(self):
        permission = self.issue()
        self.backend.on_qa = lambda: self.store.invalidate(self.case, permission, self.version, "Synthetic revocation", expected_revision=self.rev())
        result = self.execute(permission)
        self.assertEqual("FAILED", result["state"])
        self.assertEqual("BLOCK", result["decision"]["decision"])
        self.no_output()

    def test_signed_unconsumed_permission_cannot_contain_another_consumer(self):
        permission = self.issue()
        with self.store._db() as db:
            body = self.runtime._permission(db, self.case, permission)
            self.runtime._save_permission(db, dict(body, consumed_by=str(uuid4())))
        self.assertIn("IZIN_BOZUK", self.execute(permission)["decision"]["reasons"])
        self.assertEqual(0, self.backend.prepared)

    def test_target_quote_change_digest_and_wrong_old_text_are_checked(self):
        path = self.sources / "Revizyon kaynağı.docx"; path.write_bytes(docx_bytes())
        doc = self.store.create_document(self.case, "DOCX", expected_revision=self.rev())
        version = self.store.ingest(self.case, doc, path, expected_revision=self.rev())["version_id"]
        reading = self.store.read_document(self.case, version, format="DOCX")
        unit = next(x for x in reading["result"]["units"] if "Garanti süresi" in x["views"]["AFTER"])
        text = unit["views"]["AFTER"]
        target = {"format": "DOCX", "unit_id": unit["unit_id"], "view": "AFTER", "start": 0, "end": len(text), "expected_text": text, "field_kind": "OBLIGATION"}
        req = request(self.case, version, hash_file(path))
        req["plan"]["action_type"] = "APPLY_TRACK_CHANGES"
        req["payload"]["changes"] = [{"version_id": version, "reading_id": reading["processing_id"], "target": target, "new_text": "Garanti 48 ay."}]
        req["plan"]["parameters"]["change_plan_sha256"] = hash_value(req["payload"]["changes"])
        self.host.authorize(req)
        self.assertEqual("ALLOW", self.runtime.evaluate(request=req)["decision"])
        old_digest = payload_digest(req)
        req["payload"]["changes"][0]["new_text"] = "Garanti 60 ay."
        req["plan"]["parameters"]["change_plan_sha256"] = hash_value(req["payload"]["changes"])
        self.assertNotEqual(old_digest, payload_digest(req))
        req["payload"]["changes"][0]["target"]["expected_text"] = "Garanti 24 ay."
        req["plan"]["parameters"]["change_plan_sha256"] = hash_value(req["payload"]["changes"])
        self.host.authorize(req)
        self.assertIn("KAYNAK_ALINTISI", self.runtime.evaluate(request=req)["reasons"])

    def test_fake_document_payload_hash_fails_before_effect(self):
        bad = copy.deepcopy(self.req); bad["payload"]["content_plan"]["body_text"] += " changed"
        self.assertIn("PAYLOAD_HASH_FARKLI", self.runtime.evaluate(request=bad)["reasons"])

    def test_permissions_cannot_be_issued_outside_isolated_runtime(self):
        backend = Backend(); backend.synthetic_only = False
        runtime = SyntheticGuardRuntime(self.store, identity_provider=self.host, backend=backend, signing_key=KEY)
        self.assertIn("TEST_SCOPE_REQUIRED", runtime.evaluate(request=self.req)["reasons"])
        with patch("sozlesme_cekirdek.guard.TEST_ROOT", self.area / "not-authorized"):
            self.assertIn("ERISIM_YOK", self.runtime.evaluate(request=self.req)["reasons"])

    def test_real_cli_has_evaluation_but_no_permission_or_execute_tool(self):
        path = self.sources / "guard.json"; path.write_text(canonical(self.req), encoding="utf-8")
        base = [sys.executable, "-m", "sozlesme_cekirdek", "--workspace", str(self.area / "work"), "--output-root", str(self.area), "--source-root", str(self.sources)]
        result = subprocess.run(base + ["action-evaluate", "--request", str(path)], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("BLOCK", json.loads(result.stdout)["result"]["decision"])
        denied = subprocess.run(base + ["permission-issue"], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(2, denied.returncode)
        self.no_output()

    def test_bounded_permission_ttl_operation_and_audit_limits(self):
        for ttl in [0, 901, True]:
            self.error("IZIN_SURESI", lambda: self.runtime.issue_permission(request=self.req, expected_revision=self.rev(), ttl_seconds=ttl))
        self.host.authorize(self.req)
        with patch("sozlesme_cekirdek.guard.MAX_OPERATIONS", 0):
            self.error("GUARD_OPERATION_LIMIT", lambda: self.runtime.issue_permission(request=self.req, expected_revision=self.rev()))
        with patch("sozlesme_cekirdek.guard.MAX_DECISIONS", 0):
            result = self.runtime.evaluate(request=self.req)
        self.assertEqual("BLOCK", result["decision"])
        self.assertFalse(result["audit_persisted"])

    def test_real_two_process_replay_race_only_one_document_effect(self):
        mail = self.req
        permission = self.issue(mail)
        ctx = multiprocessing.get_context("spawn")
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=execution_worker, args=(str(self.area), self.case, mail, permission, barrier, queue)) for _ in range(2)]
        for process in processes:process.start()
        for process in processes:
            process.join(120)
            if process.is_alive():
                process.terminate(); process.join(); self.fail("replay race timeout")
        results = [queue.get(timeout=30) for _ in range(2)]
        outcomes = sorted(item['state'] for item in results)
        self.assertEqual(["BLOCKED", "SIMULATION_COMMITTED"], outcomes, results)
        self.assertEqual([mail["plan"]["operation_id"]], (self.area / "prepare.log").read_text(encoding="utf-8").splitlines())

    def test_real_process_crash_after_document_prepare_does_not_retry(self):
        mail = self.req
        permission = self.issue(mail)
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(target=execution_worker, args=(str(self.area), self.case, mail, permission, None, None), kwargs={"crash": True})
        process.start(); process.join(30)
        if process.is_alive():
            process.terminate(); process.join(); self.fail("crash fixture timeout")
        diagnostic=self.area/"worker-phases.jsonl"
        self.assertEqual(19, process.exitcode, diagnostic.read_text(encoding="utf-8") if diagnostic.exists() else "No worker target phase: inspect native faulthandler/import failure")
        status = self.store.action_status(self.case, mail["plan"]["operation_id"])
        self.assertEqual("EXECUTING", status["state"])
        self.assertEqual("RECONCILE_REQUIRED", status["retry_safety"])
        self.assertEqual("BLOCKED", self.execute(permission, mail)["state"])
        self.assertEqual(1, len((self.area / "prepare.log").read_text(encoding="utf-8").splitlines()))

    def test_snapshot_restore_preserves_signed_lifecycle_and_blocks_replay(self):
        permission = self.issue()
        self.execute(permission)
        snapshot = self.area / "snapshot"; self.store.snapshot(snapshot)
        restored = Store.restore(snapshot, self.area / "restored", source_roots=[self.sources], output_root=self.area)
        runtime = SyntheticGuardRuntime(restored, identity_provider=self.host, backend=self.backend, signing_key=KEY, clock=self.clock)
        self.assertEqual("SIMULATION_COMMITTED", restored.action_status(self.case, self.req["plan"]["operation_id"])["state"])
        self.assertEqual("BLOCKED", runtime.execute(request=self.req, permission_id=permission)["state"])
        # Store snapshot copies the database/sources, not delivered output files.
        self.assertEqual("BLOCK", runtime.completion_gate(self.case, self.req["plan"]["operation_id"])["decision"])

    def test_migration_004_upgrades_real_003_database_and_checks_digest(self):
        from sozlesme_cekirdek.store import MIGRATION, MIGRATION_VERIFIER, MIGRATION_CONTEXT, NOW
        root = self.area / "older"; system = root / ".sistem"; system.mkdir(parents=True)
        with duckdb.connect(str(system / "sozlesme.duckdb")) as db:
            for index, path in enumerate([MIGRATION, MIGRATION_VERIFIER, MIGRATION_CONTEXT], 1):
                text = path.read_text(encoding="utf-8"); db.execute(text)
                db.execute("INSERT INTO sema_gecmisi VALUES(?,?,?,?)", [index, "old", hashlib.sha256(text.encode()).hexdigest(), NOW()])
            db.execute("INSERT INTO dosyalar VALUES(?,?,0,'NEW',?)", [self.case, "Existing", NOW()])
        upgraded = Store(root, source_roots=[self.sources], output_root=self.area)
        self.assertEqual(0, upgraded.case_revision(self.case))
        with upgraded._db() as db:
            self.assertEqual([1, 2, 3, 4, 5, 6], [x[0] for x in db.execute("SELECT migration_no FROM sema_gecmisi ORDER BY migration_no").fetchall()])
            self.assertEqual(23, db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='main'").fetchone()[0])
        changed = self.area / "changed-004.sql"; changed.write_text("-- drift", encoding="utf-8")
        with patch("sozlesme_cekirdek.store.MIGRATION_GUARD", changed):
            self.error("SEMA_DRIFT", lambda: Store(self.area / "work", source_roots=[self.sources], output_root=self.area))


if __name__ == "__main__":unittest.main()
