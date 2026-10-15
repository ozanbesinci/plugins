"""Synthetic engineering evidence; native Word QA is a separate real process."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from uuid import uuid4
from lxml import etree
import test_docx as helpers
from sozlesme_cekirdek import CoreError
from sozlesme_cekirdek.docx_revisions import prepare_revisions,RevisionArtifact,structural_qa,normalized
from sozlesme_cekirdek.docx_copies import prepare_copy,revision_inventory
from sozlesme_cekirdek.docx_comments import strip_comment_anchors
from sozlesme_cekirdek.guard import action_request
from sozlesme_cekirdek.readers.common import Package
from sozlesme_cekirdek.readers.docx import q,read_docx
from sozlesme_cekirdek.safety import hash_value,hash_file
from guard_fixtures import request
from reader_fixtures import docx_bytes,docx_parts,package_bytes

WHEN=helpers.WHEN


def copy_request(data,*,mode="EXTERNAL_CLEAN_DRAFT",decision="ACCEPT",case=None,version=None):
    req=request(case or str(uuid4()),version or str(uuid4()),hashlib.sha256(data).hexdigest())
    req["plan"]["action_type"]="CREATE_CLEAN_COPY"
    req["plan"]["purpose"]="EXTERNAL_DRAFT" if mode=="EXTERNAL_CLEAN_DRAFT" else "INTERNAL_DRAFT"
    req["payload"]["content_plan"]={"body_text":"","clean_copy":{"mode":mode,"comment_policy":"DROP_ALL" if mode=="EXTERNAL_CLEAN_DRAFT" else "KEEP_ALL",
                                               "revision_decisions":[{**x,"decision":decision} for x in revision_inventory(Package(data))]}}
    req["plan"]["parameters"]["content_plan_sha256"]=hash_value(req["payload"]["content_plan"])
    return req


def with_comments(req):
    req=copy.deepcopy(req)
    req["payload"]["content_plan"]["comments"]=[{"change_index":0,"text":"İç değerlendirme örneği.","audience":"INTERNAL"},
                                                  {"change_index":1,"text":"Tutar karşı önerisi açıklaması.","audience":"EXTERNAL"}]
    req["plan"]["parameters"]["content_plan_sha256"]=hash_value(req["payload"]["content_plan"])
    return req


def refreshed(req):
    req["plan"]["parameters"]["content_plan_sha256"]=hash_value(req["payload"]["content_plan"])
    return req


class CopyTests(unittest.TestCase):
    def setUp(self): self.data=docx_bytes();self.req=copy_request(self.data)
    def error(self,code,fn):
        with self.assertRaises(CoreError) as caught:fn()
        self.assertEqual(code,caught.exception.code)
    def clean(self,req=None,data=None):return prepare_copy(data or self.data,req or self.req,when=WHEN)

    def test_real_comments_and_new_anchors_preserve_old_comment(self):
        req=with_comments(helpers.edit_request(self.data))
        artifact=prepare_revisions(self.data,req,when=WHEN)
        package=Package(artifact.data)
        self.assertEqual(3,len(package.roots['word/comments.xml']))
        original=Package(self.data).roots['word/comments.xml'][0]
        self.assertEqual(normalized(original),normalized(package.roots['word/comments.xml'][0]))
        self.assertEqual('PASS',structural_qa(self.data,artifact)['status'])
        for row in artifact.manifest['comments']:
            for tag in ('commentRangeStart','commentRangeEnd','commentReference'):
                self.assertEqual(1,sum(x.get(q('id'))==row['comment_id'] for x in package.roots['word/document.xml'].iter(q(tag))))

    def test_comment_part_relationship_and_type_are_created_when_absent(self):
        parts=docx_parts();del parts['word/comments.xml']
        root=etree.fromstring(parts['word/document.xml'].encode());strip_comment_anchors(root,{'0'})
        parts['word/document.xml']=etree.tostring(root)
        rels=etree.fromstring(parts['word/_rels/document.xml.rels'].encode())
        for child in list(rels):
            if child.get('Type').endswith('/comments'):rels.remove(child)
        parts['word/_rels/document.xml.rels']=etree.tostring(rels)
        types=etree.fromstring(parts['[Content_Types].xml'].encode())
        for child in list(types):
            if child.get('PartName')=='/word/comments.xml':types.remove(child)
        parts['[Content_Types].xml']=etree.tostring(types)
        data=package_bytes(parts);req=with_comments(helpers.edit_request(data))
        artifact=prepare_revisions(data,req,when=WHEN)
        self.assertEqual(2,len(Package(artifact.data).roots['word/comments.xml']))
        self.assertEqual('PASS',structural_qa(data,artifact)['status'])

    def test_internal_comment_is_not_automatically_copied_to_external_revision(self):
        req=with_comments(helpers.edit_request(self.data));req['plan']['purpose']='EXTERNAL_DRAFT'
        self.error('P5_INTERNAL_COMMENT',lambda:prepare_revisions(self.data,req,when=WHEN))
        for row in req['payload']['content_plan']['comments']:row['audience']='EXTERNAL'
        artifact=prepare_revisions(self.data,refreshed(req),when=WHEN)
        self.assertEqual('PASS',structural_qa(self.data,artifact)['status'])

    def test_bad_comment_index_duplicate_or_deleted_target_are_blocked(self):
        for mutate in (lambda c:c[0].update(change_index=63),lambda c:c[1].update(change_index=0),lambda c:c[0].update(text=' \n')):
            req=with_comments(helpers.edit_request(self.data));mutate(req['payload']['content_plan']['comments'])
            self.error('P5_COMMENT_SCOPE',lambda:prepare_revisions(self.data,refreshed(req),when=WHEN))
        req=helpers.edit_request(self.data,edits=[('Avans oranı','20','')])
        req['payload']['content_plan']['comments']=[{'change_index':0,'text':'Silme açıklaması','audience':'INTERNAL'}]
        self.error('P5_COMMENT_SCOPE',lambda:prepare_revisions(self.data,refreshed(req),when=WHEN))

    def test_tampered_old_or_new_comment_and_anchor_fail_qa(self):
        artifact=prepare_revisions(self.data,with_comments(helpers.edit_request(self.data)),when=WHEN)
        for name,old,new in [('word/comments.xml',b'Oran',b'Gizli'),('word/comments.xml','İç'.encode(),'Yan'.encode()),('word/document.xml',b'commentRangeStart',b'bookmarkStart')]:
            parts=dict(Package(artifact.data).parts);parts[name]=parts[name].replace(old,new)
            data=package_bytes(parts);manifest=copy.deepcopy(artifact.manifest);manifest['artifact_sha256']=hashlib.sha256(data).hexdigest()
            self.error('P5_QA_FAILED',lambda:structural_qa(self.data,RevisionArtifact(data,manifest)))

    def test_accept_reject_and_mixed_choice_are_explicit_content(self):
        for decision,expected in [('ACCEPT','Garanti süresi 36 aydır.'),('REJECT','Garanti süresi 24 aydır.')]:
            artifact=self.clean(copy_request(self.data,decision=decision))
            reading=read_docx(artifact.data)
            self.assertIn(expected,[x['views']['AFTER'] for x in reading['units']])
            self.assertEqual([],reading['revisions']);self.assertEqual('PASS',structural_qa(self.data,artifact)['status'])
        req=copy_request(self.data)
        req['payload']['content_plan']['clean_copy']['revision_decisions'][1]['decision']='REJECT'
        artifact=self.clean(refreshed(req))
        self.assertIn('Garanti süresi  aydır.',[x['views']['AFTER'] for x in read_docx(artifact.data)['units']])
        self.assertEqual('PASS',structural_qa(self.data,artifact)['status'])

    def test_comment_manifest_cannot_rebind_to_another_new_revision(self):
        artifact=prepare_revisions(self.data,with_comments(helpers.edit_request(self.data)),when=WHEN)
        artifact.manifest['comments'][0]['anchor_revision_id']=artifact.manifest['changes'][1]['revision_ids'][-1]
        self.error('P5_MANIFEST',lambda:structural_qa(self.data,artifact))

    def test_external_copy_drops_all_comment_bytes_and_wiring(self):
        revision=prepare_revisions(self.data,with_comments(helpers.edit_request(self.data)),when=WHEN)
        artifact=self.clean(copy_request(revision.data),revision.data)
        package=Package(artifact.data)
        self.assertNotIn('word/comments.xml',package.parts)
        self.assertFalse(any(x['type'].endswith('/comments') for x in package.relationships))
        self.assertNotIn(b'commentReference',package.parts['word/document.xml'])
        self.assertNotIn('İç değerlendirme'.encode(),b''.join(package.parts.values()))
        self.assertEqual('NOT_GRANTED',artifact.manifest['business_approval'])
        self.assertEqual('PASS',structural_qa(revision.data,artifact)['status'])

    def test_internal_copy_keeps_comments_and_non_target_structure(self):
        revision=prepare_revisions(self.data,with_comments(helpers.edit_request(self.data)),when=WHEN)
        artifact=self.clean(copy_request(revision.data,mode='INTERNAL_RESOLVED_DRAFT'),revision.data)
        before,after=Package(revision.data),Package(artifact.data)
        self.assertEqual(before.parts['word/comments.xml'],after.parts['word/comments.xml'])
        for name in ['word/footnotes.xml','word/endnotes.xml','word/header1.xml','word/footer1.xml','word/styles.xml']:
            self.assertEqual(before.parts[name],after.parts[name])
        for tag in ('tblPr','tblGrid','tcPr','sectPr'):
            self.assertEqual([normalized(x) for x in before.roots['word/document.xml'].iter(q(tag))],[normalized(x) for x in after.roots['word/document.xml'].iter(q(tag))])

    def test_missing_extra_duplicate_and_wrong_metadata_selection_stop(self):
        for mutation in ('missing','extra','duplicate','author','date','kind'):
            req=copy.deepcopy(self.req);choices=req['payload']['content_plan']['clean_copy']['revision_decisions']
            if mutation=='missing':choices.pop()
            elif mutation=='extra':choices.append({**choices[0],'revision_id':'999'})
            elif mutation=='duplicate':choices[1]=copy.deepcopy(choices[0])
            elif mutation=='author':choices[0]['expected_author']='Fake Legal'
            elif mutation=='date':choices[0]['expected_date']='2026-01-01T00:00:00Z'
            else:choices[0]['kind']='INSERTION'
            self.error('P5_REVISION_SELECTION',lambda:self.clean(refreshed(req)))

    def test_external_keep_comments_wrong_purpose_and_approval_are_blocked(self):
        req=copy.deepcopy(self.req);req['payload']['content_plan']['clean_copy']['comment_policy']='KEEP_ALL'
        self.error('P5_INTERNAL_COMMENT',lambda:self.clean(refreshed(req)))
        req=copy.deepcopy(self.req);req['plan']['purpose']='INTERNAL_DRAFT'
        self.error('P5_COPY_SCOPE',lambda:self.clean(req))
        req=copy.deepcopy(self.req);req['plan']['purpose']='APPROVED_OUTPUT'
        self.error('P5_BUSINESS_APPROVAL_REQUIRED',lambda:self.clean(req))
        artifact=self.clean();artifact.manifest['business_approval']='APPROVED'
        self.error('SEMA_HATASI',lambda:structural_qa(self.data,artifact))

    def test_unknown_metadata_custom_parts_hidden_fields_and_modern_comments_stop(self):
        for name,value in [('docProps/core.xml','<secret>Internal</secret>'),('word/headerSecret.xml','<secret/>'),('customXml/item1.xml','<secret/>'),('word/commentsExtended.xml','<secret/>')]:
            parts=docx_parts();parts[name]=value;data=package_bytes(parts)
            req=copy_request(data)
            with self.assertRaises(CoreError):self.clean(req,data)
        for markup in ('<w:rPr><w:vanish/></w:rPr>','<w:instrText>DDE</w:instrText>'):
            parts=docx_parts();parts['word/header1.xml']=parts['word/header1.xml'].replace('<w:t>',markup+'<w:t>')
            data=package_bytes(parts);req=copy_request(data)
            self.error('P5_COPY_UNSUPPORTED',lambda:self.clean(req,data))

    def test_structural_nested_and_duplicate_revisions_stop(self):
        for mutation in ('structural','nested','duplicate','side'):
            parts=docx_parts()
            if mutation=='structural':parts['word/document.xml']=parts['word/document.xml'].replace('<w:sectPr>','<w:p><w:pPr><w:pPrChange w:id="100"/></w:pPr></w:p><w:sectPr>')
            elif mutation=='nested':parts['word/document.xml']=parts['word/document.xml'].replace('<w:ins w:id="11"','<w:ins w:id="12"><w:ins w:id="11"').replace('</w:ins>','</w:ins></w:ins>')
            elif mutation=='duplicate':parts['word/document.xml']=parts['word/document.xml'].replace('w:id="11"','w:id="10"')
            else:parts['word/header1.xml']=parts['word/header1.xml'].replace('<w:r>','<w:ins w:id="20" w:author="Other" w:date="2026-10-01T00:00:00Z"><w:r>').replace('</w:r>','</w:r></w:ins>')
            data=package_bytes(parts)
            with self.assertRaises(CoreError):revision_inventory(Package(data))

    def test_already_unrevised_source_has_explicit_empty_selection(self):
        first=self.clean();req=copy_request(first.data)
        self.assertEqual([],req['payload']['content_plan']['clean_copy']['revision_decisions'])
        second=self.clean(req,first.data)
        self.assertEqual('PASS',structural_qa(first.data,second)['status'])

    def test_reintroduced_comment_and_unplanned_main_text_fail_qa(self):
        artifact=self.clean()
        for added in (True,False):
            parts=dict(Package(artifact.data).parts)
            if added:parts['word/comments.xml']=Package(self.data).parts['word/comments.xml']
            else:parts['word/document.xml']=parts['word/document.xml'].replace(b'Garanti',b'Changed')
            data=package_bytes(parts);manifest=copy.deepcopy(artifact.manifest);manifest['artifact_sha256']=hashlib.sha256(data).hexdigest()
            self.error('P5_QA_FAILED',lambda:structural_qa(self.data,RevisionArtifact(data,manifest)))

    def test_source_hash_clock_determinism_and_tracking_off(self):
        artifact=self.clean();self.assertEqual(artifact,self.clean())
        package=Package(artifact.data)
        settings=next(x['resolved_part'] for x in package.relationships if x['type'].endswith('/settings'))
        self.assertEqual('false',package.roots[settings].find(q('trackRevisions')).get(q('val')))
        self.assertEqual(docx_bytes(),self.data)
        req=copy.deepcopy(self.req);req['plan']['source_versions'][0]['sha256']='0'*64
        self.error('P5_SOURCE_HASH',lambda:self.clean(req))
        self.error('P5_TIME',lambda:prepare_copy(self.data,self.req,when='invalid'))

    def test_unplanned_copy_comment_fields_and_model_approval_rejected(self):
        req=copy.deepcopy(self.req);req['payload']['content_plan']['clean_copy']['approved']=True
        self.error('SEMA_HATASI',lambda:action_request(req))
        req=with_comments(helpers.edit_request(self.data));req['plan']['action_type']='BUILD_DOCUMENT';req['payload']['changes']=[];req['plan']['parameters']['change_plan_sha256']=None
        self.error('SEMA_HATASI',lambda:action_request(req))


class CopyStoreTests(unittest.TestCase):
    rev=helpers.DocxStoreTests.rev
    issue=helpers.DocxStoreTests.issue
    execute=helpers.DocxStoreTests.execute
    output_count=helpers.DocxStoreTests.output_count
    def setUp(self):
        helpers.DocxStoreTests.setUp(self)
        self.req=copy_request(self.path.read_bytes(),case=self.case,version=self.version)

    def test_real_clean_backend_guard_history_and_completion(self):
        before=self.rev();result=self.execute()
        self.assertEqual('SIMULATION_COMMITTED',result['state'])
        history=self.store.docx_output_history(self.case)['outputs'][0]
        self.assertEqual('EXTERNAL_CLEAN_DRAFT',history['copy_mode']);self.assertEqual('NOT_GRANTED',history['business_approval'])
        self.assertEqual(before,self.rev());self.assertEqual([],read_docx(Path(result['output_path']).read_bytes())['revisions'])
        self.assertEqual('ALLOW',self.runtime.completion_gate(self.case,self.req['plan']['operation_id'])['decision'])

    def test_revision_decision_change_invalidates_old_permission(self):
        permit=self.issue();self.req['payload']['content_plan']['clean_copy']['revision_decisions'][0]['decision']='REJECT';refreshed(self.req);self.host.authorize(self.req)
        self.assertEqual('BLOCKED',self.execute(permit)['state']);self.assertEqual(0,self.output_count())

    def test_comment_policy_change_invalidates_old_permission(self):
        permit=self.issue();self.req['payload']['content_plan']['clean_copy']['comment_policy']='KEEP_ALL';refreshed(self.req);self.host.authorize(self.req)
        self.assertEqual('BLOCKED',self.execute(permit)['state'])

    def test_new_comment_text_change_invalidates_old_permission(self):
        self.req=with_comments(helpers.edit_request(self.path.read_bytes(),case=self.case,version=self.version,reading=self.req.get('reading_id')))
        # Use the real reading ID created in the setup, not a caller-invented unit receipt.
        self.req['payload']['changes'][0]['reading_id']=self.store.read_document(self.case,self.version,format='DOCX')['processing_id']
        self.req['payload']['changes'][1]['reading_id']=self.req['payload']['changes'][0]['reading_id']
        self.req['plan']['parameters']['change_plan_sha256']=hash_value(self.req['payload']['changes'])
        permit=self.issue();self.req['payload']['content_plan']['comments'][0]['text']='Değişmiş metin';refreshed(self.req);self.host.authorize(self.req)
        self.assertEqual('BLOCKED',self.execute(permit)['state'])

    def test_clean_missing_qa_cannot_publish(self):
        self.backend.evidence_provider=None
        self.assertEqual('FAILED',self.execute()['state']);self.assertEqual(0,self.output_count())
        self.assertFalse((self.store.root/self.req['plan']['parameters']['target_relative_path']).exists())

    def test_clean_snapshot_preserves_copy_type_but_not_delivery_file(self):
        self.execute();snapshot=self.area/'snapshot';self.store.snapshot(snapshot)
        from sozlesme_cekirdek import Store
        restored=Store.restore(snapshot,self.area/'restored',source_roots=[self.sources],output_root=self.area)
        history=restored.docx_output_history(self.case)['outputs'][0]
        self.assertEqual('FINAL_UNAVAILABLE',history['state']);self.assertEqual('EXTERNAL_CLEAN_DRAFT',history['copy_mode'])

    def test_source_stale_revokes_completion(self):
        self.execute();self.path.write_bytes(b'changed')
        self.assertEqual('NEEDS_REVIEW',self.store.docx_output_history(self.case)['outputs'][0]['state'])
        self.assertEqual('BLOCK',self.runtime.completion_gate(self.case,self.req['plan']['operation_id'])['decision'])

    def test_clean_generation_is_not_approved_output(self):
        self.req['plan']['purpose']='APPROVED_OUTPUT'
        result=self.execute()
        self.assertEqual('FAILED',result['state']);self.assertEqual(0,self.output_count())
        self.assertEqual(hashlib.sha256(docx_bytes()).hexdigest(),hash_file(self.path))


if __name__=='__main__':unittest.main()
