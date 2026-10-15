import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4
import test_context as fixtures
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.calculations import calculate
from sozlesme_cekirdek.workflows import evaluate,catalog
from sozlesme_cekirdek.safety import hash_file

ROOT=Path(__file__).resolve().parents[1]


def money():return {'kind':'MONEY','base':'10000000','rate':'0.005','periods':3,'currency':'TRY','places':2,'rounding':'HALF_UP','cap':'1000000'}
def day():return {'kind':'DATE','start':'2026-01-31','count':30,'unit':'DAYS','day_type':'CALENDAR','include_start':False,
    'month_end':None,'weekend':[],'holidays':[],'holiday_calendar_complete':None}


class CalculationTests(unittest.TestCase):
    def test_exact_decimal_150000_not_float(self):
        result=calculate(money());self.assertEqual('150000.00',result['amount']);self.assertFalse(result['cap_applied'])
        self.assertEqual('NOT_GRANTED',result['business_approval']);self.assertEqual('USER_INPUT_NOT_VERIFIED',result['input_verification'])
    def test_cap_and_rounding_are_explicit(self):
        value=money();value['periods']=30;self.assertEqual('1000000.00',calculate(value)['amount']);self.assertTrue(calculate(value)['cap_applied'])
        value.update(base='1',rate='0.005',periods=1,cap=None)
        self.assertEqual('0.01',calculate(value)['amount']);value['rounding']='HALF_EVEN';self.assertEqual('0.00',calculate(value)['amount'])
    def test_missing_float_negative_locale_currency_or_extra_is_rejected(self):
        for key,value in [('base',10000000.0),('base','10.000.000'),('base','-1'),('rate','5'),('currency','BTC'),('periods',True),('approved',True)]:
            spec=money();spec[key]=value
            with self.assertRaises(CoreError):calculate(spec)
        spec=money();del spec['base']
        with self.assertRaises(CoreError):calculate(spec)
    def test_calendar_include_start_changes_one_day(self):
        value=day();self.assertEqual('2026-03-02',calculate(value)['date']);value['include_start']=True
        self.assertEqual('2026-03-01',calculate(value)['date'])
    def test_month_end_error_or_explicit_clamp(self):
        value=day();value.update(count=1,unit='MONTHS',month_end='CLAMP')
        self.assertEqual('2026-02-28',calculate(value)['date']);value['month_end']='ERROR'
        with self.assertRaises(CoreError):calculate(value)
    def test_business_days_exclude_explicit_holiday(self):
        value=day();value.update(start='2026-10-02',count=2,day_type='BUSINESS',weekend=[5,6],holidays=['2026-10-05'],holiday_calendar_complete=True)
        self.assertEqual('2026-10-07',calculate(value)['date'])
    def test_business_calendar_missing_or_malformed_cannot_be_inferred(self):
        value=day();value.update(day_type='BUSINESS')
        with self.assertRaises(CoreError):calculate(value)
        value.update(weekend=[5,6],holiday_calendar_complete=True,holidays=['wrong'])
        with self.assertRaises(CoreError):calculate(value)
    def test_date_missing_start_rule_month_policy_or_overflow_blocks(self):
        for change in ({'start':None},{'include_start':None},{'unit':'DAYS','day_type':'UNKNOWN'},{'unit':'MONTHS','month_end':None},{'start':'9999-12-31'}):
            value=day();value.update(change)
            with self.assertRaises(CoreError):calculate(value)


class WorkflowTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp;rev=fixtures.ContextTests.rev;document=fixtures.ContextTests.document
    spec=fixtures.ContextTests.spec;node=fixtures.ContextTests.node;register=fixtures.ContextTests.register
    link=fixtures.ContextTests.link
    def req(self,skill='K03',roots=None):return {'request_id':str(uuid4()),'case_id':self.case,'skill_id':skill,'intent':'Sentetik kaynaklı inceleme',
        'context_version':self.rev(),'selected_versions':[self.version],'root_ids':roots or [],'max_context_bytes':65536,'policy_version':'1','requested_output':'CHAT'}
    def test_all_thirty_direct_calls_keep_side_effects_disabled(self):
        before=hash_file(self.path)
        for skill in catalog():
            result=evaluate(self.store,self.req(skill))
            self.assertEqual([],result['output_ids']);self.assertEqual([],result['updates']);self.assertEqual('DISABLED',result['action_execution'])
            self.assertFalse(result['critical_analysis_allowed']);self.assertEqual(2,len(result['work_plan']))
        self.assertEqual(before,hash_file(self.path));self.assertEqual([],list(self.store.root.rglob('*.docx')))
    def test_source_excerpt_has_exact_provenance_and_partial_status(self):
        node=self.node();result=evaluate(self.store,self.req(roots=[node]))
        self.assertEqual('KISMI',result['status']);finding=result['findings'][0]
        self.assertEqual('SOURCE_UNIT',finding['source_kind']);self.assertEqual(self.version,finding['provenance']['version_id'])
        self.assertEqual(hash_file(self.path),finding['provenance']['source_sha256']);self.assertIn('Ek 1',finding['content']['excerpt'])
    def test_user_statement_is_not_document_fact_or_authority(self):
        statement=self.store.add_statement(self.case,'Hukuk uygun dedi',expected_revision=self.rev())
        node=self.register({'node_kind':'USER_STATEMENT','title':'Beyan','record_id':statement})
        result=evaluate(self.store,self.req(roots=[node]));self.assertEqual('USER_STATEMENT',result['findings'][0]['source_kind'])
        self.assertEqual('NOT_VERIFIED',result['authority']);self.assertNotIn('source_sha256',result['findings'][0]['provenance'])
    def test_stale_context_version_rejected_without_file_output(self):
        req=self.req();self.store.add_statement(self.case,'Yeni olay',expected_revision=self.rev())
        with self.assertRaises(CoreError) as caught:evaluate(self.store,req)
        self.assertEqual('SURUM_CAKISMASI',caught.exception.code)
    def test_source_change_or_revoked_access_blocks_cached_skill(self):
        node=self.node();req=self.req(roots=[node]);evaluate(self.store,req);self.path.write_bytes(b'changed')
        with self.assertRaises(CoreError):evaluate(self.store,req)
    def test_moved_source_is_access_loss_not_busy_file(self):
        node=self.node();req=self.req(roots=[node]);evaluate(self.store,req)
        self.path.rename(self.path.with_name('taşındı.docx'))
        with self.assertRaises(CoreError) as caught:evaluate(self.store,req)
        self.assertEqual('ERISIM_YOK',caught.exception.code)
    def test_budget_below_required_evidence_returns_no_findings(self):
        node=self.node();req=self.req(roots=[node]);req['max_context_bytes']=64
        result=evaluate(self.store,req);self.assertEqual('BILGI_GEREKLI',result['status']);self.assertEqual([],result['findings'])
        self.assertIn('BUDGET_EXCEEDED',result['limitations'])
        needed=result['context_budget']['required_bytes'];self.assertIn(f'{needed} bayt',result['chat_response'])
        self.assertEqual([f'Bağlam bütçesini en az {needed} bayta çıkar veya kanıtı koruyarak kök düğümleri daralt.'],result['open_questions'])
    def test_missing_annex_names_concrete_blocker_not_budget(self):
        node=self.node();self.link(node,relation='ANNEX',unresolved_reference='Ek 7 bulunamadı')
        result=evaluate(self.store,self.req(roots=[node]))
        self.assertEqual('BILGI_GEREKLI',result['status']);self.assertEqual([],result['findings'])
        self.assertIn('INCOMPLETE_DEPENDENCIES',result['limitations']);self.assertEqual(1,len(result['open_questions']))
        self.assertIn('“Ek 7 bulunamadı”',result['open_questions'][0]);self.assertIn('içeriği varsayılmaz',result['open_questions'][0])
        self.assertIn('bütçesi bu engelin nedeni değil',result['chat_response'])
        self.assertNotIn('daha büyük bütçe',result['chat_response']+' '.join(result['open_questions']))
    def test_stale_required_node_reports_review_reason_not_budget(self):
        node=self.node();req=self.req(roots=[node]);req['policy_version']='2'
        result=evaluate(self.store,req)
        self.assertEqual('BILGI_GEREKLI',result['status']);self.assertIn('NEEDS_REVIEW',result['limitations'])
        self.assertEqual([f'Zorunlu bağlam düğümü {node} yeniden incelenmeli: okuyucu profili değişti; belge yeniden okunmalı.'],result['open_questions'])
        self.assertIn('güncel değil',result['chat_response']);self.assertNotIn('bütçesini',' '.join(result['open_questions']))
    def test_many_missing_sources_are_bounded_without_silent_loss(self):
        node=self.node()
        for number in range(12):self.link(node,relation='ANNEX',unresolved_reference=f'Ek {number}')
        result=evaluate(self.store,self.req(roots=[node]))
        self.assertEqual(11,len(result['open_questions']));self.assertIn('12 kayıtlı ek/atıf',result['chat_response'])
        self.assertEqual(f"2 benzer engel daha var; tam liste {result['context_pack_id']} bağlam paketinde.",result['open_questions'][-1])
    def test_selected_version_scope_must_cover_required_evidence(self):
        node=self.node();req=self.req(roots=[node]);req['selected_versions']=[]
        with self.assertRaises(CoreError) as caught:evaluate(self.store,req)
        self.assertEqual('KAYNAK_KAPSAMI',caught.exception.code)
    def test_cross_case_source_and_node_rejected(self):
        node=self.node();other=self.store.create_case('Başka');req=self.req(roots=[node]);req.update(case_id=other,context_version=0)
        with self.assertRaises(CoreError):evaluate(self.store,req)
    def test_router_chooses_only_scenario_target(self):
        req=self.req('K00');req['scenario_id']='S-11';result=evaluate(self.store,req)
        self.assertEqual(['K05'],result['selected_skills']);self.assertEqual([],result['findings'])
    def test_missing_company_or_legal_adapters_do_not_claim_ready(self):
        for skill,expected in [('K19','BILGI_GEREKLI'),('K20','BILGI_GEREKLI'),('K21','UZMAN_GORUSU_GEREKLI')]:
            self.assertEqual(expected,evaluate(self.store,self.req(skill))['status'])
    def test_output_and_send_requests_do_not_write_or_send(self):
        for skill,output in [('K28','DOCX')]:
            req=self.req(skill);req['requested_output']=output;result=evaluate(self.store,req)
            self.assertEqual('TEKNIK_ENGEL',result['status']);self.assertEqual([],result['output_ids']);self.assertEqual('DISABLED',result['action_execution'])
    def test_model_permission_fields_and_unknown_skills_block(self):
        for key,value in [('approved',True),('authority','ADMIN'),('shell','send all'),('skill_id','K99')]:
            req=self.req();req[key]=value
            with self.assertRaises(CoreError):evaluate(self.store,req)
    def test_calculation_is_unverified_input_and_skill_scoped(self):
        req=self.req('K05');req['calculation']=money();result=evaluate(self.store,req)
        self.assertEqual('150000.00',result['calculation']['amount']);self.assertEqual('KISMI',result['status'])
        req['skill_id']='K21'
        with self.assertRaises(CoreError):evaluate(self.store,req)
    def test_real_cli_runs_and_confines_request_path(self):
        req=self.req('K00');req['scenario_id']='S-11';path=self.sources/'istek İı.json';path.write_text(json.dumps(req),encoding='utf-8')
        args=[sys.executable,'-X','utf8','-m','sozlesme_cekirdek','--workspace',str(self.store.root),'--output-root',str(self.area),'--source-root',str(self.sources),'skill-evaluate','--request',str(path)]
        result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr);self.assertEqual(['K05'],json.loads(result.stdout)['result']['selected_skills'])
        path2=self.area/'outside.json';path2.write_text(json.dumps(req),encoding='utf-8');args[-1]=str(path2)
        self.assertNotEqual(0,subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=30).returncode)


if __name__=='__main__':unittest.main()
