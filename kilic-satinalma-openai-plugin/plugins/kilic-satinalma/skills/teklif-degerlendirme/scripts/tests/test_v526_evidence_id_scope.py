"""Model-local evidence labels must not replace evidence from another task."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db import connect
from record_results import _record_facts, _record_requirements
from workflow import prepare


class EvidenceIdScopeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='teklif-v526-evidence-'))
        self.source = self.root / 'source'
        self.source.mkdir()
        self.run = self.root / 'run'
        for supplier, total in [('Alpha', 100000), ('Beta', 105000)]:
            book = Workbook()
            sheet = book.active
            sheet.title = 'Teklif'
            sheet['A1'] = 'Fiyat Teklifi'
            sheet['A2'] = 'Firma'
            sheet['B2'] = supplier
            sheet['A3'] = 'Genel Toplam'
            sheet['B3'] = total
            sheet['A4'] = 'Para Birimi'
            sheet['B4'] = 'EUR'
            book.save(self.source / f'{supplier}_teklif.xlsx')
        prepare(self.source, self.run, 'hizli')

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_same_local_evidence_id_preserves_both_offer_links(self):
        con = connect(self.run)
        try:
            docs = con.execute(
                "SELECT document_id,offer_id FROM documents WHERE offer_id IS NOT NULL ORDER BY document_id"
            ).fetchall()
            self.assertEqual(len(docs), 2)
            for index, (doc_id, offer_id) in enumerate(docs):
                unit_id = con.execute(
                    'SELECT unit_id FROM document_units WHERE document_id=? LIMIT 1', [doc_id]
                ).fetchone()[0]
                task = {'task_id': f'task-model-{index}', 'offer_id': offer_id, 'document_id': doc_id}
                result = {
                    'evidence': [{
                        'evidence_id': 'ev_shared', 'document_id': doc_id, 'unit_id': unit_id,
                        'locator': {'sheet': 'Teklif'}, 'quote': 'Fiyat Teklifi',
                        'evidence_status': 'verified', 'confidence': 1,
                    }],
                    'facts': [{
                        'offer_id': offer_id, 'field_key': 'scope_signature',
                        'value_text': 'Fiyat Teklifi', 'evidence_status': 'verified',
                        'evidence_id': 'ev_shared', 'normalized': {'evidence_refs': ['ev_shared']},
                    }],
                }
                _record_facts(con, task, {'document_ids': [doc_id]}, result, 'semantic_llm')
            con.commit()
            rows = con.execute(
                "SELECT f.offer_id,f.evidence_id,e.document_id,f.normalized_json "
                "FROM facts f JOIN evidence e ON e.evidence_id=f.evidence_id "
                "WHERE f.field_key='scope_signature' ORDER BY f.offer_id"
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(len({row[1] for row in rows}), 2)
            by_offer = {offer_id: doc_id for doc_id, offer_id in docs}
            for offer_id, evidence_id, doc_id, normalized in rows:
                self.assertEqual(doc_id, by_offer[offer_id])
                self.assertEqual(json.loads(normalized)['evidence_refs'], [evidence_id])
        finally:
            con.close()

    def test_same_local_scope_and_issue_ids_preserve_both_offers(self):
        con = connect(self.run)
        try:
            docs = con.execute(
                "SELECT document_id,offer_id FROM documents WHERE offer_id IS NOT NULL ORDER BY document_id"
            ).fetchall()
            self.assertEqual(len(docs), 2)
            for index, (doc_id, offer_id) in enumerate(docs):
                unit_id = con.execute(
                    'SELECT unit_id FROM document_units WHERE document_id=? LIMIT 1', [doc_id]
                ).fetchone()[0]
                evidence_id = f'ev_unique_{index}'
                task = {'task_id': f'task-issue-{index}', 'offer_id': offer_id, 'document_id': doc_id}
                result = {
                    'evidence': [{
                        'evidence_id': evidence_id, 'document_id': doc_id, 'unit_id': unit_id,
                        'locator': {'sheet': 'Teklif'}, 'quote': 'Fiyat Teklifi',
                        'evidence_status': 'verified', 'confidence': 1,
                    }],
                    'facts': [{
                        'offer_id': offer_id, 'field_key': 'scope_signature',
                        'value_text': 'Fiyat Teklifi', 'evidence_status': 'verified',
                        'evidence_id': evidence_id,
                    }],
                    'scope_items': [{
                        'scope_id': 'scope_shared', 'offer_id': offer_id,
                        'classification': 'product', 'description': f'Ürün {index}',
                        'status': 'verified', 'evidence_ids': [evidence_id],
                        'cost_role': 'included_in_price',
                    }],
                    'open_issues': [{
                        'issue_id': 'rfi_shared', 'owner': f'FIRMA:Örnek {index}',
                        'severity': 'medium', 'issue_type': 'validity',
                        'question': f'Teklif {index} geçerliliği nedir?',
                        'fact_ids': [f'{offer_id}/field/scope_signature'],
                        'evidence_ids': [evidence_id],
                    }],
                    'exclusions': [{
                        'exclusion_id': 'exc_shared', 'offer_id': offer_id,
                        'decision': 'review', 'reason': f'Belge {index} kapsam incelemesi',
                        'evidence_ids': [evidence_id],
                    }],
                }
                _record_facts(con, task, {'document_ids': [doc_id]}, result, 'semantic_llm')
            con.commit()
            scopes = con.execute("SELECT offer_id,evidence_ids_json FROM scope_items WHERE classification='product'").fetchall()
            issues = con.execute("SELECT fact_ids_json,evidence_ids_json FROM open_issues WHERE issue_type='validity'").fetchall()
            exclusions = con.execute("SELECT offer_id,evidence_ids_json FROM exclusions WHERE reason LIKE 'Belge % kapsam incelemesi'").fetchall()
            self.assertEqual({row[0] for row in scopes}, {offer_id for _, offer_id in docs})
            self.assertEqual(len(issues), 2)
            self.assertEqual({row[0] for row in exclusions}, {offer_id for _, offer_id in docs})
            self.assertEqual(
                {json.loads(row[0])[0].split('/field/')[0] for row in issues},
                {offer_id for _, offer_id in docs},
            )
        finally:
            con.close()

    def test_same_local_requirement_id_preserves_both_source_documents(self):
        con = connect(self.run)
        try:
            docs = con.execute(
                'SELECT document_id FROM documents WHERE active=true ORDER BY document_id'
            ).fetchall()
            self.assertEqual(len(docs), 2)
            for index, (doc_id,) in enumerate(docs):
                unit_id = con.execute(
                    'SELECT unit_id FROM document_units WHERE document_id=? LIMIT 1', [doc_id]
                ).fetchone()[0]
                task = {'task_id': f'task-requirement-{index}', 'document_id': doc_id}
                result = {
                    'evidence': [{
                        'evidence_id': 'ev_requirement', 'document_id': doc_id,
                        'unit_id': unit_id, 'locator': {'sheet': 'Teklif'},
                        'quote': 'Fiyat Teklifi', 'evidence_status': 'verified',
                    }],
                    'requirements': [{
                        'requirement_id': 'req_shared', 'source_unit_id': unit_id,
                        'text': 'Fiyat Teklifi', 'category': 'information',
                        'evidence_id': 'ev_requirement',
                    }],
                }
                _record_requirements(con, task, {'document_ids': [doc_id]}, result)
            con.commit()
            rows = con.execute(
                "SELECT requirement_id,source_document_id,evidence_id FROM requirements "
                "WHERE text='Fiyat Teklifi' ORDER BY source_document_id"
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual({row[1] for row in rows}, {doc_id for (doc_id,) in docs})
            self.assertEqual(len({row[0] for row in rows}), 2)
            for _, doc_id, evidence_id in rows:
                self.assertEqual(
                    con.execute('SELECT document_id FROM evidence WHERE evidence_id=?', [evidence_id]).fetchone()[0],
                    doc_id,
                )
        finally:
            con.close()


if __name__ == '__main__':
    unittest.main()
