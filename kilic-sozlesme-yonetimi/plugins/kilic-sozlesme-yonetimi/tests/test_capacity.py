import unittest
from unittest.mock import patch

import test_context as fixtures
from sozlesme_cekirdek.errors import CoreError


class CapacityTests(unittest.TestCase):
    setUp=fixtures.ContextTests.setUp
    rev=fixtures.ContextTests.rev
    document=fixtures.ContextTests.document
    spec=fixtures.ContextTests.spec
    node=fixtures.ContextTests.node
    register=fixtures.ContextTests.register

    def resources(self,case=None):
        return {row['resource']:row for row in self.store.capacity(case or self.case)['resources'] if row['scope']=='CASE'}

    def test_retained_counts_and_remaining_are_case_scoped_without_mutation(self):
        revision=self.rev()
        with self.store._db() as db:before=db.execute('SELECT count(*) FROM kayitlar WHERE case_id=?',[self.case]).fetchone()[0]
        other=self.store.create_case('other synthetic case')
        first=self.resources();second=self.resources()
        self.assertEqual(first,second);self.assertEqual(revision,self.rev())
        self.assertEqual(0,self.resources(other)['icerik_birimleri']['used'])
        self.assertTrue(all(row['remaining']==max(0,row['limit']-row['used']) for row in first.values()))
        with self.store._db() as db:after=db.execute('SELECT count(*) FROM kayitlar WHERE case_id=?',[self.case]).fetchone()[0]
        self.assertEqual(before,after)

    def test_exact_and_exceeded_quota_are_visible_and_never_silently_clipped(self):
        self.node('Avans oranı')
        used=self.resources()['icerik_birimleri']['used'];self.assertGreater(used,0)
        with patch('sozlesme_cekirdek.context.MAX_NODES',used):
            row=self.resources()['icerik_birimleri'];self.assertEqual('AT_LIMIT',row['status']);self.assertEqual(0,row['remaining'])
        with patch('sozlesme_cekirdek.context.MAX_NODES',used-1):
            row=self.resources()['icerik_birimleri'];self.assertEqual('OVER_LIMIT',row['status']);self.assertEqual(used,row['used'])

    def test_unknown_case_cannot_read_capacity(self):
        from uuid import uuid4
        with self.assertRaises(CoreError):self.store.capacity(str(uuid4()))
