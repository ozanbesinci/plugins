"""Automatic setup: policy negatives and a real pinned installer in an empty profile."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class _AutomaticSetupCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="csa-", dir=os.environ.get("SOZLESME_TEST_PROFILE_ROOT"))
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name).resolve()
        self.env = dict(os.environ, USERPROFILE=str(self.profile))
        self.env.pop("SOZLESME_DEVELOPMENT", None)
        self.script = ROOT / "scripts/ortam-hazirla.ps1"

    def ps(self, body, timeout=60):
        command = ". " + quote(self.script) + " -LibraryOnly; " + body
        return subprocess.run(["powershell.exe", "-NoProfile", "-Command", command],
                              env=self.env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)


class AutomaticSetupPolicyTests(_AutomaticSetupCase):
    def test_library_load_does_not_download_or_create_user_environment(self):
        result = self.ps("'LOADED'")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("LOADED", result.stdout)
        self.assertFalse((self.profile / "KilicPython").exists())
        self.assertFalse((self.profile / "Downloads").exists())

    def test_failed_download_never_launches_installer_and_removes_only_own_partial(self):
        marker = self.profile / "must-not-run"
        result = self.ps("function Receive-SetupInstaller($Path) {[IO.File]::WriteAllText($Path,'partial');throw 'SYNTHETIC_NETWORK_FAILURE'}; "
                         "function Start-SetupInstaller($Path) {[IO.File]::WriteAllText(" + quote(marker) + ",'bad')}; "
                         "try {Invoke-ContractAutomaticSetup K03;exit 8} catch {$_.Exception.Message}")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("SYNTHETIC_NETWORK_FAILURE", result.stdout)
        self.assertFalse(marker.exists())
        self.assertEqual([], list(self.profile.rglob("*.partial")))
        self.assertFalse((self.profile / "KilicPython").exists())

    def test_wrong_download_hash_blocks_before_execution(self):
        result = self.ps("function Receive-SetupInstaller($Path) {[IO.File]::WriteAllText($Path,'wrong installer')}; "
                         "function Start-SetupInstaller($Path) {throw 'MUST_NOT_EXECUTE'}; "
                         "try {Invoke-ContractAutomaticSetup K03;exit 8} catch {$_.Exception.Message}")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("INSTALLER_HASH_MISMATCH", result.stdout)
        self.assertNotIn("MUST_NOT_EXECUTE", result.stdout)
        self.assertEqual([], list(self.profile.rglob("*.exe")))

    def test_existing_wrong_file_is_preserved_and_not_executed_or_downloaded_over(self):
        installer = self.profile / "Downloads/KilicSozlesme/KilicSozlesmeKurulum-0.1.1.exe"
        installer.parent.mkdir(parents=True)
        installer.write_bytes(b"synthetic different bytes")
        result = self.ps("function Receive-SetupInstaller($Path) {throw 'MUST_NOT_DOWNLOAD'}; "
                         "function Start-SetupInstaller($Path) {throw 'MUST_NOT_EXECUTE'}; "
                         "try {Invoke-ContractAutomaticSetup K03;exit 8} catch {$_.Exception.Message}")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("INSTALLER_HASH_MISMATCH", result.stdout)
        self.assertEqual(b"synthetic different bytes", installer.read_bytes())
        self.assertFalse((self.profile / "KilicPython").exists())

    def test_unfinished_existing_setup_is_not_repaired_or_replayed(self):
        state = self.profile / "KilicPython/sozlesme-setup/previous-run/keep.txt"
        state.parent.mkdir(parents=True)
        state.write_bytes(b"previous evidence")
        result = self.ps("function Receive-SetupInstaller($Path) {throw 'MUST_NOT_DOWNLOAD'}; "
                         "try {Invoke-ContractAutomaticSetup K03;exit 8} catch {$_.Exception.Message}")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("RECOVERY_REQUIRED", result.stdout)
        self.assertEqual(b"previous evidence", state.read_bytes())
        self.assertFalse((self.profile / "Downloads").exists())

    def test_missing_environment_uses_automatic_setup_without_personal_permission(self):
        protocol = (ROOT / "references/skill-runtime.md").read_text(encoding="utf-8")
        runtime = (ROOT / "references/runtime-integration.md").read_text(encoding="utf-8")
        self.assertIn("ortam-hazirla.ps1", protocol)
        self.assertIn("otomatik çalıştırıp", protocol)
        self.assertIn("kişisel izin isteme", protocol)
        self.assertNotIn("yayımlanmış indirme adresi yoktur", runtime)
        self.assertNotIn("Windows kurulum paketini indirip çalıştırın", runtime)


class AutomaticSetupNativeTests(_AutomaticSetupCase):
    def test_real_published_installer_installs_then_same_profile_reuses_ready_environment(self):
        installer = os.environ.get("SOZLESME_TEST_INSTALLER")
        if not installer:
            self.skipTest("NOT_RUN: explicit pinned published installer required")
        self.env["SOZLESME_TEST_INSTALLER"] = installer
        marker = self.profile / "download-count.txt"
        body = ("function Receive-SetupInstaller($Path) {"
                "[IO.File]::Copy($env:SOZLESME_TEST_INSTALLER,$Path);"
                "[IO.File]::AppendAllText(" + quote(marker) + ",'once')}; "
                "$a=Invoke-ContractAutomaticSetup K03; "
                "$b=Invoke-ContractAutomaticSetup K03; "
                "@{first=$a;second=$b}|ConvertTo-Json -Depth 30 -Compress")
        result = self.ps(body, timeout=360)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual("INSTALLED_AND_VERIFIED", value["first"]["automatic_setup"])
        self.assertEqual("READY", value["first"]["status"])
        self.assertTrue(value["first"]["resume_allowed"])
        self.assertEqual("REGISTERED", value["first"]["execution_profile"])
        self.assertEqual("NOT_NEEDED", value["second"]["automatic_setup"])
        self.assertEqual("READY", value["second"]["status"])
        self.assertEqual("once", marker.read_text())
        self.assertEqual(1, len(list((self.profile / "KilicPython/sozlesme-envs").iterdir())))
        self.assertTrue(all(p["status"] == "PASS" for p in value["first"]["packages"]))
