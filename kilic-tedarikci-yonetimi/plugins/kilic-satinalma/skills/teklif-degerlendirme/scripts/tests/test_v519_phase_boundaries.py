"""Stage-order and source-input atomicity regressions; no model calls."""
import json
import unittest
from unittest.mock import patch
from test_v518_transition_contracts import TransitionContracts
from workflow import _needs_llm_response
from task_queue import _add_task, pending_tasks
from source_relations import declare


class PhaseBoundaries(TransitionContracts):
    # Only new tests are selected by the targeted runner; inherited tests stay intact.
    def test_last_classification_does_not_dispatch_two_visual_tasks(self):
        classify=_add_task(self.con,'PREPARE','semantic_extraction','document_classification',{},priority=99)
        for n in range(2):
            _add_task(self.con,'EXTRACT','visual_exception','visual_source_review',{'n':n},priority=1)
        self.con.commit()
        policy={'context_packet':{},'max_concurrent_llm_tasks':3}
        with patch('workflow._task_contexts',side_effect=lambda r,p,t:t):
            result=_needs_llm_response(self.run,policy,pending_tasks(self.run))
        self.assertEqual([t['task_id'] for t in result['tasks']],[classify])
        self.assertEqual(result['pending_total'],3)

    def test_future_phase_retry_limit_does_not_block_last_classification(self):
        classify=_add_task(self.con,'PREPARE','semantic_extraction','document_classification',{},priority=99)
        future=_add_task(self.con,'EXTRACT','visual_exception','visual_source_review',{},priority=1)
        self.con.execute('UPDATE task_queue SET attempts=2 WHERE task_id=?',[future]);self.con.commit()
        with patch('workflow._task_contexts',side_effect=lambda r,p,t:t):
            result=_needs_llm_response(self.run,{'context_packet':{}},pending_tasks(self.run))
        self.assertEqual(result['status'],'NEEDS_LLM')
        self.assertEqual([t['task_id'] for t in result['tasks']],[classify])

    def test_relationship_after_dispatch_rejected_without_canonical_mutation(self):
        self.confirmation_sources()
        self.con.execute('DELETE FROM source_relations')
        task=_add_task(self.con,'EXTRACT','visual_exception','visual_source_review',{},document_id='image')
        self.con.execute("INSERT INTO task_dispatches(task_id,packet_sha256,schema_sha256,execution_sha256,context_path,created_at) VALUES (?,'packet','schema','execution','tasks/context.json','now')",[task]);self.con.commit()
        before={table:self.con.execute('SELECT * FROM '+table).fetchall() for table in ['documents','offers','source_relations','task_dispatches']}
        with self.assertRaisesRegex(ValueError,'dispatch|fresh run'):
            declare(self.run,'sheet','image','independent_alternative',{'authority':'test author','reason':'late mutation'})
        after={table:self.con.execute('SELECT * FROM '+table).fetchall() for table in before}
        self.assertEqual(before,after)

    def test_relationship_before_classification_finishes_rejected(self):
        self.confirmation_sources()
        self.con.execute('DELETE FROM source_relations')
        _add_task(self.con,'PREPARE','semantic_extraction','document_classification',{},document_id='image');self.con.commit()
        with self.assertRaisesRegex(ValueError,'classification|PREPARE'):
            declare(self.run,'sheet','image','independent_alternative',{'authority':'test author','reason':'too early'})
        self.assertEqual(self.con.execute('SELECT count(*) FROM source_relations').fetchone()[0],0)

    def test_finished_classification_opens_source_input_then_visual_dispatch(self):
        self.confirmation_sources()
        self.con.execute('DELETE FROM source_relations')
        classify=_add_task(self.con,'PREPARE','semantic_extraction','document_classification',{},document_id='image',priority=99)
        visual=_add_task(self.con,'EXTRACT','visual_exception','visual_source_review',{'document_id':'image'},document_id='image',offer_id='o',priority=1)
        self.con.commit()
        policy={'context_packet':{'max_units':12,'max_chars':12000},'roles':{}}
        first=_needs_llm_response(self.run,policy,pending_tasks(self.run))
        self.assertEqual([t['task_id'] for t in first['tasks']],[classify])
        self.assertEqual(self.con.execute('SELECT count(*) FROM task_dispatches').fetchone()[0],1)
        self.con.execute("UPDATE task_queue SET status='completed' WHERE task_id=?",[classify]);self.con.commit()
        declare(self.run,'sheet','image','independent_alternative',{'authority':'test author','reason':'valid input window'})
        following=_needs_llm_response(self.run,policy,pending_tasks(self.run))
        self.assertEqual([t['task_id'] for t in following['tasks']],[visual])
        original=(self.run/'tasks'/visual/'context.json').read_bytes()
        self.assertEqual(_needs_llm_response(self.run,policy,pending_tasks(self.run))['tasks'],following['tasks'])
        self.assertEqual((self.run/'tasks'/visual/'context.json').read_bytes(),original)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(PhaseBoundaries(name) for name in sorted(PhaseBoundaries.__dict__) if name.startswith('test_'))
