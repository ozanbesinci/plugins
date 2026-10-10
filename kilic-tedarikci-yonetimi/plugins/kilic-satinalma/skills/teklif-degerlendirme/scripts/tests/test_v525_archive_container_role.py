"""The ZIP carrier must not become an extra commercial offer."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from db import connect
from adapters.archive_adapter import extract_zip
from ingest import ingest_source
from record_results import _record_document_classification
from task_queue import generate_initial_tasks


class ArchiveContainerRoleTests(unittest.TestCase):
    def test_zip_is_support_while_member_is_separate_document(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            with zipfile.ZipFile(source / "Çakır.zip", "w") as zf:
                zf.writestr("teklif.txt", "Fiyat teklifi 12 EUR")
            self.assertEqual(len(extract_zip(source / "Çakır.zip", root / "control-extraction")), 1)
            run = root / "run"
            inventory = ingest_source(source, run)
            self.assertEqual(len(inventory), 2, inventory)
            carrier = next(row for row in inventory if row["format_family"] == "zip")
            self.assertEqual(carrier["document_role"], "support")
            self.assertIsNone(carrier["offer_id"])
            self.assertEqual(next(row for row in inventory if row.get("parent_document_id"))["parent_document_id"], carrier["document_id"])
            generate_initial_tasks(run, "yuksek_guvence")
            con = connect(run)
            try:
                task = {"document_id": carrier["document_id"]}
                with self.assertRaisesRegex(ValueError, "Archive container cannot"):
                    _record_document_classification(con, task, {"document_role": "offer"})
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
