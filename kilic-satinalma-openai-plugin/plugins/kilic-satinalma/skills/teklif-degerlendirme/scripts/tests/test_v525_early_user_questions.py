"""User input stops dependent work and never verifies offer evidence by itself."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from test_workflow_integration import WorkflowIntegrationTests
from workflow import advance, prepare, status
from db import connect, get_meta, init_db, set_meta, set_state
from user_question_gate import record_response, waiting
from record_results import record_task_result
from validate_run import validate


class EarlyUserQuestions(WorkflowIntegrationTests):
    def test_ready_pdf_is_not_deliverable_during_visual_qa(self):
        init_db(self.run)
        set_meta(self.run, 'profile', 'yuksek_guvence')
        set_state(self.run, 'REPORT', 'PASS', {'pdf': 'created'})
        set_state(self.run, 'QA', 'RUNNING', {'visual_pending_pages': 37})
        con = connect(self.run)
        try:
            con.execute("INSERT INTO artifacts(artifact_id,artifact_type,relative_path,sha256,status,created_at) VALUES (?,?,?,?,?,?)",
                ['pending-pdf','pdf','output/Teklif_Degerlendirme.pdf','pending-hash','ready','2026-10-07T00:00:00Z'])
            con.commit()
        finally:
            con.close()
        observed = status(self.run)
        self.assertFalse(observed['deliverable_artifacts'])
        self.assertEqual(observed['delivery_reason'], 'final validation has not completed')
        self.assertFalse(observed['artifacts'][0]['deliverable'])

    def test_late_qa_question_marks_existing_artifact_undeliverable(self):
        self._write_offer('Alpha_fiyat_teklifi.xlsx',100000)
        self._write_offer('Beta_fiyat_teklifi.xlsx',105000)
        prepare(self.src,self.run,'hizli')
        self.assertEqual(advance(self.run)['status'],'NEEDS_LLM')
        _,calc_id=self._support_refs()
        record_task_result(self.run,self._pending_decision_task(),{
            'summary':'İki teklif karşılaştırılmıştır.',
            'recommendation':{'type':'cost_observation','text':'Maliyetler ayrıca gösterilmiştir.'},
            'claims':[{'type':'calculated','text':'Hesaplanan maliyet gösterilmiştir.',
                'calculation_ids':[calc_id],
                'assertions':[{'source_type':'calculation','source_id':calc_id,
                               'path':'comparable_total','operator':'exists'}]}]},
            model_name='synthetic-test-fixture',reasoning_effort='test-only',
            input_tokens=0,cached_input_tokens=0,output_tokens=0)
        from qa import run_qa as real_qa
        def qa_with_new_question(run):
            con=connect(run)
            try:
                con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                    ['late-qa','IDARE','critical','comparability_contract',
                     'Karşılaştırma kapsamı için teyit gereklidir.','[]','[]','open'])
                con.commit()
            finally:con.close()
            return real_qa(run)
        with patch('qa.run_qa',side_effect=qa_with_new_question):
            final=advance(self.run)
        self.assertEqual(final['status'],'NEEDS_USER_INPUT')
        self.assertTrue(any(x['issue_id']=='late-qa' for x in final['questions']))
        self.assertTrue((self.run/'output'/'Teklif_Degerlendirme.xlsx').is_file())
        self.assertFalse(status(self.run)['deliverable_artifacts'])
        self.assertEqual(validate(self.run)['status'],'BLOCKED')

    def test_report_export_question_is_shown_before_qa(self):
        self._write_offer('Alpha_fiyat_teklifi.xlsx',100000)
        self._write_offer('Beta_fiyat_teklifi.xlsx',105000)
        prepare(self.src,self.run,'hizli')
        self.assertEqual(advance(self.run)['status'],'NEEDS_LLM')
        _,calc_id=self._support_refs()
        record_task_result(self.run,self._pending_decision_task(),{
            'summary':'İki teklif karşılaştırılmıştır.',
            'recommendation':{'type':'cost_observation','text':'Maliyetler ayrıca gösterilmiştir.'},
            'claims':[{'type':'calculated','text':'Hesaplanan maliyet gösterilmiştir.',
                'calculation_ids':[calc_id],
                'assertions':[{'source_type':'calculation','source_id':calc_id,
                               'path':'comparable_total','operator':'exists'}]}]},
            model_name='synthetic-test-fixture',reasoning_effort='test-only',
            input_tokens=0,cached_input_tokens=0,output_tokens=0)
        from report_export import export_report as real_export
        def export_with_question(run):
            report=real_export(run)
            con=connect(run)
            try:
                con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                    ['late-report','IDARE','critical','comparability_contract',
                     'Rapor kapsamı için teyit gereklidir.','[]','[]','open'])
                con.commit()
            finally:con.close()
            return report
        with patch('report_export.export_report',side_effect=export_with_question):
            final=advance(self.run)
        self.assertEqual(final['status'],'NEEDS_USER_INPUT')
        self.assertTrue(any(x['issue_id']=='late-report' for x in final['questions']))
        self.assertFalse(status(self.run)['deliverable_artifacts'])
        states={x['phase']:x['status'] for x in status(self.run)['states']}
        self.assertEqual(states['REPORT'],'BLOCKED')
        self.assertEqual(states['QA'],'SKIPPED')

    def test_internal_confirmation_issue_is_not_sent_to_user(self):
        self._write_offer('Alpha_fiyat_teklifi.xlsx',100000)
        self._write_offer('Beta_fiyat_teklifi.xlsx',105000)
        prepare(self.src,self.run,'standart')
        con=connect(self.run)
        try:
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                ['confirmation-test','IDARE','critical','independent_confirmation_required','Confirm cited values','[]','[]','open'])
            con.commit()
        finally:con.close()
        self.assertIsNone(waiting(self.run))

    def test_revision_ambiguity_blocks_dependent_dispatch(self):
        self._write_offer('Alpha_rev1_teklifi.xlsx',100000)
        self._write_offer('Alpha_rev2_teklifi.xlsx',99000)
        prepared=prepare(self.src,self.run,'standart')
        step=advance(self.run) if prepared['status']=='PREPARED' else prepared
        self.assertEqual(step['status'],'NEEDS_USER_INPUT')
        self.assertTrue(any(x['issue_type']=='source_authority_conflict' for x in step['questions']))
        con=connect(self.run)
        try:
            dispatched=con.execute("""SELECT t.phase,t.task_kind FROM task_dispatches d
                JOIN task_queue t ON t.task_id=d.task_id""").fetchall()
            self.assertTrue(all(phase=='PREPARE' and kind=='document_classification' for phase,kind in dispatched))
            self.assertEqual(con.execute("SELECT count(*) FROM task_queue WHERE task_kind='decision_summary'").fetchone()[0],0)
        finally:con.close()

    def _expired(self):
        self._write_offer('Alpha_fiyat_teklifi.xlsx', 100000, quote_date='01.01.2026', validity='30 gün')
        self._write_offer('Beta_fiyat_teklifi.xlsx', 105000, quote_date='01.01.2026', validity='30 gün')
        prepare(self.src,self.run,'standart')
        step=advance(self.run)
        self.assertEqual(step['status'],'NEEDS_USER_INPUT')
        return step

    def test_question_scope_and_repeat_are_stable(self):
        first=self._expired()
        second=advance(self.run)
        self.assertEqual(first['questions'],second['questions'])
        self.assertEqual(first['open_question_count'],second['open_question_count'])
        self.assertFalse(status(self.run)['deliverable_artifacts'])

    def test_invalid_scope_and_free_text_do_not_verify_fact(self):
        step=self._expired(); q=step['questions'][0]
        con=connect(self.run)
        try: before=con.execute('SELECT fact_id,evidence_status FROM facts ORDER BY fact_id').fetchall()
        finally:con.close()
        with self.assertRaisesRegex(ValueError,'kapsam'):
            record_response(self.run,{'issue_id':q['issue_id'],'scope_sha256':'old-scope',
                'answer_text':'Geçerli olduğunu düşünüyorum.','answer_kind':'clarification'},self.root/'next-run')
        result=record_response(self.run,{'issue_id':q['issue_id'],'scope_sha256':q['scope_sha256'],
            'answer_text':'Yenilenmiş teklif talep edilecektir.','answer_kind':'clarification'},self.root/'next-run')
        self.assertEqual(result['status'],'RECORDED_STILL_WAITING')
        self.assertEqual(advance(self.run)['status'],'NEEDS_USER_INPUT')
        con=connect(self.run)
        try:
            self.assertEqual(before,con.execute('SELECT fact_id,evidence_status FROM facts ORDER BY fact_id').fetchall())
            self.assertEqual(con.execute("SELECT count(*) FROM workflow_events WHERE event_type='user_response_recorded'").fetchone()[0],1)
        finally:con.close()

    def test_financial_rate_requires_new_run_and_tamper_is_rejected(self):
        self._write_offer('Alpha_fiyat_teklifi.xlsx',100000)
        self._write_offer('Beta_fiyat_teklifi.xlsx',105000)
        prepare(self.src,self.run,'standart')
        con=connect(self.run)
        try:
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?,?)",
                ['finance-test','IDARE','critical','payment_comparability','Provide annual effective discount/financing rate for EUR to compare different payment schedules.','[]','[]','open'])
            con.commit()
        finally:con.close()
        q=waiting(self.run)['questions'][0]
        answer={'issue_id':q['issue_id'],'scope_sha256':q['scope_sha256'],'answer_text':'EUR için yıllık efektif iskonto oranı %12.',
                'answer_kind':'financial_rate','currency':'EUR','annual_effective_rate':0.12}
        with self.assertRaisesRegex(ValueError,'para birimine'):
            record_response(self.run,{**answer,'currency':'USD'},self.root/'next-run')
        with self.assertRaisesRegex(ValueError,'kaynak'):
            record_response(self.run,{**answer,'source':str(self.root/'missing')},self.root/'next-run')
        result=record_response(self.run,answer,self.root/'next-run')
        self.assertEqual(result['status'],'RECORDED_NEW_RUN_REQUIRED')
        self.assertEqual(record_response(self.run,answer,self.root/'next-run')['status'],'ALREADY_RECORDED')
        with self.assertRaisesRegex(ValueError,'farklı girdi'):
            record_response(self.run,{**answer,'annual_effective_rate':0.16},self.root/'next-run')
        with self.assertRaisesRegex(ValueError,'farklı girdi'):
            record_response(self.run,answer,self.root/'different-run')
        request=json.loads(Path(result['resume_request']).read_text(encoding='utf-8'))
        self.assertEqual(request['financial_parameters']['discount_rates']['EUR'],0.12)
        self.assertEqual(waiting(self.run)['status'],'NEEDS_USER_INPUT')
        parent=Path(request['user_response_record'])
        self.assertTrue(parent.is_file())
        bad_hash='0'*64
        with self.assertRaisesRegex(ValueError,'hash'):
            prepare(self.src,self.root/'next-run','standart',user_response_record=parent,user_response_sha256=bad_hash)
        self.assertFalse((self.root/'next-run').exists())
        with self.assertRaisesRegex(ValueError,'girdileri'):
            prepare(self.src,self.root/'next-run','standart',financial_params={'discount_rates':{'EUR':0.15}},
                user_response_record=parent,user_response_sha256=request['user_response_sha256'])
        self.assertFalse((self.root/'next-run').exists())
        resumed=prepare(self.src,self.root/'next-run','standart',financial_params=request['financial_parameters'],
            user_response_record=parent,user_response_sha256=request['user_response_sha256'])
        self.assertEqual(resumed['status'],'PREPARED')
        self.assertEqual(get_meta(self.root/'next-run','financial_parameters',{},parse_json=True)['discount_rates']['EUR'],0.12)
        self.assertEqual(get_meta(self.root/'next-run','parent_user_response',{},parse_json=True)['sha256'],request['user_response_sha256'])
        parent.write_text('tampered',encoding='utf-8')
        from validate_run import validate
        result=validate(self.root/'next-run')
        self.assertIn('parent user response record missing or changed',result['blocking_reasons'])

    def test_renewed_source_starts_fresh_analysis_without_old_approval(self):
        step=self._expired()
        q=next(x for x in step['questions'] if x['issue_type']=='offer_validity')
        renewed=self.root/'renewed-source'
        renewed.mkdir()
        original=self.src
        self.src=renewed
        self._write_offer('Alpha_fiyat_teklifi.xlsx',100000,quote_date='03.10.2026',validity='90 gün')
        self._write_offer('Beta_fiyat_teklifi.xlsx',105000,quote_date='03.10.2026',validity='90 gün')
        self.src=original
        recorded=record_response(self.run,{'issue_id':q['issue_id'],'scope_sha256':q['scope_sha256'],
            'answer_text':'Yenilenmiş iki teklif ayrı kaynak klasöründe sunuldu.',
            'answer_kind':'new_source','source':str(renewed)},self.root/'new-run')
        self.assertEqual(recorded['status'],'RECORDED_NEW_RUN_REQUIRED')
        request=json.loads(Path(recorded['resume_request']).read_text(encoding='utf-8'))
        resumed=prepare(renewed,self.root/'new-run','standart',
            user_response_record=Path(request['user_response_record']),
            user_response_sha256=request['user_response_sha256'])
        self.assertEqual(resumed['status'],'PREPARED')
        self.assertEqual(advance(self.root/'new-run')['status'],'NEEDS_LLM')
        self.assertEqual(advance(self.run)['status'],'NEEDS_USER_INPUT')
        self.assertFalse((self.run/'output'/'Teklif_Degerlendirme.xlsx').exists())


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(EarlyUserQuestions(name) for name in sorted(EarlyUserQuestions.__dict__) if name.startswith('test_'))
