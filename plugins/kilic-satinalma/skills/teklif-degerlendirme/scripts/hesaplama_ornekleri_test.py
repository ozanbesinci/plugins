"""Sentetik yöntem örnekleri. Excel motoru veya gerçek teklif onayı değildir.

Çalıştırma: python scripts/hesaplama_ornekleri_test.py
Harici paket veya ticari veri gerekmez.
"""
import math
import unittest
from datetime import date
from decimal import Decimal as D


def pv(flows, rate):
    if rate <= -1:
        raise ValueError("İskonto oranı -1'den büyük olmalı")
    return sum(amount / (1 + rate) ** year for year, amount in flows)


class CalculationExamples(unittest.TestCase):
    def test_sequential_discount(self):
        self.assertEqual(D('1000') * D('.90') * D('.95'), D('855'))

    def test_price_per_hundred(self):
        self.assertEqual(250 * 800 / 100, 2000)

    def test_common_quantity_reverses_ranking(self):
        self.assertLess(96 * 103, 100 * 100)
        self.assertGreater(100 * 103, 100 * 100)

    def test_fixed_cost_not_scaled(self):
        self.assertEqual(120 * 10 + 500, 1700)
        self.assertNotEqual((100 * 10 + 500) * 1.2, 1700)

    def test_moq_pack_and_yield(self):
        ordered = math.ceil(max(1100, 950 / .95) / 100) * 100
        self.assertEqual(ordered, 1100)
        self.assertEqual(ordered * .95 - 950, 95)

    def test_active_ingredient(self):
        self.assertEqual(500 / (20 * .25), 100)

    def test_tier_pricing_types_differ(self):
        self.assertEqual(110 * 9, 990)
        self.assertEqual(100 * 10 + 10 * 9, 1090)

    def test_split_order_freight_can_reverse_choice(self):
        single = 100 + 120 + 10
        split = 100 + 100 + 20 + 20
        self.assertLess(single, split)

    def test_vat_partial_deduction(self):
        net = D('120') / D('1.20')
        tax = D('120') - net
        self.assertEqual(net + tax * D('.5'), D('110'))

    def test_currency_unit(self):
        self.assertEqual(10000 * 30 / 100, 3000)

    def test_financing_adjustment_sign(self):
        nominal = 100000
        payment_pv = pv([(1, nominal)], .20)
        adjustment = payment_pv - nominal
        self.assertAlmostEqual(adjustment, -16666.6666667, places=5)
        self.assertAlmostEqual(nominal + adjustment, 83333.3333333, places=5)

    def test_advance_and_retention_reconcile(self):
        self.assertEqual(20 + (50-10-5) + (50-10-5) + 10, 100)

    def test_deposit_net_cost(self):
        self.assertAlmostEqual(pv([(0, 10000), (1, -10000)], .2), 1666.6666667, places=5)

    def test_recoverable_vat_financing(self):
        self.assertAlmostEqual(pv([(0, 20000), (1, -20000)], .2), 3333.3333333, places=5)

    def test_escalation_pv_bridge(self):
        increase = 100000 * .6 * .2
        self.assertEqual(pv([(1, increase)], .2), 10000)
        self.assertAlmostEqual(pv([(1, 100000)], .2) + 10000, pv([(1, 112000)], .2))

    def test_currency_discount_and_parity_equivalence(self):
        direct = 100000 / 1.04 * 45
        forward = 45 * 1.4 / 1.04
        self.assertAlmostEqual(direct, 4326923.076923, places=5)
        self.assertAlmostEqual(direct, 100000 * forward / 1.4)
        self.assertNotAlmostEqual(direct, 100000 * 45 / 1.4)

    def test_real_nominal_consistency(self):
        real = 1.4 / 1.3 - 1
        real_pv = pv([(t, 1000000) for t in range(1, 11)], real)
        nominal_pv = pv([(t, 1000000 * 1.3**t) for t in range(1, 11)], .4)
        self.assertAlmostEqual(real_pv, nominal_pv, places=6)
        self.assertAlmostEqual(real_pv, 6804212.43631948, places=5)

    def test_zero_and_negative_real_rate(self):
        self.assertEqual(pv([(0, 20), (1, 80)], 0), 100)
        self.assertGreater(pv([(1, 100)], -.05), 100)
        with self.assertRaises(ValueError):
            pv([(1, 100)], -1)

    def test_energy_dimensions(self):
        difference_kwh = (30/.9 - 30/.95) * 6000
        self.assertAlmostEqual(difference_kwh, 10526.31578947, places=5)

    def test_common_cost_can_reverse_total_score(self):
        def scores(common):
            costs = [100+common, 120+common]
            price = [10 * min(costs)/c for c in costs]
            return [.3*price[0]+.7*8, .3*price[1]+.7*8.4]
        before, after = scores(0), scores(1000)
        self.assertGreater(before[0], before[1])
        self.assertLess(after[0], after[1])

    def test_excluded_low_offer_not_in_min(self):
        rows = [(1, False), (100, True), (120, True)]
        eligible = [cost for cost, passed in rows if passed]
        self.assertEqual(10 * min(eligible)/100, 10)

    def test_low_discriminating_weight_can_reverse_rank(self):
        # 80 weight points equal; only two criteria differ.
        a1, b1 = .8*5 + .15*10, .8*5 + .05*10
        a2, b2 = .8*5 + .05*10, .8*5 + .15*10
        self.assertGreater(a1, b1)
        self.assertLess(a2, b2)

    def test_calendar_quarter_not_ninety_days(self):
        days = (date(2026, 4, 1) - date(2026, 1, 1)).days
        self.assertEqual(days, 90)
        summer_days = (date(2026, 7, 1) - date(2026, 4, 1)).days
        self.assertEqual(summer_days, 91)
        self.assertEqual(math.ceil(summer_days / 90), 2)  # But one calendar quarter.

    def test_commission_conditional_example(self):
        self.assertEqual(D('1000000') * D('.005') * 3 * D('1.05'), D('15750'))

    def test_break_even_exchange_rate(self):
        a, b, c, d = 200000, 10000, 700000, 0
        rate = (c-a)/(b-d)
        self.assertEqual(rate, 50)
        self.assertEqual(a+b*rate, c+d*rate)

    def test_oee_quality_not_applied_twice(self):
        good_output = 100 * 8 * .9 * .8 * .95
        self.assertAlmostEqual(good_output, 547.2)
        self.assertLess(good_output * .95, good_output)

    def test_peak_cash_differs_from_final_and_largest_payment(self):
        net = [300, 400, 200, -150]
        cumulative = [sum(net[:i+1]) for i in range(len(net))]
        self.assertEqual(max(net), 400)
        self.assertEqual(max(cumulative), 900)
        self.assertEqual(cumulative[-1], 750)
        self.assertEqual(cumulative.index(max(cumulative)), 2)
        self.assertEqual(max(max(0, v-500) for v in cumulative), 400)

    def test_cash_with_sufficient_allocation(self):
        self.assertEqual(max(0, 900-1000), 0)

    def test_monthly_netting_hides_cash_peak(self):
        # Same month: payment first, refund later.
        movements = [100, -100]
        self.assertEqual(sum(movements), 0)
        self.assertEqual(max(sum(movements[:i+1]) for i in range(2)), 100)

    def test_vat_offset_reduces_tax_payment_once(self):
        normal_tax, deductible_vat = 500, 200
        actual_payment = normal_tax-deductible_vat
        self.assertEqual(actual_payment, 300)
        self.assertNotEqual(actual_payment-deductible_vat, 300)

    def test_quality_quantity_and_cost_reconcile(self):
        initial, defective, reworked, replacements = 1000, 40, 20, 20
        usable = initial-defective+reworked+replacements
        total = 10000+100+40+30+200-200
        self.assertEqual(usable, 1000)
        self.assertEqual(total, 10170)
        self.assertEqual(total/usable, 10.17)

    def test_yield_loss_already_in_purchased_quantity(self):
        purchased, price, yield_rate = 1000, 10, .95
        usable = purchased*yield_rate
        self.assertEqual(purchased*price, 10000)
        self.assertAlmostEqual(purchased*price/usable, 10.5263157895)
        # Adding rejected material purchase cost again would duplicate it.
        self.assertGreater(purchased*price + (purchased-usable)*price, 10000)

    def test_annual_vs_monthly_inventory_cost(self):
        annual = 12000*10 + 200 + 6000*1
        monthly = 12000*10 + 12*200 + 500*1
        discounted_bulk = 12000*10*.95 + 200 + 6000*1
        self.assertEqual(annual, 126200)
        self.assertEqual(monthly, 122900)
        self.assertEqual(discounted_bulk, 120200)
        self.assertLess(monthly, annual)
        self.assertLess(discounted_bulk, monthly)

    def test_nominal_bulk_discount_can_lose_on_payment_pv(self):
        # Contract prices fixed, storage paid at year end; monthly purchases at month start.
        bulk_pv = 114000+200+6000/1.2
        monthly_pv = sum(10200/1.2**(m/12) for m in range(12)) + 500/1.2
        self.assertLess(monthly_pv, bulk_pv)

    def test_order_count_and_delivery_count_distinct(self):
        one_contract_twelve_deliveries = 1*100 + 12*200
        self.assertEqual(one_contract_twelve_deliveries, 2500)
        self.assertNotEqual(one_contract_twelve_deliveries, 12*(100+200))

    def test_shortage_is_not_negative_inventory_saving(self):
        opening, delivered, demand, loss = 100, 1000, 1100, 20
        closing = opening+delivered-demand-loss
        self.assertEqual(closing, -20)
        self.assertEqual(max(0, -closing), 20)

    def test_inventory_time_weighted_average(self):
        # 100 units held 10 days, 20 held 20 days; endpoint averaging is wrong.
        average = (100*10 + 20*20)/30
        self.assertAlmostEqual(average, 46.6666666667)
        self.assertNotEqual(average, (100+20)/2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
