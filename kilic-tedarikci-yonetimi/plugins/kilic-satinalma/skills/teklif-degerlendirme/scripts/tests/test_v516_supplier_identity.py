import json
import tempfile
import unittest
from pathlib import Path

from db import init_db, connect
from common import stable_id
from ingest import revision_candidate, normalize_supplier_name, ingest_source
from record_results import _record_document_classification
from source_authority import refresh
from field_extract import extract


class SupplierIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.run=self.root/'run'
        init_db(self.run)

    def tearDown(self):
        self.tmp.cleanup()

    def add_doc(self,con,did,revision=None,role='unknown'):
        sid=stable_id('sup',did,length=16)
        con.execute("INSERT INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES (?,?,?,'provisional')",[sid,did,did])
        con.execute("INSERT INTO documents(document_id,relative_path,filename,document_role,format_family,supplier_id,revision_label,sha256,size_bytes,parse_status,active) VALUES (?,?,?,?,?,?,?,?,?,?,true)",[did,did,did+'.pdf',role,'pdf',sid,revision,did+'sha',10,'read'])
        return sid

    def classify(self,con,did,name='AKVAPLAST PLASTİK VE DENİZCİLİK A.Ş.'):
        return _record_document_classification(con,{'document_id':did},{'document_role':'offer','confidence':1,'supplier_name':name,'supplier_confidence':1 if name else None})

    def test_same_confirmed_supplier_keeps_eight_sources_and_unresolved_authority(self):
        con=connect(self.run)
        try:
            for n in range(8):
                did=f'doc{n}'; self.add_doc(con,did,str(n)); self.classify(con,did)
            self.assertEqual(con.execute("SELECT count(DISTINCT supplier_id) FROM documents").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT count(*) FROM suppliers").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT identification_status FROM suppliers").fetchone()[0],'confirmed')
            self.assertEqual(con.execute("SELECT count(*) FROM offers").fetchone()[0],8)
            self.assertTrue(all(len(json.loads(r[0]))==1 for r in con.execute("SELECT source_document_ids_json FROM offers").fetchall()))
            con.commit()
        finally:con.close()
        result=refresh(self.run)
        self.assertEqual(result['controlling'],0)
        self.assertEqual(result['unresolved'],8)
        con=connect(self.run)
        try:self.assertEqual(con.execute("SELECT count(*) FROM open_issues WHERE issue_type='source_authority_conflict' AND status='open'").fetchone()[0],8)
        finally:con.close()

    def test_existing_single_source_offer_and_facts_are_rebound(self):
        con=connect(self.run)
        try:
            old=self.add_doc(con,'doc',role='offer')
            con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('off',?,'active','[\"doc\"]')",[old])
            con.execute("UPDATE documents SET offer_id='off' WHERE document_id='doc'")
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,evidence_status,extraction_path,updated_at) VALUES ('f','off',?,'total',1250,'requires_confirmation','deterministic','2026-10-05')",[old])
            self.classify(con,'doc'); self.classify(con,'doc')
            actual=con.execute("SELECT supplier_id FROM documents WHERE document_id='doc'").fetchone()[0]
            self.assertNotEqual(actual,old)
            self.assertEqual(con.execute("SELECT supplier_id FROM facts WHERE fact_id='f'").fetchone()[0],actual)
            self.assertEqual(con.execute("SELECT supplier_id FROM offers WHERE offer_id='off'").fetchone()[0],actual)
            self.assertEqual(con.execute("SELECT count(*) FROM offers").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT count(*) FROM suppliers").fetchone()[0],1)
        finally:con.close()

    def test_missing_name_is_not_upgraded_from_filename(self):
        con=connect(self.run)
        try:self.add_doc(con,'unnamed');self.classify(con,'unnamed',None);con.commit()
        finally:con.close()
        result=refresh(self.run)
        self.assertEqual(result['controlling'],0);self.assertEqual(result['unresolved'],1)

    def test_shared_legacy_offer_cannot_be_silently_rebound(self):
        con=connect(self.run)
        try:
            old=self.add_doc(con,'doc',role='offer')
            con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('off',?,'active','[\"doc\",\"other\"]')",[old])
            con.execute("UPDATE documents SET offer_id='off' WHERE document_id='doc'")
            with self.assertRaisesRegex(ValueError,'Shared legacy offer'):self.classify(con,'doc')
            self.assertEqual(con.execute("SELECT supplier_id FROM offers WHERE offer_id='off'").fetchone()[0],old)
        finally:con.close()

    def test_deterministic_same_supplier_sources_keep_distinct_totals(self):
        src=self.root/'source';src.mkdir()
        for n,total in [(1,100),(2,200)]:
            (src/f'Quote_{n}.txt').write_text(f'Fiyat Teklifi\nFirma: Akvaplast\nGenel Toplam: {total} EUR\n',encoding='utf-8')
        inventory=ingest_source(src,self.run)
        self.assertEqual(len({d['supplier_id'] for d in inventory}),1)
        self.assertEqual(len({d['offer_id'] for d in inventory}),2)
        extract(self.run)
        con=connect(self.run)
        try:
            values=sorted(r[0] for r in con.execute("SELECT value_number FROM facts WHERE field_key='total'").fetchall())
            self.assertEqual(values,[100,200])
        finally:con.close()
        self.assertEqual(refresh(self.run)['controlling'],2)

    def test_revision_labels_are_observed_without_current_precedence(self):
        self.assertEqual(revision_candidate('REVİZE-7.pdf',''),'7')
        self.assertEqual(revision_candidate('revize_8.pdf',''),'8')
        self.assertIsNone(revision_candidate('REVİZE TEKLİF.pdf',''))

    def test_turkish_name_normalization_is_consistent(self):
        self.assertEqual(normalize_supplier_name('AKVAPLAST DENİZCİLİK A.Ş.'),normalize_supplier_name('Akvaplast Denizcilik A.S.'))
