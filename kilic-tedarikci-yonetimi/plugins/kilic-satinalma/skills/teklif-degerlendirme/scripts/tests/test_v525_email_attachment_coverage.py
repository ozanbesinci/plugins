"""MIME attachment bytes must enter the auditable document inventory."""
import hashlib
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

from ingest import ingest_source


class EmailAttachmentCoverageTests(unittest.TestCase):
    def test_attachment_identical_to_physical_file_is_audited_but_inactive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "offer.txt").write_bytes(b"same offer")
            message = EmailMessage()
            message.set_content("Ekli teklif")
            message.add_attachment(b"same offer", maintype="text", subtype="plain", filename="offer.txt")
            (source / "message.eml").write_bytes(message.as_bytes())
            inventory = ingest_source(source, root / "run")
            self.assertEqual(len(inventory), 3)
            child = next(row for row in inventory if row.get("parent_document_id"))
            self.assertFalse(child["active"])
            self.assertEqual(child["metadata"]["duplicate_of_relative_path"], "offer.txt")
            physical = next(row for row in inventory if row["relative_path"] == "offer.txt")
            self.assertNotIn("duplicate_of_relative_path", physical["metadata"])

    def test_email_attachments_are_child_documents_without_source_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            message = EmailMessage()
            message["Subject"] = "Ağ teklifi"
            message.set_content("Teklif yazışması")
            message.add_attachment(b"birinci fiyat", maintype="text", subtype="plain", filename="../teklif.txt")
            message.add_attachment(b"ikinci fiyat", maintype="text", subtype="plain", filename="teklif.txt")
            mail = source / "teklif.eml"
            mail.write_bytes(message.as_bytes())
            before = mail.read_bytes()
            inventory = ingest_source(source, root / "run")
            self.assertEqual(len(inventory), 3)
            self.assertEqual(mail.read_bytes(), before)
            children = [row for row in inventory if row.get("parent_document_id")]
            self.assertEqual(len(children), 2)
            self.assertEqual({row["sha256"] for row in children}, {
                hashlib.sha256(b"birinci fiyat").hexdigest(),
                hashlib.sha256(b"ikinci fiyat").hexdigest()})
            for child in children:
                self.assertTrue(Path(child["source_path"]).is_relative_to((root / "run").resolve()))
                self.assertIn("email_part_number", child["metadata"])


if __name__ == "__main__":
    unittest.main()
