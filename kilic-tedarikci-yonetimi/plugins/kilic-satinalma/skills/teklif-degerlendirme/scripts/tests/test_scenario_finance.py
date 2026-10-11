import copy
from pathlib import Path
import tempfile
import unittest
from db import init_db
from scenario_finance import payment_reference, finance_reference, policy_valid

POLICY = {"base_currency":"EUR","source_currency":"EUR","rate_date":"2026-10-11",
          "rate_source":"Explicit synthetic user scenario","direction":"TARGET_PER_SOURCE","kind":"FIXED_SCENARIO"}
VALUES = {"annual_rate":0.1,"years":2,"energy_annual":10,"maintenance_annual":10,"residual":5,"fx_rate":1}
FINANCE = {"payments":[{"percent":0.5,"days":0},{"percent":0.5,"days":365}],"vat_refund_days":365,
           "policy":POLICY,"base_present_value":100}

class ScenarioFinanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); init_db(Path(self.tmp.name))
    def tearDown(self): self.tmp.cleanup()
    def test_two_payments_and_discounted_tco_match_independent_constants(self):
        v=copy.deepcopy(VALUES); f=copy.deepcopy(FINANCE)
        r=finance_reference(v,f,cash=120,cost=100)
        self.assertEqual(r['status'],'SCENARIO_CALCULATED')
        self.assertAlmostEqual(r['payment_present_value'],114.54545454545455)
        self.assertAlmostEqual(r['recoverable_vat_present_value'],18.18181818181818)
        self.assertAlmostEqual(r['opex_present_value'],34.71074380165289)
        self.assertAlmostEqual(r['residual_present_value'],4.132231404958678)
        self.assertAlmostEqual(r['total_present_value'],126.94214876033058)
        self.assertAlmostEqual(r['difference'],26.94214876033058)
        self.assertEqual(v,VALUES); self.assertEqual(f,FINANCE)
    def test_zero_rate_is_finite_and_known_zero_cost_is_retained(self):
        v={**VALUES,'annual_rate':0};r=finance_reference(v,FINANCE,cash=120,cost=100)
        self.assertEqual(r['total_present_value'],135)
        self.assertEqual(payment_reference(0,0,[{'percent':1,'days':0}])['present_value'],0)
    def test_unknown_payments_and_refund_timing_do_not_become_zero(self):
        r=finance_reference(VALUES,{**FINANCE,'payments':None},cash=120,cost=100)
        self.assertIsNone(r['payment_present_value']);self.assertIsNone(r['total_present_value'])
        r=finance_reference(VALUES,{**FINANCE,'vat_refund_days':None},cash=120,cost=100)
        self.assertIsNone(r['recoverable_vat_present_value']);self.assertIsNone(r['total_present_value'])
    def test_unknown_opex_residual_and_policy_keep_full_tco_unknown(self):
        for key in ('energy_annual','maintenance_annual','residual','years'):
            r=finance_reference({**VALUES,key:None},FINANCE,cash=120,cost=100)
            self.assertEqual(r['status'],'INCOMPLETE');self.assertIsNone(r['total_present_value'])
        r=finance_reference(VALUES,{**FINANCE,'policy':None},cash=120,cost=100)
        self.assertIsNone(r['payment_present_value']);self.assertIsNone(r['total_present_value'])
    def test_bad_schedule_ratio_negative_boolean_and_nonfinite_reject(self):
        for payments in [[{'percent':0.9,'days':0}],[{'percent':1,'days':-1}],[{'percent':True,'days':0}],[{'percent':1,'days':float('inf')}]]:
            with self.assertRaises(ValueError):payment_reference(120,0.1,payments)
    def test_unknown_schedule_row_has_no_invented_payment(self):
        r=payment_reference(120,0.1,[{'percent':None,'days':0},{'percent':0.5,'days':365}])
        self.assertIsNone(r['present_value']);self.assertEqual(r['status'],'INCOMPLETE')
    def test_wrong_rate_direction_date_and_same_currency_multiplier_reject(self):
        for policy in [{**POLICY,'direction':'SOURCE_PER_TARGET'},{**POLICY,'rate_date':'2026-02-31'}]:
            with self.assertRaises(ValueError):policy_valid(policy,1)
        with self.assertRaises(ValueError):policy_valid(POLICY,2)
    def test_no_tax_credit_needs_no_invented_refund_date_and_zero_baseline_has_no_ratio(self):
        r=finance_reference(VALUES,{**FINANCE,'vat_refund_days':None,'base_present_value':0},cash=100,cost=100)
        self.assertEqual(r['recoverable_vat_present_value'],0)
        self.assertEqual(r['status'],'SCENARIO_CALCULATED')
        self.assertIsNone(r['relative_difference'])
