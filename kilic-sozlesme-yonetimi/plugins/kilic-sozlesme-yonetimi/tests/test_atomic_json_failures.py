"""Real temporary-file ownership and preservation under serialization/I/O failure."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sozlesme_cekirdek import safety


class AtomicJSONTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="contract-atomic-")
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.target = self.area / "result.json"
        self.target.write_bytes(b'{"old":true}\n')
        self.before = self.target.read_bytes()
        self.foreign = self.area / "another-call.tmp"
        self.foreign.write_bytes(b"another operation owns this")

    def preserved(self):
        self.assertEqual(self.before, self.target.read_bytes())
        self.assertEqual(b"another operation owns this", self.foreign.read_bytes())
        self.assertEqual([], list(self.area.glob("result.json.*.tmp")))

    def test_nonfinite_and_unsupported_values_leave_no_temp(self):
        for value in [{"bad": float("nan")}, {"bad": object()}]:
            with self.assertRaises((ValueError, TypeError)):
                safety.atomic_json(self.target, value)
            self.preserved()

    def test_fsync_failure_preserves_target_and_cleans_owned_file(self):
        with patch.object(safety.os, "fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                safety.atomic_json(self.target, {"new": True})
        self.preserved()

    def test_replace_failure_preserves_target_and_cleans_owned_file(self):
        with patch.object(safety.os, "replace", side_effect=OSError("synthetic replace failure")):
            with self.assertRaises(OSError):
                safety.atomic_json(self.target, {"new": True})
        self.preserved()

    def test_transient_access_denied_on_replace_is_retried_boundedly(self):
        real = safety.os.replace
        calls = []
        def flaky(source, target):
            calls.append(source)
            if len(calls) < 3:
                raise PermissionError(13, "synthetic scanner handle")
            return real(source, target)
        with patch.object(safety.os, "replace", side_effect=flaky), patch.object(safety.time, "sleep") as sleep:
            safety.atomic_json(self.target, {"new": True})
        self.assertEqual(3, len(calls)); self.assertEqual(2, sleep.call_count)
        self.assertEqual(b'{"new":true}', self.target.read_bytes())
        self.assertEqual([], list(self.area.glob("result.json.*.tmp")))

    def test_persistent_access_denied_still_fails_and_cleans_owned_file(self):
        with patch.object(safety.os, "replace", side_effect=PermissionError(13, "denied")) as replace, \
                patch.object(safety.time, "sleep"), self.assertRaises(PermissionError):
            safety.atomic_json(self.target, {"new": True})
        self.assertEqual(len(safety.REPLACE_RETRY_SECONDS) + 1, replace.call_count)
        self.preserved()

    def test_other_replace_errors_are_not_retried(self):
        with patch.object(safety.os, "replace", side_effect=OSError("disk")) as replace, self.assertRaises(OSError):
            safety.atomic_json(self.target, {"new": True})
        self.assertEqual(1, replace.call_count)
        self.preserved()

    def test_staging_directory_rename_retries_transient_access_denied(self):
        # Store.snapshot/restore: just-closed DuckDB file inside the stage held by a scanner (WinError 5).
        stage, final = self.area / "restored.restore-pending", self.area / "restored"
        stage.mkdir(); (stage / "db").write_bytes(b"x")
        real = safety.os.rename
        calls = []
        def flaky(source, target):
            calls.append(source)
            if len(calls) < 3:
                raise PermissionError(13, "synthetic scanner handle")
            return real(source, target)
        with patch.object(safety.os, "rename", side_effect=flaky), patch.object(safety.time, "sleep") as sleep:
            safety.rename_owned(stage, final)
        self.assertEqual(3, len(calls)); self.assertEqual(2, sleep.call_count)
        self.assertEqual(b"x", (final / "db").read_bytes()); self.assertFalse(stage.exists())

    def test_staging_directory_rename_never_overwrites_and_gives_up(self):
        stage, final = self.area / "stage", self.area / "final"
        stage.mkdir(); final.mkdir(); (final / "keep").write_bytes(b"keep")
        with patch.object(safety.time, "sleep") as sleep, self.assertRaises(FileExistsError):
            safety.rename_owned(stage, final)
        self.assertEqual(0, sleep.call_count); self.assertEqual(b"keep", (final / "keep").read_bytes())
        with patch.object(safety.os, "rename", side_effect=PermissionError(13, "denied")) as rename, \
                patch.object(safety.time, "sleep"), self.assertRaises(PermissionError):
            safety.rename_owned(stage, self.area / "other")
        self.assertEqual(len(safety.REPLACE_RETRY_SECONDS) + 1, rename.call_count)
        self.assertTrue(stage.exists())

    def test_write_failure_preserves_target_and_cleans_owned_file(self):
        original_open = Path.open
        class BrokenWriter:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): return self
            def __exit__(self, *args): self.stream.close()
            def write(self, value): raise OSError("synthetic write failure")
        def opening(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return BrokenWriter(stream) if args and args[0] == "x" else stream
        with patch.object(Path, "open", opening), self.assertRaises(OSError):
            safety.atomic_json(self.target, {"new": True})
        self.preserved()

    def test_exclusive_open_failure_does_not_delete_unowned_collision(self):
        collision = self.area / "result.json.fixed.tmp"
        collision.write_bytes(b"unowned collision")
        with patch.object(safety, "uuid4", return_value="fixed"), self.assertRaises(FileExistsError):
            safety.atomic_json(self.target, {"new": True})
        self.assertEqual(b"unowned collision", collision.read_bytes())
        self.assertEqual(self.before, self.target.read_bytes())

    def test_success_uses_canonical_bytes_and_keeps_foreign_temp(self):
        safety.atomic_json(self.target, {"z": 1, "a": "İı"})
        self.assertEqual('{"a":"İı","z":1}'.encode("utf-8"), self.target.read_bytes())
        self.assertEqual([], list(self.area.glob("result.json.*.tmp")))
        self.assertTrue(self.foreign.exists())


if __name__ == "__main__":
    unittest.main()
