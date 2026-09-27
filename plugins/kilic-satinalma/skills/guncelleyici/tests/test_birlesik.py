"""Ensure the offer release cannot restore an old updater or alter the merged skill."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "skills" / "guncelleyici" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "teklif-degerlendirme" / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paket_olustur import build
from teklif_paket_legacy import UpdateError
from test_teklif_paket import package as old_package

OFFER_VERSION = (ROOT / "skills" / "teklif-degerlendirme" / "VERSION").read_text(encoding="utf-8").strip()
CHANGED_VERSION = ".".join([*OFFER_VERSION.split(".")[:-1], str(int(OFFER_VERSION.split(".")[-1]) + 1)]) + "\n"

spec = importlib.util.spec_from_file_location("teklif_guncelle", ROOT / "skills" / "guncelleyici" / "scripts" / "teklif-guncelle.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class BirlesikTest(unittest.TestCase):
    def test_check_compares_component_version_not_bundle_label(self):
        for release_version, offer_version, expected in (
            ("3.1.0", "3.2.0", "available"),
            ("3.2.0", "3.1.1", "up_to_date"),
        ):
            with self.subTest(release=release_version), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                updater.apply(root, *old_package("3.1.1"), "3.1.1")
                data, digest = old_package(release_version, versions={
                    "teklif-degerlendirme": offer_version,
                    "teklif-degerlendirme-guncelle": "1.2.0"})
                release = {"version": release_version, "name": "release.zip",
                           "checksum_url": "checksum", "archive_url": "archive"}
                def download(url, limit=None):
                    return f"{digest}  release.zip".encode() if url == "checksum" else data
                prepared = {}
                with patch.object(updater, "latest_release", return_value=release), patch.object(updater, "download", side_effect=download):
                    result = updater.inspect(root, prepared)
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["latest"], offer_version)
                self.assertEqual(prepared["data"], data)
                self.assertEqual(updater.state_for(root)["version"], "3.1.1")

    def test_check_rejects_corrupted_release(self):
        with tempfile.TemporaryDirectory() as td:
            release = {"version": "3.1.1", "name": "release.zip", "checksum_url": "checksum", "archive_url": "archive"}
            with patch.object(updater, "latest_release", return_value=release), patch.object(updater, "download", side_effect=[b"0" * 64 + b"  release.zip", b"corrupt"]):
                with self.assertRaises(UpdateError):
                    updater.inspect(Path(td))
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_unified_update_rolls_back_when_state_write_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            updater.apply(root, *old_package("3.0.1"), "3.0.1")
            before = updater.tree(root)
            old_state = (root / updater.STATE).read_bytes()
            actual_replace = updater.replace_path
            def fail_state(source, target):
                if Path(target) == root / updater.STATE:
                    raise OSError("simulated state write failure")
                return actual_replace(source, target)
            with patch.object(updater, "replace_path", side_effect=fail_state):
                with self.assertRaises(OSError):
                    updater.apply(root, *old_package("3.1.1"), "3.1.1")
            self.assertEqual(updater.tree(root), before)
            self.assertEqual((root / updater.STATE).read_bytes(), old_state)
            self.assertFalse((root / updater.JOURNAL).exists())

    def test_failed_rollback_retains_journal_and_blocks_next_update(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            updater.apply(root, *old_package("3.0.1"), "3.0.1")
            actual_replace = updater.replace_path
            def fail_placement_and_restore(source, target):
                if Path(target) == root / updater.NAME:
                    raise OSError("simulated locked target")
                return actual_replace(source, target)
            with patch.object(updater, "replace_path", side_effect=fail_placement_and_restore):
                with self.assertRaises(OSError):
                    updater.apply(root, *old_package("3.1.1"), "3.1.1")
            self.assertTrue((root / updater.JOURNAL).exists())
            self.assertTrue(any(root.glob(".teklif-only-stage-*/old/VERSION")))
            with self.assertRaises(UpdateError):
                updater.apply(root, *old_package("3.1.1"), "3.1.1")

    def test_local_candidate_registers_only_when_package_matches(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = base / f"teklif-degerlendirme-v{OFFER_VERSION}.zip"
            info = build(ROOT / "skills", package)
            installed = base / "installed"
            installed.mkdir()
            shutil.copytree(ROOT / "skills" / "teklif-degerlendirme", installed / "teklif-degerlendirme",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            result = updater.register(installed, package.read_bytes(), info["sha256"])
            self.assertEqual(result["status"], "registered")
            self.assertEqual(updater.state_for(installed)["version"], OFFER_VERSION)
            state_path = installed / ".guncelleyici-teklif-install.json"
            stale = json.loads(state_path.read_text(encoding="utf-8"))
            stale["files"]["skills/teklif-degerlendirme/VERSION"] = "0" * 64
            state_path.write_text(json.dumps(stale), encoding="utf-8")
            with self.assertRaises(UpdateError):
                updater.register(installed, package.read_bytes(), info["sha256"])
            updater.register(installed, package.read_bytes(), info["sha256"], replace_local=True)
            self.assertEqual(updater.state_for(installed)["version"], OFFER_VERSION)
            (installed / "teklif-degerlendirme" / "VERSION").write_text(CHANGED_VERSION, encoding="utf-8")
            with self.assertRaises(UpdateError):
                updater.register(installed, package.read_bytes(), info["sha256"])

    def test_old_paired_release_does_not_restore_old_updater(self):
        versions = {"teklif-degerlendirme": "3.1.1",
                    "teklif-degerlendirme-guncelle": "1.1.0"}
        archive, digest = old_package("3.1.1", versions=versions)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            merged = root / "guncelleyici"
            merged.mkdir()
            marker = merged / "marker.txt"
            marker.write_text("unchanged", encoding="utf-8")
            result = updater.apply(root, archive, digest, "3.1.1")
            self.assertEqual(result["version"], "3.1.1")
            self.assertFalse((root / "teklif-degerlendirme-guncelle").exists())
            self.assertEqual(marker.read_text(encoding="utf-8"), "unchanged")

    def test_schema_one_release_remains_readable(self):
        archive, digest = old_package("3.0.1")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = updater.apply(root, archive, digest, "3.0.1")
            self.assertEqual(result["version"], "3.0.1")
            self.assertFalse((root / "teklif-degerlendirme-guncelle").exists())

    def test_release_changes_only_offer_tree_and_rejects_local_change(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            package = base / f"teklif-degerlendirme-v{OFFER_VERSION}.zip"
            info = build(ROOT / "skills", package)
            installed = base / "installed"
            installed.mkdir()
            merged = installed / "guncelleyici"
            merged.mkdir()
            marker = merged / "marker.txt"
            marker.write_text("unchanged", encoding="utf-8")
            result = updater.apply(installed, package.read_bytes(), info["sha256"], OFFER_VERSION)
            self.assertEqual(result["status"], "installed")
            self.assertEqual(marker.read_text(encoding="utf-8"), "unchanged")
            self.assertFalse((installed / "teklif-degerlendirme-guncelle").exists())
            self.assertEqual(updater.state_for(installed)["version"], OFFER_VERSION)
            local = installed / "teklif-degerlendirme" / "VERSION"
            local.write_text(CHANGED_VERSION, encoding="utf-8")
            with self.assertRaises(UpdateError):
                updater.apply(installed, package.read_bytes(), info["sha256"], OFFER_VERSION)
            self.assertEqual(local.read_text(encoding="utf-8"), CHANGED_VERSION)
            self.assertEqual(marker.read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
