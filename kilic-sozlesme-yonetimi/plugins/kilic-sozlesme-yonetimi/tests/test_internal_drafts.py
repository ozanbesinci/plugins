"""Core state-machine tests with an explicitly fake renderer; NOT real Word QA."""
import copy
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from sozlesme_cekirdek import CoreError, Store
from sozlesme_cekirdek.safety import hash_file, hash_value


class InternalDraftTests(unittest.TestCase):
    def setUp(self):
        runtime = Path(__file__).resolve().parent / '.runtime'
        runtime.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='ic-taslak-İı-', dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.sources = self.area / 'sources'
        self.sources.mkdir()
        self.store = Store(self.area / 'work', source_roots=[self.sources], output_root=self.area)
        self.case = self.store.create_case('SENTETİK iç çalışma taslağı')
        self.request = {'request_id': str(uuid4()), 'case_id': self.case, 'context_version': 0,
                        'selected_versions': [], 'policy_version': '1', 'partial_review': False,
                        'mode': 'INTERNAL_DRAFT', 'title': 'Test taslağı',
                        'sections': [{'heading': 'Çalışma notu', 'text': 'Henüz kararlaştırılmamış öneri.',
                                      'kind': 'DRAFT_TEXT', 'node_ids': []}]}
        self.evaluation = self.eval()

    def eval(self):
        return {'case_id': self.case, 'request_id': self.request['request_id'],
                'context_version': self.request['context_version'], 'status': 'BILGI_GEREKLI',
                'skill_id': 'K28', 'authority': 'NOT_VERIFIED', 'critical_analysis_allowed': False,
                'findings': [], 'context_pack_id': None, 'partial_review': None}

    def error(self, code, call):
        with self.assertRaises(CoreError) as caught:
            call()
        self.assertEqual(code, caught.exception.code)

    @staticmethod
    def fake_render(docx, directory):
        """Intentionally invalid PDF/PNG fixture; proves state transitions only."""
        pdf = directory / 'render.pdf'
        pdf.write_bytes(b'%PDF-FAKE-TEST-ONLY')
        pages = []
        for number in (1, 2):
            page = directory / ('page-' + str(number) + '.png')
            page.write_bytes(b'\x89PNG\r\n\x1a\nFAKE-TEST-ONLY' + bytes([number]))
            pages.append({'page': number, 'path': str(page), 'sha256': hash_file(page)})
        return {'renderer': {'name': 'EXPLICIT_FAKE_TEST_RENDERER', 'version': 'TEST_ONLY',
                             'exe_sha256': '0' * 64, 'adapter_sha256': '1' * 64},
                'pdf': {'path': str(pdf), 'sha256': hash_file(pdf)}, 'pages': pages}

    def prepare(self, *, render=None):
        with ExitStack() as stack:
            stack.enter_context(patch('sozlesme_cekirdek.draft_document.build_docx', return_value=b'PK-FAKE-TEST-DOCX'))
            stack.enter_context(patch('sozlesme_cekirdek.draft_document.structural_qa', return_value={'passed': True, 'checks': ['EXPLICIT_TEST_FAKE']}))
            stack.enter_context(patch('sozlesme_cekirdek.draft_document.render_docx', side_effect=render or self.fake_render))
            return self.store.prepare_internal_draft(self.request, self.evaluation)

    def review(self, prepared, decision='ACCEPT'):
        return {'case_id': self.case, 'draft_id': prepared['draft_id'], 'request_id': str(uuid4()),
                'context_version': self.request['context_version'], 'manifest_sha256': prepared['manifest_sha256'],
                'decision': decision, 'observation': 'SENTETİK TEST: sayfalar yalnız birim testi için eşleştirildi.',
                'reviewed_pages': [{'page': p['page'], 'sha256': p['sha256']} for p in prepared['manifest']['pages']]}

    def bind_statement(self):
        statement = self.store.add_statement(self.case, 'Kullanıcının kayıtlı örnek beyanı.', expected_revision=self.store.case_revision(self.case))
        node = self.store.register_context_node(self.case, spec={'node_kind': 'USER_STATEMENT', 'title': 'Beyan', 'record_id': statement},
                                                expected_revision=self.store.case_revision(self.case))['node_id']
        self.request['context_version'] = self.store.case_revision(self.case)
        pack = self.store.context_pack(self.case, request={'root_ids': [node], 'purpose': 'İç taslak',
                                                          'max_context_bytes': 100000, 'policy_version': '1', 'include_related': False})
        self.evaluation = self.eval()
        self.evaluation.update(status='KISMI', context_pack_id=pack['pack_id'])
        self.evaluation['findings'] = [{'node_id': e['node_id'], 'source_kind': e['node_kind'], 'content': e['content'],
                                       'provenance': e['provenance'], 'verification_status': e['knowledge_status'], 'trust': e['trust']}
                                      for e in pack['result']['context']['entries']]
        self.request['sections'] = [{'heading': 'Beyan', 'text': 'Kullanıcının kayıtlı örnek beyanı.', 'kind': 'USER_STATEMENT', 'node_ids': [node]}]
        return node

    def test_prepare_is_quarantined_until_full_review_and_idempotent(self):
        prepared = self.prepare()
        self.assertEqual('REVIEW_PENDING', prepared['state'])
        self.assertIsNone(prepared['final_path'])
        self.assertFalse((self.store.root / 'ic-taslaklar').exists())
        self.assertEqual(prepared, self.prepare(render=lambda *_: self.fail('Aynı istek yeniden render edilmemeli')))
        review = self.review(prepared)
        published = self.store.review_internal_draft(review)
        self.assertEqual('PUBLISHED', published['state'])
        self.assertEqual(hash_file(Path(published['final_path'])), prepared['manifest']['docx']['sha256'])
        self.assertEqual('NOT_GRANTED', published['business_acceptance'])
        self.assertFalse(published['critical_analysis_allowed'])
        self.assertEqual(0, self.store.case_revision(self.case))
        self.assertEqual(published, self.store.review_internal_draft(review))

    def test_schema_rejects_authority_output_path_and_unknown_mode(self):
        for key, value in [('authority', 'APPROVED'), ('output_path', 'somewhere.docx'), ('mode', 'SIGNED')]:
            bad = dict(self.request, **{key: value})
            self.error('SEMA_HATASI', lambda b=bad: self.store.prepare_internal_draft(b, self.evaluation))

    def test_same_request_different_text_rejected(self):
        self.prepare()
        self.request['sections'][0]['text'] = 'Farklı metin'
        self.error('GECERSIZ_GIRDI', self.prepare)

    def test_published_artifact_tamper_is_not_delivered_on_status_or_retry(self):
        prepared = self.prepare()
        review = self.review(prepared)
        published = self.store.review_internal_draft(review)
        Path(published['final_path']).write_bytes(b'TAMPERED-AFTER-PUBLICATION')
        self.error('KAYNAK_BOZUK', lambda: self.store.internal_draft_status(self.case, prepared['draft_id']))
        self.error('KAYNAK_BOZUK', self.prepare)
        self.error('KAYNAK_BOZUK', lambda: self.store.review_internal_draft(review))

    def test_uuid_case_is_canonical_and_duplicate_versions_rejected(self):
        self.request['case_id'] = self.case.upper()
        self.request['request_id'] = self.request['request_id'].upper()
        self.evaluation = self.eval()
        prepared = self.prepare()
        self.assertEqual(self.case, prepared['case_id'])
        self.request['case_id'] = self.case
        self.request['request_id'] = self.request['request_id'].lower()
        self.assertEqual(prepared, self.prepare())
        duplicate = str(uuid4())
        self.request['selected_versions'] = [duplicate, duplicate.upper()]
        self.error('SEMA_HATASI', self.prepare)

    def test_partial_page_list_or_wrong_manifest_rejected(self):
        prepared = self.prepare()
        incomplete = self.review(prepared)
        incomplete['reviewed_pages'].pop()
        self.error('RENDER_HATASI', lambda: self.store.review_internal_draft(incomplete))
        wrong = self.review(prepared)
        wrong['manifest_sha256'] = '0' * 64
        self.error('SURUM_CAKISMASI', lambda: self.store.review_internal_draft(wrong))
        reversed_pages = self.review(prepared)
        reversed_pages['reviewed_pages'].reverse()
        self.error('RENDER_HATASI', lambda: self.store.review_internal_draft(reversed_pages))

    def test_wrong_case_and_stale_revision_rejected(self):
        prepared = self.prepare()
        wrong = self.review(prepared)
        wrong['case_id'] = self.store.create_case('Başka case')
        self.error('KAYNAK_KAPSAMI', lambda: self.store.review_internal_draft(wrong))
        self.store.add_statement(self.case, 'Sonradan değişen beyan', expected_revision=0)
        self.error('SURUM_CAKISMASI', lambda: self.store.review_internal_draft(self.review(prepared)))

    def test_review_hashes_actual_pdf_png_and_docx(self):
        for kind in ('docx', 'pdf', 'png'):
            self.request['request_id'] = str(uuid4())
            self.evaluation = self.eval()
            prepared = self.prepare()
            artifact = prepared['manifest']['pages'][0] if kind == 'png' else prepared['manifest'][kind]
            Path(artifact['path']).write_bytes(b'TAMPERED')
            self.error('KAYNAK_BOZUK', lambda p=prepared: self.store.review_internal_draft(self.review(p)))

    def test_reject_never_publishes_and_accept_cannot_follow(self):
        prepared = self.prepare()
        rejected = self.store.review_internal_draft(self.review(prepared, 'REJECT'))
        self.assertEqual('REJECTED', rejected['state'])
        self.assertIsNone(rejected['final_path'])
        self.error('GECERSIZ_DURUM', lambda: self.store.review_internal_draft(self.review(prepared)))

    def test_render_failure_is_durable_and_not_blindly_retried(self):
        def fail(*_):
            raise CoreError('CONFIG_REQUIRED', 'TEST renderer yok')
        self.error('CONFIG_REQUIRED', lambda: self.prepare(render=fail))
        resumed = self.prepare(render=lambda *_: self.fail('Yeniden render yasak'))
        self.assertEqual('QUARANTINED', resumed['state'])
        self.assertEqual('CONFIG_REQUIRED', resumed['error_code'])

    def test_snapshot_with_internal_draft_fails_before_creating_output(self):
        self.prepare()
        target = self.area / 'snapshot-with-draft'
        self.error('SNAPSHOT_KAPSAMI', lambda: self.store.snapshot(target))
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + '.pending').exists())

    def test_renderer_runs_without_db_lock_and_case_change_is_rechecked(self):
        def render(docx, directory):
            self.store.add_statement(self.case, 'Render sırasında yeni bilgi', expected_revision=0)
            return self.fake_render(docx, directory)
        self.error('SURUM_CAKISMASI', lambda: self.prepare(render=render))
        self.assertEqual('QUARANTINED', self.prepare()['state'])

    def test_existing_target_is_never_overwritten(self):
        prepared = self.prepare()
        final = self.store.root / 'ic-taslaklar' / (prepared['draft_id'] + '.docx')
        final.parent.mkdir()
        final.write_bytes(b'EXISTING-USER-FILE')
        with self.assertRaises(CoreError):
            self.store.review_internal_draft(self.review(prepared))
        self.assertEqual(b'EXISTING-USER-FILE', final.read_bytes())

    def test_interruption_after_rename_reconciles_without_regeneration(self):
        prepared = self.prepare()
        original = self.store._draft_current
        calls = []
        def crash(db, row):
            calls.append(1)
            if len(calls) == 3:
                raise RuntimeError('SENTETİK: rename sonrası DB kesintisi')
            return original(db, row)
        with patch.object(self.store, '_draft_current', side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.store.review_internal_draft(self.review(prepared))
        self.assertEqual('PUBLISHING', self.store.internal_draft_status(self.case, prepared['draft_id'])['state'])
        reopened = Store(self.store.root, source_roots=[self.sources], output_root=self.area)
        recovered = reopened.reconcile_internal_drafts(self.case)[0]
        self.assertEqual('PUBLISHED', recovered['state'])
        self.assertEqual(prepared['manifest']['docx']['sha256'], hash_file(Path(recovered['final_path'])))

    def test_old_published_revision_does_not_block_new_draft_recovery(self):
        first = self.prepare()
        self.store.review_internal_draft(self.review(first))
        self.store.add_statement(self.case, 'Sonraki çalışma için yeni bilgi.', expected_revision=0)
        self.request['request_id'] = str(uuid4())
        self.request['context_version'] = self.store.case_revision(self.case)
        self.evaluation = self.eval()
        second = self.prepare()
        original = self.store._draft_current
        calls = []
        def crash(db, row):
            calls.append(1)
            if len(calls) == 3:
                raise RuntimeError('SENTETİK: ikinci taslak rename sonrası DB kesintisi')
            return original(db, row)
        with patch.object(self.store, '_draft_current', side_effect=crash):
            with self.assertRaises(RuntimeError):
                self.store.review_internal_draft(self.review(second))
        self.error('SURUM_CAKISMASI', lambda: self.store.internal_draft_status(self.case, first['draft_id']))
        recovered = self.store.reconcile_internal_drafts(self.case)
        self.assertEqual(1, len(recovered))
        self.assertEqual(second['draft_id'], recovered[0]['draft_id'])
        self.assertEqual('PUBLISHED', recovered[0]['state'])
        self.assertEqual(second['manifest']['docx']['sha256'], hash_file(Path(recovered[0]['final_path'])))

    def test_statement_must_equal_bound_text_and_cannot_be_source_excerpt(self):
        self.bind_statement()
        valid = copy.deepcopy(self.request)
        self.request['sections'][0]['text'] += ' Eklenen uydurma cümle.'
        self.error('KAYNAK_ALINTISI', self.prepare)
        self.request = copy.deepcopy(valid)
        self.request['sections'][0]['kind'] = 'SOURCE_EXCERPT'
        self.error('KAYNAK_ALINTISI', self.prepare)
        self.request = valid
        self.assertEqual('REVIEW_PENDING', self.prepare()['state'])

    def test_selected_source_rechecked_after_render_and_before_review(self):
        path = self.sources / 'kaynak.txt'
        path.write_text('İlk kaynak.', encoding='utf-8')
        doc = self.store.create_document(self.case, 'Kaynak', expected_revision=0)
        version = self.store.ingest(self.case, doc, path, expected_revision=1)['version_id']
        self.request['selected_versions'] = [version]
        self.bind_statement()
        prepared = self.prepare()
        path.write_text('Değişmiş kaynak.', encoding='utf-8')
        self.error('YENIDEN_INCELE', lambda: self.store.review_internal_draft(self.review(prepared)))

    def test_published_source_change_blocks_status_and_idempotent_delivery(self):
        path = self.sources / 'kaynak.txt'
        path.write_text('Yayın anında güncel kaynak.', encoding='utf-8')
        doc = self.store.create_document(self.case, 'Kaynak', expected_revision=0)
        version = self.store.ingest(self.case, doc, path, expected_revision=1)['version_id']
        self.request['selected_versions'] = [version]
        self.bind_statement()
        prepared = self.prepare()
        review = self.review(prepared)
        published = self.store.review_internal_draft(review)
        self.assertEqual('PUBLISHED', published['state'])
        path.write_text('Yayından sonra değişen kaynak.', encoding='utf-8')
        self.error('YENIDEN_INCELE', lambda: self.store.internal_draft_status(self.case, prepared['draft_id']))
        self.error('YENIDEN_INCELE', self.prepare)
        self.error('YENIDEN_INCELE', lambda: self.store.review_internal_draft(review))

    def test_unavailable_selected_context_is_not_source_free(self):
        self.evaluation['context_pack_id'] = str(uuid4())
        self.error('BAGLAM_BOZUK', self.prepare)
        self.evaluation['context_pack_id'] = None
        self.request['partial_review'] = True
        self.error('BAGLAM_BOZUK', self.prepare)

    def test_partial_draft_preserves_all_27_missing_annexes_in_real_docx(self):
        # The real builder and structural QA run; only Office rendering is fake.
        import io
        import xml.etree.ElementTree as ET
        import zipfile
        node = self.bind_statement()
        references = [f'Eksik ek {number:02d}' for number in range(1, 28)]
        for reference in references:
            self.store.register_context_relation(self.case,
                spec={'from_id': node, 'relation': 'ANNEX', 'unresolved_reference': reference,
                      'rationale': 'SENTETİK TEST: kapsamı eksik zorunlu ek.'},
                expected_revision=self.store.case_revision(self.case))
        self.request['context_version'] = self.store.case_revision(self.case)
        self.request['partial_review'] = True
        pack = self.store.context_pack(self.case, request={'root_ids': [node], 'purpose': 'Kısmi iç taslak',
            'max_context_bytes': 100000, 'policy_version': '1', 'include_related': False, 'allow_partial_review': True})
        self.evaluation = self.eval()
        self.evaluation.update(status='KISMI', context_pack_id=pack['pack_id'], partial_review={
            'scope': 'AVAILABLE_REGISTERED_EVIDENCE_ONLY', 'registered_closure_complete': False,
            'missing_dependencies': pack['result']['missing_dependencies']})
        self.evaluation['findings'] = [{'node_id': e['node_id'], 'source_kind': e['node_kind'], 'content': e['content'],
            'provenance': e['provenance'], 'verification_status': e['knowledge_status'], 'trust': e['trust']}
            for e in pack['result']['partial_context']['entries']]
        self.assertEqual(27, len(self.evaluation['partial_review']['missing_dependencies']))
        with patch('sozlesme_cekirdek.draft_document.render_docx', side_effect=self.fake_render):
            prepared = self.store.prepare_internal_draft(self.request, self.evaluation)
        self.assertEqual('REVIEW_PENDING', prepared['state'])
        self.assertTrue(prepared['manifest']['structural_qa']['passed'])
        with zipfile.ZipFile(io.BytesIO(Path(prepared['manifest']['docx']['path']).read_bytes())) as archive:
            document = ET.fromstring(archive.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        paragraphs = [''.join(text.text or '' for text in paragraph.findall('.//w:t', ns))
                      for paragraph in document.findall('.//w:p', ns)]
        expected = ['Eksik kaynak: ' + reference for reference in references]
        missing_paragraphs = [p for p in paragraphs if p.startswith('Eksik kaynak: ')]
        self.assertCountEqual(expected, missing_paragraphs)
        self.assertEqual(27, len(missing_paragraphs))

    def test_review_payload_cannot_claim_business_authority(self):
        prepared = self.prepare()
        bad = self.review(prepared)
        bad['company_approved'] = True
        self.error('SEMA_HATASI', lambda: self.store.review_internal_draft(bad))

    def test_preparing_interruption_is_quarantined_without_regeneration(self):
        prepared = self.prepare()
        with self.store._db() as db:
            db.execute("UPDATE ic_taslaklar SET state='PREPARING',manifest=NULL,manifest_sha256=NULL WHERE draft_id=?", [prepared['draft_id']])
        state = self.store.reconcile_internal_drafts(self.case)[0]
        self.assertEqual('QUARANTINED', state['state'])
        self.assertEqual('HAZIRLAMA_KESILDI', state['error_code'])


if __name__ == '__main__':
    unittest.main()
