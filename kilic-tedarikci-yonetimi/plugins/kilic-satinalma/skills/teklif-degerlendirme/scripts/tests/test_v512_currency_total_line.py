"""Regression (real set, RC9): a day-rate clause must not make a verified offer currency."""
from pathlib import Path
import sys, unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from field_extract import _text_candidates


def cands(text):
    return _text_candidates({"text_content": text, "unit_type": "page", "unit_index": 1, "locator": {"page": 1}})


class CurrencyOnTotalLineTests(unittest.TestCase):
    def test_day_rate_clause_currency_is_not_verified(self):
        c = cands("13. Devreye alma hizmetinin uzaması durumunda hizmet 500€ gün x adam + KDV bedel karşılığında yapılacaktır.")
        self.assertTrue(c["currency"])
        self.assertTrue(all(x["score"] < 0.8 for x in c["currency"]))

    def test_price_sentence_without_total_label_needs_review(self):
        c = cands("Yukarıda belirtilen kapsam için fiyatımız 2,297,500.- USD + KDV'dir")
        self.assertTrue(all(x["score"] < 0.8 for x in c["currency"]))

    def test_explicit_total_line_keeps_verified_currency_and_total(self):
        c = cands("SON TOPLAM: USD 2.297.500,00")
        self.assertEqual([(x["value_text"], x["score"]) for x in c["currency"]], [("USD", 0.9)])
        self.assertEqual([(x["value_number"], x["score"]) for x in c["total"]], [(2297500.0, 0.82)])


if __name__ == "__main__":
    unittest.main()
