"""Actual-reply scope import never bypasses source or waiting controls."""
import json
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook
from common import sha256_file
from db import connect, get_meta
from question_waits import UserAnswerRequired, register
from source_authority import refresh
from source_selection import attach
from workflow import prepare


class SourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.src = self.root / 'source'
        self.run = self.root / 'run'
        self.src.mkdir()
        for firm in ('Alpha', 'Beta'):
            wb = Workbook(); ws = wb.active
            for row in [('Fiyat Teklifi', ''), ('Tedarikçi', firm + ' Ltd.'), ('Teklif Tarihi', '12.10.2026'),
                        ('Genel Toplam', 100000), ('Para Birimi', 'USD'), ('Miktar', 6), ('Birim', 'adet'),
                        ('Ürün', 'Tank'), ('KDV', 'hariç'), ('Ödeme', '%100 teslimde'), ('Geçerlilik', '90 gün')]:
                ws.append(row)
            wb.save(self.src / (firm + '_teklif_rev01.xlsx'))
        with patch('workflow.user_input_waiting', return_value=None):
            prepare(self.src, self.run, 'hizli', date(2026, 10, 12))
        con = connect(self.run)
        try:
            # Synthetic identity is separately confirmed; selection itself must not do this.
            con.execute("UPDATE suppliers SET identification_status='confirmed'"); con.commit()
        finally:
            con.close()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    def declaration(self):
        name = 'Alpha_teklif_rev01.xlsx'
        selected = {'filename': name, 'sha256': sha256_file(self.src / name)}
        reply = self.root / 'reply.json'; handoff = self.root / 'handoff.json'; result = self.root / 'result.json'
        self.write(reply, {'source': 'actual_user_message_question_reply', 'actual_user_answer': 'Bu dosya esas alınsın',
                           'selected_source_filenames': [name]})
        self.write(handoff, {'questions': [{'issue_id': 'source-question-A', 'issue_type': 'source_authority_conflict', 'sources': [selected]}]})
        self.write(result, {'adequate': True, 'source_selection_only': True, 'actual_reply_sha256': sha256_file(reply),
                            'question_responses': [{'issue_id': 'source-question-A', 'gate': {'state': 'answered'}}]})
        packet = {'schema': 'teklif-source-selection/v1', 'source_root': str(self.src), 'selected_sources': [selected],
                  'receipt_files': [{'role': role, 'path': str(path), 'sha256': sha256_file(path)}
                                    for role, path in [('reply', reply), ('handoff', handoff), ('result', result)]]}
        path = self.root / 'declaration.json'; self.write(path, packet)
        return path, packet

    def authority(self):
        con = connect(self.run)
        try:
            return dict(con.execute('SELECT d.filename,s.authority_status FROM source_authority s JOIN documents d USING(document_id)').fetchall())
        finally:
            con.close()

    def test_only_actual_selected_standalone_offer_resolves(self):
        path, _ = self.declaration(); attach(self.run, path); refresh(self.run)
        self.assertEqual(self.authority(), {'Alpha_teklif_rev01.xlsx': 'controlling', 'Beta_teklif_rev01.xlsx': 'needs_input'})
        self.assertEqual(get_meta(self.run, 'source_selection_v1', parse_json=True)['source_type'], 'USER_INPUT')

    def test_unselected_revision_does_not_silently_resolve(self):
        refresh(self.run)
        self.assertEqual(set(self.authority().values()), {'needs_input'})

    def test_raw_source_change_rejects_selection(self):
        path, _ = self.declaration()
        source = self.src / 'Alpha_teklif_rev01.xlsx'; source.write_bytes(source.read_bytes() + b'changed')
        with self.assertRaises(ValueError): attach(self.run, path)
        self.assertIsNone(get_meta(self.run, 'source_selection_v1'))

    def test_staged_receipt_change_does_not_rewrite_authority(self):
        path, _ = self.declaration(); attach(self.run, path); refresh(self.run); before = self.authority()
        staged = self.run / 'user_evidence/source_selection/reply.json'
        staged.write_bytes(staged.read_bytes() + b'changed')
        with self.assertRaises(ValueError): refresh(self.run)
        self.assertEqual(self.authority(), before)

    def test_partial_or_continue_reply_rejected(self):
        for text, adequate in [('Kısmen biliyorum', False), ('devam', True)]:
            path, packet = self.declaration()
            reply = self.root / 'reply.json'; value = json.loads(reply.read_text(encoding='utf-8'))
            value['actual_user_answer'] = text; self.write(reply, value)
            result = self.root / 'result.json'; value = json.loads(result.read_text(encoding='utf-8'))
            value['adequate'] = adequate; value['actual_reply_sha256'] = sha256_file(reply); self.write(result, value)
            for receipt in packet['receipt_files']: receipt['sha256'] = sha256_file(Path(receipt['path']))
            self.write(path, packet)
            with self.assertRaises(ValueError): attach(self.run, path)
        self.assertIsNone(get_meta(self.run, 'source_selection_v1'))

    def test_other_question_scope_cannot_select_source(self):
        path, packet = self.declaration(); handoff = self.root / 'handoff.json'
        value = json.loads(handoff.read_text(encoding='utf-8'))
        value['questions'][0]['sources'][0]['sha256'] = '0' * 64; self.write(handoff, value)
        for receipt in packet['receipt_files']: receipt['sha256'] = sha256_file(Path(receipt['path']))
        self.write(path, packet)
        with self.assertRaises(ValueError): attach(self.run, path)

    def test_archive_change_never_marks_source_controlling(self):
        path, _ = self.declaration(); attach(self.run, path)
        con = connect(self.run)
        try:
            row = con.execute("SELECT metadata_json FROM documents WHERE filename='Alpha_teklif_rev01.xlsx'").fetchone()
            relative = json.loads(row[0])['archived_source_path']
        finally:
            con.close()
        archive = self.run / relative; archive.write_bytes(archive.read_bytes() + b'changed')
        with self.assertRaises(ValueError): refresh(self.run)
        self.assertEqual(set(self.authority().values()), {'needs_input'})

    def test_selection_before_dispatch_and_idempotent(self):
        path, _ = self.declaration()
        self.assertEqual(attach(self.run, path)['status'], 'ATTACHED_USER_SOURCE_SELECTION')
        self.assertEqual(attach(self.run, path)['status'], 'ALREADY_ATTACHED')
        con = connect(self.run)
        try:
            con.execute('INSERT INTO task_dispatches VALUES (?,?,?,?,?,?)', ['dispatched', 'packet', 'schema', 'execution', 'context', 'now']); con.commit()
        finally:
            con.close()
        with self.assertRaises(ValueError): attach(self.run, path)

    def test_open_question_blocks_entry_before_declaration_read(self):
        register(self.run, {'issue_id': 'pending', 'scope_sha256': 'scope', 'question': 'Hangi kaynak?',
                            'issue_type': 'source_authority_conflict', 'sources': []})
        with self.assertRaises(UserAnswerRequired): attach(self.run, self.root / 'does-not-exist.json')


if __name__ == '__main__': unittest.main()
