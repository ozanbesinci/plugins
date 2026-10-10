"""Regressions for authoritative fields and partial question closure."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from db import init_db,connect
from buyer_controls import currency_basis,_resolve_field_groups
from user_question_gate import questions

class EffectiveFieldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name)/'run'
        init_db(self.run,Path(__file__).resolve().parents[2]);self.con=connect(self.run)
        self.con.execute("INSERT INTO suppliers(supplier_id,display_name) VALUES ('S','Supplier')")
        self.con.execute("INSERT INTO offers(offer_id,supplier_id,status) VALUES ('O','S','active')")
        for field in ['currency','validity','quote_date','warranty']:
            self.con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,evidence_status,normalized_json,extraction_path) VALUES (?,'O','S',?,?,'missing','{}','synthetic-unit-test')",['O/field/'+field,field,None])
        self.con.commit()
    def tearDown(self):self.con.close();self.tmp.cleanup()
    def test_currency_correction_precedes_source_without_rewriting_it(self):
        self.con.execute("UPDATE facts SET value_text='EUR',evidence_status='verified' WHERE field_key='currency'")
        with patch('buyer_controls.inputs_for',return_value=[{'value':'TRY'}]):
            self.assertEqual(currency_basis(self.con,'O')['value'],'TRY')
        self.assertEqual(tuple(self.con.execute("SELECT value_text,evidence_status FROM facts WHERE field_key='currency'").fetchone()),('EUR','verified'))
    def question(self):
        refs=['O/field/quote_date','O/field/validity','O/field/warranty']
        self.con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES ('multi','IDARE','medium','missing_terms','Dates and warranty',?,'[]','open')",[json.dumps(refs)])
        self.con.commit()
        return questions(self.run,include_medium=True)['questions'][0]
    def test_partial_answer_tracks_missing_field_then_closes_after_last_answer(self):
        q=self.question(); available={'quote_date','validity'};resolved=[]
        def authority(con,offer,field):
            return {'field':field,'value':{'date_status':'unknown','value':None}} if offer=='O' and field in available else None
        with patch('scope_ledger.buyer_authority',side_effect=authority):
            _resolve_field_groups(self.con,{'multi':q},{},resolved);self.con.commit()
            partial=questions(self.run,include_medium=True)['questions'][0]
            self.assertEqual(partial['remaining_fields'],['O/field/warranty'])
            self.assertEqual(partial['scope_sha256'],q['scope_sha256'])
            self.assertNotIn('teklif tarihi',partial['question'])
            self.assertEqual(resolved,[])
            available.add('warranty');_resolve_field_groups(self.con,{'multi':partial},{},resolved);self.con.commit()
        self.assertEqual(resolved,['multi'])
        self.assertEqual(questions(self.run,include_medium=True)['open_question_count'],0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM facts WHERE evidence_status='missing'").fetchone()[0],4)
    def test_field_answers_do_not_close_source_authority_or_other_offer_issue(self):
        q=self.question();resolved=[]
        with patch('scope_ledger.buyer_authority',return_value={'value':'known'}):
            _resolve_field_groups(self.con,{'multi':{**q,'issue_type':'source_authority_conflict'}},{},resolved)
            _resolve_field_groups(self.con,{'multi':{**q,'fact_ids':['B/field/quote_date']}},{},resolved)
        self.assertEqual(resolved,[])
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='multi'").fetchone()[0],'open')

if __name__=='__main__':unittest.main()
