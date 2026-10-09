
import unittest,json
import test_v504_audit_regressions as audit
from db import connect,init_db
from qa import _visual_tasks
class VisualRevisionTests(unittest.TestCase):
 setUp=audit.V504AuditRegressionTests.setUp
 tearDown=audit.V504AuditRegressionTests.tearDown
 def test_new_pdf_supersedes_pending_old_review_without_inheriting_pass(self):
  init_db(self.run)
  con=connect(self.run)
  try:
   con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",['old-review','QA','visual_exception','artifact_visual_review',json.dumps({'artifact_id':'old-pdf'}),80,True,'pending',0,'2026-10-04T00:00:00'])
   _visual_tasks(con,self.run,{'artifact_id':'new-pdf','relative_path':'new.pdf'},[{'page':1,'path':'new.png','sha256':'newhash'}],True)
   self.assertEqual(con.execute("SELECT status FROM task_queue WHERE task_id='old-review'").fetchone()[0],'superseded')
   self.assertEqual(con.execute("SELECT qa_status FROM render_hashes WHERE artifact_id='new-pdf' AND render_key='page:1'").fetchone()[0],'pending')
   self.assertEqual(con.execute("SELECT count(*) FROM task_queue WHERE status='pending' AND task_kind='artifact_visual_review'").fetchone()[0],1)
  finally:con.close()
