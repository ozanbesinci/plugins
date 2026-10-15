import os
from pathlib import Path
import unittest
from unittest.mock import patch

from sozlesme_cekirdek.safety import hash_file
import test_guard as fixtures


class AtomicPublicationTests(unittest.TestCase):
    setUp=fixtures.GuardTests.setUp
    rev=fixtures.GuardTests.rev
    issue=fixtures.GuardTests.issue
    execute=fixtures.GuardTests.execute
    no_output=fixtures.GuardTests.no_output

    def test_native_publication_keeps_separate_quarantine_and_final_objects(self):
        result=self.execute(self.issue())
        self.assertEqual('SIMULATION_COMMITTED',result['state'],result)
        target=Path(result['output_path'])
        quarantine=self.store.system/'eylem-karantina'/self.req['plan']['operation_id']/'artifact.bin'
        self.assertEqual(1,target.stat().st_nlink);self.assertEqual(1,quarantine.stat().st_nlink)
        self.assertNotEqual(target.stat().st_ino,quarantine.stat().st_ino)
        self.assertEqual(hash_file(target),hash_file(quarantine))
        self.assertEqual([],list(target.parent.glob('*.ready')))

    def test_destination_race_never_overwrites_foreign_bytes(self):
        original=os.rename
        target=self.store.root/self.req['plan']['parameters']['target_relative_path']
        def race(source,destination):
            Path(destination).write_bytes(b'foreign-race-bytes')
            return original(source,destination)
        with patch('sozlesme_cekirdek.guard.os.rename',side_effect=race):
            result=self.execute(self.issue())
        self.assertEqual('FAILED',result['state'],result)
        self.assertEqual(b'foreign-race-bytes',target.read_bytes())
        self.assertFalse(result['delivery_confirmed'])
        self.assertEqual(1,len(list(target.parent.glob('*.ready'))))
