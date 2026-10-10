import json
import tempfile
import unittest
from pathlib import Path
from db import connect, init_db
from task_queue import _add_task
from record_results import record_task_result, _validate_fact_contract
from llm_result_validate import ResultValidationError
from field_extract import CRITICAL_FIELDS


class FactContractTests(unittest.TestCase):
    def check(self, facts, fields=None, kind='offer_semantic_fields'):
        _validate_fact_contract({'task_kind': kind, 'offer_id': 'offer'},
                                {'fields': fields or []}, {'facts': facts})

    def test_distinct_model_ids_cannot_hide_duplicate_canonical_field(self):
        with self.assertRaisesRegex(ResultValidationError, 'Duplicate canonical'):
            self.check([{'fact_id': 'line1', 'field_key': 'quantity'},
                        {'fact_id': 'line2', 'field_key': 'quantity'}], ['quantity'])

    def test_visual_alias_is_rejected(self):
        with self.assertRaisesRegex(ResultValidationError, 'Unknown offer field_key'):
            self.check([{'field_key': 'total_price'}], kind='visual_source_review')

    def test_visual_requires_all_canonical_fields(self):
        with self.assertRaisesRegex(ResultValidationError, 'coverage mismatch'):
            self.check([{'field_key': 'total'}], kind='visual_source_review')
        self.check([{'field_key': f} for f in CRITICAL_FIELDS], kind='visual_source_review')

    def test_semantic_requires_exact_requested_coverage(self):
        for facts in [[{'field_key': 'quantity'}],
                      [{'field_key': 'quantity'}, {'field_key': 'total'}, {'field_key': 'delivery'}]]:
            with self.assertRaisesRegex(ResultValidationError, 'coverage mismatch'):
                self.check(facts, ['quantity', 'total'])

    def test_distinct_requirements_share_field_but_not_identity(self):
        facts = [{'field_key': 'requirement_status', 'requirement_id': r} for r in ['r1', 'r2']]
        self.check(facts, kind='requirement_assessment')
        with self.assertRaisesRegex(ResultValidationError, 'Duplicate canonical'):
            self.check(facts + [dict(facts[0], fact_id='new')], kind='requirement_assessment')

    def test_multiline_details_and_uncertainty_are_not_reduced_to_last_item(self):
        facts = [{'field_key': 'quantity', 'evidence_status': 'requires_confirmation',
                  'normalized': {'items': [{'quantity': 23}, {'quantity': 110}]}}]
        before = json.loads(json.dumps(facts))
        self.check(facts, ['quantity'])
        self.assertEqual(facts, before)

    def test_rejection_precedes_all_canonical_and_receipt_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); init_db(run)
            con = connect(run)
            tid = _add_task(con, 'EXTRACT', 'semantic_extraction', 'offer_semantic_fields',
                            {'fields': ['quantity']}, offer_id='offer')
            con.commit(); con.close()
            payload = {'evidence': [], 'facts': [{'fact_id': name, 'field_key': 'quantity',
                                  'evidence_status': 'missing'} for name in ['line1', 'line2']]}
            with self.assertRaisesRegex(ResultValidationError, 'Duplicate canonical'):
                record_task_result(run, tid, payload, model_name='unit-test-fixture',
                                   reasoning_effort='medium', input_tokens=0, output_tokens=0)
            con = connect(run)
            try:
                for table in ['facts', 'evidence', 'model_receipts']:
                    self.assertEqual(con.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
                status, attempts = con.execute('SELECT status,attempts FROM task_queue WHERE task_id=?', [tid]).fetchone()
                self.assertNotEqual(status, 'completed'); self.assertEqual(attempts, 1)
            finally:
                con.close()
