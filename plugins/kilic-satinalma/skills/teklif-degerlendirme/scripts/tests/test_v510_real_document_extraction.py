"""Regressions from the first real-document acceptance (oil tank offers, 05.10.2026).

Lines are synthetic paraphrases of the observed patterns; no company document text is stored.
"""
from pathlib import Path
import sys, unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ingest import revision_candidate, role_candidate
from field_extract import _text_candidates


def unit(text):
    return {"text_content": text, "unit_type": "page", "unit_index": 1, "locator": {"page": 1}}


class TotalAndCurrencyTests(unittest.TestCase):
    def test_percentage_in_terms_clause_is_never_a_verified_total(self):
        c = _text_candidates(unit("9. Sipariş iptalinde avans ödemesi toplam bedelin %20 si iade edilmez"))
        self.assertEqual(c["total"], [])

    def test_explicit_total_with_amount_stays_high_confidence(self):
        c = _text_candidates(unit("GENEL TOPLAM 1.250.000,00 TL"))
        self.assertEqual([(x["score"], x["value_number"]) for x in c["total"]], [(0.82, 1250000.0)])
        c = _text_candidates(unit("TOPLAM FİYAT (KDV HARİÇ) $ 2.295.000,00 İSKONTO $ - 45.000,00 İSKONTOLU FİYAT $ 2.250.000,00"))
        self.assertEqual(c["total"][-1]["value_number"], 2250000.0)
        self.assertGreaterEqual(c["total"][-1]["score"], 0.8)

    def test_generic_total_without_money_amount_is_not_verified(self):
        self.assertEqual(_text_candidates(unit("Toplam 12 adet tank"))["total"], [])
        weak = _text_candidates(unit("Toplam 450.000"))["total"]
        self.assertTrue(weak and all(x["score"] < 0.8 for x in weak))

    def test_currency_from_payment_clause_is_low_confidence(self):
        c = _text_candidates(unit("Döviz faturalarda TL ile ödeme talep edilirse TCMB kuru esas alınır; TL bedelli kambiyo senetleri"))
        self.assertTrue(c["currency"] and all(x["score"] < 0.8 for x in c["currency"]))
        c = _text_candidates(unit("GENEL TOPLAM 1.250.000,00 TL"))
        self.assertEqual([(x["value_text"], x["score"]) for x in c["currency"]], [("TRY", 0.9)])


class RoleAndRevisionTests(unittest.TestCase):
    def test_offer_filename_beats_incidental_certificate_text(self):
        role, conf = role_candidate("Kalite sertifika ve ISO 9001 belgelerimiz ektedir.", "FIRMA_Teklif - 26.190-R0 - Proje_rev01.pdf")
        self.assertEqual(role, "offer")
        self.assertGreaterEqual(conf, 0.45)
        self.assertEqual(role_candidate("Sartname maddeleri", "PROJE TEKNİK ŞARTNAMESİ.pdf")[0], "specification")

    def test_revision_label_is_an_ascii_code_not_a_word_fragment(self):
        self.assertIsNone(revision_candidate("x.pdf", "REVİZE TEKLİF"))
        self.assertEqual(revision_candidate("FIRMA_Teklif_rev01.pdf", "REVİZE TEKLİF"), "01")
        self.assertEqual(revision_candidate("Acme_teklif_rev2.xlsx", ""), "2")
        self.assertEqual(revision_candidate("x.pdf", "Revizyon No: 3"), "3")


if __name__ == "__main__":
    unittest.main()
