import json,tempfile,unittest
from pathlib import Path
from db import init_db,connect
from record_results import _record_document_classification
class OfferSourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name);init_db(self.run);self.con=connect(self.run)
        for did,fmt in [("excel","xlsx"),("image","image")]:
            self.con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,sha256,size_bytes,parse_status) VALUES (?,?,?,?,?,?,?)",[did,did,did,fmt,did+"hash",10,"PASS"])
    def tearDown(self):self.con.close();self.tmp.cleanup()
    def classify(self,did):return _record_document_classification(self.con,{"document_id":did},{"document_role":"offer","supplier_name":"Delta","confidence":0.9})
    def test_second_format_is_included_and_source_hashes_unchanged(self):
        before=self.con.execute("SELECT document_id,sha256 FROM documents ORDER BY document_id").fetchall()
        self.classify("excel");self.classify("image")
        offers=self.con.execute("SELECT source_document_ids_json FROM offers").fetchall()
        self.assertEqual(len(offers),2);self.assertEqual(sorted(x for row in offers for x in json.loads(row[0])),["excel","image"])
        self.assertEqual(self.con.execute("SELECT count(DISTINCT offer_id) FROM documents").fetchone()[0],2)
        self.assertEqual(self.con.execute("SELECT count(DISTINCT supplier_id) FROM documents").fetchone()[0],1)
        self.assertEqual(self.con.execute("SELECT document_id,sha256 FROM documents ORDER BY document_id").fetchall(),before)
    def test_repeated_classification_does_not_duplicate_or_drop_source(self):
        self.classify("excel");self.classify("image");self.classify("image")
        self.assertEqual(sorted(x for row in self.con.execute("SELECT source_document_ids_json FROM offers").fetchall() for x in json.loads(row[0])),["excel","image"])
    def test_invalid_existing_list_is_not_silently_replaced(self):
        self.classify("excel");self.con.execute("UPDATE offers SET source_document_ids_json='broken'")
        with self.assertRaisesRegex(ValueError,"source document"):self.classify("excel")
        self.assertEqual(self.con.execute("SELECT source_document_ids_json FROM offers").fetchone()[0],"broken")
