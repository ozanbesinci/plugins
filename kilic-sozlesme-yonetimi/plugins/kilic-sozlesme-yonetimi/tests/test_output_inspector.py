from pathlib import Path
import os
import unittest
from unittest.mock import patch

import test_guard as fixtures
from sozlesme_cekirdek.errors import CoreError


class OutputInspectorTests(unittest.TestCase):
    setUp=fixtures.GuardTests.setUp
    rev=fixtures.GuardTests.rev
    issue=fixtures.GuardTests.issue
    execute=fixtures.GuardTests.execute

    def one(self):return self.store.inspect_outputs(self.case)['operations'][0]

    def test_committed_present_is_only_synthetic_and_inspection_does_not_mutate(self):
        outcome=self.execute(self.issue());self.assertEqual('SIMULATION_COMMITTED',outcome['state'])
        before=self.rev();first=self.one();second=self.one()
        self.assertEqual(first,second);self.assertEqual(before,self.rev())
        self.assertEqual('COMMITTED_PRESENT_SYNTHETIC_ONLY',first['diagnostic'])
        self.assertFalse(first['delivery_confirmed']);self.assertEqual('NONE',first['recovery_action'])
        self.assertEqual('NOT_RUN',first['permissions'][0]['signature_verification'])

    def test_missing_final_never_replays_or_repairs(self):
        outcome=self.execute(self.issue());target=Path(outcome['output_path']);target.unlink()
        self.assertEqual('FINAL_UNAVAILABLE',self.one()['diagnostic']);self.assertFalse(target.exists())

    def test_foreign_final_and_ready_residue_are_distinguished(self):
        original=os.rename
        target=self.store.root/self.req['plan']['parameters']['target_relative_path']
        def race(source,destination):
            Path(destination).write_bytes(b'foreign')
            return original(source,destination)
        with patch('sozlesme_cekirdek.guard.os.rename',side_effect=race):outcome=self.execute(self.issue())
        self.assertEqual('FAILED',outcome['state'])
        row=self.one();self.assertEqual('FINAL_MISMATCH',row['diagnostic'])
        self.assertEqual('MATCH',row['files']['ready']['state']);self.assertEqual(b'foreign',target.read_bytes())

    def test_quarantine_without_final_is_not_delivery(self):
        permission=self.issue();self.backend.good_qa=False
        self.execute(permission)
        row=self.one();self.assertEqual('QUARANTINE_ONLY',row['diagnostic']);self.assertFalse(row['delivery_confirmed'])

    def test_case_separation_and_corrupt_operation_are_closed(self):
        self.issue();other=self.store.create_case('other')
        self.assertEqual([],self.store.inspect_outputs(other)['operations'])
        with self.store._db() as db:
            db.execute('UPDATE islemler SET request_digest=? WHERE case_id=?',['0'*64,self.case])
        with self.assertRaises(CoreError):self.store.inspect_outputs(self.case)
