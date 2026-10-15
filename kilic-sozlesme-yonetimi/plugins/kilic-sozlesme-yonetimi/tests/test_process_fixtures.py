"""Verify actual crash semantics rather than accepting arbitrary native exits."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProcessFixtureTests(unittest.TestCase):
    def child(self, area, code):
        program = """import atexit, os, sys
from pathlib import Path
import duckdb
from process_fixtures import abrupt_exit
area = Path(sys.argv[1])
connection = duckdb.connect(':memory:')
assert connection.execute('select 42').fetchone() == (42,)
connection.close()
atexit.register(lambda: (area/'atexit.txt').write_text('unexpected', encoding='utf-8'))
try:
    with (area/'before.txt').open('x', encoding='utf-8') as stream:
        stream.write('before abrupt termination'); stream.flush(); os.fsync(stream.fileno())
    abrupt_exit(int(sys.argv[2]))
finally:
    (area/'finally.txt').write_text('unexpected', encoding='utf-8')
(area/'returned.txt').write_text('unexpected', encoding='utf-8')
"""
        return subprocess.run([sys.executable, '-B', '-X', 'faulthandler', '-c', program, str(area), str(code)],
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                       PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT/'tests')),
                              capture_output=True, timeout=30)

    def test_real_abrupt_exit_preserves_fsynced_evidence_without_finally_or_atexit(self):
        with tempfile.TemporaryDirectory(prefix='cs-hard-crash-') as name:
            area = Path(name)
            result = self.child(area, 19)
            self.assertEqual(19, result.returncode, result.stderr.decode('utf-8', errors='replace'))
            self.assertEqual('before abrupt termination', (area/'before.txt').read_text(encoding='utf-8'))
            for name in ('finally.txt', 'atexit.txt', 'returned.txt'):
                self.assertFalse((area/name).exists(), name)

    def test_every_planned_crash_code_survives_actual_duckdb_worker_termination(self):
        for code in (9, 17, 19, 27, 29, 31, 37, 91):
            with self.subTest(code=code), tempfile.TemporaryDirectory(prefix='cs-hard-code-') as name:
                area = Path(name)
                result = self.child(area, code)
                self.assertEqual(code, result.returncode, result.stderr.decode('utf-8', errors='replace'))
                self.assertTrue((area/'before.txt').is_file())
                self.assertFalse((area/'finally.txt').exists())
                self.assertFalse((area/'atexit.txt').exists())
