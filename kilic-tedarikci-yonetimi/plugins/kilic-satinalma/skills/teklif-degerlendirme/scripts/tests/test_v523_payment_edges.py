"""Final-review payment edge regressions; all fixtures are local/unit-only.

Synthetic recorder metadata below exists only because the public recorder API
requires receipt fields. No model was called; this is not LLM acceptance.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import json_text
from db import connect, init_db
from comparison_contract import assess
from independent_recompute import run as independent_recompute
from procurement_engine import calculate_costs
from procurement_math import present_value_days
from record_results import record_task_result


SCRIPTS = Path(__file__).resolve().parents[1]


class V523PaymentEdgeContracts(unittest.TestCase):
    """Two final-review edge cases, intended for native SQLite and DuckDB runs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="v523-payment-edges-")
        self.root = Path(self.tmp.name)
        self.run_no = 0

    def tearDown(self):
        self.tmp.cleanup()

    def _new_run(self, name: str | None = None) -> Path:
        self.run_no += 1
        run = self.root / (name or f"run-{self.run_no}")
        init_db(run, SCRIPTS.parent)
        return run

    def test_present_value_rejects_nonfinite_amount_and_rate_with_value_error(self):
        bad_inputs = [
            (float("nan"), 60, 0.1),
            (float("inf"), 60, 0.1),
            (100, 60, float("nan")),
            (100, 60, float("inf")),
        ]
        for amount, days, rate in bad_inputs:
            with self.subTest(amount=amount, days=days, rate=rate):
                try:
                    present_value_days(amount, days, rate)
                except ValueError:
                    continue
                except Exception as exc:
                    self.fail(f"non-finite input leaked {type(exc).__name__}; expected ValueError: {exc}")
                self.fail("present_value_days accepted a non-finite amount/rate; expected ValueError")

    def test_nonfinite_discount_rate_keeps_real_cost_unverified_without_pv(self):
        for rate in (float("nan"), float("inf")):
            with self.subTest(rate=rate):
                run = self._new_run()
                con = connect(run)
                try:
                    for oid, amount in (("A", 100.0), ("B", 110.0)):
                        con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES (?,?, 'confirmed')", [oid, oid])
                        con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES (?,?, 'active','[]')", [oid, oid])
                        for field, number, text, unit, normalized in [
                            ("total", amount, None, None, {}),
                            ("currency", None, "EUR", None, {}),
                            ("payment", None, "%100 60 gün", None, {"payment_schedule": [{"ratio": 1.0, "days": 60}]}),
                        ]:
                            con.execute(
                                "INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,unit,evidence_status,critical,extraction_path,normalized_json,updated_at) VALUES (?,?,?,?,?,?,?,'verified',true,'unit_fixture',?, '2026-10-07')",
                                [f"{oid}/{field}", oid, oid, field, number, text, unit, json_text(normalized)],
                            )
                    financial = {"base_currency": "EUR", "base_date": "2026-10-07", "discount_rates": {"EUR": {"annual_effective_rate": rate}}}
                    con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('financial_parameters',?)", [json_text(financial)])
                    try:
                        calculate_costs(con, financial)
                    except Exception as exc:
                        self.fail(f"calculate_costs leaked {type(exc).__name__} for non-finite PV rate: {exc}")
                    if hasattr(con, "commit"):
                        con.commit()
                    costs = [json.loads(row[0]) for row in con.execute("SELECT result_json FROM calculations WHERE calculation_type='cost_summary' ORDER BY offer_id").fetchall()]
                    self.assertEqual(len(costs), 2)
                    for result in costs:
                        self.assertFalse(result["complete"], result)
                        self.assertIsNone(result.get("acquisition_present_value"), result)
                finally:
                    con.close()
                comparison = assess(run)
                self.assertFalse(comparison["ranking_allowed"], comparison)
                independent = independent_recompute(run)
                self.assertEqual(independent["status"], "UNVERIFIED", independent)

    def _payment_run(self, task_id: str, day: int, amount: float, payment_quote: str) -> tuple[Path, dict]:
        run = self._new_run(task_id)
        source_text = f"Offer total 100 EUR. Delivery 30 days. Payment: {payment_quote}."
        source_path = run / f"{task_id}.txt"
        source_path.write_text(source_text, encoding="utf-8")
        from common import sha256_file

        con = connect(run)
        try:
            con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES ('A','Supplier A','confirmed')")
            con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('A','A','active','[\"doc-A\"]')")
            con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,offer_id,sha256,size_bytes,parse_status,active) VALUES ('doc-A',?,?, 'text','offer','A','A',?,?, 'read',true)",
                        [source_path.name, source_path.name, sha256_file(source_path), len(source_text.encode("utf-8"))])
            con.execute("INSERT INTO document_units(unit_id,document_id,unit_type,unit_index,locator_json,text_content,structured_json,content_sha256) VALUES ('unit-A','doc-A','text_block',1,?,?,?,?)",
                        [json_text({"page": 1}), source_text, json_text({}), sha256_file(source_path)])
            for evidence_id, quote, locator in (("ev-total", "100 EUR", "A1"), ("ev-currency", "100 EUR", "A1"), ("ev-delivery", "30 days", "B1")):
                con.execute("INSERT INTO evidence(evidence_id,document_id,locator_json,quote,evidence_status,extraction_path,confidence,source_sha256) VALUES (?,'doc-A',?,?,'verified','unit_source_fixture',1.0,?)",
                            [evidence_id, json_text({"cell": locator}), quote, sha256_file(source_path)])
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at) VALUES ('A/total','A','A','total',100,NULL,'verified',true,'ev-total','unit_source_fixture','{}','2026-10-07')")
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at) VALUES ('A/currency','A','A','currency','EUR','verified',true,'ev-currency','unit_source_fixture','{}','2026-10-07')")
            con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at) VALUES ('A/delivery','A','A','delivery','30 days','verified',true,'ev-delivery','unit_source_fixture','{}','2026-10-07')")
            con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at,offer_id) VALUES (?, 'EXTRACT','semantic_extraction','offer_semantic_fields',?,1,true,'pending',0,'now','A')",
                        [task_id, json.dumps({"offer_id": "A", "fields": ["payment"], "document_ids": ["doc-A"]})])
            con.commit()
        finally:
            con.close()
        result = {
            "facts": [{"offer_id": "A", "field_key": "payment", "value_text": payment_quote, "evidence_status": "verified", "evidence_client_id": "ev-payment",
                       "normalized": {"payment_schedule": [{"amount": amount, "days": day}]}}],
            "evidence": [{"client_id": "ev-payment", "document_id": "doc-A", "locator": {"cell": "C1"}, "quote": payment_quote, "evidence_status": "verified"}],
        }
        return run, result

    @staticmethod
    def _canonical_counts(run: Path) -> tuple[list[int], str]:
        con = connect(run)
        try:
            counts = [con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in ("facts", "scope_items", "evidence", "model_receipts")]
            status = con.execute("SELECT status FROM task_queue WHERE task_id=?", [run.name]).fetchone()[0]
            return counts, status
        finally:
            con.close()

    def test_amount_only_payment_is_bound_to_delivery_relative_source_and_rejects_tampering(self):
        # Keep the existing percentage-form quote as a control and add the
        # critical amount-only literal, whose normalized day is delivery-relative.
        cases = [
            ("%100 60 days after delivery", 90, 100.0, True),
            ("%100 60 days after delivery", 60, 100.0, False),
            ("%100 60 days after delivery", 600, 100.0, False),
            ("%100 60 days after delivery", 90, 90.0, False),
            ("100 EUR, 60 days after delivery", 90, 100.0, True),
            ("100 EUR, 60 days after delivery", 60, 100.0, False),
            ("100 EUR, 60 days after delivery", 600, 100.0, False),
            ("100 EUR, 60 days after delivery", 90, 90.0, False),
        ]
        for index, (quote, day, amount, should_accept) in enumerate(cases):
            task_id = f"payment-source-{index}"
            with self.subTest(quote=quote, day=day, amount=amount, accepted=should_accept):
                run, result = self._payment_run(task_id, day, amount, quote)
                before, status_before = self._canonical_counts(run)
                self.assertEqual(status_before, "pending")
                if should_accept:
                    try:
                        recorded = record_task_result(run, task_id, result,
                                                      model_name="unit-test-fixture-no-model-call",
                                                      reasoning_effort="fixture",
                                                      input_tokens=0, output_tokens=0)
                    except Exception as exc:
                        self.fail(f"recorder rejected expected source-bound payment: {type(exc).__name__}: {exc}")
                    self.assertEqual(recorded["status"], "completed")
                    con = connect(run)
                    try:
                        saved = json.loads(con.execute("SELECT normalized_json FROM facts WHERE offer_id='A' AND field_key='payment'").fetchone()[0])
                        self.assertEqual(saved["payment_schedule"], [{"amount": 100.0, "days": 90}])
                        self.assertEqual(con.execute("SELECT count(*) FROM evidence").fetchone()[0], before[2] + 1)
                        self.assertEqual(con.execute("SELECT count(*) FROM model_receipts").fetchone()[0], 1)
                    finally:
                        con.close()
                else:
                    try:
                        record_task_result(run, task_id, result,
                                           model_name="unit-test-fixture-no-model-call",
                                           reasoning_effort="fixture",
                                           input_tokens=0, output_tokens=0)
                    except ValueError:
                        pass
                    except Exception as exc:
                        self.fail(f"source/payment rejection leaked {type(exc).__name__}; expected ValueError: {exc}")
                    else:
                        self.fail(f"recorder accepted unsupported payment source semantics: quote={quote!r}, days={day}, amount={amount}")
                    after, status_after = self._canonical_counts(run)
                    self.assertEqual(after, before, "rejected payment must not commit facts/scope/evidence/model receipt")
                    self.assertEqual(status_after, "pending")


    def test_cash_payment_keeps_explicit_delivery_event(self):
        from normalize import _payment_schedule
        for quote, lead, expected_day in [('TESLIM VE FATURA GUNUNDE PESIN', 20, 20),
                            ('TESLIM VE FATURA GUNUNDE PESIN', 15, 15),
                            ('Teslimde peşin', 30, 30), ('cash on delivery', 30, 30),
                            ('Cash at delivery', 30, 30), ('Peşin', 20, 0),
                            ('%100 advance', 30, 0)]:
            with self.subTest(quote=quote, lead=lead):
                self.assertEqual(_payment_schedule(quote, lead), [{'ratio': 1.0, 'days': expected_day}])

    def test_payment_never_invents_unknown_invoice_or_delivery_anchor(self):
        from normalize import _payment_schedule
        for quote, lead in [('Teslimde peşin', None), ('cash on delivery', None),
                            ('Fatura gününde peşin', 30), ('Cash on invoice date', 30),
                            ('%100 faturadan 60 gün sonra', 30),
                            ('%100 cash 60 days after invoice', 30),
                            ('%100 cash before delivery', 30)]:
            with self.subTest(quote=quote, lead=lead):
                self.assertIsNone(_payment_schedule(quote, lead))

    def test_cash_word_does_not_erase_installment_event_or_offset(self):
        from normalize import _payment_schedule
        cases = [('%30 peşin; %70 teslimde peşin', [{'ratio': .3, 'days': 0}, {'ratio': .7, 'days': 30}]),
                 ('%100 teslimden 60 gün sonra peşin', [{'ratio': 1.0, 'days': 90}]),
                 ('100% cash on delivery', [{'ratio': 1.0, 'days': 30}]),
                 ('100% cash 60 days after delivery', [{'ratio': 1.0, 'days': 90}])]
        for quote, expected in cases:
            with self.subTest(quote=quote):
                self.assertEqual(_payment_schedule(quote, 30), expected)

    def test_recorder_rejects_cash_day_zero_when_source_says_delivery(self):
        for day, accepted in [(0, False), (30, True)]:
            run, result = self._payment_run(f'cash-delivery-{day}', day, 100, 'TESLIM VE FATURA GUNUNDE PESIN')
            before, _ = self._canonical_counts(run)
            if accepted:
                saved = record_task_result(run, run.name, result, model_name='unit-test-fixture-no-model-call',
                                           reasoning_effort='fixture', input_tokens=0, output_tokens=0)
                self.assertEqual(saved['status'], 'completed')
            else:
                with self.assertRaisesRegex(ValueError, 'payment.*source|source.*payment'):
                    record_task_result(run, run.name, result, model_name='unit-test-fixture-no-model-call',
                                       reasoning_effort='fixture', input_tokens=0, output_tokens=0)
                after, status = self._canonical_counts(run)
                self.assertEqual(after, before)
                self.assertEqual(status, 'pending')

    def test_normalization_adds_delivery_day_without_changing_source_basis(self):
        from normalize import normalize
        run, result = self._payment_run('cash-auto-normalize', 30, 100, 'TESLIM VE FATURA GUNUNDE PESIN')
        result['facts'][0]['normalized'] = {'payment_date_basis': 'delivery_and_invoice_same_day'}
        record_task_result(run, run.name, result, model_name='unit-test-fixture-no-model-call',
                           reasoning_effort='fixture', input_tokens=0, output_tokens=0)
        normalize(run)
        con = connect(run)
        try:
            value = json.loads(con.execute("SELECT normalized_json FROM facts WHERE field_key='payment'").fetchone()[0])
            self.assertEqual(value['payment_schedule'], [{'ratio': 1.0, 'days': 30}])
            self.assertEqual(value['payment_date_basis'], 'delivery_and_invoice_same_day')
        finally:
            con.close()

    def test_recorder_cannot_treat_unknown_invoice_cash_as_order_day(self):
        run, result = self._payment_run('cash-invoice-unknown', 0, 100, 'Fatura gününde peşin')
        before, _ = self._canonical_counts(run)
        with self.assertRaises(ValueError):
            record_task_result(run, run.name, result, model_name='unit-test-fixture-no-model-call',
                               reasoning_effort='fixture', input_tokens=0, output_tokens=0)
        after, status = self._canonical_counts(run)
        self.assertEqual(after, before)
        self.assertEqual(status, 'pending')


    def _csv_day_run(self, name, day=20, header='teslim_gun'):
        from common import sha256_file
        run, result = self._payment_run(name, day, 100, 'TESLIM VE FATURA GUNUNDE PESIN')
        rows = [['firma', header, 'odeme', 'total', 'para_birimi'],
                ['Supplier A', str(day), 'TESLIM VE FATURA GUNUNDE PESIN', '100 EUR', 'EUR']]
        text = '\n'.join(','.join(row) for row in rows)
        source = run/'offer.csv'; source.write_text(text,encoding='utf-8')
        digest = sha256_file(source)
        con = connect(run)
        try:
            con.execute("UPDATE documents SET relative_path='offer.csv',filename='offer.csv',format_family='csv',sha256=?,size_bytes=?", [digest,len(text.encode('utf-8'))])
            con.execute("UPDATE document_units SET unit_type='csv_chunk',locator_json=?,text_content=?,structured_json=?,content_sha256=?",[json_text({'start_row':1,'end_row':2}),text,json_text({'rows':rows}),digest])
            con.execute("UPDATE evidence SET source_sha256=?",[digest])
            con.execute("UPDATE evidence SET unit_id='unit-A',locator_json=?,quote=? WHERE evidence_id='ev-delivery'",[json_text({'row':2,'column':2}),str(day)])
            con.execute("UPDATE facts SET value_text=?,normalized_json=? WHERE field_key='delivery'",[str(day),json_text({'days':day,'basis':'order_date'})])
            con.commit()
        finally:
            con.close()
        result['evidence'][0].update(unit_id='unit-A',locator={'row':2,'column':3})
        return run, result

    def test_csv_day_header_drives_payment_normalization(self):
        from normalize import normalize
        for day in [20,15]:
            run, result = self._csv_day_run('csv-auto-'+str(day),day)
            result['facts'][0]['normalized'] = {}
            record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)
            normalize(run)
            con=connect(run)
            try:
                value=json.loads(con.execute("SELECT normalized_json FROM facts WHERE field_key='payment'").fetchone()[0])
                self.assertEqual(value['payment_schedule'],[{'ratio':1.0,'days':day}])
            finally:
                con.close()

    def test_csv_day_header_binds_recorder_to_source_day(self):
        for day, accepted in [(20,True),(0,False)]:
            run,result=self._csv_day_run('csv-record-'+str(day))
            result['facts'][0]['normalized']['payment_schedule'][0]['days']=day
            before,_=self._canonical_counts(run)
            if accepted:
                self.assertEqual(record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)['status'],'completed')
            else:
                with self.assertRaises(ValueError):
                    record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)
                after,status=self._canonical_counts(run)
                self.assertEqual(after,before);self.assertEqual(status,'pending')

    def test_csv_day_metadata_needs_typed_source_header_and_current_owner_hash(self):
        from normalize import _delivery_days_from_fact
        from db import one_as_dict
        for case in ['unit_missing','stale_hash','foreign_offer','blank_cell','ambiguous_columns','metadata_tamper']:
            run,_=self._csv_day_run('csv-negative-'+case,header='teslim' if case=='unit_missing' else 'teslim_gun')
            con=connect(run)
            try:
                if case=='stale_hash':con.execute("UPDATE evidence SET source_sha256='stale' WHERE evidence_id='ev-delivery'")
                if case=='foreign_offer':con.execute("UPDATE documents SET offer_id='foreign'")
                if case in ['blank_cell','ambiguous_columns']:
                    obj=json.loads(con.execute('SELECT structured_json FROM document_units').fetchone()[0])
                    if case=='blank_cell':obj['rows'][1][1]=''
                    else:
                        obj['rows'][0][2]='delivery_days';obj['rows'][1][2]='30'
                        con.execute("UPDATE evidence SET locator_json=? WHERE evidence_id='ev-delivery'",[json_text({'row':2,'column':2,'end_column':3})])
                    con.execute('UPDATE document_units SET structured_json=?',[json_text(obj)])
                if case=='metadata_tamper':con.execute("UPDATE facts SET normalized_json=? WHERE field_key='delivery'",[json_text({'days':666})])
                fact=one_as_dict(con,"SELECT * FROM facts WHERE field_key='delivery'")
                self.assertEqual(_delivery_days_from_fact(con,fact),20 if case=='metadata_tamper' else None,case)
            finally:
                con.close()

    def test_csv_payment_before_delivery_fact_uses_same_payload_evidence(self):
        run,result=self._csv_day_run('csv-incoming-order')
        con=connect(run)
        try:
            con.execute("DELETE FROM facts WHERE field_key='delivery'")
            con.execute("UPDATE task_queue SET payload_json=?",[json_text({'offer_id':'A','fields':['payment','delivery'],'document_ids':['doc-A']})])
            con.commit()
        finally:
            con.close()
        result['facts'].append({'offer_id':'A','field_key':'delivery','value_text':'20','evidence_status':'verified','evidence_client_id':'ev-new-delivery','normalized':{'days':20,'basis':'order_date'}})
        result['evidence'].append({'client_id':'ev-new-delivery','document_id':'doc-A','unit_id':'unit-A','locator':{'row':2,'column':2},'quote':'20','evidence_status':'verified'})
        saved=record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)
        self.assertEqual(saved['status'],'completed')


    def _csv_range_day_run(self,name,day=20):
        from common import sha256_file
        run,result=self._csv_day_run(name,day)
        rows=[['firma','teslim_gun','teslim_baslangici','total','para_birimi','odeme'],
              ['Supplier A',str(day),'SIPARIS TARIHI','100 EUR','EUR','TESLIM VE FATURA GUNUNDE PESIN']]
        text='\n'.join(','.join(row) for row in rows);source=run/'offer.csv';source.write_text(text,encoding='utf-8');digest=sha256_file(source)
        con=connect(run)
        try:
            con.execute('UPDATE documents SET sha256=?,size_bytes=?',[digest,len(text.encode('utf-8'))])
            con.execute('UPDATE document_units SET text_content=?,structured_json=?,content_sha256=?',[text,json_text({'rows':rows}),digest])
            con.execute('UPDATE evidence SET source_sha256=?',[digest])
            con.execute("UPDATE evidence SET locator_json=?,quote=? WHERE evidence_id='ev-delivery'",[json_text({'row':2,'start_column':2,'end_column':3}),str(day)+',SIPARIS TARIHI'])
            con.execute("UPDATE facts SET value_text=? WHERE field_key='delivery'",[str(day)+',SIPARIS TARIHI']);con.commit()
        finally:con.close()
        result['evidence'][0]['locator']={'row':2,'column':6}
        return run,result

    def test_csv_start_column_range_preserves_real_payment_day(self):
        from normalize import normalize
        for day in [20,15]:
            run,result=self._csv_range_day_run('range-auto-'+str(day),day);result['facts'][0]['normalized']={}
            record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)
            normalize(run);con=connect(run)
            try:
                value=json.loads(con.execute("SELECT normalized_json FROM facts WHERE field_key='payment'").fetchone()[0])
                self.assertEqual(value['payment_schedule'],[{'ratio':1.0,'days':day}])
            finally:con.close()

    def test_csv_start_column_range_binds_recorder_and_rejects_order_day(self):
        for proposed,accepted in [(20,True),(0,False)]:
            run,result=self._csv_range_day_run('range-record-'+str(proposed));result['facts'][0]['normalized']['payment_schedule'][0]['days']=proposed
            before,_=self._canonical_counts(run)
            if accepted:self.assertEqual(record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)['status'],'completed')
            else:
                with self.assertRaises(ValueError):record_task_result(run,run.name,result,model_name='unit-test-fixture-no-model-call',reasoning_effort='fixture',input_tokens=0,output_tokens=0)
                after,status=self._canonical_counts(run);self.assertEqual(after,before);self.assertEqual(status,'pending')

    def test_csv_conflicting_column_aliases_and_invalid_ranges_are_not_proof(self):
        from normalize import _delivery_days_from_fact
        from db import one_as_dict
        for index,loc in enumerate([{'row':2,'column':2,'start_column':3,'end_column':3},
                                    {'row':2,'start_column':3,'end_column':2},
                                    {'row':2,'start_column':True,'end_column':3},
                                    {'row':1,'start_column':2,'end_column':3}]):
            run,_=self._csv_range_day_run('range-invalid-'+str(index));con=connect(run)
            try:
                con.execute("UPDATE evidence SET locator_json=? WHERE evidence_id='ev-delivery'",[json_text(loc)])
                self.assertIsNone(_delivery_days_from_fact(con,one_as_dict(con,"SELECT * FROM facts WHERE field_key='delivery'")))
            finally:con.close()

    def test_csv_range_still_requires_current_source_owner_and_unique_day_unit(self):
        from normalize import _delivery_days_from_fact
        from db import one_as_dict
        for case in ['stale','foreign','missing_unit','two_units','wrong_quote']:
            run,_=self._csv_range_day_run('range-source-'+case);con=connect(run)
            try:
                if case=='stale':con.execute("UPDATE evidence SET source_sha256='stale' WHERE evidence_id='ev-delivery'")
                if case=='foreign':con.execute("UPDATE documents SET offer_id='foreign'")
                if case=='wrong_quote':con.execute("UPDATE evidence SET quote='999,SIPARIS TARIHI' WHERE evidence_id='ev-delivery'")
                if case in ['missing_unit','two_units']:
                    obj=json.loads(con.execute('SELECT structured_json FROM document_units').fetchone()[0]);obj['rows'][0][1]='teslim' if case=='missing_unit' else 'teslim_gun'
                    if case=='two_units':obj['rows'][0][2]='delivery_days'
                    con.execute('UPDATE document_units SET structured_json=?',[json_text(obj)])
                self.assertIsNone(_delivery_days_from_fact(con,one_as_dict(con,"SELECT * FROM facts WHERE field_key='delivery'")),case)
            finally:con.close()


if __name__ == "__main__":
    unittest.main()
