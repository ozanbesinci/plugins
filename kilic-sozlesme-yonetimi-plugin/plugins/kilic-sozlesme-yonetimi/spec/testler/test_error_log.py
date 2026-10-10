import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import types
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

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

    def test_unreadable_metadata_keeps_event(self):
        logger = load_logger()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            with patch.object(Path, 'read_text', side_effect=OSError('private path')):
                self.assertTrue(logger.write_error('bootstrap', 'BOOTSTRAP_ERROR'))
            file = next((Path(tmp)/'KilicSozlesme/logs').glob('*.jsonl'))
            event = json.loads(file.read_text())
            self.assertEqual(event['package_version'], 'UNKNOWN')
            self.assertEqual(event['error_code'], 'BOOTSTRAP_ERROR')

    def test_contended_writer_returns_without_waiting(self):
        logger = load_logger()
        result = []
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            with logger._write_lock:
                worker = threading.Thread(target=lambda: result.append(logger.write_error('test', 'TEST')))
                worker.start()
                worker.join(timeout=1)
                self.assertFalse(worker.is_alive())
            self.assertEqual(result, [False])
            self.assertTrue(logger.write_error('test', 'TEST'))
            self.assertEqual(logger._count, 1)

    def test_returned_failures_logged_but_partial_results_are_not(self):
        logger = load_logger()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            for status in ('READY', 'KISMI', 'BILGI_GEREKLI', 'UZMAN_GORUSU_GEREKLI'):
                self.assertFalse(logger.write_result_error('test', {'status':status}))
            self.assertFalse((Path(tmp)/'KilicSozlesme').exists())
            for status in ('TEKNIK_ENGEL', 'DEPENDENCIES_REQUIRED', 'FAILED'):
                self.assertTrue(logger.write_result_error('test', {'status':status, 'message':'secret'}))
            self.assertTrue(logger.write_result_error('test', {'decision':'BLOCK'}))
            file = next((Path(tmp)/'KilicSozlesme/logs').glob('*.jsonl'))
            self.assertNotIn('secret', file.read_text())
            self.assertEqual(len(file.read_text().splitlines()), 4)

    def test_cli_logs_returned_block_without_changing_response(self):
        # Exercise the real CLI boundary with only the storage dependency stubbed.
        # This test does not claim to validate DuckDB or business evaluation.
        package = types.ModuleType('test_core')
        package.__path__ = []
        store = types.ModuleType('test_core.store')
        expected = {'status':'TEKNIK_ENGEL', 'chat_response':'private result text'}
        store.Store = Mock(return_value=Mock(reconcile=Mock(return_value=expected)))
        errors = types.ModuleType('test_core.errors')
        errors.CoreError = type('CoreError', (RuntimeError,), {})
        safety = types.ModuleType('test_core.safety')
        safety.confined = Mock()
        safety.native_path = Mock()
        logger = load_logger()
        modules = {'test_core':package, 'test_core.store':store,
                   'test_core.errors':errors, 'test_core.safety':safety, 'kilic_error_log':logger}
        class Stream(io.StringIO):
            def reconfigure(self, **kwargs):
                pass
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, LOCALAPPDATA=tmp):
            with patch.dict(sys.modules, modules):
                spec = importlib.util.spec_from_file_location('test_core.__main__', ROOT/'src/sozlesme_cekirdek/__main__.py')
                cli = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(cli)
                stdout, stderr = Stream(), Stream()
                with patch.object(sys, 'argv', ['core', '--workspace',tmp,'--output-root',tmp,'--source-root',tmp,'reconcile']), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    cli.main()
                response = json.loads(stdout.getvalue())
                self.assertEqual(response['status'], 'SUCCEEDED')
                self.assertEqual(response['result'], expected)
                self.assertEqual(stderr.getvalue(), '')
            file = next((Path(tmp)/'KilicSozlesme/logs').glob('*.jsonl'))
            event = json.loads(file.read_text())
            self.assertEqual(event['error_code'], 'TEKNIK_ENGEL')
            self.assertEqual(event['operation_id'], response['operation_id'])
            self.assertNotIn('private result text', file.read_text())

    def test_runtime_entrypoint_success_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, LOCALAPPDATA=tmp)
            command = [sys.executable, str(ROOT/'scripts/runtime_kontrol.py'), '--action']
            success = subprocess.run(command+['verify-upstream'], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertFalse((Path(tmp)/'KilicSozlesme/logs').exists())
            # Missing state root fails before any installation or network action.
            failure = subprocess.run(command+['pdf-child'], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(failure.returncode, 2, failure.stderr)
            response = json.loads(failure.stdout.removeprefix('@@SONUC '))
            self.assertEqual(response['status'], 'ERROR')
            files = list((Path(tmp)/'KilicSozlesme/logs').glob('*.jsonl'))
            self.assertEqual(len(files), 1)
            event = json.loads(files[0].read_text())
            self.assertEqual(event['stage'], 'runtime-pdf-child')
            self.assertEqual(event['error_code'], 'RUNTIME_ERROR')


if __name__ == "__main__":
    unittest.main()
