"""Independent S-39/S-40 behavior and explicit date/money scope regressions."""
import copy
import unittest
import test_context as fixtures
from test_workflows import WorkflowTests, day, money
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.workflows import evaluate


class RenewalScopeTests(unittest.TestCase):
    setUp = fixtures.ContextTests.setUp
    rev = fixtures.ContextTests.rev
    document = fixtures.ContextTests.document
    req = WorkflowTests.req

    def test_s39_routes_renewal_and_s40_routes_portfolio(self):
        for scenario, skill in [("S-39", "K26"), ("S-40", "K27")]:
            request = self.req("K00")
            request["scenario_id"] = scenario
            self.assertEqual([skill], evaluate(self.store, request)["selected_skills"])

    def test_renewal_plan_handles_notice_and_surviving_obligations(self):
        result = evaluate(self.store, self.req("K26"))
        plan = " ".join(result["work_plan"]).lower()
        for word in ["yenileme", "ihbar", "borç", "garanti", "teminat"]:
            self.assertIn(word, plan)
        for word in ["pay/payda", "örneklem"]:
            self.assertNotIn(word, plan)
        self.assertEqual([], result["updates"])
        self.assertEqual("DISABLED", result["action_execution"])

    def test_explicit_calendar_date_is_candidate_not_approval(self):
        request = self.req("K26")
        request["calculation"] = day()
        result = evaluate(self.store, request)
        self.assertEqual("2026-03-02", result["calculation"]["date"])
        self.assertEqual("NOT_VERIFIED", result["authority"])
        self.assertFalse(result["critical_analysis_allowed"])

    def test_missing_date_and_incomplete_business_calendar_are_not_inferred(self):
        for value in [dict(day(), start=None), dict(day(), day_type="BUSINESS")]:
            request = self.req("K26")
            request["calculation"] = value
            with self.assertRaises(CoreError):
                evaluate(self.store, request)

    def test_renewal_does_not_gain_unrelated_money_capability(self):
        request = self.req("K26")
        request["calculation"] = money()
        with self.assertRaises(CoreError) as caught:
            evaluate(self.store, request)
        self.assertEqual("HESAP_KAPSAMI", caught.exception.code)

    def test_portfolio_plan_and_existing_money_capability_remain(self):
        request = self.req("K27")
        request["calculation"] = money()
        result = evaluate(self.store, request)
        self.assertEqual("150000.00", result["calculation"]["amount"])
        self.assertIn("örneklem", " ".join(result["work_plan"]))
        self.assertIn("erişilemeyen", " ".join(result["work_plan"]))


if __name__ == "__main__":
    unittest.main()
