"""teklif_motoru için sentetik sınır ve mutabakat testleri."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from decimal import Decimal as D
from pathlib import Path

import teklif_motoru as motor


class TeklifMotoruTests(unittest.TestCase):
    def test_price_line_uses_compounded_discount_and_separates_vat(self):
        actual = motor.price_line({"quantity": "1", "unit_price": "1000", "price_unit": "1",
                                   "discounts": ["0.10", "0.05"], "vat_rate": "0.20"})
        self.assertEqual(actual["gross_before_discount"], D("1000"))
        self.assertEqual(actual["net_excluding_vat"], D("855.00"))
        self.assertEqual(actual["vat_amount"], D("171.0000"))
        self.assertEqual(actual["total_including_vat"], D("1026.0000"))

    def test_price_line_can_split_vat_inclusive_price(self):
        actual = motor.price_line({"quantity": "1", "unit_price": "120", "vat_rate": "0.20",
                                   "price_includes_vat": True})
        self.assertEqual(actual["net_excluding_vat"], D("100"))
        self.assertEqual(actual["vat_amount"], D("20"))

    def test_price_rejects_unsupplied_vat_rate(self):
        with self.assertRaisesRegex(motor.CalculationError, "vat_rate"):
            motor.price_line({"quantity": "1", "unit_price": "10"})

    def test_decimal_rejects_non_finite_and_float(self):
        for value in ("NaN", "Infinity", 1.1):
            with self.assertRaises(motor.CalculationError):
                motor.as_decimal(value, "x")

    def test_fx_respects_tcmb_unit(self):
        actual = motor.fx_convert({"amount": "10000", "forex_selling": "30", "unit": "100"})
        self.assertEqual(actual["converted_amount"], D("3000"))

    def test_npv_uses_own_currency_rate_and_act_365(self):
        actual = motor.dated_npv({"base_date": "2026-01-01", "annual_rates": {"EUR": "0.04"}, "events": [
            {"event_id": "e1", "amount": "100000", "currency": "EUR", "payment_date": "2027-01-01"}]})
        self.assertEqual(actual["present_value_by_currency"]["EUR"], D("96153.84615384615384615384615384615"))
        self.assertEqual(actual["events"][0]["years"], D("1"))

    def test_npv_rejects_missing_currency_rate_and_past_payment(self):
        base = {"base_date": "2026-01-01", "annual_rates": {"TRY": "0.2"}, "events": [
            {"event_id": "e1", "amount": "1", "currency": "EUR", "payment_date": "2027-01-01"}]}
        with self.assertRaisesRegex(motor.CalculationError, "EUR"):
            motor.dated_npv(base)
        base["events"][0]["currency"] = "TRY"
        base["events"][0]["payment_date"] = "2025-12-31"
        with self.assertRaisesRegex(motor.CalculationError, "önce"):
            motor.dated_npv(base)

    def test_duplicate_cost_event_is_rejected(self):
        event = {"event_id": "same", "owner": "alıcı", "known": True, "amount": "100",
                 "currency": "TRY", "payment_date": "2026-01-01"}
        with self.assertRaisesRegex(motor.CalculationError, "yinelenmiş"):
            motor.cost_summary({"base_date": "2026-01-01", "annual_rates": {"TRY": "0"},
                                "events": [event, event]})

    def test_unknown_cost_makes_only_known_subtotal(self):
        actual = motor.cost_summary({"base_date": "2026-01-01", "annual_rates": {"TRY": "0"}, "events": [
            {"event_id": "offer", "owner": "satıcı", "known": True, "amount": "100",
             "currency": "TRY", "payment_date": "2026-01-01"},
            {"event_id": "freight-rfi", "owner": "alıcı", "known": False,
             "currency": "TRY", "payment_date": "2026-02-01"}]})
        self.assertEqual(actual["status"], "known_subtotal_not_final")
        self.assertEqual(actual["unknown_event_ids"], ["freight-rfi"])
        self.assertEqual(actual["known_present_value_by_currency"]["TRY"], D("100"))

    def test_cost_summary_requires_owner_and_all_fx_rates(self):
        event = {"event_id": "a", "known": True, "amount": "1", "currency": "EUR", "payment_date": "2026-01-01"}
        with self.assertRaisesRegex(motor.CalculationError, "owner"):
            motor.cost_summary({"base_date": "2026-01-01", "annual_rates": {"EUR": "0"}, "events": [event]})
        event["owner"] = "alıcı"
        with self.assertRaisesRegex(motor.CalculationError, "fx_rates.EUR"):
            motor.cost_summary({"base_date": "2026-01-01", "annual_rates": {"EUR": "0"}, "events": [event],
                                "base_currency": "TRY", "fx_rates": {}})

    def test_cash_peak_keeps_same_day_sequence_and_refund(self):
        actual = motor.cash_peak({"currency": "TRY", "available_cash": "500", "events": [
            {"event_id": "pay", "amount": "900", "currency": "TRY", "payment_date": "2026-01-01"},
            {"event_id": "refund", "amount": "-150", "currency": "TRY", "payment_date": "2026-01-01"}]})
        self.assertEqual(actual["peak_cumulative_cash_need"], D("900"))
        self.assertEqual(actual["peak_additional_financing_need"], D("400"))
        self.assertEqual(actual["final_net_outflow"], D("750"))

    def test_cash_peak_rejects_currency_mix(self):
        with self.assertRaisesRegex(motor.CalculationError, "tek para biriminde"):
            motor.cash_peak({"currency": "TRY", "events": [
                {"event_id": "a", "amount": "1", "currency": "TRY", "payment_date": "2026-01-01"},
                {"event_id": "b", "amount": "1", "currency": "USD", "payment_date": "2026-01-02"}]})

    def test_cash_peak_rejects_currency_mix_when_currency_is_omitted(self):
        with self.assertRaisesRegex(motor.CalculationError, "tek para biriminde"):
            motor.cash_peak({"events": [
                {"event_id": "a", "amount": "1", "currency": "TRY", "payment_date": "2026-01-01"},
                {"event_id": "b", "amount": "1", "currency": "USD", "payment_date": "2026-01-02"}]})

    def test_cash_peak_stably_sorts_dates_but_preserves_same_day_order(self):
        actual = motor.cash_peak({"events": [
            {"event_id": "refund-later", "amount": "-500", "currency": "TRY", "payment_date": "2026-02-01"},
            {"event_id": "payment", "amount": "900", "currency": "TRY", "payment_date": "2026-01-01"},
            {"event_id": "refund-same-day", "amount": "-150", "currency": "TRY", "payment_date": "2026-01-01"}]})
        self.assertEqual(actual["convention"], "chronological_stable_same_day_input_order")
        self.assertEqual([row["event_id"] for row in actual["events"]],
                         ["payment", "refund-same-day", "refund-later"])
        self.assertEqual(actual["peak_cumulative_cash_need"], D("900"))

    @staticmethod
    def scoring_payload():
        return {"suppliers": [
            {"supplier_id": "A", "eligible": True}, {"supplier_id": "B", "eligible": True},
            {"supplier_id": "C", "eligible": False}], "criteria": [
            {"criterion_id": "cost", "weight": "60", "direction": "lower", "method": "proportional",
             "values": {"A": "100", "B": "125", "C": "1"}},
            {"criterion_id": "service", "weight": "40", "direction": "higher", "method": "proportional",
             "values": {"A": "8", "B": "10", "C": "100"}}]}

    def test_scoring_excludes_supplier_from_normalization_and_reports_distinguishing_weight(self):
        actual = motor.score_suppliers(self.scoring_payload())
        self.assertEqual(actual["suppliers"][0]["supplier_id"], "A")
        self.assertEqual(actual["suppliers"][-1]["status"], "EXCLUDED")
        self.assertEqual(actual["distinguishing_weight"], D("100"))
        self.assertEqual(actual["distinguishing_weight_ratio"], D("1"))

    def test_scoring_rejects_single_supplier_bad_weights_and_too_early_range(self):
        payload = self.scoring_payload()
        payload["suppliers"][1]["eligible"] = False
        with self.assertRaisesRegex(motor.CalculationError, "en az iki"):
            motor.score_suppliers(payload)
        payload = self.scoring_payload()
        payload["criteria"][1]["weight"] = "39"
        with self.assertRaisesRegex(motor.CalculationError, "tam 100"):
            motor.score_suppliers(payload)
        payload = self.scoring_payload()
        payload["criteria"][0]["method"] = "range"
        with self.assertRaisesRegex(motor.CalculationError, "beş"):
            motor.score_suppliers(payload)

    def test_scoring_direct_and_non_distinguishing_weight(self):
        payload = self.scoring_payload()
        payload["criteria"] = [
            {"criterion_id": "same", "weight": "70", "direction": "direct", "values": {"A": "5", "B": "5", "C": "1"}},
            {"criterion_id": "cost", "weight": "30", "direction": "lower", "values": {"A": "100", "B": "200", "C": "1"}}]
        actual = motor.score_suppliers(payload)
        self.assertEqual(actual["distinguishing_weight"], D("30"))
        self.assertEqual(actual["non_distinguishing_weight"], D("70"))

    def test_cli_emits_exact_decimal_strings_and_json_error(self):
        script = Path(__file__).with_name("teklif_motoru.py")
        valid = {"operation": "fx_convert", "payload": {"amount": "10000", "forex_selling": "30", "unit": "100"}}
        completed = subprocess.run([sys.executable, str(script)], input=json.dumps(valid), text=True, encoding="utf-8", capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(json.loads(completed.stdout)["result"]["converted_amount"], "3000")
        invalid = {"operation": "fx_convert", "payload": {"amount": "1", "forex_selling": "0", "unit": "1"}}
        completed = subprocess.run([sys.executable, str(script)], input=json.dumps(invalid), text=True, encoding="utf-8", capture_output=True, check=False)
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(json.loads(completed.stdout)["ok"])

    def test_equal_scores_never_manufacture_winner_from_input_order(self):
        payload = {"suppliers": [{"supplier_id": "B", "eligible": True}, {"supplier_id": "A", "eligible": True}],
                   "criteria": [{"criterion_id": "same", "weight": "100", "direction": "direct", "values": {"A": "8", "B": "8"}}]}
        first = motor.score_suppliers(payload)
        payload["suppliers"].reverse()
        second = motor.score_suppliers(payload)
        self.assertEqual(first, second)
        self.assertEqual([r["rank"] for r in first["suppliers"]], [1, 1])
        self.assertFalse(first["has_unique_top_score"])
        self.assertEqual(first["distinguishing_weight"], D("0"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
