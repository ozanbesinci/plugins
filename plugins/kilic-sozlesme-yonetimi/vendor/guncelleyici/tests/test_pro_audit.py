"""Named regression contracts for the 2026-10-03 Pro second audit.

These tests are intentionally explicit: a future refactor that removes a safety
control must fail with the audit finding identifier rather than only a generic
source-contract failure. They do not replace native Windows acceptance tests.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / "scripts"


def text(path):
    return path.read_text(encoding="utf-8-sig")


class ProHighPriorityContracts(unittest.TestCase):
    def test_Y1_mcp_preserves_unknown_fields_and_uses_transaction(self):
        src = text(S / "mcp_ayar.py")
        self.assertIn("config_transaction", src)
        self.assertIn("expected = copy.deepcopy(before)", src)
        self.assertIn('entry["command"] = executable', src)
        self.assertNotIn('entry = {"command": executable', src)

    def test_Y2_plan_binds_targets_code_identity_and_revalidates_under_lock(self):
        src = text(S / "core.ps1")
        apply = src.split("function Apply-Plan", 1)[1].split("function Verify-Selected", 1)[0]
        self.assertIn("code_fingerprint=(Get-CodeFingerprint)", src)
        self.assertIn("before_fingerprint", src)
        self.assertLess(apply.index("Enter-Guard"), apply.index("Get-Observation $component.key -LocalOnly"))
        self.assertNotIn("Build-Plan", apply)
        self.assertNotIn("Get-RemoteJson", apply)

    def test_Y3_version_health_and_verify_are_separate(self):
        core = text(S / "core.ps1")
        chat = text(S / "sohbet.ps1")
        self.assertIn("Sürüm kontrolü güncel; bu taramada işlev testi çalıştırılmadı.", core)
        self.assertIn("function Read-Health", core)
        self.assertIn("function Verify-Selected", core)
        self.assertIn("'scan','apply','verify'", chat)

    def test_Y4_failure_recovery_is_explicit_for_mutating_components(self):
        node = text(S / "node-kur.ps1")
        pnpm = text(S / "pnpm-kur.ps1")
        py = text(S / "python-kur.ps1")
        libs = text(S / "kurulum-testi.py")
        duck = text(S / "python-paket-kur.py")
        for src in (node, pnpm):
            self.assertIn("backup", src)
            self.assertIn("recovery_required", src)
        self.assertIn("MutationStarted", py)
        self.assertIn("recovery_required", libs)
        self.assertIn("recovery_required", duck)

    def test_Y5_shared_python_is_guarded_and_nontransactional_risk_is_disclosed(self):
        core = text(S / "core.ps1")
        common = text(S / "program-ortak.ps1")
        ref = text(ROOT / "references" / "program-kurulumu.md")
        self.assertIn("Assert-MaintenanceWindow", core)
        self.assertIn("Get-CimInstance Win32_Process", common)
        self.assertIn("transactional_rollback=$false", core)
        self.assertIn("pip tüm paketler için atomik bir geri dönüş sağlamaz", ref)

    def test_Y6_selection_is_not_apply_and_cli_requires_confirmation(self):
        core = text(S / "core.ps1")
        chat = text(S / "sohbet.ps1")
        skill = text(ROOT / "SKILL.md")
        self.assertIn("if(-not $Confirmed)", core)
        self.assertIn("[switch]$ConfirmApply", chat)
        self.assertIn("-ConfirmApply", skill)
        self.assertIn("Seçim değiştirmek kurulum değildir", skill)

    def test_Y7_not_run_is_not_pass_and_mcp_schema_is_validated(self):
        safe = text(S / "islem_guvencesi.py")
        pbi = text(S / "powerbi-mcp-kur.ps1")
        self.assertIn('return "NOT_RUN"', safe)
        self.assertIn("MCP boş/geçersiz araç listesi", pbi)
        self.assertIn("inputSchema", pbi)


class ProMediumPriorityContracts(unittest.TestCase):
    def test_O1_scan_uses_local_or_readonly_modes(self):
        core = text(S / "core.ps1")
        self.assertIn("'-LocalOnly'", core)
        self.assertIn("'-YalnizBul'", core)
        self.assertIn("'--local-only'", core)
        self.assertIn("'--yalniz-bul'", core)

    def test_O2_cross_session_file_guard_and_run_token_exist(self):
        core = text(S / "core.ps1")
        common = text(S / "program-ortak.ps1")
        self.assertIn("update.guard", core)
        self.assertIn("GUNCELLEYICI_RUN_TOKEN", core)
        self.assertIn("GUNCELLEYICI_RUN_TOKEN", common)

    def test_O3_supply_chain_checks_are_component_specific(self):
        py = text(S / "python-kur.ps1")
        node = text(S / "node-kur.ps1")
        pnpm = text(S / "pnpm-kur.ps1")
        pbi = text(S / "powerbi-mcp-kur.ps1")
        self.assertIn("Python Software Foundation", py)
        self.assertIn("OpenJS Foundation", node)
        self.assertIn("SHA512", pnpm)
        self.assertIn("Microsoft Corporation", pbi)

    def test_O4_removed_offer_component_has_no_dispatch_or_installer(self):
        core = text(S / "core.ps1")
        self.assertNotIn("teklif-guncelle.py", core)
        self.assertNotIn("Get-OfferLatest", core)
        self.assertFalse((S / "teklif-guncelle.py").exists())
        self.assertFalse((S / "teklif_paket_legacy.py").exists())

    def test_O5_json_and_process_exit_contract_are_coupled(self):
        common = text(S / "program-ortak.ps1")
        chat = text(S / "sohbet.ps1")
        self.assertIn("if ($r.ExitCode -ne 0)", common)
        self.assertIn("process_exit_code", common)
        self.assertIn("if($out.status -in 'error','busy','stale'){exit 2}", chat)

    def test_O6_timeout_kills_only_spawned_process_tree(self):
        common = text(S / "program-ortak.ps1")
        self.assertIn("taskkill.exe", common)
        self.assertIn("/PID $process.Id /T /F", common)
        self.assertNotIn("Stop-Process -Name", common)

    def test_O7_upstream_stable_is_not_mislabeled_corporate_approved(self):
        ref = text(ROOT / "references" / "program-kurulumu.md")
        build = text(ROOT / "BUILD.json")
        self.assertIn("şirketçe onaylandı iddiasında bulunmaz", ref)
        self.assertIn('"production_approved": false', build)


if __name__ == "__main__":
    unittest.main()
