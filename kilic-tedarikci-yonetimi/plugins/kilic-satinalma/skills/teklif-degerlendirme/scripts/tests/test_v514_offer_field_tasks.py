"""Regression (real set, RC11): offer field tasks ask only deterministic gaps of offer-level
fields; requirement assessment facts and model-answered fields are never re-asked."""
from pathlib import Path
import json, os, shutil, sys, tempfile, unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from db import connect, init_db
from task_queue import _offer_field_tasks
from context_packet import task_packet


class OfferFieldTaskTests(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault('TEKLIF_TEST_SQLITE', '1')
        self.root = Path(tempfile.mkdtemp(prefix="teklif-v514-"))
        init_db(self.root, SCRIPTS.parent)
        con = connect(self.root)
        con.execute("INSERT INTO offers(offer_id,supplier_id,display_name,status) VALUES ('O1','S1','Firma','active')")
        con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,offer_id,sha256,size_bytes,parse_status,active) VALUES ('D1','a.pdf','a.pdf','pdf','offer','S1','O1','h',1,'read',1)")
        rows = [
            ("O1/field/total", None, "total", "missing", "deterministic"),
            ("O1/field/incoterms", None, "incoterms", "missing", "semantic_llm"),
            ("O1/field/quantity", None, "quantity", "requires_confirmation", "semantic_llm"),
            ("O1/req/R1", "R1", "requirement_compliance", "missing", "semantic_llm"),
            ("O1/req/R2", "R2", "requirement_compliance", "requires_confirmation", "deterministic"),
        ]
        for fid, rid, key, status, path in rows:
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,requirement_id,field_key,evidence_status,critical,extraction_path) VALUES (?,?,?,?,?,?,?,?)",
                        [fid, "O1", "S1", rid, key, status, True, path])
        con.commit(); con.close()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def payloads(self):
        con = connect(self.root)
        try:
            return [json.loads(r[0]) for r in con.execute("SELECT payload_json FROM task_queue WHERE task_kind='offer_semantic_fields'").fetchall()]
        finally:
            con.close()

    def test_only_deterministic_offer_level_gaps_are_requested(self):
        con = connect(self.root)
        try:
            _offer_field_tasks(con, {})
            con.commit()
        finally:
            con.close()
        payloads = self.payloads()
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["fields"], ["total"])

    def test_no_task_when_only_model_answered_or_requirement_gaps_remain(self):
        con = connect(self.root)
        try:
            con.execute("UPDATE facts SET extraction_path='semantic_llm' WHERE fact_id='O1/field/total'")
            _offer_field_tasks(con, {})
            con.commit()
        finally:
            con.close()
        self.assertEqual(self.payloads(), [])

    def test_bounded_packet_allows_only_requested_field(self):
        con = connect(self.root)
        try:
            _offer_field_tasks(con, {})
            con.commit()
            task_id = con.execute("SELECT task_id FROM task_queue WHERE task_kind='offer_semantic_fields'").fetchone()[0]
        finally:
            con.close()
        packet = task_packet(self.root, task_id, max_units=8, max_chars=20000)
        self.assertEqual(packet["instructions"]["fields"], ["total"])
        self.assertEqual(packet["fact_contract"]["allowed_offer_field_keys"], ["total"])
        self.assertIn("no other fact field", packet["fact_contract"]["field_coverage"])


if __name__ == "__main__":
    unittest.main()
