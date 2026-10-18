"""Real DB/CLI regression tests for the three observed Work integration failures."""
import contextlib
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

from db import connect, init_db, set_meta
from model_telemetry import receipt_values
from record_results import record_task_result
from task_queue import _add_task
from workflow import _token_budget
from question_waits import register

SCRIPTS = Path(__file__).resolve().parents[1]
PACKAGE = SCRIPTS.parents[2]
sys.path.insert(0, str(PACKAGE / "scripts"))
spec = importlib.util.spec_from_file_location("offer_runtime_launcher_test", PACKAGE / "scripts/runtime_launcher.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class WorkHostIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "run"
        init_db(self.run)

    def tearDown(self):
        self.temp.cleanup()

    def task(self):
        con = connect(self.run)
        try:
            tid = _add_task(con, "REQUIREMENTS", "semantic_extraction", "requirements_extraction", {})
            con.commit()
            return tid
        finally:
            con.close()

    def test_explicit_host_unavailable_records_null_tokens_atomically(self):
        tid = self.task()
        result = record_task_result(self.run, tid, {"requirements": [], "evidence": []},
                    telemetry_status="host_unavailable", telemetry_reason="ChatGPT Work does not expose task usage")
        self.assertEqual(result["status"], "completed")
        con = connect(self.run)
        try:
            row = con.execute("SELECT model_name,reasoning_effort,input_tokens,cached_input_tokens,output_tokens,telemetry_status,telemetry_reason FROM model_receipts").fetchone()
            self.assertEqual(row[:6], ("HOST_UNAVAILABLE", "HOST_UNAVAILABLE", None, None, None, "host_unavailable"))
            self.assertTrue(row[6])
            self.assertEqual(con.execute("SELECT status FROM llm_result_validations").fetchone()[0], "PASS")
        finally:
            con.close()
        budget = _token_budget(self.run, {"profiles": {"standart": {"max_input_tokens": 10}}})
        self.assertTrue(budget["usage_unknown"])
        self.assertIsNone(budget["input_tokens"])
        self.assertIsNone(budget["ratio"])
        self.assertFalse(budget["hard_stop"])
        self.assertEqual(budget["enforcement"], "KNOWN_USAGE_ONLY")

    def test_unavailable_telemetry_cannot_skip_result_schema(self):
        tid = self.task()
        with self.assertRaises(ValueError):
            record_task_result(self.run, tid, {"invented": "invalid"}, telemetry_status="host_unavailable", telemetry_reason="Host does not expose usage")
        con = connect(self.run)
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM model_receipts").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT status FROM task_queue WHERE task_id=?", [tid]).fetchone()[0], "pending")
        finally:
            con.close()

    def test_missing_receipt_still_rejected_by_default(self):
        with self.assertRaisesRegex(ValueError, "actual model_name"):
            receipt_values()

    def test_reason_and_null_counts_required_for_unavailable(self):
        for data in ({}, {"telemetry_reason": "Work", "input_tokens": 0}, {"telemetry_reason": "Work", "cached_input_tokens": 0}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                receipt_values(telemetry_status="host_unavailable", **data)

    def test_measured_counts_are_validated(self):
        for values in ({"input_tokens": -1, "output_tokens": 1}, {"input_tokens": 1.5, "output_tokens": 1},
                       {"input_tokens": 1, "output_tokens": 1, "cached_input_tokens": 2}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                receipt_values(model_name="actual", reasoning_effort="medium", **values)

    def test_unexplained_historical_usage_still_stops(self):
        con = connect(self.run)
        try:
            con.execute("INSERT INTO model_receipts(receipt_id,task_id,model_name,reasoning_effort,recorded_at) VALUES ('r','t','model','medium','now')")
            con.commit()
        finally:
            con.close()
        self.assertTrue(_token_budget(self.run, {})["hard_stop"])

    def test_measured_cap_still_stops_when_other_usage_is_unknown(self):
        record_task_result(self.run, self.task(), {"requirements": [], "evidence": []},
                           telemetry_status="host_unavailable", telemetry_reason="Host usage unavailable")
        con = connect(self.run)
        try:
            con.execute("INSERT INTO model_receipts(receipt_id,task_id,model_name,reasoning_effort,input_tokens,output_tokens,recorded_at) VALUES ('measured','t','actual','medium',10,2,'now')")
            con.commit()
        finally:
            con.close()
        budget = _token_budget(self.run, {"profiles": {"standart": {"max_input_tokens": 10}}})
        self.assertTrue(budget["hard_stop"])
        self.assertEqual(budget["known_totals"]["input_tokens"], 10)
        self.assertIsNone(budget["input_tokens"])

    def test_final_validation_exposes_usage_limitation_without_token_block(self):
        record_task_result(self.run, self.task(), {"requirements": [], "evidence": []},
                           telemetry_status="host_unavailable", telemetry_reason="Host usage unavailable")
        from validate_run import validate
        result = validate(self.run)
        self.assertEqual(len(result["model_telemetry"]["unavailable_receipts"]), 1)
        self.assertTrue(result["telemetry_warning"])
        self.assertFalse(any("telemetry receipt" in b or "token usage" in b for b in result["blocking_reasons"]))

    def test_report_discloses_unknown_usage(self):
        record_task_result(self.run, self.task(), {"requirements": [], "evidence": []},
                           telemetry_status="host_unavailable", telemetry_reason="Host usage unavailable")
        from report_model import build_preliminary
        model = build_preliminary(self.run, "Synthetic blocked case")
        self.assertTrue(any("kullanım toplamı bilinmiyor" in s for s in model["limitations"]))
        self.assertNotEqual(model["content_status"], "SAFETY_NOTICE")

    def test_record_cli_accepts_explicit_unknown_without_fake_model(self):
        task = self.task()
        result_file = self.run / "synthetic-result.json"
        result_file.write_text(json.dumps({"requirements": [], "evidence": []}), encoding="utf-8")
        proc = subprocess.run([sys.executable, "-B", str(SCRIPTS / "record_results.py"), "--run", str(self.run),
                 "--task-id", task, "--input", str(result_file), "--telemetry-status", "host_unavailable",
                 "--telemetry-reason", "Work task does not expose model usage"],
                 capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["telemetry"]["input_tokens"], None)

    def invoke_report(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPTS / "report_delivery.py"), "--run", str(self.run), *args],
                              capture_output=True, text=True, encoding="utf-8",
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=45)

    def test_supported_report_cli_creates_and_inspects_actual_pair(self):
        proc = self.invoke_report("--reason", "Synthetic blocked analysis; no recommendation")
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        result = json.loads(proc.stdout)
        self.assertEqual(result["delivery_status"], "READY")
        self.assertTrue(Path(result["xlsx"]).is_file())
        self.assertTrue(Path(result["pdf"]).is_file())
        self.assertEqual(result["decision_assurance"], "NO_DECISION")
        check = self.invoke_report("--inspect")
        self.assertEqual(check.returncode, 0, check.stderr + check.stdout)

    def test_report_no_action_is_not_silent_success(self):
        self.assertEqual(self.invoke_report().returncode, 2)
        self.assertFalse((self.run / "reports").exists())

    def test_inspect_missing_pair_is_not_success(self):
        proc = self.invoke_report("--inspect")
        self.assertEqual(proc.returncode, 3, proc.stderr + proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["delivery_status"], "NOT_CREATED")

    def test_report_cli_preserves_question_wait(self):
        register(self.run, {"issue_id": "q", "scope_sha256": "scope", "question": "Hangi belge?", "issue_type": "source_authority_conflict",
                            "owner": "IDARE", "fact_ids": [], "evidence_ids": [], "sources": [{"document_id": "doc-A"}]})
        proc = self.invoke_report("--reason", "Must wait")
        self.assertEqual(proc.returncode, 4, proc.stderr + proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["status"], "NEEDS_USER_INPUT")
        self.assertFalse((self.run / "reports").exists())

    def entry(self, *, runtime_error=None, command_error=None):
        out = io.StringIO()
        with patch.object(launcher, "current", side_effect=runtime_error, return_value={"runtime_id": "test"}), \
             patch.object(launcher, "main", side_effect=command_error), contextlib.redirect_stdout(out):
            code = launcher.entry()
        return code, json.loads(out.getvalue())

    def test_real_runtime_validation_failure_routes_to_installer(self):
        code, value = self.entry(runtime_error=ValueError("Wrong package lock"))
        self.assertEqual(code, 3)
        self.assertEqual(value["status"], "BLOCKED_ENVIRONMENT")
        self.assertIn("Kur.cmd", value["next_step"])

    def test_ready_permission_failure_never_suggests_reinstall(self):
        code, value = self.entry(command_error=PermissionError("[WinError 5] output denied"))
        self.assertEqual(code, 3)
        self.assertEqual(value["status"], "BLOCKED_FILE_ACCESS")
        self.assertEqual(value["runtime_status"], "READY")
        self.assertNotIn("Kur.cmd", value["next_step"])

    def test_bad_command_is_not_an_environment_failure(self):
        self.assertEqual(self.entry(command_error=ValueError("Invalid run"))[1]["status"], "BLOCKED_COMMAND")

    def test_library_without_cli_is_rejected(self):
        with patch.object(sys, "argv", ["launcher", "common"]), self.assertRaisesRegex(ValueError, "komut satırı"):
            launcher.main({"runtime_id": "test"})


if __name__ == "__main__":
    unittest.main()
