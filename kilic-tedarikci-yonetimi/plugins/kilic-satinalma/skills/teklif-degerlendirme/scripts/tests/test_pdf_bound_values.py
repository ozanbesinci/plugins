"""Preserve the same numbers but swap owners/fields: neither may verify."""
import copy
import tempfile
import unittest
from pathlib import Path
import fitz
from pdf_bound_values import check_bound_values
from pdf_renderer import render_pdf


class PdfBoundValueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "report.pdf"
        self.model = {"profile":"hizli", "content_status":"PRELIMINARY", "decision_assurance":"NO_DECISION",
                      "comparison_status":"BLOCKED", "source_digest":"synthetic", "limitations":[],
                      "suppliers":[{"supplier_id":"A", "display_name":"Alpha Firma"}, {"supplier_id":"B", "display_name":"Beta Firma"}],
                      "offers":[{"offer_id":"O1", "supplier_id":"A", "status":"active"}, {"offer_id":"O2", "supplier_id":"B", "status":"active"}],
                      "facts":[], "calculations":[]}
        for oid, sid, total, base, cost in (("O1", "A", 100, 110, 120), ("O2", "B", 200, 220, 240)):
            self.model["facts"].append({"offer_id":oid,"supplier_id":sid,"field_key":"total","value_number":total,"currency":"EUR","evidence_status":"verified"})
            self.model["calculations"].append({"offer_id":oid,"calculation_type":"cost_summary","status":"complete",
                "result":{"base_amount":base,"comparable_total":cost,"base_currency":"EUR"}})

    def tearDown(self):
        self.tmp.cleanup()

    def text(self, model):
        render_pdf(model, self.path)
        with fitz.open(self.path) as doc:
            return "\n".join(page.get_text() for page in doc)

    def test_actual_render_preserves_offer_field_and_currency(self):
        self.assertEqual(check_bound_values(self.text(self.model), self.model), [])

    def test_same_global_numbers_under_wrong_supplier_cannot_pass(self):
        wrong = copy.deepcopy(self.model)
        wrong["facts"][0]["value_number"], wrong["facts"][1]["value_number"] = 200, 100
        wrong["calculations"][0]["result"], wrong["calculations"][1]["result"] = wrong["calculations"][1]["result"], wrong["calculations"][0]["result"]
        self.assertGreaterEqual(len(check_bound_values(self.text(wrong), self.model)), 4)

    def test_same_offer_wrong_field_or_currency_cannot_pass(self):
        wrong = copy.deepcopy(self.model)
        wrong["calculations"][0]["result"].update(base_amount=120, comparable_total=110)
        wrong["facts"][1]["currency"] = "USD"
        self.assertGreaterEqual(len(check_bound_values(self.text(wrong), self.model)), 3)

    def test_offer_id_prefix_cannot_substitute_for_missing_offer(self):
        model = copy.deepcopy(self.model)
        model["offers"][1].update(offer_id="O10", supplier_id="A")
        model["facts"][1].update(offer_id="O10", supplier_id="A", value_number=100)
        model["calculations"][1].update(offer_id="O10", result={"base_amount":110,"comparable_total":120,"base_currency":"EUR"})
        wrong = copy.deepcopy(model)
        wrong["offers"] = [wrong["offers"][1]]
        errors = check_bound_values(self.text(wrong), model)
        self.assertTrue(any("header: O1" in error for error in errors), errors)
