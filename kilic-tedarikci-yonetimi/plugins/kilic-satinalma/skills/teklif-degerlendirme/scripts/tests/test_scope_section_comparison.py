"""Source section identity must survive different model display labels."""
import json,unittest
from db import connect
from comparison_contract import assess
from independent_recompute import _raw_comparison_failures
import test_v504_audit_regressions as audit

class ScopeSectionComparisonTests(unittest.TestCase):
    setUp=audit.V504AuditRegressionTests.setUp
    tearDown=audit.V504AuditRegressionTests.tearDown
    offer=audit.V504AuditRegressionTests.offer
    valid_pair=audit.V504AuditRegressionTests.valid_pair

    def setup_sections(self):
        self.valid_pair();c=connect(self.run)
        rows=c.execute("SELECT fact_id,offer_id,evidence_id FROM facts WHERE field_key='scope_signature' ORDER BY offer_id").fetchall()
        self.rows=rows
        for i,(fid,oid,eid) in enumerate(rows):
            norm={'sections':[{'description':'model label '+str(i),'evidence_refs':[eid]}]}
            c.execute('UPDATE facts SET value_text=?,normalized_json=? WHERE fact_id=?',
                ['Pompa' if i==0 else 'Sadece yeşil fiyat hücreleri',json.dumps(norm),fid])
        c.commit();c.close()

    def independent_scope_failed(self):
        c=connect(self.run)
        try:
            cur=c.execute("SELECT * FROM facts WHERE evidence_status='verified'");keys=[x[0] for x in cur.description]
            facts={(r['offer_id'],r['field_key']):r for r in [dict(zip(keys,x)) for x in cur.fetchall()]}
            return 'scope_identity' in _raw_comparison_failures(c,[r[1] for r in self.rows],facts,{}, {})
        finally:c.close()

    def test_same_source_sections_different_display_labels_match(self):
        self.setup_sections();self.assertNotIn('scope_identity',assess(self.run)['failed_dimensions'])
        self.assertFalse(self.independent_scope_failed())

    def test_missing_wrong_owner_or_unverified_section_never_falls_back_to_label(self):
        self.setup_sections()
        for mode in ['missing','foreign','unverified']:
            with self.subTest(mode=mode):
                c=connect(self.run);fid,oid,eid=self.rows[0]
                ref='absent' if mode=='missing' else self.rows[1][2] if mode=='foreign' else eid
                c.execute('UPDATE facts SET normalized_json=? WHERE fact_id=?',[json.dumps({'sections':[{'evidence_refs':[ref]}]}),fid])
                if mode=='unverified':c.execute("UPDATE evidence SET evidence_status='requires_confirmation' WHERE evidence_id=?",[eid])
                c.commit();c.close()
                self.assertIn('scope_identity',assess(self.run)['failed_dimensions']);self.assertTrue(self.independent_scope_failed())

    def test_additional_different_section_blocks_even_when_first_matches(self):
        self.setup_sections();c=connect(self.run);fid,oid,eid=self.rows[0]
        extra=c.execute("SELECT evidence_id FROM facts WHERE offer_id=? AND field_key='total'",[oid]).fetchone()[0]
        c.execute('UPDATE facts SET normalized_json=? WHERE fact_id=?',[json.dumps({'sections':[{'evidence_refs':[eid]},{'evidence_refs':[extra]}]}),fid]);c.commit();c.close()
        self.assertIn('scope_identity',assess(self.run)['failed_dimensions']);self.assertTrue(self.independent_scope_failed())

    def test_duplicate_or_empty_sections_block(self):
        self.setup_sections()
        for sections in [[],[{'evidence_refs':[]}],[{'evidence_refs':[self.rows[0][2]]}]*2]:
            c=connect(self.run);c.execute('UPDATE facts SET normalized_json=? WHERE fact_id=?',[json.dumps({'sections':sections}),self.rows[0][0]]);c.commit();c.close()
            self.assertIn('scope_identity',assess(self.run)['failed_dimensions']);self.assertTrue(self.independent_scope_failed())
