"""A run-scoped user declaration identifies supplier folders without a legal-name claim."""
import json
import tempfile
import unittest
from pathlib import Path

from common import stable_id
from db import connect, init_db
from ingest import ingest_source
from record_results import _record_document_classification
from source_authority import refresh
from task_queue import generate_initial_tasks


class UserFolderDeclarationTests(unittest.TestCase):
    def test_preparation_uses_declared_supplier_without_model_identity_task(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            supplier_dir = root / "source" / "teklifler" / "Akvaplast" / "REVİZE"
            supplier_dir.mkdir(parents=True)
            (supplier_dir / "teklif.txt").write_text("Fiyat teklifi: 12 EUR", encoding="utf-8")
            run = root / "run"
            inventory = ingest_source(root / "source", run, folder_mappings={"teklifler/Akvaplast": "Akvaplast"})
            self.assertEqual(len(inventory), 1)
            con = connect(run)
            try:
                self.assertEqual(con.execute("SELECT display_name,identification_status FROM suppliers").fetchall(),
                                 [("Akvaplast", "user_declared")])
            finally:
                con.close()
            created = generate_initial_tasks(run, "yuksek_guvence")
            self.assertEqual(created.get("document_classification", 0), 0)

    def test_nested_supplier_folder_uses_longest_declared_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            init_db(run)
            con = connect(run)
            try:
                declaration = {"source": "user_declaration", "mappings": {
                    "Bodrum-Mersin-Agromey/teklifler/Akvaplast": "Akvaplast",
                    "Bodrum-Mersin-Agromey/teklifler/Çakır": "Çakır"},
                    "legal_entity_verified": False}
                con.execute("INSERT INTO run_meta(key,value) VALUES (?,?)",
                            ["supplier_folder_declaration_v1", json.dumps(declaration, ensure_ascii=False)])
                for did, supplier, subfolder in (("docA", "Akvaplast", "REVİZE"), ("docC", "Çakır", "Çakır")):
                    old = stable_id("sup", did, length=16)
                    con.execute("INSERT INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES (?,?,?,'provisional')",
                                [old, did, did])
                    con.execute("""INSERT INTO documents(document_id,relative_path,filename,document_role,format_family,supplier_id,sha256,size_bytes,parse_status,active)
                                   VALUES (?,?,?,'unknown','pdf',?,?,10,'read',true)""",
                                [did, f"Bodrum-Mersin-Agromey/teklifler/{supplier}/{subfolder}/offer.pdf", "offer.pdf", old, did])
                    _record_document_classification(con, {"document_id": did}, {"document_role": "offer"})
                con.commit()
                self.assertEqual({row[0] for row in con.execute("SELECT display_name FROM suppliers").fetchall()}, {"Akvaplast", "Çakır"})
            finally:
                con.close()

    def test_declared_folder_name_groups_offers_when_model_returns_role_only(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            init_db(run)
            con = connect(run)
            try:
                declaration = {"source": "user_declaration", "mappings": {"Batu Balık": "Batu Balık"},
                               "legal_entity_verified": False}
                con.execute("INSERT INTO run_meta(key,value) VALUES (?,?)",
                            ["supplier_folder_declaration_v1", json.dumps(declaration, ensure_ascii=False)])
                for index in (1, 2):
                    did = f"doc{index}"
                    old = stable_id("sup", did, length=16)
                    con.execute("INSERT INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES (?,?,?,'provisional')",
                                [old, did, did])
                    con.execute("""INSERT INTO documents(document_id,relative_path,filename,document_role,format_family,supplier_id,sha256,size_bytes,parse_status,active)
                                   VALUES (?,?,?,'unknown','docx',?,?,10,'read',true)""",
                                [did, f"Batu Balık/item{index}.docx", f"item{index}.docx", old, f"sha{index}"])
                    _record_document_classification(con, {"document_id": did}, {"document_role": "offer"})
                con.commit()
                suppliers = con.execute("SELECT display_name,identification_status FROM suppliers").fetchall()
                offer_ids = con.execute("SELECT offer_id,supplier_id FROM offers ORDER BY offer_id").fetchall()
                self.assertEqual(suppliers, [("Batu Balık", "user_declared")])
                self.assertEqual(len(offer_ids), 2)
                self.assertEqual(len({row[1] for row in offer_ids}), 1)
            finally:
                con.close()
            authority = refresh(run)
            self.assertEqual(authority["controlling"], 2)
            self.assertEqual(authority["unresolved"], 0)


if __name__ == "__main__":
    unittest.main()
