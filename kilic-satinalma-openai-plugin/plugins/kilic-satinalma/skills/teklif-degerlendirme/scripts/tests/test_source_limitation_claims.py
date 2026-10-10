import json,tempfile,unittest
from pathlib import Path
from db import init_db,connect,set_meta
from claim_registry import rebuild

class SourceLimitationClaims(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name)/'run'
        init_db(self.run,Path(__file__).resolve().parents[2]);set_meta(self.run,'decision_status','SUFFICIENT')
        c=connect(self.run)
        c.execute("INSERT INTO facts(fact_id,field_key,evidence_status,extraction_path,critical) VALUES ('f','currency','missing','synthetic-test',true)")
        c.commit();c.close()
    def tearDown(self):self.tmp.cleanup()
    def claim(self,kind,assertions):
        c=connect(self.run)
        c.execute("INSERT INTO claims(claim_id,claim_type,claim_text,support_status,fact_ids_json,calculation_ids_json,assertions_json,revision,created_at) VALUES ('c',?,'Source limitation','unverified','[\"f\"]','[]',?,'test','now')",[kind,json.dumps(assertions)])
        c.commit();c.close();return rebuild(self.run)
    def status_assertion(self,value='missing'):
        return {'source_type':'fact','source_id':'f','path':'evidence_status','operator':'equals','value_text':value}
    def test_exact_status_observation_passes_without_verifying_source_value(self):
        result=self.claim('observation',[self.status_assertion()]);self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['claims'][0]['source_limitation_facts'],['f'])
        c=connect(self.run)
        try:self.assertEqual(c.execute("SELECT evidence_status FROM facts WHERE fact_id='f'").fetchone()[0],'missing')
        finally:c.close()
    def test_unbound_missing_source_observation_still_fails(self):
        self.assertEqual(self.claim('observation',[])['status'],'FAIL')
    def test_false_status_or_positive_source_value_still_fails(self):
        self.assertEqual(self.claim('observation',[self.status_assertion('verified')])['status'],'FAIL')
    def test_source_status_cannot_be_positive_recommendation_support(self):
        self.assertEqual(self.claim('recommendation',[self.status_assertion()])['status'],'FAIL')

if __name__=='__main__':unittest.main()
