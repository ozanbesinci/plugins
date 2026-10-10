"""Regressions from the real-document acceptance: models must see the evidence rules the
recorder enforces, and a currency symbol in the quote supports its ISO code."""
from pathlib import Path
import sqlite3, sys, unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import context_packet
from record_results import _validate_fact_evidence_semantics


class EvidenceContractTests(unittest.TestCase):
    def test_every_source_reader_kind_gets_the_contract(self):
        c = context_packet.EVIDENCE_CONTRACT
        for key in ("quote", "verified_text_value", "verified_number", "currency", "not_supported"):
            self.assertIn(key, c)
        self.assertIn("normalized", c["verified_text_value"])
        self.assertIn("offer_semantic_fields", context_packet.SOURCE_READER_TASKS)
        self.assertIn("requirement_assessment", context_packet.SOURCE_READER_TASKS)
        self.assertNotIn("decision_summary", context_packet.SOURCE_READER_TASKS)


class CurrencyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.con.execute("CREATE TABLE evidence(evidence_id TEXT, quote TEXT)")

    def tearDown(self):
        self.con.close()

    def check(self, code, quote):
        self.con.execute("DELETE FROM evidence")
        self.con.execute("INSERT INTO evidence VALUES ('e1', ?)", [quote])
        _validate_fact_evidence_semantics(self.con, {"evidence_status": "verified", "field_key": "currency", "value_text": code}, "e1")

    def test_symbols_support_their_iso_code(self):
        self.check("USD", "$ 2.420.600,00")
        self.check("EUR", "Toplam 1.000,00 €")
        self.check("TRY", "Fiyat 5.000 TL")
        self.check("USD", "2,297,500.- USD + KDV")

    def test_symbol_of_another_currency_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check("EUR", "$ 2.420.600,00")
        with self.assertRaises(ValueError):
            self.check("USD", "Fiyat 5.000 TL")

    def test_paraphrased_text_value_is_still_rejected(self):
        self.con.execute("INSERT INTO evidence VALUES ('e2', 'Teslim süresi 8 aydır.')")
        with self.assertRaises(ValueError):
            _validate_fact_evidence_semantics(self.con, {"evidence_status": "verified", "field_key": "delivery", "value_text": "En geç 8 ay, avans sonrası"}, "e2")


if __name__ == "__main__":
    unittest.main()
