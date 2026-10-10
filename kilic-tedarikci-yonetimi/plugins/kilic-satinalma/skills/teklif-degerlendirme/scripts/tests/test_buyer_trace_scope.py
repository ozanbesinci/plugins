"""Buyer decision authority stays separate from supplier source facts."""
import json
import unittest
from unittest.mock import patch

from scope_ledger import buyer_authority


class BuyerAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.base = {'offer_id':'O','issue_id':'I','scope_sha256':'S',
                     'source_hashes':{'D':'H'}}

    def check(self, field='currency', *, item=None, result=None, calc_status='complete',
              independent_status='pass', independent_hash='HASH', event=True,
              derived=False, event_payload=None, issue_refs=None, issue_status='resolved'):
        kind={'currency':'currency','payment':'payment_terms','warranty':'warranty_terms'}[field]
        value={'currency':{'value':'EUR'},
               'payment':{'milestones':[{'trigger':'work_start','percent':50},{'trigger':'work_delivery','percent':50}]},
               'warranty':{'duration_years':5,'scope':'whole_work'}}[field]
        entry=item or {**self.base,'kind':kind,**value}
        expected={
            'currency':{'currency':'EUR','currency_basis':'buyer_declaration'},
            'payment':{'payment_basis':'buyer_declaration','payment_terms':value},
            'warranty':{'warranty_basis':'buyer_declaration','warranty_terms':value},
        }[field]
        calc={'calculation_id':'C','offer_id':'O','calculation_type':'cost_summary',
              'status':calc_status,'input_hash':'HASH',
              'result_json':json.dumps(result or {**expected,'buyer_inputs':{kind:[entry]}})}
        independent=[{'independent_id':'IC','calculation_id':'C','input_hash':independent_hash,
                      'status':independent_status}]
        payload=event_payload or ({'issue_id':'J','scope_sha256':'S2',
                'original_answer_issue_ids':['I'],'resolution_basis':'same_source_hashed_currency_declaration_applied',
                'supplier_facts_modified':False,'buyer_inputs':[entry]} if derived else
                {'issue_id':'I','scope_sha256':'S','supplier_facts_modified':False,'buyer_inputs':[entry]})
        events=[{'event_type':'buyer_response_applied_derived' if derived else 'buyer_response_applied',
                 'payload_json':json.dumps(payload)}] if event else []
        issue=[{'issue_id':'J','status':issue_status,'issue_type':'currency_missing',
                'fact_ids_json':json.dumps(issue_refs if issue_refs is not None else ['O/field/currency'])}]
        def query(_con, sql, _params=None):
            if 'FROM independent_calculations' in sql: return independent
            if 'FROM workflow_events' in sql: return events
            if 'FROM open_issues' in sql: return issue
            raise AssertionError(sql)
        with patch('scope_ledger.inputs_for',return_value=[entry]), \
             patch('scope_ledger.current_calculations',return_value=[calc]), \
             patch('scope_ledger.rows_as_dict',side_effect=query):
            return buyer_authority(object(),'O',field)

    def test_exact_three_bases_are_separate_trace_units(self):
        for field in ('currency','payment','warranty'):
            with self.subTest(field=field):
                authority=self.check(field)
                self.assertEqual(authority['method'],'deterministic_buyer_authority')
                self.assertEqual(authority['field'],field)
                self.assertEqual(authority['source_hashes'],{'D':'H'})
                self.assertEqual(authority['independent_id'],'IC')

    def test_stale_hash_wrong_offer_unverified_calculation_or_missing_scope_fails_closed(self):
        with patch('scope_ledger.inputs_for', side_effect=ValueError('source hash changed')):
            self.assertIsNone(buyer_authority(object(), 'O', 'currency'))
        self.assertIsNone(self.check(item={**self.base,'kind':'currency','value':'EUR','offer_id':'B'}))
        self.assertIsNone(self.check(calc_status='incomplete'))
        self.assertIsNone(self.check(independent_status='unverified'))
        self.assertIsNone(self.check(independent_hash='STALE'))
        self.assertIsNone(self.check(event=False))
        self.assertIsNone(self.check(result={'currency':'EUR','currency_basis':'supplier_fact',
             'buyer_inputs':{'currency':[{**self.base,'kind':'currency','value':'EUR'}]}}))

    def test_derived_currency_event_requires_exact_original_answer_and_single_offer_field(self):
        self.assertEqual(self.check(derived=True)['issue_id'],'I')
        self.assertIsNone(self.check(derived=True,issue_refs=['B/field/currency']))
        self.assertIsNone(self.check(derived=True,issue_refs=['O/field/currency','O/field/total']))
        self.assertIsNone(self.check(derived=True,issue_status='open'))
        entry={**self.base,'kind':'currency','value':'EUR'}
        payload={'issue_id':'J','scope_sha256':'S2','original_answer_issue_ids':['WRONG'],
                 'resolution_basis':'same_source_hashed_currency_declaration_applied',
                 'supplier_facts_modified':False,'buyer_inputs':[entry]}
        self.assertIsNone(self.check(derived=True,event_payload=payload))
        self.assertIsNone(self.check(derived=True,event_payload={**payload,'original_answer_issue_ids':['I'],
                                                           'buyer_inputs':[{**entry,'source_hashes':{'D':'STALE'}}]}))
        self.assertIsNone(self.check('payment',derived=True))


if __name__ == '__main__':
    unittest.main()
