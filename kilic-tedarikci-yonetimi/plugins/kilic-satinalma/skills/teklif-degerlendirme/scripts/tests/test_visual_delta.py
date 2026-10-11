from __future__ import annotations
import json, os, shutil, sys, tempfile, unittest
from pathlib import Path
os.environ.setdefault('TEKLIF_TEST_SQLITE', '1')
SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
from db import init_db, connect
from qa import _visual_tasks
from context_packet import task_packet
from common import utc_now

class VisualDeltaTests(unittest.TestCase):
    def setUp(self):
        self.run=Path(tempfile.mkdtemp(prefix='teklif-v5-qa-')); init_db(self.run)
    def tearDown(self): shutil.rmtree(self.run,ignore_errors=True)
    def test_identical_page_inherits_and_only_changed_page_queues(self):
        con=connect(self.run)
        try:
            con.execute("INSERT INTO artifacts(artifact_id,artifact_type,relative_path,sha256,status,created_at) VALUES (?,?,?,?,?,?)",['A1','pdf','output/old.pdf','old','ready','2026-10-03T00:00:00Z'])
            con.execute("INSERT INTO render_hashes(artifact_id,render_key,render_sha256,qa_status,qa_note) VALUES (?,?,?,?,?)",['A1','page:1','h1','pass','ok'])
            con.execute("INSERT INTO render_hashes(artifact_id,render_key,render_sha256,qa_status,qa_note) VALUES (?,?,?,?,?)",['A1','page:2','h2','pass','ok'])
            con.execute("INSERT INTO artifacts(artifact_id,artifact_type,relative_path,sha256,status,created_at) VALUES (?,?,?,?,?,?)",['A2','pdf','output/new.pdf','new','ready','2026-10-03T01:00:00Z'])
            renders=[{'page':1,'path':'/tmp/p1.png','sha256':'h1'},{'page':2,'path':'/tmp/p2.png','sha256':'h3'}]
            created=_visual_tasks(con,self.run,{'artifact_id':'A2','relative_path':'output/new.pdf'},renders,full_first=True)
            con.commit()
            self.assertEqual(created,1)
            p1=con.execute("SELECT qa_status FROM render_hashes WHERE artifact_id='A2' AND render_key='page:1'").fetchone()[0]
            p2=con.execute("SELECT qa_status FROM render_hashes WHERE artifact_id='A2' AND render_key='page:2'").fetchone()[0]
            self.assertEqual(p1,'pass'); self.assertEqual(p2,'pending')
            tid=con.execute("SELECT task_id FROM task_queue WHERE task_kind='artifact_visual_review'").fetchone()[0]
        finally: con.close()
        packet=task_packet(self.run,tid,24,80000)
        self.assertEqual(len(packet['artifact']['pages']),1)
        self.assertEqual(packet['artifact']['pages'][0]['render_key'],'page:2')

    def test_large_pdf_visual_packets_cover_each_page_in_bounded_groups(self):
        renders=[{'page':page,'path':f'/tmp/page-{page}.png','sha256':f'hash-{page}'} for page in range(1,38)]
        con=connect(self.run)
        try:
            created=_visual_tasks(con,self.run,{'artifact_id':'A37','relative_path':'output/report.pdf'},renders,full_first=True)
            payloads=[json.loads(row[0]) for row in con.execute("SELECT payload_json FROM task_queue WHERE task_kind='artifact_visual_review'").fetchall()]
            statuses=con.execute("SELECT count(*) FROM render_hashes WHERE artifact_id='A37' AND qa_status='pending'").fetchone()[0]
        finally: con.close()
        self.assertEqual(created,13)
        self.assertEqual(statuses,37)
        self.assertTrue(all(1 <= len(packet['pages']) <= 3 for packet in payloads))
        self.assertEqual(sorted(page['page'] for packet in payloads for page in packet['pages']),list(range(1,38)))

if __name__=='__main__': unittest.main()
