"""Real paired revisions and transaction failures, independent of analytic approval."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from db import connect, get_meta, set_meta
from common import sha256_file
from reviewed_snapshot import freeze
from report_export import export_report
from official_delivery import inspect_official, RegistrationError
from test_report_slice import seed

class OfficialAtomicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "run"
        seed(self.run, "hizli")
        freeze(self.run)
    def tearDown(self):
        self.tmp.cleanup()
    def export(self):
        with patch("report_export._recalc_with_excel", return_value={"available": False, "reason": "explicit_unit_no_com"}):
            return export_report(self.run)
    def state(self):
        con = connect(self.run)
        try:
            return (get_meta(self.run, "official_report_delivery"), con.execute("SELECT artifact_id,relative_path,sha256 FROM artifacts WHERE artifact_type IN ('xlsx','pdf','decision_snapshot') ORDER BY artifact_id").fetchall(), con.execute("SELECT count(*) FROM artifact_bindings").fetchone()[0])
        finally:
            con.close()
    def assert_old(self, first, before):
        self.assertEqual(self.state(), before)
        self.assertEqual(sha256_file(Path(first["xlsx"])), first["paired_revision"]["files"]["Teklif_Degerlendirme.xlsx"])
        self.assertEqual(inspect_official(self.run)["delivery_status"], "READY")
    def test_one_committed_revision_has_whole_artifact_group(self):
        first = self.export()
        self.assertEqual(inspect_official(self.run)["delivery_status"], "READY")
        self.assertEqual(len(first["paired_revision"]["artifact_ids"]), 3)
        self.assertEqual(Path(first["xlsx"]).parent, Path(first["pdf"]["path"]).parent)
        self.assertFalse((self.run / "output/Teklif_Degerlendirme.xlsx").exists())
        from cross_output_consistency import check
        consistency = check(self.run)
        self.assertFalse(any(f.get("field") == "artifact" and f.get("sheet") == "decision_snapshot.json" for f in consistency["findings"]), consistency)
    def test_missing_pdf_preserves_previous_pair_and_attempts_alternative(self):
        first = self.export(); before = self.state()
        with patch("pdf_renderer.render_pdf", side_effect=OSError("injected primary PDF failure")), patch("pdf_fallback.render_safety_pdf", side_effect=OSError("injected independent PDF failure")), patch("report_export._export_pdf_with_excel", return_value={"available": False}), self.assertRaises(OSError):
            self.export()
        self.assert_old(first, before)
    def test_independent_pdf_renderer_preserves_full_bound_values(self):
        with patch("pdf_renderer.render_pdf", side_effect=OSError("injected primary PDF failure")):
            report = self.export()
        self.assertEqual(report["pdf"]["renderer"], "pymupdf_fallback")
        self.assertEqual(inspect_official(self.run)["delivery_status"], "READY")
    def test_second_artifact_failure_rolls_back_entire_registration(self):
        first = self.export(); before = self.state()
        from report_export import _artifact
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(args[3])
            if len(calls) == 2: raise OSError("injected metadata write failure")
            return _artifact(*args, **kwargs)
        with patch("report_export._artifact", side_effect=fail_second), self.assertRaises(RegistrationError):
            self.export()
        self.assertEqual(calls, ["xlsx", "pdf"])
        self.assert_old(first, before)
    def test_commit_failure_preserves_pointer_rows_and_bindings(self):
        first = self.export(); before = self.state()
        real = connect(self.run)
        class BrokenCommit:
            def execute(self, *args): return real.execute(*args)
            def commit(self): raise OSError("injected commit failure")
            def rollback(self): return real.rollback()
            def close(self): return real.close()
        with patch("report_export.connect", return_value=BrokenCommit()), self.assertRaises(RegistrationError):
            self.export()
        self.assert_old(first, before)
    def test_primary_disk_failure_uses_other_directory(self):
        first = self.export()
        from official_delivery import _publish_directory
        def fail_primary(stage, target):
            if target.parent.parent.name == "output": raise PermissionError("injected primary disk failure")
            return _publish_directory(stage, target)
        with patch("official_delivery._publish_directory", side_effect=fail_primary):
            second = self.export()
        self.assertTrue(second["alternate_report_path_attempted"])
        self.assertIn("output_fallback", second["xlsx"])
        self.assertTrue(Path(first["xlsx"]).is_file())
        self.assertEqual(inspect_official(self.run)["delivery_status"], "READY")
    def test_snapshot_change_during_render_does_not_register_new_pair(self):
        first = self.export(); before = self.state()
        from pdf_renderer import render_pdf
        def change(model, path):
            rendered = render_pdf(model, path)
            set_meta(self.run, "decision_summary", "New decision during render")
            freeze(self.run)
            return rendered
        with patch("pdf_renderer.render_pdf", side_effect=change), self.assertRaises(RegistrationError):
            self.export()
        self.assert_old(first, before)
    def test_changed_pdf_or_filesystem_manifest_cannot_reuse_ready(self):
        first = self.export()
        path = Path(first["xlsx"]).parent / "manifest.json"
        value = json.loads(path.read_text(encoding="utf-8")); value["pair_validation"] = "FORGED_PASS"
        path.write_text(json.dumps(value), encoding="utf-8")
        self.assertEqual(inspect_official(self.run)["delivery_status"], "FAILED")
    def test_missing_published_pdf_cannot_be_ready(self):
        first = self.export()
        Path(first["pdf"]["path"]).unlink()
        result = inspect_official(self.run)
        self.assertEqual(result["delivery_status"], "FAILED")
        self.assertFalse(result["deliverable_artifacts"])
    def test_native_deadline_keeps_workbook_and_independent_pdf_deliverable(self):
        from office_execution import execute_office
        import shutil
        worker=Path(self.tmp.name)/'hung-office-fixture.py'
        worker.write_text("import sys,time\nfrom pathlib import Path\nPath(sys.argv[sys.argv.index('--input')+1]).write_bytes(b'unfinished copy')\ntime.sleep(30)\n",encoding='utf-8')
        attempts=[]
        def deadline(path):
            with patch('office_execution.platform.system',return_value='Windows'):
                result=execute_office('recalculate',path,timeout_seconds=0.4,_worker=worker)
            attempts.append(result)
            return result
        try:
            with patch('report_export._recalc_with_excel',side_effect=deadline):
                report=export_report(self.run)
            self.assertFalse(report['recalc']['available']);self.assertEqual(report['recalc']['reason'],'native_office_timeout')
            self.assertTrue(Path(report['xlsx']).is_file());self.assertTrue(Path(report['pdf']['path']).is_file())
            self.assertEqual(inspect_official(self.run)['delivery_status'],'READY')
            self.assertFalse(get_meta(self.run,'mechanical_qa_pass',False))
        finally:
            for attempt in attempts:
                if attempt.get('isolated_copy'):
                    work=Path(attempt['isolated_copy']).resolve()
                    self.assertEqual(work.parent,Path(tempfile.gettempdir()).resolve());self.assertTrue(work.name.startswith('kilic-office-'))
                    shutil.rmtree(work)
    def test_closed_model_tamper_blocks_old_verified_label(self):
        from test_v504_audit_regressions import V504AuditRegressionTests
        from validate_run import validate
        case = V504AuditRegressionTests()
        case.root = Path(self.tmp.name)
        case.src = case.root / "sealed-source"; case.src.mkdir()
        case.run = case.root / "sealed-run"
        case.valid_pair()
        with patch("report_export._recalc_with_excel", return_value={"available": True, "status": "explicit_unit_mock"}):
            final = case.finish_valid()
        self.assertEqual(final["status"], "VERIFIED", final)
        path = Path(final["report"]["xlsx"]).parent / "report_model.json"
        path.write_text('{"forged_model":true}', encoding="utf-8")
        result = validate(case.run)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("official report pair" in x for x in result["blocking_reasons"]), result)
