"""A table row must preserve numeric evidence as separate source values."""
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from record_results import _decimal_tokens


class NumericEvidenceTokenTests(unittest.TestCase):
    def test_adjacent_table_values_do_not_merge(self):
        row = "1 48 11 7+1 € 5.525,00 30 € 165.750,00"
        self.assertEqual(
            _decimal_tokens(row),
            [Decimal("1"), Decimal("48"), Decimal("11"), Decimal("7"),
             Decimal("1"), Decimal("5525.00"), Decimal("30"), Decimal("165750.00")],
        )
        self.assertNotIn(Decimal("14811"), _decimal_tokens(row))
        self.assertNotIn(Decimal("5525.0030"), _decimal_tokens(row))

    def test_nbsp_grouping_remains_supported(self):
        self.assertEqual(_decimal_tokens("1\u00a0234,50 2\u202f500,00"),
                         [Decimal("1234.50"), Decimal("2500.00")])


if __name__ == "__main__":
    unittest.main()
