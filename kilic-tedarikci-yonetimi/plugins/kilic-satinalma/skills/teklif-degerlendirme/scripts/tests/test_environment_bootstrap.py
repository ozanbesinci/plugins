from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import environment_check as ec
from workflow import prepare


class EnvironmentBootstrapTests(unittest.TestCase):
    def test_requirements_parser_accepts_skill_requirements(self):
        root = SCRIPTS.parent
        result = ec.check_requirements(root / "requirements.txt")
        self.assertEqual(result["parse_errors"], [])
        self.assertTrue(any(x.get("package", "").lower() == "duckdb" for x in result["items"]))
    def test_both_pdf_renderers_have_installable_requirements_and_correct_imports(self):
        with tempfile.TemporaryDirectory() as td:
            req=Path(td)/"requirements.txt"
            req.write_text("PyMuPDF>=1.24,<2\nreportlab>=4,<6\n",encoding="utf-8")
            with patch.object(ec,"module_version",return_value={"available":False,"version":None}) as probe:
                result=ec.check_requirements(req)
            self.assertEqual(probe.call_args_list[0].args,("PyMuPDF","fitz"))
            self.assertEqual(probe.call_args_list[1].args,("reportlab","reportlab"))
            self.assertEqual(len(result["missing"]),2)
            self.assertFalse(result["ok"])
        declared={row["package"].casefold() for row in ec.parse_requirements(SCRIPTS.parent/"requirements.txt")}
        self.assertTrue({"pymupdf","reportlab"}<=declared)

    def test_environment_check_blocks_with_component_list_and_no_updater(self):
        fake_req = {
            "requirements_file": "requirements.txt",
            "items": [{"package": "duckdb", "requirement": "duckdb>=1.4,<2", "status": "missing"},
                      {"package": "openpyxl", "requirement": "openpyxl>=3.1,<4", "status": "version_mismatch", "version": "2.6.0"}],
            "missing": ["duckdb>=1.4,<2"], "version_mismatch": [{"requirement": "openpyxl>=3.1,<4", "installed": "2.6.0"}],
            "parse_errors": [], "ok": False,
        }
        with patch.object(ec, "check_requirements", return_value=fake_req), patch.object(
            ec, "check_duckdb_pdf", return_value={"duckdb": False, "pdf_extension": False, "required": True}
        ):
            result = ec.check(SCRIPTS.parent / "requirements.txt",require_pdf_extension=True)
        self.assertEqual(result["status"], "BLOCKED_ENVIRONMENT")
        self.assertEqual(result["action"], "STOP_ANALYSIS")
        self.assertFalse(result["automatic_installation"])
        self.assertFalse(result["installation_performed"])
        components = {x["component"]: x for x in result["missing_components"]}
        self.assertIn("duckdb", components)
        self.assertEqual(components["openpyxl"]["installed"], "2.6.0")
        self.assertEqual(sum(1 for x in result["missing_components"] if x["component"] == "duckdb"), 1)
        self.assertIn("duckdb>=1.4,<2", result["user_message"])
        self.assertIn("otomatik kurulum yapmaz", result["user_message"])
        text = repr(result).casefold()
        for removed in ("guncelleyici", "updater", "runtime_handoff", "repair-runtime", "repair"):  # negative-assertion: must stay absent
            self.assertNotIn(removed, text)

    def test_missing_pdf_extension_is_listed(self):
        ok_req = {"requirements_file": "r", "items": [], "missing": [], "version_mismatch": [], "parse_errors": [], "ok": True}
        with patch.object(ec, "check_requirements", return_value=ok_req), patch.object(
            ec, "check_duckdb_pdf", return_value={"duckdb": True, "pdf_extension": False, "pdf_installed": False, "required": True}
        ):
            result = ec.check(SCRIPTS.parent / "requirements.txt",require_pdf_extension=True)
        self.assertEqual(result["status"], "BLOCKED_ENVIRONMENT")
        self.assertEqual([x["component"] for x in result["missing_components"]], ["DuckDB pdf eklentisi"])

    def test_optional_secondary_pdf_reader_does_not_block_or_claim_available(self):
        ok_req={"requirements_file":"r","items":[],"missing":[],"version_mismatch":[],"parse_errors":[],"ok":True}
        with patch.object(ec,"check_requirements",return_value=ok_req),patch.object(
            ec,"check_duckdb_pdf",return_value={"duckdb":True,"pdf_extension":False,"pdf_installed":False,"required":False}
        ) as probe:
            result=ec.check(SCRIPTS.parent/"requirements.txt")
        probe.assert_called_once_with(require_pdf_extension=False)
        self.assertEqual(result["status"],"READY")
        self.assertEqual(result["missing_components"],[])
        self.assertFalse(result["duckdb"]["pdf_extension"])
        self.assertTrue(result["warnings"])
        self.assertFalse(result["installation_performed"])

    def test_strict_cli_exit_3_for_missing_requirement_without_installing(self):
        import subprocess, json as _json
        with tempfile.TemporaryDirectory(prefix="teklif-env-cli-") as td:
            req = Path(td) / "requirements.txt"
            req.write_text("teklif_synthetic_missing_probe_20261004>=1" + chr(10), encoding="ascii")
            proc = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "environment_check.py"), "--strict",
                                   "--pdf-extension-optional", "--requirements", str(req)],
                                  capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 3, proc.stderr)
            report = _json.loads(proc.stdout)
            self.assertEqual(report["status"], "BLOCKED_ENVIRONMENT")
            self.assertEqual(report["missing_components"][0]["component"], "teklif_synthetic_missing_probe_20261004")
            self.assertIn("teklif analizi başlatılmadı", proc.stderr)

    def test_prepare_blocks_before_ingest_when_environment_not_ready(self):
        old = os.environ.pop("TEKLIF_TEST_SQLITE", None)
        try:
            with tempfile.TemporaryDirectory(prefix="teklif-env-gate-") as td:
                source = Path(td) / "source"; source.mkdir()
                run = Path(td) / "run"
                fake = {
                    "status": "BLOCKED_ENVIRONMENT", "blocking_reasons": ["DuckDB Python paketi yüklenemedi"],
                    "missing_components": [{"component": "duckdb", "required": "duckdb>=1.4,<2", "installed": None, "reason": "Python paketi bulunamadı"}],
                    "user_message": "Çalışma ortamı hazır değil",
                }
                with patch("environment_check.check", return_value=fake) as preflight:
                    result = prepare(source, run, "standart")
                self.assertEqual(result["status"], "BLOCKED_ENVIRONMENT")
                self.assertEqual(result["missing_components"][0]["component"], "duckdb")
                self.assertFalse(result["installation_performed"])
                self.assertEqual(preflight.call_args.kwargs["require_pdf_extension"],False)
                self.assertNotIn("updater", repr(result).casefold())
                self.assertTrue((run / "environment.json").exists())
                self.assertFalse((run / "inventory.json").exists())
        finally:
            if old is not None:
                os.environ["TEKLIF_TEST_SQLITE"] = old
            else:
                os.environ.pop("TEKLIF_TEST_SQLITE", None)


if __name__ == "__main__":
    unittest.main()
