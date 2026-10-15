"""Behavior build identity and real persisted reader namespace regressions."""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import test_context as fixtures
from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.runtime_identity import ROOT, _reader_files, reader_build_identity, component_identity
from sozlesme_cekirdek.safety import hash_file


class BuildIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cs-build-id-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in _reader_files():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def test_actual_reader_code_changes_fingerprint_without_version_bump(self):
        before = reader_build_identity(self.root)
        path = self.root / "src/sozlesme_cekirdek/readers/common.py"
        path.write_bytes(path.read_bytes() + b"\n# synthetic immutable reader build variant\n")
        self.assertNotEqual(before, reader_build_identity(self.root))

    def test_schema_changes_fingerprint(self):
        before = reader_build_identity(self.root)
        path = self.root / "schemas/p2_reading.schema.json"
        value = json.loads(path.read_text())
        value["description"] = "Synthetic changed schema build"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertNotEqual(before, reader_build_identity(self.root))

    def test_instruction_document_does_not_change_reader_build(self):
        before = reader_build_identity(self.root)
        (self.root / "README.md").write_text("Instruction-only change", encoding="utf-8")
        self.assertEqual(before, reader_build_identity(self.root))

    def _with_optional(self, versions, kind):
        real = importlib.metadata.version
        def fake(name):
            if name in versions:
                if versions[name] is None:
                    raise importlib.metadata.PackageNotFoundError(name)
                return versions[name]
            return real(name)
        with mock.patch.object(importlib.metadata, "version", fake):
            return reader_build_identity(self.root, kind=kind)

    def test_unrelated_host_packages_do_not_change_docx_or_eml_build(self):
        # CR-10: system Python with numpy/cryptography vs private venv without them.
        bare = {"numpy": None, "defusedxml": None, "cryptography": None}
        loaded = {"numpy": "2.5.1", "defusedxml": "0.7.1", "cryptography": "48.0.0"}
        for kind in ("DOCX", "EML"):
            self.assertEqual(self._with_optional(bare, kind), self._with_optional(loaded, kind), kind)

    def test_format_relevant_optional_packages_still_change_build(self):
        self.assertNotEqual(self._with_optional({"defusedxml": None}, "XLSX"), self._with_optional({"defusedxml": "0.7.1"}, "XLSX"))
        self.assertNotEqual(self._with_optional({"numpy": None}, "XLSX"), self._with_optional({"numpy": "2.5.1"}, "XLSX"))
        self.assertNotEqual(self._with_optional({"cryptography": None}, "PDF"), self._with_optional({"cryptography": "48.0.0"}, "PDF"))
        self.assertEqual(self._with_optional({"defusedxml": None}, "PDF"), self._with_optional({"defusedxml": "0.7.1"}, "PDF"))

    def test_build_identity_is_format_specific_and_rejects_unknown_format(self):
        self.assertNotEqual(reader_build_identity(self.root, kind="DOCX"), reader_build_identity(self.root, kind="EML"))
        with self.assertRaises(CoreError):
            reader_build_identity(self.root, kind="ODT")

    def test_component_versions_are_distinct_and_commit_is_not_invented(self):
        identity = component_identity()
        self.assertEqual("0.1.0", identity["plugin_version"])
        self.assertEqual("0.2.0", identity["core_version"])
        self.assertEqual("p6-1.2", identity["result_schema_version"])
        self.assertEqual("2.3.0", identity["vendor_version"])
        self.assertIsNone(identity["source_commit"])
        self.assertEqual("UNVERIFIED", identity["source_commit_attestation"])
        self.assertEqual(64, len(identity["source_digest"]))


class ReaderNamespaceTests(unittest.TestCase):
    setUp = fixtures.ContextTests.setUp
    rev = fixtures.ContextTests.rev
    document = fixtures.ContextTests.document

    def test_real_changed_build_process_does_not_reuse_old_processing(self):
        old = self.reading["processing_id"]
        source_sha = hash_file(self.path)
        with tempfile.TemporaryDirectory(prefix="cs-new-build-") as directory:
            changed = Path(directory) / "package"
            shutil.copytree(ROOT, changed, ignore=shutil.ignore_patterns(".runtime", "__pycache__"))
            code = changed / "src/sozlesme_cekirdek/readers/common.py"
            code.write_bytes(code.read_bytes() + b"\n# synthetic changed code, identical declared reader version\n")
            env = dict(os.environ, PYTHONPATH=str(changed / "src"), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
            command = [sys.executable, "-X", "utf8", "-m", "sozlesme_cekirdek", "--workspace", str(self.store.root),
                       "--output-root", str(self.area), "--source-root", str(self.sources), "document-read", "--case-id", self.case,
                       "--version-id", self.version, "--format", "DOCX"]
            completed = subprocess.run(command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90)
            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            output = json.loads(completed.stdout)
            self.assertNotEqual(old, output["result"]["processing_id"])
            self.assertFalse(output["result"]["reused"])
            self.assertEqual(source_sha, output["result"]["result"]["sha256"])
            self.assertEqual("0.2.0", output["tool_version"])
            self.assertIsNone(output["components"]["source_commit"])
        self.assertEqual(source_sha, hash_file(self.path))


if __name__ == "__main__":
    unittest.main()
