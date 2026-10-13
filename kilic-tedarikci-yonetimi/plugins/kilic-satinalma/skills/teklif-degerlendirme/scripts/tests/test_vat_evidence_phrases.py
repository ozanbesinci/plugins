"""Literal VAT evidence respects Turkish/English negation."""
from pathlib import Path
import tempfile
import unittest
from db import connect, init_db
from record_results import _validate_fact_evidence_semantics

class VatEvidencePhraseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.run=Path(self.temp.name);init_db(self.run)
    def tearDown(self):self.temp.cleanup()
    def validate(self,text,value):
        con=connect(self.run)
        try:
            con.execute('INSERT OR REPLACE INTO evidence(evidence_id,document_id,unit_id,locator_json,quote,evidence_status,extraction_path) VALUES (?,?,?,?,?,?,?)',
                        ['ev','doc','unit','{}',text,'verified','synthetic']);con.commit()
            _validate_fact_evidence_semantics(con,{'field_key':'vat','value_text':value,'evidence_status':'verified'},'ev')
        finally:con.close()
    def test_actual_alagen_phrase_supports_exclusion(self):
        self.validate('TEKLİFİMİZE KDV DAHİL DEĞİLDİR.','excluded')
    def test_actual_alagen_phrase_never_supports_inclusion(self):
        with self.assertRaises(ValueError):self.validate('TEKLİFİMİZE KDV DAHİL DEĞİLDİR.','included')
    def test_plain_inclusion_preserved(self):self.validate('KDV dahildir.','included')
    def test_plain_inclusion_cannot_mean_exclusion(self):
        with self.assertRaises(ValueError):self.validate('KDV dahildir.','excluded')
    def test_plain_exclusion_preserved(self):self.validate('(KDV HARİÇ) GENEL TOPLAM','excluded')
    def test_english_not_included_respects_negation(self):
        self.validate('VAT not included.','excluded')
        with self.assertRaises(ValueError):self.validate('VAT not included.','included')
    def test_turkish_not_added_respects_negation(self):
        self.validate('KDV dahil edilmemiştir.','excluded')
        with self.assertRaises(ValueError):self.validate('KDV dahil edilmemiştir.','included')
    def test_negated_exclusion_does_not_prove_exclusion(self):
        with self.assertRaises(ValueError):self.validate('KDV hariç değildir.','excluded')

if __name__=='__main__':unittest.main()
