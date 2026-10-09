import json,tempfile,unittest
from pathlib import Path
from db import connect,init_db,set_meta
from task_queue import _add_task,retry_decision_summary
from record_results import record_task_result
from claim_registry import rebuild
from active_records import current_claims
class SemanticRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name);init_db(self.run)
        set_meta(self.run,"profile","hizli");set_meta(self.run,"decision_status","SUFFICIENT")
        con=connect(self.run)
        self.tid=_add_task(con,"REPORT","decision_summary","decision_summary",{"goal":"summary"})
        con.execute("INSERT INTO calculations(calculation_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status,updated_at) VALUES ('C','cost_summary','{}','{\"comparable_total\":100}','test','hash','complete','now')")
        con.commit();con.close()
        self.record(self.tid,False)
    def tearDown(self):self.tmp.cleanup()
    def record(self,tid,valid):
        claim={"type":"calculated","text":"Maliyet hesaplandı.","calculation_ids":["C"],"assertions":[{"source_type":"calculation","source_id":"C","path":"comparable_total","operator":"exists"}]} if valid else {"type":"observation","text":"Dayanaksız gözlem."}
        path=self.run/(tid+".json");result={"summary":"Maliyet hesaplandı.","recommendation":None,"claims":[claim]}
        if path.exists():
            path=self.run/(tid+"-unrecorded-attempt.json")
        path.write_text(json.dumps(result),encoding="utf-8")
        return record_task_result(self.run,tid,result,str(path),model_name="unit-test-fixture",reasoning_effort="medium",input_tokens=10,output_tokens=5)
    def test_invalid_summary_gets_new_task_and_old_receipt_is_retained(self):
        self.assertEqual(rebuild(self.run)["status"],"FAIL")
        retry=retry_decision_summary(self.run);self.assertEqual(retry["status"],"RETRY_PENDING");self.assertNotEqual(retry["task_id"],self.tid)
        self.assertEqual(retry_decision_summary(self.run)["task_id"],retry["task_id"])
        self.record(retry["task_id"],True);self.assertEqual(rebuild(self.run)["status"],"PASS")
        con=connect(self.run)
        self.assertEqual(con.execute("SELECT count(*) FROM claims").fetchone()[0],2)
        self.assertEqual(len(current_claims(con)),1)
        self.assertEqual(con.execute("SELECT count(*) FROM model_receipts").fetchone()[0],2)
        self.assertEqual(con.execute("SELECT status FROM task_queue WHERE task_id=?",[self.tid]).fetchone()[0],"completed")
        con.close();self.assertTrue((self.run/(self.tid+".json")).exists())
    def test_revision_limit_keeps_bad_new_summary_blocked(self):
        retry=retry_decision_summary(self.run);self.record(retry["task_id"],False)
        self.assertEqual(retry_decision_summary(self.run)["status"],"MANUAL_REVIEW_REQUIRED")
        self.assertEqual(rebuild(self.run)["status"],"FAIL")
    def test_completed_result_is_immutable_and_cannot_be_overwritten(self):
        con=connect(self.run);before=con.execute("SELECT value FROM run_meta WHERE key='decision_summary_task_id'").fetchone()[0];con.close()
        self.assertEqual(self.record(self.tid,True)["status"],"already_completed")
        self.assertEqual(rebuild(self.run)["status"],"FAIL")
        con=connect(self.run);self.assertEqual(con.execute("SELECT value FROM run_meta WHERE key='decision_summary_task_id'").fetchone()[0],before);con.close()
    def test_bad_active_pointer_is_rejected(self):
        set_meta(self.run,"decision_summary_task_id","foreign")
        con=connect(self.run)
        try:
            with self.assertRaisesRegex(ValueError,"pointer"):current_claims(con)
        finally:con.close()
    def test_unowned_claim_remains_visible_after_valid_retry(self):
        retry=retry_decision_summary(self.run);self.record(retry["task_id"],True)
        con=connect(self.run)
        con.execute("INSERT INTO claims SELECT 'unowned-claim',claim_type,claim_text,support_status,fact_ids_json,calculation_ids_json,requirement_ids_json,evidence_ids_json,assertions_json,caveat,'outside-summary-task',revision,created_at FROM claims WHERE source_task_id=?", [self.tid])
        con.commit()
        self.assertEqual(len(current_claims(con)),2)
        con.close()
        self.assertEqual(rebuild(self.run)["status"],"FAIL")
