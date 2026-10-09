from unittest import TestCase,mock
import test_v504_audit_regressions as audit
from db import connect,set_meta
from task_queue import generate_decision_summary_task
from workflow import advance
class SummaryOrderTests(TestCase):
 setUp=audit.V504AuditRegressionTests.setUp
 tearDown=audit.V504AuditRegressionTests.tearDown
 offer=audit.V504AuditRegressionTests.offer
 valid_pair=audit.V504AuditRegressionTests.valid_pair
 def test_pending_old_summary_cannot_bypass_new_independent_review(self):
  self.valid_pair();set_meta(self.run,'profile','yuksek_guvence')
  c=connect(self.run);c.execute("UPDATE facts SET extraction_path='semantic_llm' WHERE field_key='currency'");c.commit();c.close()
  generate_decision_summary_task(self.run)
  with mock.patch('workflow.generate_specialist_tasks',return_value={}):result=advance(self.run)
  self.assertEqual(result['status'],'NEEDS_LLM')
  self.assertTrue(result['tasks']);self.assertTrue(all(t['task_kind']=='independent_fact_review' for t in result['tasks']),result)
