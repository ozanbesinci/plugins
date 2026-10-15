import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.safety import confined, hash_file, open_verified_source, read_verified_bytes


class WindowsSourceHandleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cs-object-')
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.allowed = self.area/'allowed'; self.allowed.mkdir()
        self.source = self.allowed/'kaynak İı.txt'; self.source.write_bytes(b'source-bytes')

    def test_native_handle_preserves_source_and_exact_hash(self):
        before = self.source.read_bytes()
        self.assertEqual(before,read_verified_bytes(confined(self.source,[self.allowed])))
        self.assertEqual(hashlib.sha256(before).hexdigest(),hash_file(self.source))
        self.assertEqual(before,self.source.read_bytes())

    def test_native_hardlink_cannot_import_an_outside_object(self):
        outside = self.area/'outside.txt'; outside.write_bytes(b'outside-object')
        alias = self.allowed/'alias.txt'; os.link(outside,alias)
        self.assertEqual(2,alias.stat().st_nlink)
        with self.assertRaises(CoreError):confined(alias,[self.allowed])
        with self.assertRaises(CoreError):read_verified_bytes(alias)
        self.assertEqual(b'outside-object',outside.read_bytes())

    def test_native_writer_and_rename_are_denied_during_bound_read(self):
        with open_verified_source(self.source) as stream:
            with self.assertRaises(OSError):
                self.source.write_bytes(b'mutated')
            with self.assertRaises(OSError):
                self.source.rename(self.source.with_name('moved.txt'))
            self.assertEqual(b'source-bytes',stream.read())
        self.assertEqual(b'source-bytes',self.source.read_bytes())

    def test_native_directory_junction_is_rejected_before_read(self):
        import subprocess
        outside=self.area/'outside-dir'; outside.mkdir(); (outside/'secret.txt').write_bytes(b'secret')
        alias=self.allowed/'junction'
        command=f'New-Item -ItemType Junction -Path "{alias}" -Target "{outside}" | Out-Null'
        run=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,timeout=15)
        self.assertEqual(0,run.returncode,run.stderr)
        try:
            with self.assertRaises(CoreError):confined(alias/'secret.txt',[self.allowed])
            with self.assertRaises(CoreError):read_verified_bytes(alias/'secret.txt')
        finally:
            alias.rmdir() # Remove only the junction, never its target contents.
        self.assertEqual(b'secret',(outside/'secret.txt').read_bytes())

    def test_native_missing_source_is_access_loss_not_busy(self):
        missing=self.allowed/'taşındı İı.txt'
        for call in (lambda:read_verified_bytes(missing),lambda:hash_file(missing)):
            with self.assertRaises(CoreError) as error:call()
            self.assertEqual('ERISIM_YOK',error.exception.code);self.assertIn('bulunamadı',str(error.exception))
        self.assertFalse(missing.exists())

    def test_native_open_writer_is_reported_busy(self):
        with self.source.open('r+b'):
            with self.assertRaises(CoreError) as error:read_verified_bytes(self.source)
        self.assertEqual('KAYNAK_MESGUL',error.exception.code)
        self.assertEqual(b'source-bytes',read_verified_bytes(self.source))

    def test_native_oversized_bound_read_returns_no_content(self):
        with self.assertRaises(CoreError) as error:read_verified_bytes(self.source,limit=3)
        self.assertEqual('BOYUT_SINIRI',error.exception.code)
