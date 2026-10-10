import tempfile
import unittest
from pathlib import Path

from db import connect, init_db
from source_authority import refresh


class V525AuthorityScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="teklif-v525-authority-")
        self.root = Path(self.tmp.name)
        self.run = self.root / "run"
        init_db(self.run)
        self.con = connect(self.run)
        self.con.execute(
            "INSERT INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES ('S1','Ağ Sistemleri','ag sistemleri','confirmed')"
        )

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def add_doc(self, did, filename, *, role="offer", revision_label=None, mtime=None):
        self.con.execute(
            """INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,
               revision_label,source_mtime,sha256,size_bytes,parse_status,active)
               VALUES (?,?,?,'pdf',?,'S1',?,?,?,10,'read',true)""",
            [did, filename, filename, role, revision_label, mtime, f"sha-{did}"],
        )

    def authority(self):
        self.con.commit()
        return refresh(self.run)

    def states(self):
        return dict(self.con.execute("SELECT document_id,authority_status FROM source_authority").fetchall())

    def test_distinct_item_offers_from_same_supplier_remain_independent(self):
        self.add_doc("pump", "AĞ POMPA PROFORMA.pdf")
        self.add_doc("switch", "AĞ SWITCH PROFORMA.pdf")

        result = self.authority()

        self.assertEqual(result["controlling"], 2)
        self.assertEqual(result["unresolved"], 0)
        self.assertEqual(set(self.states().values()), {"controlling"})
        self.assertEqual(self.con.execute("SELECT count(*) FROM open_issues WHERE issue_type='source_authority_conflict' AND status='open'").fetchone()[0], 0)

    def test_matching_explicit_revision_root_stays_unresolved_regardless_of_mtime(self):
        self.add_doc("rev7", "AĞ PROFORMA 02-04REVİZE-7.pdf", revision_label="7", mtime=2_000_000_000)
        self.add_doc("rev8", "AĞ PROFORMA 02-04REVİZE-8.pdf", revision_label="8", mtime=1_000_000_000)

        result = self.authority()

        self.assertEqual(result["controlling"], 0)
        self.assertEqual(result["unresolved"], 2)
        self.assertEqual(set(self.states().values()), {"needs_input"})
        self.assertEqual(self.con.execute("SELECT count(*) FROM open_issues WHERE issue_type='source_authority_conflict' AND status='open'").fetchone()[0], 1)

    def test_rev_numbered_filename_pair_uses_shared_root(self):
        self.add_doc("rev1", "Alpha_rev1_teklifi.xlsx", revision_label="1")
        self.add_doc("rev2", "Alpha_rev2_teklifi.xlsx", revision_label="2")

        result = self.authority()

        self.assertEqual(result["controlling"], 0)
        self.assertEqual(result["unresolved"], 2)
        self.assertEqual(set(self.states().values()), {"needs_input"})

    def test_single_revision_tagged_offer_is_unresolved(self):
        self.add_doc("rev", "AĞ PROFORMA REVİZE-7.pdf", revision_label="7")

        result = self.authority()

        self.assertEqual(result["controlling"], 0)
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(self.states()["rev"], "needs_input")

    def test_unique_offer_controls_and_support_document_stays_supplemental(self):
        self.add_doc("offer", "AĞ PROFORMA.pdf")
        self.add_doc("support", "AĞ PROFORMA REVİZE-8.pdf", role="support", revision_label="8")

        result = self.authority()

        states = self.states()
        self.assertEqual(result["controlling"], 1)
        self.assertEqual(states["offer"], "controlling")
        self.assertEqual(states["support"], "supplemental")
        self.assertEqual(self.con.execute("SELECT count(*) FROM open_issues WHERE issue_type='source_authority_conflict' AND status='open'").fetchone()[0], 0)

    def test_unresolved_supplier_identity_still_blocks_unique_offer(self):
        self.add_doc("offer", "AĞ PROFORMA.pdf")
        self.con.execute("UPDATE suppliers SET identification_status='provisional' WHERE supplier_id='S1'")

        result = self.authority()

        self.assertEqual(result["controlling"], 0)
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(self.states()["offer"], "needs_input")
        self.assertEqual(self.con.execute("SELECT count(*) FROM open_issues WHERE issue_type='supplier_identity_unresolved' AND status='open'").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
