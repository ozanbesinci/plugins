"""Answer-scoped suspension with continuing independent workers and durable state."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from db import connect, init_db
from task_queue import _add_task
from question_waits import (UserAnswerRequired, active, assert_agent_allowed,
                            assert_task_allowed, record_answer, register)
from record_results import record_task_result
from report_delivery import export_preliminary
from workflow import advance


class QuestionDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.run = self.root / 'run'
        init_db(self.run)

    def tearDown(self):
        self.temp.cleanup()

    def task(self, document='doc-A', fields=None, offer=None):
        con = connect(self.run)
        try:
            return _add_task(con, 'EXTRACT' if fields else 'REQUIREMENTS',
                             'semantic_extraction', 'offer_semantic_fields' if fields else 'requirements_extraction',
                             {'document_ids':[document], **({'fields':fields} if fields else {})},
                             document_id=document, offer_id=offer)
        finally:
            con.commit(); con.close()

    def question(self, issue='q-A', kind='source_authority_conflict', scope='scope-A', **extra):
        return {'issue_id':issue, 'scope_sha256':scope, 'question':'Hangi belge geçerli?',
                'issue_type':kind, 'owner':'IDARE', 'fact_ids':[], 'evidence_ids':[],
                'sources':[{'document_id':'doc-A','offer_id':'off-A'}], **extra}

    def answer(self, q, *, text='R1 geçerlidir.', sufficient=True):
        return record_answer(self.run, q['issue_id'], q['scope_sha256'], text,
                             sufficient=sufficient, response_sha256='a'*64)

    def test_source_dependency_blocks_only_affected_task(self):
        dependent=self.task(); independent=self.task('doc-B')
        register(self.run,self.question())
        with self.assertRaises(UserAnswerRequired): assert_task_allowed(self.run,dependent)
        assert_task_allowed(self.run,independent)

    def test_same_offer_unrelated_field_does_not_wait(self):
        currency=self.task(fields=['currency'],offer='off-A')
        quantity=self.task(fields=['quantity'],offer='off-A')
        register(self.run,self.question(kind='critical_field',fact_ids=['off-A/field/currency']))
        with self.assertRaises(UserAnswerRequired): assert_task_allowed(self.run,currency)
        assert_task_allowed(self.run,quantity)

    def test_same_requirement_other_firm_continues_but_global_criterion_waits(self):
        con=connect(self.run)
        try:
            con.execute("INSERT INTO facts(fact_id,offer_id,requirement_id,field_key,evidence_status,extraction_path) VALUES (?,?,?,?,?,?)",
                        ['fact-A','off-A','shared-requirement','requirement','requires_confirmation','synthetic'])
            a=_add_task(con,'EXTRACT','difficult_semantics','requirement_assessment',
                        {'offer_id':'off-A','requirement_ids':['shared-requirement']},offer_id='off-A')
            b=_add_task(con,'EXTRACT','difficult_semantics','requirement_assessment',
                        {'offer_id':'off-B','requirement_ids':['shared-requirement']},offer_id='off-B')
            con.commit()
        finally:con.close()
        q=self.question(kind='requirement_unresolved',owner='FIRMA:sup-A',fact_ids=['fact-A'])
        register(self.run,q)
        with self.assertRaises(UserAnswerRequired):assert_task_allowed(self.run,a)
        assert_task_allowed(self.run,b)
        register(self.run,{**q,'issue_id':'global-criterion','owner':'IDARE'})
        with self.assertRaises(UserAnswerRequired):assert_task_allowed(self.run,b)

    def test_specialist_disjoint_fact_subset_in_same_offer_continues(self):
        con=connect(self.run)
        try:
            unrelated=_add_task(con,'REVIEW','technical_exception','technical_exception',
                                {'offer_id':'off-A','fact_ids':['clean-fact']},offer_id='off-A')
            related=_add_task(con,'REVIEW','technical_exception','technical_exception',
                              {'offer_id':'off-A','fact_ids':['off-A/field/warranty']},offer_id='off-A')
            con.commit()
        finally:con.close()
        register(self.run,self.question(kind='critical_field',fact_ids=['off-A/field/warranty']))
        assert_task_allowed(self.run,unrelated)
        with self.assertRaises(UserAnswerRequired):assert_task_allowed(self.run,related)

    def test_explicit_optional_and_approval_agent_bindings(self):
        for kind in ('optional','preference','approval'):
            q=self.question(issue='q-'+kind,kind=kind)
            with self.assertRaises(ValueError): register(self.run,q)
            register(self.run,q,agent_ids=['waiting-agent'])
        with self.assertRaises(UserAnswerRequired): assert_agent_allowed(self.run,'waiting-agent')
        assert_agent_allowed(self.run,'independent-agent')

    def test_no_timeout_and_restart_cannot_release_dependency(self):
        task=self.task();register(self.run,self.question())
        con=connect(self.run)
        try:
            con.execute("UPDATE user_question_waits SET created_at='1900-01-01T00:00:00Z'");con.commit()
        finally:con.close()
        script=Path(__file__).resolve().parents[1]
        code=("import sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;"
              "from question_waits import assert_task_allowed;assert_task_allowed(Path(sys.argv[2]),sys.argv[3])")
        result=subprocess.run([sys.executable,'-B','-c',code,str(script),str(self.run),task],
                              capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('UserAnswerRequired',result.stderr)
        with self.assertRaises(UserAnswerRequired):assert_task_allowed(self.run,task)

    def test_partial_unrelated_and_continue_answers_never_resume(self):
        task=self.task();q=self.question();register(self.run,q)
        for text in ('Sadece bir kısmını biliyorum.','Başka konuya geçelim.','devam'):
            self.assertFalse(self.answer(q,text=text,sufficient=False)['resumed'])
            with self.assertRaises(UserAnswerRequired):assert_task_allowed(self.run,task)
        with self.assertRaises(ValueError):self.answer(q,text='devam',sufficient=True)

    def test_answer_resumes_only_its_dependencies_once(self):
        a=self.task('doc-A');b=self.task('doc-B')
        q1=self.question(kind='optional',issue='q-1');q2=self.question(kind='optional',issue='q-2')
        register(self.run,q1,task_ids=[a,b]);register(self.run,q2,task_ids=[b])
        self.assertTrue(self.answer(q1)['resumed'])
        self.assertFalse(self.answer(q1)['resumed'])
        assert_task_allowed(self.run,a)
        with self.assertRaises(UserAnswerRequired):assert_task_allowed(self.run,b)
        self.assertTrue(self.answer(q2)['resumed']);assert_task_allowed(self.run,b)

    def test_repeated_registration_does_not_reask_answered_question(self):
        q=self.question(kind='optional');register(self.run,q,agent_ids=['A'])
        self.answer(q);register(self.run,q,agent_ids=['A'])
        self.assertEqual(active(self.run),[]);assert_agent_allowed(self.run,'A')
        con=connect(self.run)
        try:self.assertEqual(con.execute('SELECT count(*) FROM user_question_waits').fetchone()[0],1)
        finally:con.close()

    def test_changed_scope_rejects_old_answer(self):
        q=self.question(kind='optional');register(self.run,q,agent_ids=['A'])
        newer={**q,'scope_sha256':'changed-scope'};register(self.run,newer,agent_ids=['A'])
        with self.assertRaises(ValueError):self.answer(q)
        with self.assertRaises(UserAnswerRequired):assert_agent_allowed(self.run,'A')

    def test_waiting_result_cannot_be_recorded_or_increment_attempts(self):
        task=self.task();register(self.run,self.question())
        with self.assertRaises(UserAnswerRequired):
            record_task_result(self.run,task,{'requirements':[],'evidence':[]},
                               model_name='test',reasoning_effort='medium',input_tokens=10,output_tokens=2)
        con=connect(self.run)
        try:
            self.assertEqual(con.execute('SELECT attempts,status FROM task_queue WHERE task_id=?',[task]).fetchone(),(0,'pending'))
            self.assertEqual(con.execute('SELECT count(*) FROM model_receipts').fetchone()[0],0)
        finally:con.close()

    def test_running_independent_worker_finishes_after_question(self):
        task=self.task('doc-B');started=threading.Event();proceed=threading.Event();outcome=[]
        def worker():
            started.set();proceed.wait(10)
            try:
                result=record_task_result(self.run,task,{'requirements':[],'evidence':[]},
                                         model_name='test',reasoning_effort='medium',input_tokens=10,output_tokens=2)
                outcome.append(result['status'])
            except Exception as exc:outcome.append(type(exc).__name__+': '+str(exc))
        thread=threading.Thread(target=worker);thread.start();self.assertTrue(started.wait(10))
        register(self.run,self.question());proceed.set();thread.join(20)
        self.assertFalse(thread.is_alive());self.assertEqual(outcome,['completed'])

    def test_report_cannot_bypass_wait(self):
        register(self.run,self.question())
        with patch('report_delivery.build_preliminary') as build:
            with self.assertRaises(UserAnswerRequired):export_preliminary(self.run,'Ön rapor')
            build.assert_not_called()
        self.assertFalse((self.run/'reports').exists())

    def test_repeated_next_does_not_run_dependent_processing_or_report(self):
        register(self.run,self.question())
        wait={'status':'NEEDS_USER_INPUT','questions':[self.question()],
              'open_question_count':1,'remaining_question_count':0,
              'wait_policy':'dependent_tasks_only_no_timeout'}
        with patch('workflow.user_input_waiting',return_value=wait),patch('workflow._pending_by_phase',return_value=[]),\
             patch('workflow.extract_fields') as extract,patch('workflow.normalize') as normalize,\
             patch('report_hooks.export_preliminary') as report:
            self.assertEqual(advance(self.run)['status'],'NEEDS_USER_INPUT')
            extract.assert_not_called();normalize.assert_not_called();report.assert_not_called()

    def test_record_cli_waits_before_reading_result_file(self):
        task=self.task();register(self.run,self.question())
        script=Path(__file__).resolve().parents[1]/'record_results.py'
        result=subprocess.run([sys.executable,'-B',str(script),'--run',str(self.run),'--task-id',task,
                               '--input',str(self.root/'does-not-exist.json'),'--model','test','--effort','medium'],
                              capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,4)
        self.assertEqual(json.loads(result.stdout)['status'],'NEEDS_USER_INPUT')
        self.assertNotIn('FileNotFoundError',result.stderr)

    def test_lost_control_file_never_silently_resumes(self):
        register(self.run,self.question())
        (self.run/'user_wait_control'/'state.json').unlink()
        with self.assertRaises(UserAnswerRequired):active(self.run)

    def test_updater_native_and_python_guard_only_bound_actor(self):
        q=self.question(kind='approval');register(self.run,q,agent_ids=['waiting-agent'])
        plugin=Path(__file__).resolve().parents[4]
        native=plugin/'vendor/guncelleyici/scripts/program-ortak.ps1'
        py=plugin/'vendor/guncelleyici/scripts/islem_guvencesi.py'
        state=self.run/'user_wait_control'/'state.json'
        for actor,blocked in [('waiting-agent',True),('independent-agent',False)]:
            env={**os.environ,'KILIC_USER_WAIT_STATE':str(state),'KILIC_AGENT_ID':actor}
            command=". $args[0]; Assert-UserAnswerDependencies; 'ALLOWED'"
            # Paths are passed as an argument, not interpolated as shell code.
            psfile=self.root/'guard.ps1'
            psfile.write_text("param([string]$GuardFile)\n. $GuardFile\nAssert-UserAnswerDependencies\n'ALLOWED'\n",encoding='utf-8')
            ps=subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
                               '-NoProfile','-File',str(psfile),str(native)],env=env,
                              capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
            python=subprocess.run([sys.executable,'-B',str(py)],env=env,capture_output=True,
                                  text=True,encoding='utf-8',errors='replace',timeout=30)
            self.assertEqual(ps.returncode!=0,blocked)
            self.assertEqual(python.returncode==4,blocked)


if __name__=='__main__':unittest.main()
