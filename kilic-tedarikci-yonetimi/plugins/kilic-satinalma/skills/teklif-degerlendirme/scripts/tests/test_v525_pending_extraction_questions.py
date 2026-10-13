"""Regression cases for comparison questions while semantic extraction is pending."""
import json
import unittest
from unittest.mock import patch

from test_workflow_integration import WorkflowIntegrationTests
from comparison_contract import assess
from db import connect
from task_queue import generate_initial_tasks
from user_question_gate import questions
from workflow import prepare


class PendingExtractionQuestions(WorkflowIntegrationTests):
    def _comparison_gap_with_pending_extraction(self):
        # Real source files and normal prepare path; then model unresolved gaps that
        # deterministic workbook parsing could not settle.
        self._write_offer('Alpha_rev1_teklif.xlsx', 100000)
        self._write_offer('Alpha_rev2_teklif.xlsx', 99000)
        self._write_offer('Beta_teklif.xlsx', 105000)
        # This parser/coverage fixture represents the state before publishing
        # a user ask. Post-ask suspension has its own real dependency tests.
        with patch('workflow.user_input_waiting',return_value=None):
            prepared = prepare(self.src, self.run, 'standart')
        self.assertIn(prepared['status'], {'PREPARED', 'NEEDS_USER_INPUT'})

        con = connect(self.run)
        try:
            prepare_state = con.execute("SELECT status FROM workflow_state WHERE phase='PREPARE'").fetchone()
            self.assertIsNotNone(prepare_state)
            self.assertEqual(prepare_state[0], 'PASS')
            con.execute("UPDATE facts SET evidence_status='missing',value_text=NULL,value_number=NULL,value_date=NULL,extraction_path='deterministic' WHERE requirement_id IS NULL AND field_key IN ('total','currency')")
            con.execute("UPDATE facts SET evidence_status='missing',value_text=NULL,value_number=NULL,value_date=NULL,extraction_path='deterministic' WHERE requirement_id IS NULL AND field_key='vat' AND offer_id=(SELECT min(offer_id) FROM offers WHERE status='active')")
            # Keep the scope check independently failing while semantic fields are open.
            rows = con.execute("SELECT calculation_id,result_json FROM calculations WHERE calculation_type='cost_summary'").fetchall()
            for calculation_id, raw in rows:
                result = json.loads(raw or '{}')
                result.update({'complete': False, 'unknown_scope_items': 1})
                con.execute("UPDATE calculations SET result_json=?,status='incomplete' WHERE calculation_id=?", [json.dumps(result), calculation_id])
            con.commit()
        finally:
            con.close()

        generate_initial_tasks(self.run, 'standart')
        con = connect(self.run)
        try:
            pending = con.execute("SELECT count(*) FROM task_queue WHERE phase='EXTRACT' AND task_kind='offer_semantic_fields' AND status='pending'").fetchone()[0]
            prepare_pending = con.execute("SELECT count(*) FROM task_queue WHERE phase='PREPARE' AND status='pending'").fetchone()[0]
            self.assertEqual(prepare_pending, 0, 'PREPARE sınıflandırması bitmiş olmalı')
            self.assertGreaterEqual(pending, 2)
        finally:
            con.close()
        assess(self.run)

    def test_pending_extraction_suppresses_only_comparison_questions_and_keeps_revision_question(self):
        self._comparison_gap_with_pending_extraction()
        observed = questions(self.run, limit=100)
        kinds = [q['issue_type'] for q in observed['questions']]
        self.assertTrue({'source_authority_conflict', 'revision_relation'} & set(kinds),
                        'gerçek revizyon çatışması görünür kalmalı')
        self.assertNotIn('comparability_contract', kinds, 'çıkarım beklerken karşılaştırma RFI çıkarılmamalı')

    def test_completed_extraction_surfaces_dimension_specific_comparison_question(self):
        self._comparison_gap_with_pending_extraction()
        con = connect(self.run)
        try:
            con.execute("UPDATE facts SET extraction_path='semantic_llm' WHERE evidence_status='missing' AND field_key IN ('total','currency','vat')")
            con.execute("UPDATE task_queue SET status='completed' WHERE phase='EXTRACT' AND task_kind='offer_semantic_fields' AND status='pending'")
            con.commit()
        finally:
            con.close()
        assess(self.run)
        observed = questions(self.run, limit=100)
        comparison = [q for q in observed['questions'] if q['issue_type'] == 'comparability_contract']
        self.assertTrue(comparison, 'çıkarım tamamlanıp açık kalan karşılaştırma boyutu sorulmalı')
        texts = [q['question'].casefold() for q in comparison]
        labels = {
            'total': ('teklif toplamı', 'toplam'),
            'currency': ('para birimi', 'currency'),
            'vat_basis': ('kdv esası', 'vat'),
            'scope_basis': ('teklif kapsamı', 'kapsam', 'scope'),
        }
        missing_labels = [dimension for dimension, names in labels.items() if not any(any(name in text for name in names) for text in texts)]
        self.assertFalse(missing_labels, f'boyut adı görünür değil: {missing_labels}; gelenler: {texts}')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(PendingExtractionQuestions(name) for name in sorted(PendingExtractionQuestions.__dict__) if name.startswith('test_'))


