import unittest
from unittest.mock import patch
from uuid import uuid4

import test_context as fixtures
from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.source_roles import first_byte_difference


class SourceRoleTests(unittest.TestCase):
    def test_missing_text_view_cannot_be_reported_as_equal(self):
        from reader_fixtures import pdf_bytes
        path, doc, old, _ = self.document(pdf_bytes(), 'PDF')
        path.write_bytes(path.read_bytes() + b'changed')
        new = self.store.ingest(self.case, doc, path, expected_revision=self.rev(), parent_version_id=old)['version_id']
        with self.assertRaises(CoreError) as caught:
            self.store.compare_source_roles(self.case, old, new, format='PDF', view='BEFORE')
        self.assertEqual('GORUNUM_GEREKLI', caught.exception.code)

    def test_return_to_previous_bytes_is_a_new_current_version(self):
        original = self.path.read_bytes()
        child = self.child()
        self.path.write_bytes(original)
        returned = self.store.ingest(self.case, self.doc, self.path, expected_revision=self.rev(), parent_version_id=child, acquisition_key='return-A')
        self.assertFalse(returned['reused'])
        self.assertNotEqual(self.version, returned['version_id'])
        roles = self.store.compare_source_roles(self.case, child, returned['version_id'])
        self.assertEqual('SELECTED_CURRENT_TARGET', roles['target']['role'])
        repeated = self.store.ingest(self.case, self.doc, self.path, expected_revision=self.rev(), parent_version_id=child, acquisition_key='return-A')
        self.assertTrue(repeated['reused'])
        self.assertEqual(returned['version_id'], repeated['version_id'])

    def test_same_bytes_from_new_permitted_path_bind_new_acquisition(self):
        new_path = self.path.with_name('relocated.docx')
        self.path.rename(new_path)
        result = self.store.ingest(self.case, self.doc, new_path, expected_revision=self.rev())
        self.assertFalse(result['reused'])
        self.assertNotEqual(self.version, result['version_id'])
        self.assertEqual(new_path.read_bytes(), self.store.read_version(self.case, result['version_id']))
        self.assertTrue(self.store.ingest(self.case, self.doc, new_path, expected_revision=self.rev())['reused'])

    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document

    def child(self):
        self.path.write_bytes(self.path.read_bytes()+b'new-version-trailer')
        return self.store.ingest(self.case,self.doc,self.path,expected_revision=self.rev(),parent_version_id=self.version)['version_id']

    def test_old_reference_is_readable_but_never_current_decision_input(self):
        child=self.child();revision=self.rev()
        result=self.store.compare_source_roles(self.case,self.version,child)
        self.assertEqual('REFERENCE_ONLY',result['reference']['role'])
        self.assertFalse(result['reference']['original_file_matches_snapshot'])
        self.assertEqual('SELECTED_CURRENT_TARGET',result['target']['role'])
        self.assertTrue(result['target']['original_file_matches_snapshot'])
        self.assertEqual('NONE',result['reference']['decision_authority'])
        self.assertFalse(result['critical_analysis_allowed']);self.assertEqual('BYTES_ONLY',result['comparison_scope'])
        self.assertEqual(revision,self.rev())

    def test_parent_with_child_cannot_be_selected_as_current_target(self):
        child=self.child()
        with self.assertRaises(CoreError):self.store.compare_source_roles(self.case,child,self.version)

    def test_different_case_or_logical_document_is_rejected(self):
        other=self.store.create_case('other')
        with self.assertRaises(CoreError):self.store.compare_source_roles(other,self.version,self.version)
        _,_,version,_=self.document(self.path.read_bytes(),'DOCX')
        with self.assertRaises(CoreError):self.store.compare_source_roles(self.case,self.version,version)

    def test_access_revoked_reference_cannot_be_read_from_snapshot(self):
        child=self.child()
        self.path.unlink()
        with self.assertRaises(CoreError):self.store.compare_source_roles(self.case,self.version,child)

    def test_target_source_edit_during_delta_is_rejected(self):
        child=self.child()
        def changing(old,new):
            self.path.write_bytes(b'changed-during-delta')
            return first_byte_difference(old,new)
        with patch('sozlesme_cekirdek.source_roles.first_byte_difference',side_effect=changing):
            with self.assertRaises(CoreError):self.store.compare_source_roles(self.case,self.version,child)
