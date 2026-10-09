from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from procurement_math import (
    ddp_equivalent,
    distinguishing_weight_ratio,
    fx_to_base,
    line_gross,
    present_value_schedule,
    real_rate,
    required_order_quantity,
    sequential_discount,
    vat_split,
    weighted_score,
)


class ProcurementMathTests(unittest.TestCase):
    def test_line_price_and_sequential_discount(self):
        self.assertEqual(line_gross(100, 25, 10), Decimal('250'))
        self.assertEqual(sequential_discount(1000, [0.10, 0.05]), Decimal('855.000'))

    def test_moq_pack_and_loss(self):
        self.assertEqual(required_order_quantity(950, 0.05, 1100, 100), Decimal('1100'))

    def test_currency_specific_present_value(self):
        pv, detail = present_value_schedule(100000, [{'ratio': 1, 'days': 365}], 0.20)
        self.assertAlmostEqual(float(pv), 83333.3333333, places=3)
        self.assertEqual(len(detail), 1)

    def test_real_rate_is_fisher_not_subtraction(self):
        self.assertAlmostEqual(float(real_rate(0.40, 0.30)), 0.0769230769, places=8)

    def test_fx_unit_and_vat(self):
        self.assertEqual(fx_to_base(10000, 30, 100), Decimal('3000'))
        v = vat_split(100, 0.20, 0.50)
        self.assertEqual(v['cost_basis'], Decimal('110.000'))
        self.assertEqual(v['cash_gross'], Decimal('120.0'))

    def test_ddp_no_double_count(self):
        result = ddp_equivalent(
            100,
            [{'cost_id': 'freight', 'amount': 10}],
            [{'cost_id': 'freight', 'amount': 10}, {'cost_id': 'broker', 'amount': 3}],
            [{'cost_id': 'duty', 'amount': 5}, {'cost_id': 'duty', 'amount': 5}],
        )
        self.assertEqual(Decimal(result['ddp_equivalent']), Decimal('108'))

    def test_weighted_scoring_and_distinguishing_ratio(self):
        score = weighted_score([{'weight': 60, 'score': 10}, {'weight': 40, 'score': 5}])
        self.assertEqual(score, Decimal('8'))
        ratio = distinguishing_weight_ratio([
            {'weight': 60, 'scores': [10, 8]},
            {'weight': 40, 'scores': [5, 5]},
        ])
        self.assertEqual(ratio, Decimal('0.6'))


if __name__ == '__main__':
    unittest.main()
