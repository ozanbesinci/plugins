"""Scanned unknown PDF classifications must expose their actual pixels."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from context_packet import task_packet
from db import connect
from ingest import ingest_source
from task_queue import generate_initial_tasks
from record_results import _record_requirements


class ScannedPdfClassificationTests(unittest.TestCase):
    def test_image_specification_extraction_lists_pixels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            Image.new("RGB", (300, 200), "white").save(source / "drawing.jpeg", "JPEG")
            run = root / "run"
            inventory = ingest_source(source, run)
            con = connect(run)
            try:
                con.execute("UPDATE documents SET document_role='specification' WHERE document_id=?",
                            [inventory[0]["document_id"]])
                con.commit()
            finally:
                con.close()
            generate_initial_tasks(run, "yuksek_guvence")
            con = connect(run)
            try:
                task_id = con.execute("SELECT task_id FROM task_queue WHERE task_kind='requirements_extraction'").fetchone()[0]
            finally:
                con.close()
            packet = task_packet(run, task_id, max_units=8, max_chars=20000)
            self.assertEqual(len(packet["visual_paths"]), 1)
            self.assertEqual(packet["visual_paths"][0]["sha256"], inventory[0]["sha256"])
            self.assertIn("requires_confirmation", packet["instructions"]["image_evidence"])
            self.assertIn("do not invent page=1", packet["instructions"]["image_evidence"])
            unit_id = packet["units"][0]["unit_id"]
            evidence = {"evidence_id": "image-number", "document_id": inventory[0]["document_id"],
                        "unit_id": unit_id, "locator": {"region": [0, 0, 300, 200]},
                        "quote": "51 METRE", "evidence_status": "verified"}
            requirement = {"text": "Ağın çapı 51 metre olmalıdır.", "critical": True,
                           "source_unit_id": unit_id, "evidence_id": "image-number"}
            con = connect(run)
            try:
                task = {"task_id": task_id, "document_id": inventory[0]["document_id"]}
                con.execute("BEGIN TRANSACTION")
                with self.assertRaisesRegex(ValueError, "requires independent confirmation"):
                    _record_requirements(con, task, packet["instructions"],
                                         {"evidence": [evidence], "requirements": [requirement]})
                con.rollback()
                evidence["evidence_status"] = "requires_confirmation"
                counts = _record_requirements(con, task, packet["instructions"],
                                              {"evidence": [evidence], "requirements": [requirement]})
                self.assertEqual(counts, {"requirements": 1, "evidence": 1})
                self.assertEqual(con.execute("SELECT extraction_path,evidence_status FROM evidence WHERE evidence_id='image-number'").fetchone(),
                                 ("vision", "requires_confirmation"))
            finally:
                con.close()

    def test_unknown_scanned_pdf_is_visual_task_with_rendered_page(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            Image.new("RGB", (300, 200), "white").save(source / "scan.pdf", "PDF")
            run = root / "run"
            inventory = ingest_source(source, run)
            self.assertEqual(inventory[0]["parse_status"], "partial")
            generate_initial_tasks(run, "yuksek_guvence")
            con = connect(run)
            try:
                row = con.execute("SELECT task_id,role FROM task_queue WHERE task_kind='document_classification'").fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[1], "visual_exception")
            finally:
                con.close()
            packet = task_packet(run, row[0], max_units=8, max_chars=20000)
            self.assertEqual(len(packet["visual_paths"]), 1)
            self.assertEqual(packet["visual_paths"][0]["page"], 1)
            self.assertTrue(Path(packet["visual_paths"][0]["path"]).is_file())
            self.assertTrue(Path(packet["visual_paths"][0]["path"]).resolve().is_relative_to(run.resolve()))


if __name__ == "__main__":
    unittest.main()
