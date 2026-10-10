import json, tempfile, unittest
from pathlib import Path
from db import connect, init_db
from qa import _supersede_visual_findings
from common import sha256_file
from validate_run import validate

class FindingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name);init_db(self.run)
        self.con=connect(self.run);(self.run/"new.pdf").write_bytes(b"current PDF fixture")
        self.art={"artifact_id":"new","relative_path":"new.pdf","sha256":sha256_file(self.run/"new.pdf"),"created_at":"2026-10-04T02:00:00"}
        for aid,typ,created in [("old","pdf","01"),("new","pdf","02"),("sheet","xlsx","01")]:
            self.con.execute("INSERT INTO artifacts(artifact_id,artifact_type,relative_path,sha256,status,created_at) VALUES (?,?,?,?,?,?)",
                             [aid,typ,"new.pdf",self.art["sha256"],"ready","2026-10-04T"+created+":00:00"])
        for fid,aid,typ in [("old-layout","old","visual_layout"),("global",None,"manual_gate"),("sheet-layout","sheet","visual_layout"),("orphan","unknown","visual_layout")]:
            self.con.execute("INSERT INTO qa_findings(finding_id,artifact_id,finding_type,severity,status,message) VALUES (?,?,?,?,?,?)",[fid,aid,typ,"critical","open",fid])
        self.renders=[{"page":1,"sha256":"hash1"},{"page":2,"sha256":"hash2"}]
        for r in self.renders:self.con.execute("INSERT INTO render_hashes VALUES (?,?,?,?,?)",["new","page:"+str(r["page"]),r["sha256"],"pass","observed"])
    def tearDown(self):self.con.close();self.tmp.cleanup()
    def state(self,fid):return self.con.execute("SELECT status FROM qa_findings WHERE finding_id=?",[fid]).fetchone()[0]
    def test_pass_retires_old_only_and_preserves_audit_and_global_gate(self):
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,self.renders),1)
        self.assertEqual(self.state("old-layout"),"superseded")
        for fid in ["global","sheet-layout","orphan"]:self.assertEqual(self.state(fid),"open")
        event=self.con.execute("SELECT replacement_artifact_id,replacement_sha256 FROM qa_finding_supersessions").fetchone()
        self.assertEqual(event,("new",self.art["sha256"]))
        self.con.commit();self.con.close();self.con=connect(self.run)
        self.assertIn("global",validate(self.run)["blocking_reasons"])
    def test_current_failed_page_keeps_old_findings(self):
        self.con.execute("UPDATE render_hashes SET qa_status='fail' WHERE render_key='page:2'")
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,self.renders),0);self.assertEqual(self.state("old-layout"),"open")
    def test_missing_page_keeps_old_findings(self):
        self.con.execute("DELETE FROM render_hashes WHERE render_key='page:2'")
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,self.renders),0)
    def test_changed_render_hash_keeps_old_findings(self):
        self.con.execute("UPDATE render_hashes SET render_sha256='tampered' WHERE render_key='page:2'")
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,self.renders),0)
    def test_current_open_finding_is_not_silenced(self):
        self.con.execute("INSERT INTO qa_findings(finding_id,artifact_id,finding_type,severity,status,message) VALUES ('current','new','visual_layout','critical','open','current')")
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,self.renders),0)
        self.assertEqual(self.state("current"),"open")
    def test_tampered_pdf_and_empty_review_never_accept(self):
        (self.run/"new.pdf").write_bytes(b"tampered")
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,self.renders),0)
        self.assertEqual(_supersede_visual_findings(self.con,self.run,self.art,[]),0)
