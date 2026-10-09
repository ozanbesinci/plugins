"""Explicit buyer declarations are scoped, replayable, and non-verifying."""
import json
import unittest
from pathlib import Path
from openpyxl import load_workbook

from test_workflow_integration import WorkflowIntegrationTests
from db import connect, get_meta, set_meta
from common import sha256_file
from user_question_gate import questions, record_response
from buyer_inputs import inputs_for
from workflow import prepare


class BuyerInputsTests(WorkflowIntegrationTests):
    def _issue(self, dimension='currency_basis'):
        self._write_offer('Alpha_fiyat_teklifi.xlsx', 100000)
        self._write_offer('Beta_fiyat_teklifi.xlsx', 105000)
        prepare(self.src, self.run, 'standart')
        con = connect(self.run)
        try:
            offer = con.execute("SELECT offer_id FROM offers WHERE status='active' ORDER BY offer_id LIMIT 1").fetchone()[0]
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                ['buyer-test','IDARE','critical','comparability_contract',
                 'watering scope requires explicit buyer input' if dimension=='scope_basis' else 'Explicit buyer input required',
                 '[]','["ev-test"]' if dimension=='scope_basis' else '[]','open'])
            con.commit()
        finally:
            con.close()
        set_meta(self.run, 'generated_issue_ownership_v1', {'buyer-test':{'component':'comparison_contract','key':dimension}})
        q = next(x for x in questions(self.run)['questions'] if x['issue_id']=='buyer-test')
        return offer, q

    def _response(self, q, entries=None):
        out = {'issue_id':q['issue_id'],'scope_sha256':q['scope_sha256'],
               'answer_text':'Alıcı tarafından açıkça beyan edildi.','answer_kind':'clarification'}
        if entries is not None:
            out['buyer_inputs'] = entries
        return out

    def test_currency_resume_replay_and_existing_finance_preserved(self):
        offer, q = self._issue()
        set_meta(self.run,'financial_parameters',{'discount_rates':{'EUR':0.10}})
        answer = self._response(q,[{'kind':'currency','offer_id':offer,'value':'EUR'}])
        before = connect(self.run)
        try:
            facts = before.execute('SELECT fact_id,evidence_status FROM facts ORDER BY fact_id').fetchall()
        finally:
            before.close()
        result = record_response(self.run,answer,self.root/'new-run')
        self.assertEqual(result['status'],'RECORDED_NEW_RUN_REQUIRED')
        self.assertEqual(record_response(self.run,answer,self.root/'new-run')['status'],'ALREADY_RECORDED')
        request = json.loads(Path(result['resume_request']).read_text(encoding='utf-8'))
        self.assertEqual(request['financial_parameters']['discount_rates'],{'EUR':0.10})
        self.assertEqual(len(request['financial_parameters']['buyer_inputs']),1)
        declaration = request['financial_parameters']['buyer_inputs'][0]
        self.assertTrue(declaration['source_hashes'])
        with self.assertRaises(ValueError):
            record_response(self.run,self._response(q,[{'kind':'currency','offer_id':offer,'value':'USD'}]),self.root/'new-run')
        resumed = prepare(self.src,self.root/'new-run','standart',
            financial_params=request['financial_parameters'],
            user_response_record=Path(request['user_response_record']),
            user_response_sha256=request['user_response_sha256'])
        self.assertEqual(resumed['status'],'PREPARED')
        con=connect(self.root/'new-run')
        try:
            self.assertEqual(inputs_for(con,offer,'currency')[0]['value'],'EUR')
        finally:
            con.close()
        con=connect(self.root/'new-run')
        try:
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                ['later-rate','IDARE','critical','payment_comparability',
                 'Provide rate for EUR to compare payment terms','[]','[]','open'])
            con.commit()
        finally:
            con.close()
        rate_q=next(x for x in questions(self.root/'new-run')['questions'] if x['issue_id']=='later-rate')
        rate_recorded=record_response(self.root/'new-run',{'issue_id':rate_q['issue_id'],
            'scope_sha256':rate_q['scope_sha256'],'answer_text':'EUR yıllık oran yüzde on',
            'answer_kind':'financial_rate','currency':'EUR','annual_effective_rate':0.10},self.root/'third-run')
        later=json.loads(Path(rate_recorded['resume_request']).read_text(encoding='utf-8'))
        self.assertEqual(prepare(self.src,self.root/'third-run','standart',
            financial_params=later['financial_parameters'],
            user_response_record=Path(later['user_response_record']),
            user_response_sha256=later['user_response_sha256'])['status'],'PREPARED')
        con=connect(self.root/'third-run')
        try:
            self.assertEqual(inputs_for(con,offer,'currency')[0]['value'],'EUR')
            con.execute("UPDATE documents SET sha256='stale' WHERE document_id=?", [next(iter(declaration['source_hashes']))])
            con.commit()
            with self.assertRaisesRegex(ValueError,'stale'):
                inputs_for(con,offer,'currency')
        finally:
            con.close()
        con=connect(self.run)
        try:
            self.assertEqual(facts,con.execute('SELECT fact_id,evidence_status FROM facts ORDER BY fact_id').fetchall())
        finally:
            con.close()

    def test_freeform_and_scope_rejection(self):
        offer,q = self._issue()
        self.assertEqual(record_response(self.run,self._response(q),self.root/'next')['status'],'RECORDED_STILL_WAITING')
        with self.assertRaisesRegex(ValueError,'kapsam'):
            record_response(self.run,{**self._response(q,[{'kind':'currency','offer_id':offer,'value':'EUR'}]),
                                     'scope_sha256':'old'},self.root/'next')
        with self.assertRaisesRegex(ValueError,'boyutu'):
            record_response(self.run,self._response(q,[{'kind':'scope_cost','offer_id':offer,
                'scope_id':'missing','amount':1,'currency':'EUR'}]),self.root/'next')
        with self.assertRaisesRegex(ValueError,'teklif hedefi'):
            record_response(self.run,self._response(q,[{'kind':'currency','offer_id':'not-offer','value':'EUR'}]),self.root/'next')

    def test_numeric_validation(self):
        offer,q = self._issue('scope_basis')
        con=connect(self.run)
        try:
            con.execute("INSERT INTO scope_items(scope_id,offer_id,classification,description,status,evidence_ids_json) VALUES (?,?,?,?,?,?)",
                        ['test-scope',offer,'extra','watering details','requires_confirmation','["ev-test"]'])
            con.commit()
        finally:
            con.close()
        for bad in [True,-1,float('nan'),float('inf'),'12']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                record_response(self.run,self._response(q,[{'kind':'scope_cost','offer_id':offer,
                    'scope_id':'test-scope','amount':bad,'currency':'EUR'}]),self.root/'next')
        valid = self._response(q,[{'kind':'scope_cost','offer_id':offer,
            'scope_id':'test-scope','amount':0,'currency':'EUR'}])
        self.assertEqual(record_response(self.run,valid,self.root/'next')['status'],'RECORDED_NEW_RUN_REQUIRED')

    def test_display_name_owner_and_fact_scope(self):
        offer,q=self._issue()
        con=connect(self.run)
        try:
            supplier=con.execute("""SELECT s.display_name FROM offers o JOIN suppliers s
                ON s.supplier_id=o.supplier_id WHERE o.offer_id=?""",[offer]).fetchone()[0]
            con.execute("UPDATE open_issues SET owner=?,issue_type='critical_field',fact_ids_json=? WHERE issue_id='buyer-test'",
                ['FIRMA:  '+supplier.upper()+'  ',json.dumps([f'{offer}/field/currency'])])
            con.commit()
        finally:
            con.close()
        q=next(x for x in questions(self.run)['questions'] if x['issue_id']=='buyer-test')
        self.assertEqual(record_response(self.run,self._response(q,[{'kind':'currency','offer_id':offer,'value':'EUR'}]),self.root/'next')['status'],
                         'RECORDED_NEW_RUN_REQUIRED')

    def test_medium_scope_signature_requires_matching_evidence(self):
        offer,q=self._issue('scope_basis')
        con=connect(self.run)
        try:
            con.execute("INSERT INTO facts(fact_id,offer_id,field_key,evidence_status,extraction_path) VALUES (?,?,?,'requires_confirmation','test')",
                        ['scope-fact',offer,'scope_signature'])
            con.execute("UPDATE open_issues SET severity='medium',issue_type='unpriced_employer_responsibility',question='Beton sonrası sulama işveren maliyeti',fact_ids_json=?,evidence_ids_json=? WHERE issue_id='buyer-test'",
                        [json.dumps([f'{offer}/field/scope_signature']),json.dumps(['ev-watering'])])
            for sid,description,evidence in [('watering','Beton sonrası sabah akşam sulama','ev-watering'),('other','Beton sonrası sulama','ev-other')]:
                con.execute("INSERT INTO scope_items(scope_id,offer_id,classification,description,status,evidence_ids_json) VALUES (?,?,?,?,?,?)",
                            [sid,offer,'unpriced_employer_responsibility',description,'unknown',json.dumps([evidence])])
            con.commit()
        finally:
            con.close()
        self.assertFalse(any(x['issue_id']=='buyer-test' for x in questions(self.run)['questions']))
        q=next(x for x in questions(self.run,include_medium=True)['questions'] if x['issue_id']=='buyer-test')
        with self.assertRaisesRegex(ValueError,'bağlanmıyor'):
            record_response(self.run,self._response(q,[{'kind':'scope_cost','offer_id':offer,'scope_id':'other',
                'amount':0,'currency':'EUR'}]),self.root/'next')
        self.assertEqual(record_response(self.run,self._response(q,[{'kind':'scope_cost','offer_id':offer,'scope_id':'watering',
            'amount':0,'currency':'EUR'}]),self.root/'next')['status'],'RECORDED_NEW_RUN_REQUIRED')

    def test_reference_quantity_requires_source_row_evidence(self):
        self._write_offer('Alpha_fiyat_teklifi.xlsx',100000)
        book=load_workbook(self.src/'Alpha_fiyat_teklifi.xlsx')
        sheet=book.active
        sheet['C7']=100
        sheet['D7']=1000
        sheet['E7']='adet'
        book.save(self.src/'Alpha_fiyat_teklifi.xlsx')
        prepare(self.src,self.run,'standart')
        con=connect(self.run)
        try:
            offer=con.execute("SELECT offer_id FROM offers WHERE status='active'").fetchone()[0]
            unit_id,doc_id,sha=con.execute("""SELECT u.unit_id,d.document_id,d.sha256 FROM document_units u
                JOIN documents d ON d.document_id=u.document_id WHERE d.offer_id=?""",[offer]).fetchone()
            con.execute("INSERT INTO evidence(evidence_id,document_id,unit_id,locator_json,evidence_status,extraction_path,source_sha256) VALUES (?,?,?,?,?,?,?)",
                ['buyer-row-ev',doc_id,unit_id,json.dumps({'range':'A7:E7'}),'verified','parser',sha])
            con.execute("UPDATE facts SET normalized_json=? WHERE offer_id=? AND field_key='quantity'",
                [json.dumps({'items':[{'item_id':'item-q','evidence_refs':['buyer-row-ev']}]}),offer])
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                ['quantity-question','IDARE','critical','scope_comparability','Reference quantity required','[]','[]','open'])
            con.commit()
        finally:
            con.close()
        q=next(x for x in questions(self.run)['questions'] if x['issue_id']=='quantity-question')
        con=connect(self.run)
        try:
            structured=json.loads(con.execute('SELECT structured_json FROM document_units WHERE unit_id=?',[unit_id]).fetchone()[0])
            line=next(c for c in structured['cells'] if c['cell']=='D7')
            line.update({'formula_or_value':'=B7*C7','calculated_value':999,
                         'is_formula':True,'calculated_available':True})
            con.execute('UPDATE document_units SET structured_json=? WHERE unit_id=?',[json.dumps(structured),unit_id])
            con.commit()
        finally:
            con.close()
        entry={'kind':'reference_quantity','offer_id':offer,'quantity_item_id':'item-q',
            'quantity':20,'unit':'adet','source_row':{'unit_id':unit_id,'quantity_cell':'B7',
            'unit_price_cell':'C7','line_total_cell':'D7','unit_cell':'E7'}}
        with self.assertRaisesRegex(ValueError,'cached toplam'):
            record_response(self.run,self._response(q,[entry]),self.root/'next')
        line['calculated_value']=1000
        con=connect(self.run)
        try:
            con.execute('UPDATE document_units SET structured_json=? WHERE unit_id=?',[json.dumps(structured),unit_id])
            con.commit()
        finally:
            con.close()
        recorded=record_response(self.run,self._response(q,[entry]),self.root/'next')
        self.assertEqual(recorded['status'],'RECORDED_NEW_RUN_REQUIRED')
        request=json.loads(Path(recorded['resume_request']).read_text(encoding='utf-8'))
        prepared=prepare(self.src,self.root/'next','standart',
            financial_params=request['financial_parameters'],
            user_response_record=Path(request['user_response_record']),
            user_response_sha256=request['user_response_sha256'])
        self.assertEqual(prepared['status'],'PREPARED')
        con=connect(self.root/'next')
        try:
            # The new run has not extracted canonical item-q yet. Audit/source
            # validation is still possible; the cost engine decides readiness.
            self.assertEqual(inputs_for(con,offer,'reference_quantity')[0]['quantity_item_id'],'item-q')
        finally:
            con.close()


    def test_supplier_folder_declaration_survives_buyer_resume_and_tamper_rejects(self):
        source=self.src
        for name,amount in [('Alpha',100000),('Beta',105000)]:
            self.src=source/name
            self.src.mkdir(parents=True)
            self._write_offer(f'{name}_fiyat_teklifi.xlsx',amount)
        self.src=source
        declaration=self.root/'supplier-folder-declaration.json'
        declaration_bytes=(json.dumps({'schema':'supplier-folder-declaration/v1',
            'legal_entity_verified':False,'mappings':{'Alpha':'Alpha','Beta':'Beta'},
            'source':'test user declaration'},ensure_ascii=False)+'\n').encode('utf-8')
        declaration.write_bytes(declaration_bytes)
        prepare(self.src,self.run,'standart',supplier_folder_declaration=declaration)
        con=connect(self.run)
        try:
            offer_ids=[r[0] for r in con.execute("SELECT offer_id FROM offers WHERE status='active' ORDER BY offer_id").fetchall()]
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                ['folder-currency','IDARE','critical','comparability_contract','Currency comparison','[]','[]','open'])
            con.commit()
        finally:
            con.close()
        self.assertEqual(len(offer_ids),2)
        set_meta(self.run,'generated_issue_ownership_v1',{'folder-currency':{'component':'comparison_contract','key':'currency'}})
        q=next(x for x in questions(self.run)['questions'] if x['issue_id']=='folder-currency')
        recorded=record_response(self.run,self._response(q,[{'kind':'currency','offer_id':oid,'value':'EUR'}
            for oid in offer_ids]),self.root/'next')
        request=json.loads(Path(recorded['resume_request']).read_text(encoding='utf-8'))
        self.assertEqual(request['supplier_folder_declaration'],str(declaration.resolve()))
        self.assertEqual(request['supplier_folder_declaration_sha256'],sha256_file(declaration))
        declaration.write_text('tampered',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'girdileri|declaration|changed'):
            prepare(self.src,self.root/'next','standart',
                financial_params=request['financial_parameters'],
                user_response_record=Path(request['user_response_record']),
                user_response_sha256=request['user_response_sha256'],
                supplier_folder_declaration=declaration)
        self.assertFalse((self.root/'next').exists())
        declaration.write_bytes(declaration_bytes)
        resumed=prepare(self.src,self.root/'next','standart',
            financial_params=request['financial_parameters'],
            user_response_record=Path(request['user_response_record']),
            user_response_sha256=request['user_response_sha256'],
            supplier_folder_declaration=declaration)
        self.assertEqual(resumed['status'],'PREPARED')
        self.assertEqual(get_meta(self.root/'next','supplier_folder_declaration_v1',{},parse_json=True)['mappings'],
                         {'Alpha':'Alpha','Beta':'Beta'})


    def test_owner_name_mismatch_requires_exact_single_offer_scope(self):
        offer, _ = self._issue()
        con = connect(self.run)
        try:
            other = con.execute('SELECT offer_id FROM offers WHERE offer_id<>? AND status=\'active\' LIMIT 1', [offer]).fetchone()[0]
            own_fact = con.execute("SELECT fact_id FROM facts WHERE offer_id=? AND field_key='currency'", [offer]).fetchone()[0]
            other_fact = con.execute("SELECT fact_id FROM facts WHERE offer_id=? AND field_key='currency'", [other]).fetchone()[0]
            document, sha = con.execute('SELECT document_id,sha256 FROM documents WHERE offer_id=? AND active=true LIMIT 1', [offer]).fetchone()
            other_doc, other_sha = con.execute('SELECT document_id,sha256 FROM documents WHERE offer_id=? AND active=true LIMIT 1', [other]).fetchone()
            for evidence_id, doc_id, source_sha in [('scope-own',document,sha),('scope-other',other_doc,other_sha)]:
                con.execute('INSERT INTO evidence(evidence_id,document_id,locator_json,evidence_status,extraction_path,source_sha256) VALUES (?,?,?,?,?,?)',
                            [evidence_id,doc_id,'{}','verified','test',source_sha])
            con.execute("UPDATE open_issues SET owner='FIRMA:ALPHA TICARET UNVANI',issue_type='critical_field' WHERE issue_id='buyer-test'")
            con.commit()
        finally:
            con.close()

        def answer(fact_ids, evidence_ids, target=offer):
            con = connect(self.run)
            try:
                con.execute('UPDATE open_issues SET fact_ids_json=?,evidence_ids_json=? WHERE issue_id=\'buyer-test\'',
                            [json.dumps(fact_ids),json.dumps(evidence_ids)])
                con.commit()
            finally:
                con.close()
            q = next(x for x in questions(self.run)['questions'] if x['issue_id']=='buyer-test')
            return record_response(self.run,self._response(q,[{'kind':'currency','offer_id':target,'value':'EUR'}]),self.root/'next')

        for fact_ids,evidence_ids,target in [
            ([],['scope-own'],offer),
            ([own_fact,'unknown-fact'],['scope-own'],offer),
            ([own_fact,other_fact],['scope-own'],offer),
            ([own_fact],[],offer),
            ([own_fact],['scope-own','unknown-evidence'],offer),
            ([own_fact],['scope-own','scope-other'],offer),
            ([own_fact],['scope-own'],other),
        ]:
            with self.subTest(facts=fact_ids,evidence=evidence_ids,target=target), self.assertRaisesRegex(ValueError,'kapsamı dışında'):
                answer(fact_ids,evidence_ids,target)
        con = connect(self.run)
        try:
            con.execute('UPDATE documents SET active=false WHERE document_id=?', [document])
            con.commit()
        finally:
            con.close()
        with self.assertRaisesRegex(ValueError,'kapsamı dışında'):
            answer([own_fact],['scope-own'])
        con = connect(self.run)
        try:
            con.execute('UPDATE documents SET active=true WHERE document_id=?', [document])
            con.commit()
        finally:
            con.close()
        self.assertEqual(answer([own_fact],['scope-own'])['status'],'RECORDED_NEW_RUN_REQUIRED')

    def test_payment_terms_resume_and_reject_invalid_percent_or_scope(self):
        offer, q = self._issue('payment_basis')
        entry = {'kind':'payment_terms','offer_id':offer,'milestones':[
            {'trigger':'work_start','percent':50},
            {'trigger':'work_delivery','percent':50}]}
        answer = self._response(q,[entry])
        for bad in [
            {**entry,'milestones':[{'trigger':'work_start','percent':60},{'trigger':'work_delivery','percent':50}]},
            {**entry,'milestones':[{'trigger':'work_start','percent':-1},{'trigger':'work_delivery','percent':101}]},
            {**entry,'milestones':[{'trigger':'work_start','percent':True},{'trigger':'work_delivery','percent':50}]},
            {**entry,'milestones':[{'trigger':'work_start','percent':50,'days':0},{'trigger':'work_delivery','percent':50}]},
            {**entry,'annual_effective_rate':0.1},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                record_response(self.run,self._response(q,[bad]),self.root/'next')
        with self.assertRaisesRegex(ValueError,'kapsam'):
            record_response(self.run,{**answer,'scope_sha256':'stale'},self.root/'next')
        with self.assertRaisesRegex(ValueError,'teklif hedefi'):
            record_response(self.run,self._response(q,[{**entry,'offer_id':'unknown'}]),self.root/'next')
        recorded = record_response(self.run,answer,self.root/'next')
        self.assertEqual(record_response(self.run,answer,self.root/'next')['status'],'ALREADY_RECORDED')
        request=json.loads(Path(recorded['resume_request']).read_text(encoding='utf-8'))
        self.assertNotIn('discount_rates',request['financial_parameters'])
        prepared=prepare(self.src,self.root/'next','standart',
            financial_params=request['financial_parameters'],
            user_response_record=Path(request['user_response_record']),
            user_response_sha256=request['user_response_sha256'])
        self.assertIn(prepared['status'],{'PREPARED','NEEDS_USER_INPUT'})
        self.assertEqual(get_meta(self.root/'next','financial_parameters',{},parse_json=True),
                         request['financial_parameters'])
        con=connect(self.root/'next')
        try:
            declaration=inputs_for(con,offer,'payment_terms')[0]
            self.assertEqual(declaration['milestones'],entry['milestones'])
            self.assertEqual(declaration['scope_sha256'],q['scope_sha256'])
            self.assertTrue(declaration['source_hashes'])
            con.execute('UPDATE documents SET sha256=? WHERE document_id=?',
                ['stale',next(iter(declaration['source_hashes']))])
            con.commit()
            with self.assertRaisesRegex(ValueError,'stale'):
                inputs_for(con,offer,'payment_terms')
        finally:
            con.close()

    def test_warranty_terms_resume_and_reject_negative_duration_or_wrong_field(self):
        offer, _ = self._issue()
        con=connect(self.run)
        try:
            con.execute("UPDATE open_issues SET issue_type='missing_warranty',fact_ids_json=? WHERE issue_id='buyer-test'",
                [json.dumps([f'{offer}/field/warranty'])])
            con.commit()
        finally:
            con.close()
        q=next(x for x in questions(self.run)['questions'] if x['issue_id']=='buyer-test')
        entry={'kind':'warranty_terms','offer_id':offer,'duration_years':5,'scope':'whole_work'}
        with self.assertRaisesRegex(ValueError,'boyutu'):
            record_response(self.run,self._response(q,[{'kind':'payment_terms','offer_id':offer,
                'milestones':[{'trigger':'work_start','percent':50},
                              {'trigger':'work_delivery','percent':50}]}]),self.root/'next')
        for bad in [
            {**entry,'duration_years':-5}, {**entry,'duration_years':0},
            {**entry,'duration_years':5.5}, {**entry,'scope':'selected_items'},
            {**entry,'start_event':'work_delivery'},
        ]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                record_response(self.run,self._response(q,[bad]),self.root/'next')
        recorded=record_response(self.run,self._response(q,[entry]),self.root/'next')
        request=json.loads(Path(recorded['resume_request']).read_text(encoding='utf-8'))
        self.assertEqual(prepare(self.src,self.root/'next','standart',
            financial_params=request['financial_parameters'],
            user_response_record=Path(request['user_response_record']),
            user_response_sha256=request['user_response_sha256'])['status'],'PREPARED')
        con=connect(self.root/'next')
        try:
            self.assertEqual(inputs_for(con,offer,'warranty_terms')[0]['duration_years'],5)
            self.assertEqual(inputs_for(con,offer,'payment_terms'),[])
        finally:
            con.close()


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(BuyerInputsTests(name) for name in sorted(BuyerInputsTests.__dict__) if name.startswith('test_'))
