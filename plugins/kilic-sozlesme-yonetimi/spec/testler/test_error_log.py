import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load_logger():
    spec = importlib.util.spec_from_file_location("test_logger", ROOT / "src/kilic_error_log.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ErrorLogTests(unittest.TestCase):
    def test_jsonl_privacy_silence_and_cap(self):
        logger = load_logger()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            output = io.StringIO()
            try:
                raise ValueError("secret=abc C:\\Users\\sensitive\\contract.docx")
            except ValueError as exc:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    for _ in range(100):
                        self.assertTrue(logger.write_error("document-read", "TEKNIK_HATA", exc, skill_id="K01"))
                    self.assertFalse(logger.write_error("document-read", "TEKNIK_HATA", exc))
            self.assertEqual(output.getvalue(), "")
            files = list((Path(tmp)/"KilicSozlesme/logs").glob("*.jsonl"))
            self.assertEqual(len(files), 1)
            raw = files[0].read_text()
            self.assertNotIn("secret", raw)
            self.assertNotIn("sensitive", raw)
            rows = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(len(rows), 100)
            self.assertEqual(len({r["event_id"] for r in rows}), 100)
            self.assertEqual(rows[0]["skill_id"], "K01")
            self.assertEqual(rows[0]["exception_type"], "ValueError")
            self.assertTrue(rows[0]["frames"])

    def test_bad_destination_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp)/"not-a-directory"
            blocker.write_text("x")
            with patch.dict(os.environ, LOCALAPPDATA=str(blocker)):
                self.assertFalse(load_logger().write_error("prepare", "TEST"))

    def test_missing_localappdata_does_not_create_files(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(load_logger().write_error("prepare", "TEST"))

    def test_different_sessions_do_not_share_files(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            self.assertTrue(load_logger().write_error("prepare", "TEST"))
            self.assertTrue(load_logger().write_error("prepare", "TEST"))
            self.assertEqual(len(list((Path(tmp)/"KilicSozlesme/logs").glob("*.jsonl"))), 2)

    def test_file_size_cap(self):
        logger = load_logger()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            self.assertTrue(logger.write_error("prepare", "TEST"))
            file = next((Path(tmp)/"KilicSozlesme/logs").glob("*.jsonl"))
            with file.open("ab") as stream:
                stream.truncate(logger.MAX_BYTES)
            self.assertFalse(logger.write_error("prepare", "TEST"))
            self.assertEqual(file.stat().st_size, logger.MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
