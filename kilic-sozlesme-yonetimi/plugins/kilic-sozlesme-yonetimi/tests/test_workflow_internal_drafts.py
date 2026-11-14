"""P6 routes explicit K28 draft requests without broadening corporate actions."""
import copy
import unittest
from unittest.mock import Mock
from uuid import uuid4
import test_context as fixtures
from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.workflows import evaluate

class DraftWorkflowTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def request(self):
        return {'request_id':str(uuid4()),'case_id':self.case,'skill_id':'K28','intent':'İç çalışma taslağı',
                'context_version':self.rev(),'selected_versions':[],'root_ids':[],'max_context_bytes':65536,
                'policy_version':'1','requested_output':'DOCX',
                'document_request':{'mode':'INTERNAL_DRAFT','title':'İç değerlendirme',
                    'sections':[{'heading':'Kapsam','text':'İç çalışma önerisidir.','kind':'DRAFT_TEXT','node_ids':[]}]}}

    def result(self,r):
        return {'schema_version':'internal-draft-1.0','draft_id':str(uuid4()),'case_id':self.case,
                'request_id':r['request_id'],'context_version':self.rev(),'mode':'INTERNAL_DRAFT','state':'PREPARING',
                'request_digest':'a'*64,'manifest_sha256':None,'manifest':None,'final_path':None,
                'review_scope':'MODEL_VISUAL_REVIEW_ONLY','authority':'NOT_VERIFIED','business_acceptance':'NOT_GRANTED',
                'critical_analysis_allowed':False,'source_mutation':'NONE','error_code':None}

    def test_explicit_prepare_routes_typed_payload_and_preserves_authority(self):
        request=self.request();self.store.prepare_internal_draft=Mock(return_value=self.result(request))
        result=evaluate(self.store,request)
        payload,evaluation=self.store.prepare_internal_draft.call_args.args
        self.assertEqual('INTERNAL_DRAFT',payload['mode']);self.assertFalse(payload['partial_review'])
        self.assertEqual('K28',evaluation['skill_id']);self.assertEqual('KISMI',result['status'])
        self.assertEqual('NOT_VERIFIED',result['authority']);self.assertFalse(result['critical_analysis_allowed'])
        self.assertEqual([],result['output_ids']);self.assertEqual('INTERNAL_DRAFT_ONLY',result['action_execution'])
        self.assertIsNone(result['internal_draft']['final_path'])

    def test_review_has_distinct_new_request_id_and_parent_draft(self):
        request=self.request();del request['document_request']
        parent=str(uuid4());request['document_review']={'draft_id':parent,'manifest_sha256':'a'*64,'decision':'REJECT',
            'observation':'Sayfa gözlemi','reviewed_pages':[{'page':1,'sha256':'b'*64}]}
        self.store.review_internal_draft=Mock(return_value=self.result(request))
        evaluate(self.store,request);payload=self.store.review_internal_draft.call_args.args[0]
        self.assertEqual(parent,payload['draft_id']);self.assertEqual(request['request_id'],payload['request_id'])
        self.assertEqual(self.case,payload['case_id'])

    def test_wrong_skill_chat_both_modes_or_authority_extra_reject_before_write(self):
        original=self.request();self.store.prepare_internal_draft=Mock()
        for changes in ({'skill_id':'K21'},{'requested_output':'CHAT'},
                        {'document_review':{'draft_id':str(uuid4()),'manifest_sha256':'a'*64,'decision':'ACCEPT','observation':'x','reviewed_pages':[{'page':1,'sha256':'b'*64}]}},
                        {'authenticated':True}):
            request=copy.deepcopy(original);request.update(changes)
            with self.subTest(changes=changes),self.assertRaises(CoreError):evaluate(self.store,request)
        self.store.prepare_internal_draft.assert_not_called()

    def test_unqualified_docx_stays_blocked(self):
        request=self.request();del request['document_request']
        self.store.prepare_internal_draft=Mock()
        result=evaluate(self.store,request)
        self.assertEqual('TEKNIK_ENGEL',result['status']);self.assertNotIn('internal_draft',result)
        self.store.prepare_internal_draft.assert_not_called()

    def test_writer_capacity_rejected_before_prepare_in_both_contracts(self):
        from sozlesme_cekirdek.context import checked
        self.store.prepare_internal_draft=Mock()
        original=self.request()
        for field in ('title','heading','sections'):
            request=copy.deepcopy(original);doc=request['document_request']
            if field=='title':doc['title']='a'*201
            elif field=='heading':doc['sections'][0]['heading']='a'*201
            else:doc['sections']*=101
            with self.subTest(field=field),self.assertRaises(CoreError):evaluate(self.store,request)
            payload={k:request[k] for k in ('request_id','case_id','context_version','selected_versions','policy_version')}
            payload.update(doc,partial_review=False)
            with self.subTest(core=field),self.assertRaises(CoreError):checked('internal_draft_request',payload)
        self.store.prepare_internal_draft.assert_not_called()
