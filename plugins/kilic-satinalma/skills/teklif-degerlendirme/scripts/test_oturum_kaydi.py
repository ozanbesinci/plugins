"""Synthetic local processes only: no Codex/model or network calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from oturum_kaydi import read_native_session, native_receipt_valid


class SessionTests(unittest.TestCase):
    def test_seal_binds_accepting_model_not_later_context(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "log.jsonl"
            seal = {"run_id": "fixture", "artifact_sha256": "a" * 64}
            events = [
                {"type": "session_meta", "payload": {"id": "session", "cwd": folder}},
                {"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "high"}},
                {"type": "response_item", "payload": {"type": "function_call_output", "output": json.dumps({"output": "TEKLIF_RESULT_SEAL:" + json.dumps(seal)})}},
                {"type": "turn_context", "payload": {"model": "gpt-5.6-sol", "effort": "high"}}]
            path.write_text("\n".join(json.dumps(x) for x in events) + "\n", encoding="utf-8")
            receipt = read_native_session(path, seal=seal)
            self.assertEqual(receipt["model"], "gpt-6-astra")
            self.assertTrue(native_receipt_valid(receipt))
            with path.open("a", encoding="utf-8") as stream: stream.write('{"new":"event"}\n')
            self.assertTrue(native_receipt_valid(receipt))
            path.write_text(path.read_text().replace("gpt-6-astra", "fake-model"), encoding="utf-8")
            self.assertFalse(native_receipt_valid(receipt))

    def test_marker_in_prompt_is_not_tool_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "log.jsonl"
            events = [{"type": "session_meta", "payload": {"id": "session", "cwd": folder}},
                      {"type": "turn_context", "payload": {"model": "gpt-5.6-sol", "effort": "high"}},
                      {"type": "response_item", "payload": {"type": "message", "output": 'TEKLIF_RESULT_SEAL:{"fixture":true}'}}]
            path.write_text("\n".join(json.dumps(x) for x in events), encoding="utf-8")
            with self.assertRaises(ValueError): read_native_session(path, seal={"fixture": True})


if __name__ == '__main__': unittest.main()
