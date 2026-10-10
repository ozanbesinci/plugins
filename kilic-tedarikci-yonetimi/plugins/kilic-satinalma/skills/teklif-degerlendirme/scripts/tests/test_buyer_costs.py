from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from common import json_text, sha256_file
from db import connect, init_db
from independent_recompute import run as independent_recompute
from procurement_engine import calculate_costs


class BuyerCostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="buyer-cost-")
        self.run = Path(self.tmp.name) / "run"
        init_db(self.run, SCRIPTS.parent)
        archive = self.run / "sources" / "tez.xlsx"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(b"fixed supplier source bytes")
        self.source_hash = sha256_file(archive)
        self.con = connect(self.run)
        c = self.con
        for oid, total in (("TEZ", 2547640), ("OTHER", 1900000)):
            c.execute("INSERT INTO suppliers(supplier_id,display_name) VALUES (?,?)", [oid, oid])
            c.execute("INSERT INTO offers(offer_id,supplier_id,status) VALUES (?,?,'active')", [oid, oid])
            c.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,evidence_status,extraction_path,normalized_json) VALUES (?,?,?,?,?,'verified','test',?)",
                      [f"{oid}/total", oid, oid, "total", total, "{}"])
            c.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,extraction_path,normalized_json) VALUES (?,?,?,?,?,'verified','test','{}')",
                      [f"{oid}/currency", oid, oid, "currency", "TRY"])
        items = [{"item_id": "q26", "quantity": 120, "unit": "MT", "evidence_status": "verified", "evidence_refs": ["ev26"]},
                 {"item_id": "q27", "quantity": 80, "unit": "MT", "evidence_status": "verified", "evidence_refs": ["ev27"]}]
        c.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,evidence_status,extraction_path,normalized_json) VALUES ('TEZ/quantity','TEZ','TEZ','quantity','requires_confirmation','test',?)", [json_text({"items": items})])
        c.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,supplier_id,offer_id,sha256,size_bytes,parse_status,metadata_json,active) VALUES ('tez-doc','tez.xlsx','tez.xlsx','xlsx','TEZ','TEZ',?,1,'read',?,true)",
                  [self.source_hash, json_text({"archived_source_path": "sources/tez.xlsx"})])
        cells = []
        for row, quantity, unit_price, line_total in ((26, 120, 4000, 480000), (27, 80, 5400, 432000), (28, 120, 9999, 1199880)):
            for col, value in (("D", "MT"), ("E", quantity), ("F", unit_price), ("G", line_total)):
                cells.append({"cell": f"{col}{row}", "formula_or_value": value, "calculated_value": value,
                              "is_formula": False, "calculated_available": True})
        c.execute("INSERT INTO document_units(unit_id,document_id,unit_type,locator_json,structured_json,content_sha256) VALUES ('tez-sheet','tez-doc','xlsx_sheet','{}',?, 'unit-sha')", [json_text({"cells": cells})])
        for row in (26, 27):
            c.execute("INSERT INTO evidence(evidence_id,document_id,unit_id,locator_json,quote,evidence_status,extraction_path,source_sha256) VALUES (?,?,?,?,?,'verified','semantic_llm',?)",
                      [f"ev{row}", "tez-doc", "tez-sheet", json_text({"cell": f"E{row}"}), f"E{row}={120 if row == 26 else 80}", self.source_hash])
        c.execute("INSERT INTO scope_items(scope_id,offer_id,classification,cost_role,description,status) VALUES ('scope-1','TEZ','incremental_adjustment','incremental_adjustment','explicit buyer scope','unknown')")
        c.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def _row(self, row, item, **changes):
        result = {"offer_id": "TEZ", "kind": "reference_quantity", "quantity_item_id": item,
                  "quantity": 40, "unit": "MT", "issue_id": "issue-quantity", "scope_sha256": "a" * 64,
                  "answer_text": "Her kalem 40 MT", "declaration": "buyer_explicit", "provenance": "user_response",
                  "source_hashes": {"tez-doc": self.source_hash},
                  "source_row": {"unit_id": "tez-sheet", "quantity_cell": f"E{row}",
                                 "unit_price_cell": f"F{row}", "line_total_cell": f"G{row}", "unit_cell": f"D{row}"}}
        result.update(changes)
        return result

    def _install(self, declarations):
        params = {"buyer_inputs": declarations}
        record = self.run / "response.json"
        record.write_text(json.dumps({"authorized_resume": {"run": str(self.run), "financial_parameters": params},
                                      "buyer_inputs": declarations}), encoding="utf-8")
        self.con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('financial_parameters',?)", [json_text(params)])
        self.con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('parent_user_response',?)",
                         [json_text({"path": str(record), "sha256": sha256_file(record)})])
        self.con.commit()
        return params

    def _result(self, params):
        costs = calculate_costs(self.con, params)["costs"]
        self.con.commit()
        return {x["offer_id"]: x for x in costs}

    def test_event_payment_and_warranty_preserve_source_and_have_no_invented_pv(self):
        self.con.execute("DELETE FROM scope_items")
        self.con.execute("INSERT INTO facts(fact_id,offer_id,field_key,value_text,evidence_status,extraction_path,normalized_json) VALUES ('TEZ/payment','TEZ','payment','source terms','requires_confirmation','test',?)",
                         [json_text({"payment_schedule":[{"days":99,"ratio":1}]})])
        base = {"offer_id":"TEZ","issue_id":"commercial","scope_sha256":"c"*64,
                "answer_text":"50/50 ve beş yıl", "declaration":"buyer_explicit","provenance":"user_response",
                "source_hashes":{"tez-doc":self.source_hash}}
        payment = {**base,"kind":"payment_terms","milestones":[{"trigger":"work_start","percent":50},{"trigger":"work_delivery","percent":50}]}
        warranty = {**base,"kind":"warranty_terms","duration_years":5,"scope":"whole_work"}
        params=self._install([payment,warranty])
        result=self._result(params)["TEZ"]
        self.assertEqual(result["payment_terms"], {"milestones":payment["milestones"]})
        self.assertEqual(result["warranty_terms"], {"duration_years":5,"scope":"whole_work"})
        self.assertIsNone(result["acquisition_present_value"])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='TEZ/payment'").fetchone()[0],"requires_confirmation")
        checked=independent_recompute(self.run)
        self.assertEqual(checked["status"],"PASS")
        self.con.execute("UPDATE calculations SET result_json=? WHERE offer_id='TEZ' AND calculation_type='cost_summary'",[json_text({**result,"warranty_terms":{"duration_years":6,"scope":"whole_work"}})])
        self.con.commit()
        self.assertEqual(independent_recompute(self.run)["status"],"FAIL")

    def test_tez_40_40_reprices_only_proven_lines_and_independent_engine_agrees(self):
        zero = {"offer_id": "TEZ", "kind": "scope_cost", "scope_id": "scope-1", "amount": 0,
                "currency": "TRY", "issue_id": "issue-scope", "scope_sha256": "b" * 64,
                "answer_text": "Ek kapsam maliyeti sıfır", "declaration": "buyer_explicit", "provenance": "user_response",
                "source_hashes": {"tez-doc": self.source_hash}}
        params = self._install([self._row(26, "q26"), self._row(27, "q27"), zero])
        results = self._result(params)
        self.assertEqual(results["TEZ"]["stated_total"], "2547640.0")
        self.assertEqual(results["TEZ"]["buyer_quantity_adjustment"], "-536000")
        self.assertEqual(results["TEZ"]["acquisition_cost_basis"], "2011640.0")
        self.assertEqual(results["TEZ"]["unknown_scope_items"], 0)
        self.assertTrue(results["TEZ"]["complete"])
        self.assertNotIn("buyer_quantity_adjustment", results["OTHER"])
        self.assertEqual(self.con.execute("SELECT status,amount FROM scope_items WHERE scope_id='scope-1'").fetchone(), ("unknown", None))
        checks = independent_recompute(self.run)["checks"]
        self.assertEqual([x["status"] for x in checks if x["calculation_type"] == "cost_summary"], ["pass", "pass"])

    def _pending_source_row(self):
        raw = self.con.execute("SELECT normalized_json FROM facts WHERE fact_id='TEZ/quantity'").fetchone()[0]
        value = json.loads(raw)
        value['items'][0]['evidence_status'] = 'requires_confirmation'
        value['items'][0]['notes'] = 'Description says 40 MT; supplier quantity cell says 120 MT.'
        self.con.execute("UPDATE facts SET normalized_json=? WHERE fact_id='TEZ/quantity'", [json_text(value)])
        self.con.execute("UPDATE evidence SET locator_json=?,quote=? WHERE evidence_id='ev26'",
                         [json_text({'range':'D26:G26'}), 'D26=MT\nE26=120\nF26=4000\nG26=480000'])
        self.con.execute("DELETE FROM scope_items")
        self.con.commit()
        return json_text(value)

    def test_pending_quantity_reconciles_source_and_buyer_answer_without_rewriting_fact(self):
        before = self._pending_source_row()
        params = self._install([self._row(26,'q26'), self._row(27,'q27')])
        result = self._result(params)['TEZ']
        self.assertTrue(result['complete'])
        self.assertEqual(result['buyer_quantity_adjustment'], '-536000')
        self.assertEqual(result['comparable_total'], '2011640.0')
        self.assertEqual(result['stated_total'], '2547640.0')
        self.assertEqual(result['buyer_quantity_rows'][0]['source']['verification_basis'],
                         'verified_source_cells_and_buyer_quantity')
        self.assertEqual(self.con.execute("SELECT normalized_json FROM facts WHERE fact_id='TEZ/quantity'").fetchone()[0], before)
        self.assertEqual(sha256_file(self.run/'sources/tez.xlsx'), self.source_hash)
        self.assertEqual(independent_recompute(self.run)['status'], 'PASS')

    def test_pending_quantity_cannot_apply_without_explicit_buyer_answer(self):
        self._pending_source_row()
        result = self._result(self._install([]))['TEZ']
        self.assertEqual(result['comparable_total'], '2547640.0')
        self.assertEqual(result.get('buyer_quantity_adjustment','0'), '0')

    def test_pending_quantity_requires_full_verified_source_row_evidence(self):
        self._pending_source_row()
        params = self._install([self._row(26,'q26')])
        for change in (
                {'locator_json':json_text({'cell':'E26'}),'quote':'E26=120'},
                {'evidence_status':'requires_confirmation'},
                {'source_sha256':'0'*64},
                {'extraction_path':'vision'},
                {'unit_id':'different-sheet'}):
            with self.subTest(change=change):
                old = {key:self.con.execute(f'SELECT {key} FROM evidence WHERE evidence_id=?',['ev26']).fetchone()[0] for key in change}
                for key,val in change.items():self.con.execute(f'UPDATE evidence SET {key}=? WHERE evidence_id=?',[val,'ev26'])
                result=self._result(params)['TEZ']
                self.assertFalse(result['complete'])
                self.assertEqual(result['buyer_quantity_adjustment'],'0')
                for key,val in old.items():self.con.execute(f'UPDATE evidence SET {key}=? WHERE evidence_id=?',[val,'ev26'])

    def test_pending_quantity_rejects_row_arithmetic_and_cell_binding_errors(self):
        self._pending_source_row()
        original=self.con.execute("SELECT structured_json FROM document_units WHERE unit_id='tez-sheet'").fetchone()[0]
        for address,value in [('E26',121),('G26',480001),('D26','ADET'),('F26',None)]:
            with self.subTest(address=address):
                data=json.loads(original)
                for cell in data['cells']:
                    if cell['cell']==address:cell.update(formula_or_value=value,calculated_value=value)
                self.con.execute("UPDATE document_units SET structured_json=? WHERE unit_id='tez-sheet'",[json_text(data)])
                result=self._result(self._install([self._row(26,'q26')]))['TEZ']
                self.assertFalse(result['complete'])
                self.assertEqual(result['buyer_quantity_adjustment'],'0')
        self.con.execute("UPDATE document_units SET structured_json=? WHERE unit_id='tez-sheet'",[original])
        for entry in [self._row(28,'q26'),self._row(26,'q26',unit='ADET'),self._row(26,'q26',unit_price_item_id='q27')]:
            result=self._result(self._install([entry]))['TEZ']
            self.assertFalse(result['complete'])
            self.assertEqual(result['buyer_quantity_adjustment'],'0')

    def test_conflicting_unreadable_or_duplicate_quantity_is_not_reconciled(self):
        original=self._pending_source_row()
        params=self._install([self._row(26,'q26')])
        for status in ['missing','conflicting','unreadable']:
            value=json.loads(original);value['items'][0]['evidence_status']=status
            self.con.execute("UPDATE facts SET normalized_json=? WHERE fact_id='TEZ/quantity'",[json_text(value)])
            self.assertFalse(self._result(params)['TEZ']['complete'])
        value=json.loads(original);value['items'].append({**value['items'][0], 'quantity':40})
        self.con.execute("UPDATE facts SET normalized_json=? WHERE fact_id='TEZ/quantity'",[json_text(value)])
        result=self._result(params)['TEZ']
        self.assertFalse(result['complete'])
        self.assertEqual(result['buyer_quantity_adjustment'],'0')

    def test_quantity_discrepancy_closure_checks_all_targets_and_source_again(self):
        from buyer_controls import _quantity_discrepancy_answered
        self._pending_source_row()
        self.con.execute("UPDATE facts SET fact_id='TEZ/field/quantity' WHERE fact_id='TEZ/quantity'")
        entries=[self._row(26,'q26'),self._row(27,'q27')]
        costs=self._result(self._install(entries))
        q={'fact_ids':['TEZ/field/quantity'],'evidence_ids':['ev26']}
        self.assertTrue(_quantity_discrepancy_answered(self.con,q,entries,costs))
        self.assertFalse(_quantity_discrepancy_answered(self.con,q,[entries[1]],costs))
        self.assertFalse(_quantity_discrepancy_answered(self.con,{**q,'fact_ids':['TEZ/field/quantity','TEZ/currency']},entries,costs))
        self.assertFalse(_quantity_discrepancy_answered(self.con,q,[entries[0],entries[0]],costs))
        self.con.execute("UPDATE evidence SET source_sha256='changed' WHERE evidence_id='ev26'")
        self.assertFalse(_quantity_discrepancy_answered(self.con,q,entries,costs))

    def test_bad_price_cell_item_unit_and_source_hash_cannot_make_complete_cost(self):
        cases = [self._row(26, "q26", source_row={"unit_id": "tez-sheet", "quantity_cell": "E26", "unit_price_cell": "F27", "line_total_cell": "G26", "unit_cell": "D26"}),
                 self._row(26, "unknown"), self._row(26, "q26", unit="adet"),
                 self._row(28, "q26")]
        for declaration in cases:
            with self.subTest(declaration=declaration):
                params = self._install([declaration])
                result = self._result(params)["TEZ"]
                self.assertFalse(result["complete"])
                self.assertEqual(result["buyer_quantity_adjustment"], "0")
        params = self._install([self._row(26, "q26")])
        (self.run / "sources" / "tez.xlsx").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self._result(params)

    def test_explicit_currency_fills_only_missing_currency_fact(self):
        self.con.execute("DELETE FROM facts WHERE fact_id='TEZ/currency'")
        self.con.execute("DELETE FROM scope_items WHERE scope_id='scope-1'")
        declaration = {"offer_id": "TEZ", "kind": "currency", "value": "TRY",
                       "issue_id": "issue-currency", "scope_sha256": "c" * 64,
                       "answer_text": "Karşılaştırma para birimi TRY", "declaration": "buyer_explicit",
                       "provenance": "user_response", "source_hashes": {"tez-doc": self.source_hash}}
        params = self._install([declaration])
        result = self._result(params)["TEZ"]
        self.assertEqual(result["currency_basis"], "buyer_declaration")
        self.assertEqual(result["currency"], "TRY")
        self.assertEqual(result["stated_total"], "2547640.0")
        self.assertTrue(result["complete"])
        checks = independent_recompute(self.run)["checks"]
        self.assertEqual([x["status"] for x in checks if x["calculation_type"] == "cost_summary"], ["pass", "pass"])

    def test_unit_price_item_must_have_same_source_row_as_quantity_item(self):
        for suffix, cell, price in (("good", "F26", 4000), ("wrong", "F28", 9999)):
            self.con.execute("INSERT INTO evidence(evidence_id,document_id,unit_id,locator_json,quote,evidence_status,extraction_path,source_sha256) VALUES (?,?,?,?,?,'verified','semantic_llm',?)",
                             [f"price-{suffix}", "tez-doc", "tez-sheet", json_text({"cell": cell}), f"{cell}={price}", self.source_hash])
            item = {"item_id": f"price-{suffix}", "quantity": 1, "unit": "MT", "amount": price,
                    "amount_basis": "unit_price", "currency": "TRY", "evidence_status": "verified",
                    "evidence_refs": [f"price-{suffix}"]}
            self.con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,evidence_status,extraction_path,normalized_json) VALUES (?, 'TEZ','TEZ','total','requires_confirmation','test',?)",
                             [f"TEZ/item-{suffix}", json_text({"items": [item]})])
        self.con.execute("DELETE FROM scope_items WHERE scope_id='scope-1'")
        good = self._row(26, "q26", unit_price_item_id="price-good")
        good.pop("source_row")
        params = self._install([good])
        result = self._result(params)["TEZ"]
        self.assertTrue(result["complete"])
        self.assertEqual(result["buyer_quantity_adjustment"], "-320000")
        bad = self._row(26, "q26", unit_price_item_id="price-wrong")
        bad.pop("source_row")
        params = self._install([bad])
        result = self._result(params)["TEZ"]
        self.assertFalse(result["complete"])
        self.assertEqual(result["buyer_quantity_adjustment"], "0")

    def test_verified_employer_responsibility_accepts_exact_buyer_cost(self):
        self.employer_responsibility_accepts_exact_buyer_cost('isveren_yukumlulugu')

    def test_english_employer_responsibility_preserves_source_and_exact_buyer_cost(self):
        self.employer_responsibility_accepts_exact_buyer_cost('employer_responsibility')

    def employer_responsibility_accepts_exact_buyer_cost(self, classification):
        self.con.execute("""UPDATE scope_items SET scope_id='scope_employer_watering',
            cost_role='unresolved_adjustment',classification=?,
            status='verified',amount=NULL,currency=NULL WHERE scope_id='scope-1'""",[classification])
        self.con.commit()
        source_row=self.con.execute("SELECT status,cost_role,amount,currency FROM scope_items WHERE scope_id='scope_employer_watering'").fetchone()
        for amount in (0,125):
            with self.subTest(amount=amount):
                declaration={"offer_id":"TEZ","kind":"scope_cost","scope_id":"scope_employer_watering",
                    "amount":amount,"currency":"TRY","issue_id":"rfi_employer_watering_cost",
                    "scope_sha256":"d"*64,"answer_text":"Açık işveren maliyeti",
                    "declaration":"buyer_explicit","provenance":"user_response",
                    "source_hashes":{"tez-doc":self.source_hash}}
                params=self._install([declaration])
                result=self._result(params)["TEZ"]
                self.assertTrue(result["complete"])
                self.assertEqual(result["unknown_scope_items"],0)
                self.assertEqual(result["known_scope_adjustment"],str(amount))
                self.assertEqual(result["acquisition_cost_basis"],f"{2547640+amount}.0")
                checks=independent_recompute(self.run)["checks"]
                self.assertEqual([x["status"] for x in checks if x["calculation_type"]=="cost_summary"],
                                 ["pass","pass"])
                self.assertEqual(self.con.execute("SELECT status,cost_role,amount,currency FROM scope_items WHERE scope_id='scope_employer_watering'").fetchone(),source_row)

    def test_buyer_scope_cannot_override_known_or_unrelated_source_scope(self):
        declaration={"offer_id":"TEZ","kind":"scope_cost","scope_id":"scope-1",
            "amount":0,"currency":"TRY","issue_id":"rfi_employer_watering_cost",
            "scope_sha256":"d"*64,"answer_text":"İlave maliyet yok",
            "declaration":"buyer_explicit","provenance":"user_response",
            "source_hashes":{"tez-doc":self.source_hash}}
        cases=[
            ("conflicting_incremental","incremental_adjustment","extra","conflicting",None,None),
            ("unreadable_incremental","incremental_adjustment","extra","unreadable",None,None),
            ("known_verified_amount","unresolved_adjustment","isveren_yukumlulugu","verified",25,"TRY"),
            ("unrelated_scope","unresolved_adjustment","other","verified",None,None),
            ("conflicting_responsibility","unresolved_adjustment","isveren_yukumlulugu","conflicting",None,None),
            ("unreadable_responsibility","unresolved_adjustment","isveren_yukumlulugu","unreadable",None,None),
        ]
        for label,role,classification,status,amount,currency in cases:
            with self.subTest(label=label):
                self.con.execute("UPDATE scope_items SET cost_role=?,classification=?,status=?,amount=?,currency=? WHERE scope_id='scope-1'",
                                 [role,classification,status,amount,currency])
                self.con.commit()
                params=self._install([declaration])
                result=self._result(params)["TEZ"]
                self.assertFalse(result["complete"])
                self.assertEqual(result["known_scope_adjustment"],"0")
                self.assertEqual(result["acquisition_cost_basis"],"2547640.0")
                checks=independent_recompute(self.run)["checks"]
                self.assertEqual([x["status"] for x in checks if x["calculation_type"]=="cost_summary"],
                                 ["pass","unverified"])
        self.con.execute("UPDATE scope_items SET cost_role='included_in_price',classification='included_in_price',status='verified',amount=25,currency='TRY' WHERE scope_id='scope-1'")
        self.con.commit()
        params=self._install([declaration])
        result=self._result(params)["TEZ"]
        self.assertEqual(result["known_scope_adjustment"],"0")
        self.assertEqual(result["acquisition_cost_basis"],"2547640.0")

if __name__ == "__main__":
    unittest.main()
