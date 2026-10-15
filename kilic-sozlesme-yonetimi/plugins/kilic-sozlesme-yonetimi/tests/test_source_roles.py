import unittest
from unittest.mock import patch
from uuid import uuid4

import test_context as fixtures
from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek.source_roles import first_byte_difference


class SourceRoleTests(unittest.TestCase):
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
