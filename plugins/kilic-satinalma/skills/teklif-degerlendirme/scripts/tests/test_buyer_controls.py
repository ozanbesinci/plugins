from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from buyer_controls import payment_basis, resolve_answered_questions, warranty_basis
from common import json_text
from db import connect, init_db


class BuyerControlTests(unittest.TestCase):
    def _case(self, sqlite: bool, issue_type: str, fact_ids: list[str], evidence_ids: list[str],
              declarations: list[dict], result: dict, *, severity='high', extra_facts=None, scopes=None, extra_offer=False, input_error=False, issue_owner='IDARE'):
        prior = os.environ.get('TEKLIF_TEST_SQLITE')
        if sqlite:
            os.environ['TEKLIF_TEST_SQLITE'] = '1'
        else:
            os.environ.pop('TEKLIF_TEST_SQLITE', None)
        try:
            with tempfile.TemporaryDirectory(prefix='buyer-controls-') as tmp:
                run = Path(tmp) / 'run'
                init_db(run, SCRIPTS.parent)
                con = connect(run)
                try:
                    con.execute("INSERT INTO suppliers(supplier_id,display_name) VALUES ('S','Supplier')")
                    con.execute("INSERT INTO offers(offer_id,supplier_id,status) VALUES ('O','S','active')")
                    if extra_offer:
                        con.execute("INSERT INTO suppliers(supplier_id,display_name) VALUES ('SB','Other Supplier')")
                        con.execute("INSERT INTO offers(offer_id,supplier_id,status) VALUES ('B','SB','active')")
                        con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,evidence_status,extraction_path,normalized_json) VALUES ('B/field/currency','B','SB','currency','missing','test','{}')")
                    for fact in extra_facts or []:
                        con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,evidence_status,evidence_id,extraction_path,normalized_json) VALUES (?,?,?,?,?,?,'test',?)",
                                    [fact['id'], fact.get('offer_id', 'O'), fact.get('supplier_id', 'S'), fact['field'], fact.get('status', 'requires_confirmation'), fact.get('evidence_id'), json_text(fact.get('normalized', {}))])
                    for scope in scopes or []:
                        con.execute("INSERT INTO scope_items(scope_id,offer_id,classification,cost_role,description,status,evidence_ids_json) VALUES (?,'O','incremental_adjustment','incremental_adjustment','scope','unknown',?)",
                                    [scope['id'], json_text(scope['evidence'])])
                    con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status) VALUES ('issue',?,?,?,?,?,?,'open')",
                                [issue_owner, severity, issue_type, 'Scoped question', json_text(fact_ids), json_text(evidence_ids)])
                    con.execute("INSERT INTO calculations(calculation_id,offer_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status,updated_at) VALUES ('cost','O','cost_summary','{}',?,'test','hash','complete','now')", [json_text(result)])
                    con.commit()
                finally:
                    con.close()
                question = {'issue_id': 'issue', 'scope_sha256': 'scopehash', 'issue_type': issue_type,
                            'fact_ids': fact_ids, 'evidence_ids': evidence_ids, 'severity': severity}
                def checked_inputs(con, offer, kind):
                    if input_error:
                        raise ValueError('source hash changed')
                    return [d for d in declarations if d['kind'] == kind and d['offer_id'] == offer]
                with patch('user_question_gate.questions', return_value={'questions': [question]} ) as questions, \
                     patch('buyer_controls.inputs_for', side_effect=checked_inputs):
                    closed = resolve_answered_questions(run)['resolved']
                con = connect(run)
                try:
                    status = con.execute("SELECT status FROM open_issues WHERE issue_id='issue'").fetchone()[0]
                    count = con.execute("SELECT count(*) FROM workflow_events WHERE event_type LIKE 'buyer_response_applied%'").fetchone()[0]
                    facts = con.execute('SELECT fact_id,evidence_status,normalized_json FROM facts ORDER BY fact_id').fetchall()
                finally:
                    con.close()
                self.assertEqual(questions.call_args.kwargs['include_medium'], True)
                return closed, status, count, facts
        finally:
            if prior is None:
                os.environ.pop('TEKLIF_TEST_SQLITE', None)
            else:
                os.environ['TEKLIF_TEST_SQLITE'] = prior

    @staticmethod
    def _entry(kind, **fields):
        return {'kind': kind, 'offer_id': 'O', 'issue_id': 'issue', 'scope_sha256': 'scopehash', **fields}

    def test_currency_closes_only_its_explicit_critical_field(self):
        entry = self._entry('currency', value='TRY')
        result = {'known': True, 'currency': 'TRY', 'currency_basis': 'buyer_declaration',
                  'buyer_inputs': {'currency': [entry]}}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                closed, status, count, _ = self._case(sqlite, 'critical_field', ['O/field/currency'], [], [entry], result)
                self.assertEqual((closed, status, count), (['issue'], 'resolved', 1))
                closed, status, count, _ = self._case(sqlite, 'critical_field', ['O/field/payment'], [], [entry], result)
                self.assertEqual((closed, status, count), ([], 'open', 0))
                closed, status, count, _ = self._case(sqlite, 'comparability_contract', ['O/field/currency'], [], [entry], result)
                self.assertEqual((closed, status, count), ([], 'open', 0))

    def test_medium_scope_cost_closes_its_target_without_other_scope_completion(self):
        entry = self._entry('scope_cost', scope_id='scope-1', amount=0, currency='TRY')
        result = {'known': True, 'complete': False, 'buyer_inputs': {'scope_cost': [entry]},
                  'steps': [{'stage': 'buyer_scope_cost', 'scope_id': 'scope-1', 'amount': '0', 'currency': 'TRY'}]}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                closed, status, _, _ = self._case(sqlite, 'unpriced_employer_responsibility', [], ['ev1'], [entry], result,
                    severity='medium', scopes=[{'id': 'scope-1', 'evidence': ['ev1']}, {'id': 'scope-2', 'evidence': ['ev2']}])
                self.assertEqual((closed, status), (['issue'], 'resolved'))
                closed, status, _, _ = self._case(sqlite, 'unpriced_employer_responsibility', [], ['ev1', 'ev2'], [entry], result,
                    severity='medium', scopes=[{'id': 'scope-1', 'evidence': ['ev1']}, {'id': 'scope-2', 'evidence': ['ev2']}])
                self.assertEqual((closed, status), ([], 'open'))

    def test_quantity_requires_exact_question_evidence_item_coverage(self):
        first = self._entry('reference_quantity', quantity_item_id='q26', quantity=40, unit='MT')
        second = self._entry('reference_quantity', quantity_item_id='q27', quantity=40, unit='MT')
        result = {'known': True, 'buyer_inputs': {'reference_quantity': [first, second]},
                  'buyer_quantity_rows': [{'quantity_item_id': 'q26', 'reference_quantity': '40', 'unit': 'MT'},
                                          {'quantity_item_id': 'q27', 'reference_quantity': '40', 'unit': 'MT'}]}
        normalized = {'items': [{'item_id': 'q26', 'evidence_status': 'verified', 'evidence_refs': ['ev26']},
                                {'item_id': 'q27', 'evidence_status': 'verified', 'evidence_refs': ['ev27']}]}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                args = dict(extra_facts=[{'id': 'O/field/quantity', 'field': 'quantity', 'normalized': normalized}])
                closed, status, _, facts = self._case(sqlite, 'quantity_scope_confirmation', ['O/field/quantity'], ['ev26','ev27'], [first, second], result, **args)
                self.assertEqual((closed, status), (['issue'], 'resolved'))
                self.assertEqual(facts[0][1], 'requires_confirmation')
                closed, status, _, _ = self._case(sqlite, 'quantity_scope_confirmation', ['O/field/quantity'], ['ev26','ev27'], [first], result, **args)
                self.assertEqual((closed, status), ([], 'open'))
                closed, status, _, _ = self._case(sqlite, 'scope_comparability', ['O/field/quantity','O/field/scope_signature'], ['ev26','ev27'], [first, second], result,
                    extra_facts=[*args['extra_facts'], {'id': 'O/field/scope_signature', 'field': 'scope_signature'}])
                self.assertEqual((closed, status), ([], 'open'))

    def test_explicit_scope_question_does_not_expand_to_general_fact_scope(self):
        entry = self._entry('scope_cost', scope_id='watering', amount=0, currency='TRY')
        result = {'known': True, 'complete': False, 'buyer_inputs': {'scope_cost': [entry]},
                  'steps': [{'stage': 'buyer_scope_cost', 'scope_id': 'watering', 'amount': '0', 'currency': 'TRY'}]}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                closed, status, _, facts = self._case(sqlite, 'unpriced_employer_responsibility',
                    ['O/field/scope_signature'], ['ev-water'], [entry], result, severity='medium',
                    extra_facts=[{'id':'O/field/scope_signature','field':'scope_signature','evidence_id':'ev-work'}],
                    scopes=[{'id':'watering','evidence':['ev-water']},{'id':'included-work','evidence':['ev-work']}])
                self.assertEqual((closed,status), (['issue'],'resolved'))
                self.assertEqual(facts[0][1], 'requires_confirmation')


    def test_same_hashed_currency_answer_closes_only_exact_secondary_question(self):
        entry = {**self._entry('currency', value='EUR'), 'issue_id': 'global-currency'}
        result = {'known': True, 'currency': 'EUR', 'currency_basis': 'buyer_declaration',
                  'buyer_inputs': {'currency': [entry]}}
        fact = {'id': 'O/field/currency', 'field': 'currency'}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                closed, status, count, facts = self._case(sqlite, 'missing_currency', ['O/field/currency'], [],
                    [entry], result, extra_facts=[fact], issue_owner='FIRMA:Alpha')
                self.assertEqual((closed, status, count), (['issue'], 'resolved', 1))
                self.assertEqual(facts[0][1], 'requires_confirmation')
                closed, status, count, _ = self._case(sqlite, 'critical_field', ['O/field/currency'], [],
                    [entry], result, extra_facts=[fact])
                self.assertEqual((closed, status, count), (['issue'], 'resolved', 1))
                closed, status, count, _ = self._case(sqlite, 'comparability_contract', ['O/field/currency'], [],
                    [entry], result, extra_facts=[fact])
                self.assertEqual((closed, status, count), ([], 'open', 0))

    def test_secondary_currency_question_rejects_other_offer_and_mixed_fields(self):
        entry = {**self._entry('currency', value='EUR'), 'issue_id': 'global-currency'}
        result = {'known': True, 'currency': 'EUR', 'currency_basis': 'buyer_declaration',
                  'buyer_inputs': {'currency': [entry]}}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                closed, status, count, _ = self._case(sqlite, 'missing_currency', ['B/field/currency'], [],
                    [entry], result, extra_offer=True)
                self.assertEqual((closed, status, count), ([], 'open', 0))
                closed, status, count, _ = self._case(sqlite, 'critical_field',
                    ['O/field/currency', 'O/field/payment'], [], [entry], result,
                    extra_facts=[{'id': 'O/field/currency', 'field': 'currency'},
                                 {'id': 'O/field/payment', 'field': 'payment'}])
                self.assertEqual((closed, status, count), ([], 'open', 0))
                with self.assertRaisesRegex(ValueError, 'source hash changed'):
                    self._case(sqlite, 'missing_currency', ['O/field/currency'], [],
                        [entry], result, extra_facts=[{'id': 'O/field/currency', 'field': 'currency'}], input_error=True)

    def test_currency_missing_global_owner_closes_only_exact_applied_offer(self):
        direct = self._entry('currency', value='EUR')
        alias = {**direct, 'issue_id': 'original-currency'}
        fact = {'id': 'O/field/currency', 'field': 'currency'}
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                for entry in (direct, alias):
                    result = {'known': True, 'currency': 'EUR', 'currency_basis': 'buyer_declaration',
                              'buyer_inputs': {'currency': [entry]}}
                    self.assertEqual(self._case(sqlite, 'currency_missing', [fact['id']], [],
                        [entry], result, extra_facts=[fact], issue_owner='TUM_FIRMALAR')[:3],
                        (['issue'], 'resolved', 1))
                    self.assertEqual(self._case(sqlite, 'currency_missing', ['B/field/currency'], [],
                        [entry], result, extra_facts=[fact], extra_offer=True,
                        issue_owner='TUM_FIRMALAR')[:3], ([], 'open', 0))
                    self.assertEqual(self._case(sqlite, 'currency_missing',
                        [fact['id'], 'O/field/payment'], [], [entry], result,
                        extra_facts=[fact, {'id': 'O/field/payment', 'field': 'payment'}],
                        issue_owner='TUM_FIRMALAR')[:3], ([], 'open', 0))
                    self.assertEqual(self._case(sqlite, 'currency_missing', [fact['id']], [],
                        [entry], {**result, 'currency': 'USD'}, extra_facts=[fact],
                        issue_owner='TUM_FIRMALAR')[:3], ([], 'open', 0))

    def test_currency_with_verified_source_total_closes_without_verifying_currency(self):
        entry = {**self._entry('currency', value='TRY'), 'issue_id': 'global-currency'}
        direct = self._entry('currency', value='TRY')
        result = {'known': True, 'currency': 'TRY', 'currency_basis': 'buyer_declaration',
                  'buyer_inputs': {'currency': [entry]}}
        facts = [{'id': 'O/field/currency', 'field': 'currency'},
                 {'id': 'O/field/total', 'field': 'total', 'status': 'verified', 'evidence_id': 'total-ev'}]
        for sqlite in (False, True):
            with self.subTest(sqlite=sqlite):
                closed, status, count, after = self._case(sqlite, 'missing_currency',
                    ['O/field/currency', 'O/field/total'], ['total-ev'], [entry], result, extra_facts=facts)
                self.assertEqual((closed, status, count), (['issue'], 'resolved', 1))
                self.assertEqual(dict((row[0], row[1]) for row in after)['O/field/currency'], 'requires_confirmation')
                direct_result = {**result, 'buyer_inputs': {'currency': [direct]}}
                self.assertEqual(self._case(sqlite, 'missing_currency',
                    ['O/field/currency', 'O/field/total'], ['total-ev'], [direct], direct_result,
                    extra_facts=facts)[:3], (['issue'], 'resolved', 1))
                for changed in ({'status': 'requires_confirmation'}, {'evidence_id': 'other-ev'}):
                    altered = [facts[0], {**facts[1], **changed}]
                    closed, status, count, _ = self._case(sqlite, 'missing_currency',
                        ['O/field/currency', 'O/field/total'], ['total-ev'], [entry], result,
                        extra_facts=altered)
                    self.assertEqual((closed, status, count), ([], 'open', 0))
                closed, status, count, _ = self._case(sqlite, 'critical_field',
                    ['O/field/currency', 'O/field/total'], ['total-ev'], [entry], result,
                    extra_facts=facts)
                self.assertEqual((closed, status, count), ([], 'open', 0))

    def test_commercial_questions_require_exact_field_and_applied_value(self):
        payment = self._entry('payment_terms', milestones=[{'trigger': 'work_start', 'percent': 50},
                                                         {'trigger': 'work_delivery', 'percent': 50}])
        warranty = self._entry('warranty_terms', duration_years=5, scope='whole_work')
        for sqlite in (False, True):
            for entry, issue_type, field, basis_key, value_key, value in (
                (payment, 'payment_timing_and_basis', 'payment', 'payment_basis', 'payment_terms',
                 {'milestones': payment['milestones']}),
                (warranty, 'missing_warranty', 'warranty', 'warranty_basis', 'warranty_terms',
                 {'duration_years': 5, 'scope': 'whole_work'})):
                with self.subTest(sqlite=sqlite, field=field):
                    result = {'known': True, 'buyer_inputs': {entry['kind']: [entry]},
                              basis_key: 'buyer_declaration', value_key: value}
                    fact = {'id': f'O/field/{field}', 'field': field}
                    args = dict(extra_facts=[fact])
                    self.assertEqual(self._case(sqlite, issue_type, [fact['id']], [], [entry], result, **args)[:3],
                                     (['issue'], 'resolved', 1))
                    self.assertEqual(self._case(sqlite, issue_type, [fact['id'], 'O/field/total'], [],
                        [entry], result, extra_facts=[fact, {'id': 'O/field/total', 'field': 'total'}])[:3],
                        ([], 'open', 0))
                    self.assertEqual(self._case(sqlite, issue_type, [fact['id']], [], [entry],
                        {**result, value_key: {}}, **args)[:3], ([], 'open', 0))

    def test_commercial_basis_keeps_buyer_authority_separate(self):
        payment = self._entry('payment_terms', milestones=[{'trigger': 'work_start', 'percent': 50},
                                                         {'trigger': 'work_delivery', 'percent': 50}])
        warranty = self._entry('warranty_terms', duration_years=5, scope='whole_work')
        with patch('buyer_controls.inputs_for', side_effect=lambda con, offer, kind:
                   [payment] if kind == 'payment_terms' else [warranty]):
            self.assertEqual(payment_basis(None, 'O')['value'], {'milestones': payment['milestones']})
            self.assertEqual(warranty_basis(None, 'O')['value'], {'duration_years': 5, 'scope': 'whole_work'})
        with patch('buyer_controls.inputs_for', return_value=[payment, {**payment, 'milestones': []}]):
            with self.assertRaisesRegex(ValueError, 'Conflicting buyer payment_terms'):
                payment_basis(None, 'O')

    def test_renamed_commercial_questions_close_only_exact_applied_field(self):
        payment = {**self._entry('payment_terms', milestones=[
            {'trigger': 'work_start', 'percent': 50}, {'trigger': 'work_delivery', 'percent': 50}]),
            'issue_id': 'original-payment'}
        warranty = {**self._entry('warranty_terms', duration_years=5, scope='whole_work'),
                    'issue_id': 'original-warranty'}
        for sqlite in (False, True):
            for entry, issue_type, field, basis_key, value_key, value in (
                (payment, 'payment_timing', 'payment', 'payment_basis', 'payment_terms',
                 {'milestones': payment['milestones']}),
                (warranty, 'warranty_missing', 'warranty', 'warranty_basis', 'warranty_terms',
                 {'duration_years': 5, 'scope': 'whole_work'})):
                with self.subTest(sqlite=sqlite, field=field):
                    fact = {'id': f'O/field/{field}', 'field': field}
                    result = {'known': True, 'buyer_inputs': {entry['kind']: [entry]},
                              basis_key: 'buyer_declaration', value_key: value}
                    self.assertEqual(self._case(sqlite, issue_type, [fact['id']], [],
                        [entry], result, extra_facts=[fact])[:3], (['issue'], 'resolved', 1))
                    direct = {**entry, 'issue_id': 'issue'}
                    direct_result = {**result, 'buyer_inputs': {entry['kind']: [direct]}}
                    self.assertEqual(self._case(sqlite, issue_type, [fact['id']], [],
                        [direct], direct_result, extra_facts=[fact])[:3], (['issue'], 'resolved', 1))
                    for refs, other in (
                        ([], []),
                        ([fact['id'], 'O/field/quote_date'], [{'id': 'O/field/quote_date', 'field': 'quote_date'}]),
                        ([fact['id'], 'O/field/validity'], [{'id': 'O/field/validity', 'field': 'validity'}]),
                        ([fact['id'], 'O/field/warranty' if field == 'payment' else 'O/field/payment'],
                         [{'id': 'O/field/warranty' if field == 'payment' else 'O/field/payment',
                           'field': 'warranty' if field == 'payment' else 'payment'}])):
                        self.assertEqual(self._case(sqlite, issue_type, refs, [], [entry], result,
                            extra_facts=[fact, *other])[:3], ([], 'open', 0))
                    self.assertEqual(self._case(sqlite, issue_type, [f'B/field/{field}'], [],
                        [entry], result, extra_offer=True, extra_facts=[
                            {'id': f'B/field/{field}', 'offer_id': 'B', 'supplier_id': 'SB', 'field': field}])[:3],
                        ([], 'open', 0))
                    self.assertEqual(self._case(sqlite, issue_type, [fact['id']], [],
                        [entry], {**result, value_key: {}}, extra_facts=[fact])[:3], ([], 'open', 0))
                    self.assertEqual(self._case(sqlite, 'source_authority_conflict', [fact['id']], [],
                        [entry], result, extra_facts=[fact])[:3], ([], 'open', 0))
                    with self.assertRaisesRegex(ValueError, 'source hash changed'):
                        self._case(sqlite, issue_type, [fact['id']], [], [entry], result,
                                   extra_facts=[fact], input_error=True)


if __name__ == '__main__':
    unittest.main()
