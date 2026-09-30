"""Native v4 orchestration regression tests; fixtures never launch a model."""
import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ajan_v4 as a
from butce import budget
from kayit_temeli import load, save
from model_secimi import resolve, recommend
from test_v4_veri import fixture


def catalog():
    return {'source':'synthetic tool catalog','observed_at':a.now(),'models':[
        {'id':'gpt-5.6-sol','efforts':['high','medium']}, {'id':'gpt-6-sol','efforts':['high','medium']},
        {'id':'gpt-6.1-sol','efforts':['low','medium','high','xhigh']},
        {'id':'gpt-5.6-terra','efforts':['medium','high']}, {'id':'gpt-6-luna','efforts':['high']}]}


def log(path, identity, model='gpt-6.1-sol', effort='high', parent=None, total=100, seal=None):
    meta={'id':identity,'cwd':str(path.parent)}
    if parent: meta['source']={'subagent':{'thread_spawn':{'parent_thread_id':parent}}}
    rows=[{'type':'session_meta','payload':meta}, {'type':'turn_context','payload':{'model':model,'effort':effort}},
          {'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':total,'output_tokens':20}}}}]
    if seal: rows.append({'type':'response_item','timestamp':a.now(),'payload':{'type':'function_call_output','output':'TEKLIF_RESULT_SEAL:'+json.dumps(seal)}})
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')


class ModelTests(unittest.TestCase):
    def test_all_roles_use_gpt61_high(self):
        roles=resolve(catalog())
        self.assertEqual(len(roles),10)
        for role, expected in roles.items():
            with self.subTest(role=role):
                self.assertEqual(expected,{'family':'sol','model':'gpt-6.1-sol','reasoning_effort':'high'})

    def test_new_version_does_not_replace_requested_model(self):
        c=catalog(); c['models'].append({'id':'gpt-7-sol','efforts':['high']})
        self.assertEqual(resolve(c)['adjudicator']['model'],'gpt-6.1-sol')

    def test_required_model_without_high_does_not_silently_downgrade(self):
        c=catalog(); next(r for r in c['models'] if r['id']=='gpt-6.1-sol')['efforts']=['low','medium','xhigh']
        with self.assertRaises(ValueError): resolve(c)

    def test_missing_required_model_and_stale_catalog_fail(self):
        c=catalog(); c['models']=[r for r in c['models'] if r['id']!='gpt-6.1-sol']
        with self.assertRaises(ValueError): resolve(c)
        c=catalog(); c['observed_at']='2020-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError): resolve(c)

    def test_required_model_alone_suffices(self):
        c=catalog(); c['models']=[r for r in c['models'] if r['id']=='gpt-6.1-sol']
        self.assertEqual(len(resolve(c)),10)

    def test_declared_policy_matches_resolved_agents(self):
        policy=load(Path(a.__file__).resolve().parents[1]/'config/ajan-politikasi.json')
        roles=resolve(catalog())
        self.assertEqual(set(policy['roles']),set(roles))
        for role, expected in roles.items():
            with self.subTest(role=role):
                self.assertEqual({key:policy['roles'][role][key] for key in expected},expected)
        self.assertEqual(policy['main_session']['model'],'gpt-6.1-sol')
        self.assertEqual(policy['main_session']['reasoning_effort'],'high')

    def test_alias_or_duplicate_model_is_rejected(self):
        c=catalog(); next(r for r in c['models'] if r['id']=='gpt-6.1-sol')['id']='gpt-6.1'
        with self.assertRaises(ValueError): resolve(c)
        c=catalog(); c['models'].append(copy.deepcopy(next(r for r in c['models'] if r['id']=='gpt-6.1-sol')))
        with self.assertRaises(ValueError): resolve(c)

    def test_profiles_recommend_not_select(self):
        base={'has_spec':False,'purchase_type':'genel_mal_hizmet','imported':False,'has_tco':False}
        self.assertEqual(recommend(**base),'hizli')
        self.assertEqual(recommend(**{**base,'has_spec':True}),'standart')
        self.assertEqual(recommend(**{**base,'imported':True,'has_tco':True}),'yuksek_guvence')
        self.assertEqual(recommend(**base,max_amount=101,fast_limit=100),'standart')


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.src=self.root/'source'; self.src.mkdir()
        (self.src/'offer.txt').write_text('Synthetic source only',encoding='utf-8')
        self.run=self.root/'run'; self.logs=self.root/'logs'; self.main=self.logs/'main.jsonl'; log(self.main,'main')
        self.context={'has_spec':False,'purchase_type':'genel_mal_hizmet','imported':False,'has_tco':False}
        a.prepare(self.src,self.run,catalog(),self.main,'standart',self.context,log_root=self.logs)

    def complete(self,role,content):
        task=a.plan_task(self.run,role,'Synthetic bounded task')
        path=self.logs/(task['task_id']+'.jsonl')
        log(path,task['task_id'],task['expected']['model'],task['expected']['reasoning_effort'],parent='main')
        a.bind(self.run,task['task_id'],path)
        output=Path(task['output_dir'])/'result.json'; save(output,content)
        seal=a.seal_result(self.run,task['task_id'],output)
        log(path,task['task_id'],task['expected']['model'],task['expected']['reasoning_effort'],parent='main',seal=seal)
        a.register(self.run,task['task_id'],output)
        return output,task,path

    def central(self):
        data,_=fixture(); m=load(self.run/'run.json'); src=m['inventory']['entries'][0]
        for f in data['facts']: f.update(source_id=src['source_id'],source_sha256=src['sha256'])
        data['offers'][0]['source_ids']=[src['source_id']]
        path=self.run/'data.json'; save(path,data); a.record(self.run,'data',path)
        cov=self.run/'coverage.json'; save(cov,{'sources':[{'source_id':src['source_id'],'source_sha256':src['sha256'],'status':'read','document_kind':'offer','offer_ids':['a'],'locations':['all'],'notes':'Synthetic text reviewed'}]})
        a.record(self.run,'coverage',cov)
        return data,src

    def test_wrong_main_model_and_lower_profile_require_change(self):
        log(self.main,'main','gpt-5.6-sol')
        with self.assertRaises(ValueError): a.prepare(self.src,self.root/'other',catalog(),self.main,'standart',self.context,log_root=self.logs)
        log(self.main,'main')
        with self.assertRaises(ValueError): a.prepare(self.src,self.root/'other',catalog(),self.main,'hizli',{**self.context,'has_spec':True},log_root=self.logs)
        result=a.prepare(self.src,self.root/'other',catalog(),self.main,'hizli',{**self.context,'has_spec':True},downgrade_reason='User accepts warning for bounded comparison',log_root=self.logs)
        self.assertEqual(result['profile'],'hizli')

    def test_terra_main_rejected(self):
        log(self.main,'main','gpt-5.6-terra')
        with self.assertRaises(ValueError):
            a.prepare(self.src,self.root/'terra',catalog(),self.main,'standart',self.context,log_root=self.logs)

    def test_main_requires_exact_high_effort(self):
        for effort in ('low','medium','xhigh','max'):
            with self.subTest(effort=effort):
                log(self.main,'main',effort=effort)
                with self.assertRaises(ValueError):
                    a.prepare(self.src,self.root/effort,catalog(),self.main,'standart',self.context,log_root=self.logs)

    def test_source_or_snapshot_change_blocks_start(self):
        (self.src/'offer.txt').write_text('Changed')
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Extract')

    def test_snapshot_change_blocks_start(self):
        (self.run/'skill'/'VERSION').write_text('999')
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Extract')

    def test_no_two_unbound_tasks_or_unauthorized_expert(self):
        with self.assertRaises(ValueError): a.plan_task(self.run,'technical','Expert not in standard')
        a.plan_task(self.run,'extraction','Extract')
        with self.assertRaises(ValueError): a.plan_task(self.run,'blind_review','Read')

    def test_wrong_actual_model_cannot_bind(self):
        t=a.plan_task(self.run,'extraction','Extract'); path=self.logs/'wrong.jsonl'; log(path,'wrong',model='gpt-6-sol',parent='main')
        with self.assertRaises(ValueError): a.bind(self.run,t['task_id'],path)

    def test_wrong_actual_effort_cannot_bind(self):
        t=a.plan_task(self.run,'extraction','Extract'); path=self.logs/'wrong.jsonl'
        log(path,'wrong',effort='medium',parent='main')
        with self.assertRaises(ValueError): a.bind(self.run,t['task_id'],path)

    def test_child_cannot_change_effort_then_restore_high(self):
        t=a.plan_task(self.run,'extraction','Extract'); path=self.logs/'child.jsonl'
        log(path,'child',parent='main'); a.bind(self.run,t['task_id'],path)
        result=Path(t['output_dir'])/'result.json'; save(result,{'ok':True})
        seal=a.seal_result(self.run,t['task_id'],result)
        with path.open('a',encoding='utf-8') as stream:
            for effort in ('medium','high'):
                stream.write(json.dumps({'type':'turn_context','payload':{'model':'gpt-6.1-sol','effort':effort}})+'\n')
            stream.write(json.dumps({'type':'response_item','payload':{'type':'function_call_output','output':'TEKLIF_RESULT_SEAL:'+json.dumps(seal)}})+'\n')
        with self.assertRaises(ValueError): a.register(self.run,t['task_id'],result)

    def test_wrong_parent_cannot_bind(self):
        t=a.plan_task(self.run,'blind_review','Read'); path=self.logs/'wrong.jsonl'; log(path,'wrong',parent='other')
        with self.assertRaises(ValueError): a.bind(self.run,t['task_id'],path)

    def test_seal_is_required_and_unique_new_session(self):
        p,t,session=self.complete('extraction',{'sources':'fixture'})
        m=load(self.run/'run.json'); self.assertEqual(m['tasks'][0]['state'],'COMPLETED')
        second=a.plan_task(self.run,'extraction','Second source')
        with self.assertRaises(ValueError): a.bind(self.run,second['task_id'],session)

    def test_forged_summary_json_without_log_seal_rejected(self):
        t=a.plan_task(self.run,'extraction','Extract'); path=self.logs/'child.jsonl'; log(path,'child',t['expected']['model'],t['expected']['reasoning_effort'],parent='main')
        a.bind(self.run,t['task_id'],path); result=Path(t['output_dir'])/'result.json'; save(result,{'ok':True})
        with self.assertRaises(ValueError): a.register(self.run,t['task_id'],result)

    def test_budget_main_delta_children_cumulative_once(self):
        self.complete('extraction',{})
        log(self.main,'main',total=150)
        m=load(self.run/'run.json'); m['sessions'].append(copy.deepcopy(m['sessions'][-1]))
        result=budget(m)
        self.assertEqual(result['input_tokens'],150)
        self.assertEqual(result['sessions_counted'],2)

    def test_unknown_child_telemetry_is_not_zero(self):
        p,t,session=self.complete('extraction',{})
        rows=session.read_text().splitlines(); session.write_text('\n'.join(r for r in rows if 'token_count' not in r)+'\n')
        self.assertEqual(budget(load(self.run/'run.json'))['status'],'UNVERIFIED')
        with self.assertRaises(ValueError): a.plan_task(self.run,'blind_review','Read')

    def test_descendants_discovered_and_counted(self):
        log(self.logs/'unplanned.jsonl','child',parent='main',total=123)
        log(self.logs/'grandchild.jsonl','grandchild',parent='child',total=234)
        m=load(self.run/'run.json'); result=a.budget_state(m)
        self.assertEqual(result['input_tokens'],357)

    def test_baseline_preexisting_child_not_double_counted(self):
        log(self.logs/'before.jsonl','old-child',parent='main',total=1000)
        newrun=self.root/'after'; a.prepare(self.src,newrun,catalog(),self.main,'standart',self.context,log_root=self.logs)
        m=load(newrun/'run.json'); self.assertEqual(a.budget_state(m)['input_tokens'],0)
        log(self.logs/'before.jsonl','old-child',parent='main',total=1100)
        self.assertEqual(a.budget_state(m)['input_tokens'],100)

    def test_budget_hard_limit_blocks_new_task(self):
        m=load(self.run/'run.json'); m['created_at']=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=2)).isoformat(); save(self.run/'run.json',m)
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Over time limit')

    def test_80_percent_requires_explicit_ack(self):
        log(self.main,'main',total=20_000_101)
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Over warning')
        m=load(self.run/'run.json'); m['budget_warning_ack']={'reason':'User continue'}; save(self.run/'run.json',m)
        a.plan_task(self.run,'extraction','Authorized within same limit')

    def test_adjudicator_needs_qa_and_comparison(self):
        with self.assertRaises(ValueError): a.plan_task(self.run,'adjudicator','Review')

    def test_blind_compare_requires_all_critical_fields(self):
        d,src=self.central(); self.assertEqual(a.qa(self.run)['status'],'PASS')
        p,_,_=self.complete('blind_review',{'facts':[],'reviewed_source_ids':[src['source_id']]})
        a.record(self.run,'blind',p)
        with self.assertRaises(ValueError): a.compare_run(self.run)

    def test_fresh_adjudication_applies_and_old_excel_is_invalidated(self):
        d,src=self.central(); a.qa(self.run)
        independent=copy.deepcopy(d); independent['reviewed_source_ids']=[src['source_id']]; independent['offer_ids']=['a']
        p,_,_=self.complete('blind_review',independent); a.record(self.run,'blind',p); a.compare_run(self.run)
        m=load(self.run/'run.json'); diff=load(self.run/m['artifacts']['diff']['path'])
        verdict={'data_sha256':a.digest(d),'diff_sha256':a.digest(diff),'decisions':[],'summary':'No differences'}
        p,_,_=self.complete('adjudicator',verdict); a.record(self.run,'verdict',p)
        a.apply_run(self.run,self.run/'revised.json')
        m=load(self.run/'run.json'); self.assertIn('applied',m['artifacts']); self.assertNotIn('qa',m['artifacts'])
        self.assertEqual(a.qa(self.run)['status'],'PASS')
        self.assertEqual(a.verify(self.run)['status'],'BLOCKED')  # no Excel/decision yet

    def test_altered_registered_artifact_rejected(self):
        d,_=self.central(); (self.run/'data.json').write_text('{}')
        self.assertEqual(a.verify(self.run)['status'],'BLOCKED')

    def test_main_cannot_switch_to_luna_during_run(self):
        with self.main.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'type':'turn_context','payload':{'model':'gpt-6-luna','effort':'high'}})+'\n')
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Read')

    def test_main_cannot_change_effort_then_restore_high(self):
        with self.main.open('a',encoding='utf-8') as out:
            for effort in ('medium','high'):
                out.write(json.dumps({'type':'turn_context','payload':{'model':'gpt-6.1-sol','effort':effort}})+'\n')
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Read')

    def test_main_current_medium_blocks_start(self):
        with self.main.open('a',encoding='utf-8') as out:
            out.write(json.dumps({'type':'turn_context','payload':{'model':'gpt-6.1-sol','effort':'medium'}})+'\n')
        with self.assertRaises(ValueError): a.plan_task(self.run,'extraction','Read')

    def test_coverage_change_invalidates_prior_qa(self):
        self.central(); a.qa(self.run)
        changed=self.run/'coverage-new.json'; value=load(self.run/'coverage.json'); value['sources'][0]['status']='unreadable'; save(changed,value)
        a.record(self.run,'coverage',changed)
        m=load(self.run/'run.json'); self.assertNotIn('qa',m['artifacts']); self.assertNotIn('applied',m['artifacts'])

    def test_blind_change_invalidates_prior_decision_chain(self):
        m=load(self.run/'run.json')
        for k in ('diff','verdict','applied','decision'): m['artifacts'][k]={'path':'old','sha256':'old'}
        save(self.run/'run.json',m); p=self.run/'new-blind.json'; save(p,{})
        a.record(self.run,'blind',p)
        self.assertFalse(set(('diff','verdict','applied','decision')) & set(load(self.run/'run.json')['artifacts']))

    def test_spec_cannot_be_silently_empty(self):
        self.central(); m=load(self.run/'run.json'); m['context']['has_spec']=True; save(self.run/'run.json',m)
        result=a.qa(self.run)
        self.assertEqual(result['status'],'FAIL'); self.assertIn('Şartname var',str(result['failures']))

    def test_closed_budget_does_not_grow_with_later_chat(self):
        m=load(self.run/'run.json'); m['budget_final']=budget(m); m['closed_at']=a.now()
        log(self.main,'main',total=9000)
        self.assertEqual(budget(m)['input_tokens'],0)

    def test_input_paths_cannot_escape_run(self):
        with self.assertRaises(ValueError): a.record(self.run,'data',self.src/'offer.txt')


if __name__=='__main__': unittest.main()
