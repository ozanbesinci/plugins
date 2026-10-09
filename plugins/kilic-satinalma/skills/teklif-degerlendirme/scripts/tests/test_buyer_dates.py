"""User date answers are authoritative inputs; unknown stays an explicit limitation."""
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from openpyxl import Workbook
from buyer_inputs import validate_commercial_input, inputs_for
from common import sha256_file
from db import connect, rows_as_dict
from user_question_gate import questions, record_response
from workflow import prepare, advance
from record_results import record_task_result


class BuyerDateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='buyer-date-test-')
        self.root=Path(self.temp.name); self.source=self.root/'source';self.source.mkdir()
        self.run=self.root/'run'
        for firm,total,issued,validity in [('Alpha',100000,'',''),('Beta',105000,'07.10.2026','90 gün')]:
            wb=Workbook();ws=wb.active;ws.title='Teklif'
            for row in [('Fiyat Teklifi',''),('Teklif Tarihi',issued),('Geçerlilik',validity),
                        ('Genel Toplam',total),('Para Birimi','EUR'),('KDV','hariç'),('Miktar',10),
                        ('Birim','adet'),('Ürün','Pompa'),('Teslim','30 gün'),('Ödeme','%100 60 gün'),
                        ('Incoterm','DDP'),('Garanti','24 ay'),('Tedarikçi\nFirma: '+firm+' Ltd.','')]:
                ws.append(row)
            wb.save(self.source/(firm+'_fiyat_teklifi.xlsx'))
        prepare(self.source,self.run,'hizli',date(2026,10,9))
        self.complete_missing(self.run)

    def tearDown(self): self.temp.cleanup()

    def complete_missing(self,run):
        # Deterministic unit-test response, explicitly not a real model receipt.
        # Both cells are empty in this synthetic workbook; no evidence invented.
        step=advance(run)
        for task in step.get('tasks') or []:
            if task['task_kind']!='offer_semantic_fields': continue
            packet=json.loads(Path(task['context_path']).read_text(encoding='utf-8'))
            payload=packet['instructions']
            record_task_result(run,task['task_id'],{'facts':[
                {'field_key':field,'offer_id':payload['offer_id'],'evidence_status':'missing','critical':True}
                for field in payload['fields']], 'evidence':[]},
                model_name='synthetic-unit-test-no-model-call',reasoning_effort='medium',
                input_tokens=1,cached_input_tokens=0,output_tokens=1)
        return advance(run)

    def answer(self,run,field,status,value,target):
        q=next(q for q in questions(run,limit=10000,include_medium=True)['questions']
               if q['issue_type']=='critical_field' and any(x.endswith('/field/'+field) for x in q['fact_ids']))
        con=connect(run)
        try:
            offer=con.execute("SELECT o.offer_id FROM offers o JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE s.display_name='Alpha Ltd.'").fetchone()[0]
        finally: con.close()
        kind='validity_date' if field=='validity' else 'quote_date'
        response={'issue_id':q['issue_id'],'scope_sha256':q['scope_sha256'],
                  'answer_kind':'clarification','answer_text':'SENTETİK TEST: '+(value or 'bilinmiyor'),
                  'buyer_inputs':[{'kind':kind,'offer_id':offer,'date_status':status,'value':value}]}
        result=record_response(run,response,target)
        request=json.loads(Path(result['resume_request']).read_text(encoding='utf-8'))
        prepare(self.source,target,request['profile'],date.fromisoformat(request['analysis_date']),
                request['financial_parameters'],request.get('scoring_parameters'),
                Path(request['user_response_record']),request['user_response_sha256'])
        return offer,self.complete_missing(target),request

    def test_known_validity_then_unknown_quote_date_no_repeated_question_or_date_invention(self):
        before=connect(self.run)
        try: facts=before.execute('SELECT fact_id,value_date,evidence_status FROM facts ORDER BY fact_id').fetchall()
        finally: before.close()
        offer,first,_=self.answer(self.run,'validity','known','2026-10-30',self.root/'second')
        self.assertEqual(first['status'],'NEEDS_USER_INPUT')
        _,step,request=self.answer(self.root/'second','quote_date','unknown',None,self.root/'third')
        self.assertEqual(step['status'],'NEEDS_LLM')
        self.assertEqual(step['gate']['status'],'SUFFICIENT')
        packet=json.loads(Path(step['tasks'][0]['context_path']).read_text(encoding='utf-8'))
        self.assertEqual(packet['decision_context']['meta']['decision_status'],'SUFFICIENT')
        self.assertFalse(packet['decision_context']['pre_output']['recommendation_must_be_null'])
        self.assertEqual(questions(self.root/'third')['open_question_count'],0)
        con=connect(self.root/'third')
        try:
            self.assertEqual(facts,con.execute('SELECT fact_id,value_date,evidence_status FROM facts ORDER BY fact_id').fetchall())
            self.assertIsNone(con.execute('SELECT quote_date FROM offers WHERE offer_id=?',[offer]).fetchone()[0])
            cost=json.loads(con.execute("SELECT result_json FROM calculations WHERE offer_id=? AND calculation_type='cost_summary'",[offer]).fetchone()[0])
            self.assertEqual(cost['validity_date']['value'],'2026-10-30')
            self.assertEqual(cost['quote_date'],{'date_status':'unknown','value':None})
            self.assertEqual(Decimal(cost['comparable_total']),Decimal('100000'))
        finally: con.close()
        # Tampered response bytes cannot authorize the same date.
        record=Path(request['user_response_record']);record.write_text(record.read_text(encoding='utf-8')+' ',encoding='utf-8')
        con=connect(self.root/'third')
        try:
            with self.assertRaisesRegex(ValueError,'eksik veya değişmiş'):
                inputs_for(con,offer,'validity_date')
        finally: con.close()

    def test_unknown_validity_remains_material_and_does_not_invent_date(self):
        offer,first,_=self.answer(self.run,'validity','unknown',None,self.root/'second')
        _,step,_=self.answer(self.root/'second','quote_date','unknown',None,self.root/'third')
        self.assertTrue(step['gate']['answered_unknown_only'])
        self.assertEqual(step['gate']['status'],'PRELIMINARY_ONLY')
        self.assertEqual(questions(self.root/'third')['open_question_count'],0)
        con=connect(self.root/'third')
        try:
            cost=json.loads(con.execute("SELECT result_json FROM calculations WHERE offer_id=? AND calculation_type='cost_summary'",[offer]).fetchone()[0])
            self.assertEqual(cost['validity_date'],{'date_status':'unknown','value':None})
        finally:con.close()

    def test_date_types_reject_non_dates_unknown_values_and_extra_fields(self):
        for kind in ('validity_date','quote_date'):
            validate_commercial_input(kind,{'date_status':'known','value':'2026-10-30'})
            validate_commercial_input(kind,{'date_status':'unknown','value':None})
            for value in ({'date_status':'unknown','value':'2026-10-30'},
                          {'date_status':'known','value':'2026-02-30'},
                          {'date_status':'known','value':'30.10.2026'},
                          {'date_status':'known','value':'2026-10-30','verified':True}):
                with self.subTest(kind=kind,value=value),self.assertRaises(ValueError):
                    validate_commercial_input(kind,value)

    def test_date_input_cannot_answer_other_field_or_another_offer(self):
        q=questions(self.run,limit=10000)['questions'][0]
        con=connect(self.run)
        try: other=con.execute("SELECT o.offer_id FROM offers o JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE s.display_name='Beta Ltd.'").fetchone()[0]
        finally:con.close()
        with self.assertRaises(ValueError):
            record_response(self.run,{'issue_id':q['issue_id'],'scope_sha256':q['scope_sha256'],
                'answer_kind':'clarification','answer_text':'SENTETİK TEST',
                'buyer_inputs':[{'kind':'quote_date','offer_id':other,'date_status':'unknown','value':None}]},self.root/'bad')


if __name__=='__main__': unittest.main()
