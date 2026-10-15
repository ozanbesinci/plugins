import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.readers.process_budget import run_bounded_worker
from sozlesme_cekirdek.readers.common import result_base, unit, locator
from sozlesme_cekirdek.readers.eml import BoundedMIMEParser


class ReaderBudgetTests(unittest.TestCase):
    def run_child(self, code, data=b'', **limits):
        return run_bounded_worker([sys.executable, '-I', '-c', code], data, dict(os.environ), **limits)

    def test_native_echo_preserves_bytes(self):
        source = b'abc\x00xyz' * 10000
        child = self.run_child('import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())', source)
        self.assertEqual(0, child.returncode)
        self.assertEqual(source, child.stdout)

    def test_native_child_keeps_active_runtime_and_rejects_inherited_launcher(self):
        code = ('import sys,json,lxml;sys.stdin.buffer.read();'
                'print(json.dumps({"prefix":sys.prefix,"lxml":lxml.__file__}))')
        with patch.dict(os.environ, __PYVENV_LAUNCHER__=str(Path(sys.prefix) / 'foreign-python.exe')):
            child = self.run_child(code)
        self.assertEqual(0, child.returncode)
        result = json.loads(child.stdout)
        self.assertEqual(Path(sys.prefix).resolve(), Path(result['prefix']).resolve())
        if sys.prefix != sys.base_prefix:
            self.assertTrue(Path(result['lxml']).resolve().is_relative_to(Path(sys.prefix).resolve()))

    def test_native_job_still_rejects_a_second_process(self):
        code = ('import sys,subprocess;sys.stdin.buffer.read()\n'
                'try:\n subprocess.run([sys._base_executable,"-I","-c","pass"],check=True,timeout=5)\n'
                ' print("UNBOUNDED")\n'
                'except OSError:\n print("CHILD_PROCESS_BLOCKED")')
        child = self.run_child(code)
        self.assertEqual(0, child.returncode)
        self.assertEqual(b'CHILD_PROCESS_BLOCKED\r\n', child.stdout)

    def test_native_inherited_parallelism_is_bounded(self):
        code = 'import os,sys; sys.stdin.buffer.read(); print(os.environ["OPENBLAS_NUM_THREADS"])'
        with patch.dict(os.environ, OPENBLAS_NUM_THREADS='64'):
            child = self.run_child(code)
        self.assertEqual(b'1\r\n', child.stdout)

    def test_native_stdout_growth_is_stopped(self):
        with self.assertRaises(CoreError) as error:
            self.run_child('import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write(b"x"*2000000)', stdout_limit=8192)
        self.assertEqual('BELGE_SINIRI', error.exception.code)

    def test_native_stderr_growth_is_stopped(self):
        with self.assertRaises(CoreError) as error:
            self.run_child('import sys; sys.stdin.buffer.read(); sys.stderr.buffer.write(b"x"*2000000)', stderr_limit=8192)
        self.assertEqual('BELGE_SINIRI', error.exception.code)

    def test_native_timeout_kills_child_without_full_duration(self):
        started = time.monotonic()
        with self.assertRaises(CoreError) as error:
            self.run_child('import sys,time; sys.stdin.buffer.read(); time.sleep(30)', timeout=0.5)
        self.assertEqual('OKUMA_ZAMAN_SINIRI', error.exception.code)
        self.assertLess(time.monotonic() - started, 8)

    def test_native_job_limits_committed_memory(self):
        code = 'import sys; sys.stdin.buffer.read()\ntry:\n x=bytearray(256*1024*1024)\n print("UNBOUNDED")\nexcept MemoryError:\n print("BUDGET_ENFORCED")'
        child = self.run_child(code, memory_limit=96 * 1024 * 1024)
        self.assertEqual(0, child.returncode)
        self.assertEqual(b'BUDGET_ENFORCED\r\n', child.stdout)

    def test_job_failure_never_feeds_document(self):
        code = 'import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data)'
        with patch('sozlesme_cekirdek.readers.process_budget.WindowsJob', side_effect=CoreError('PLATFORM_BUTCE', 'synthetic')):
            with self.assertRaises(CoreError) as error:
                self.run_child(code, b'secret-document')
        self.assertEqual('PLATFORM_BUTCE', error.exception.code)

    def test_unit_count_is_checked_before_append(self):
        report = result_base(b'x', 'EML', 'test', [])
        with patch('sozlesme_cekirdek.readers.common.MAX_UNITS', 2):
            unit(report, 'EMAIL_BODY', locator(path='1'), 'a')
            unit(report, 'EMAIL_BODY', locator(path='2'), 'b')
            with self.assertRaises(CoreError):
                unit(report, 'EMAIL_BODY', locator(path='3'), 'c')
        self.assertEqual(2, len(report['units']))
        self.assertEqual(2, len(json.loads(json.dumps(report))['units']))

    def test_unit_multiview_text_budget_is_checked_before_append(self):
        report = result_base(b'x', 'EML', 'test', [])
        with patch('sozlesme_cekirdek.readers.common.MAX_TEXT_BYTES', 5):
            unit(report, 'EMAIL_BODY', locator(path='1'), 'ab', before='ab')
            with self.assertRaises(CoreError):
                unit(report, 'EMAIL_BODY', locator(path='2'), 'xy')
        self.assertEqual(1, len(report['units']))

    def test_mime_width_is_rejected_before_overlimit_node_exists(self):
        parser = BoundedMIMEParser()
        source = b'From: a@x\r\nContent-Type: multipart/mixed; boundary="b"\r\n\r\n' + (b'--b\r\nContent-Type: text/plain\r\n\r\nx\r\n' * 128) + b'--b--\r\n'
        with self.assertRaises(CoreError):
            parser.feed(source)
            parser.close()
        self.assertEqual(128, parser.part_count)

    def test_mime_depth_is_rejected_during_parse(self):
        source = b'From: a@x\r\n'
        for depth in range(18):
            boundary = str(depth).encode('ascii')
            source += b'Content-Type: multipart/mixed; boundary="' + boundary + b'"\r\n\r\n--' + boundary + b'\r\n'
        source += b'Content-Type: text/plain\r\n\r\nx\r\n'
        parser = BoundedMIMEParser()
        with self.assertRaises(CoreError):
            parser.feed(source)
            parser.close()
        self.assertEqual(17, parser.part_count)
