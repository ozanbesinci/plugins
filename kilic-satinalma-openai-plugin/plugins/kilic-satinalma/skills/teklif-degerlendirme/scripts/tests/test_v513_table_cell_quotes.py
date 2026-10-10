"""Regression (real set, RC10): a verbatim quote from a multi-line table cell or a table row
must be found; a quote not in the source must still be rejected."""
from pathlib import Path
import sys, unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from record_results import _fold_text, _structured_texts

ST = {"tables": [
    [["FİYAT"], ["Fiyatımız 2,297,500.- USD + KDV'dir\nAçıklama Miktar Fiyat\n4222 m³ Kapasiteli Saha Tankı 0 ad.\n965 m³ Kapasiteli Saha Tankı 4 ad."]],
    [["Açıklama", "Miktar", "Fiyat"], ["965 m³ Kapasiteli Saha Tankı", "4 ad.", None], ["356 m³ Kapasiteli Saha Tankı", "2 ad.", None]],
]}


def found(quote):
    q = _fold_text(quote)
    return any(q in _fold_text(s) for s in _structured_texts(ST))


class TableQuoteTests(unittest.TestCase):
    def test_multiline_cell_quote_is_found(self):
        self.assertTrue(found("4222 m³ Kapasiteli Saha Tankı 0 ad.\n965 m³ Kapasiteli Saha Tankı 4 ad."))

    def test_row_and_consecutive_rows_are_found(self):
        self.assertTrue(found("965 m³ Kapasiteli Saha Tankı 4 ad."))
        self.assertTrue(found("965 m³ Kapasiteli Saha Tankı 4 ad. 356 m³ Kapasiteli Saha Tankı 2 ad."))

    def test_text_not_in_source_is_rejected(self):
        self.assertFalse(found("965 m³ Kapasiteli Saha Tankı 6 ad."))
        self.assertFalse(found("Fiyatımız 2,297,500 EUR"))


if __name__ == "__main__":
    unittest.main()
