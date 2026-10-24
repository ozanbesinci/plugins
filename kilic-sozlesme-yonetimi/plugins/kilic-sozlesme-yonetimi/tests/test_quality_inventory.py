"""Scope, evidence-category and native physical-schema acceptance stay separate."""
import ast
from pathlib import Path
import unittest
import test_context as fixtures
from sozlesme_cekirdek.catalog import effective_test_scope, load_catalog

ROOT = Path(__file__).resolve().parents[1]
STATIC_CLASSES = {'SourceContractTests', 'ProHighPriorityContracts', 'ProMediumPriorityContracts',
                  'ChatOnlySurfaceTests', 'PowerShellSourceCompatibilityTests'}
FIXTURE_CLASSES = {'PackageTests', 'PdfTests', 'ClaudeCliTests', 'CliTests', 'ConfigEdgeTests', 'SafetyTests', 'ConfigTests'}


class QualityInventoryTests(unittest.TestCase):
    def test_all_original_104_definitions_have_explicit_effective_scope(self):
        scope = effective_test_scope()
        rows = {row['original_id']: row for row in scope['records']}
        self.assertEqual(104, len(rows))
        self.assertEqual(104, len(scope['records']))
        self.assertEqual('NOT_GRANTED', scope['product_acceptance'])
        for identifier in ['T33', 'T34', 'T44']:
            self.assertEqual('OUT_OF_SCOPE', rows[identifier]['scope_status'])
            self.assertEqual('UYGULANAMAZ', rows[identifier]['execution_status'])
        self.assertEqual('BUSINESS_CONFIRMATION_PENDING', rows['E20']['scope_status'])
        self.assertEqual('REPLACED_CURRENT_TEST', rows['T42']['scope_status'])
        self.assertIn('document', rows['T42']['current_test_id'])
        self.assertEqual(['Yalnız sohbet içinde kaynaklı cevap taslağı'], rows['E27']['effective']['expected_outputs'])
        self.assertTrue(all(row['execution_status'] != 'PASS' for row in scope['records']))

    def test_regression_traceability_names_each_definition_once_and_only_real_tests(self):
        import importlib, json
        trace = json.loads((ROOT / 'references/regression-traceability.json').read_text(encoding='utf-8'))
        manifest = json.loads((ROOT / 'tests/manifest.json').read_text(encoding='utf-8'))
        discovered = set()
        for name in manifest['classes']:
            module, cls = name.rsplit('.', 1)
            discovered.update(test.id() for test in unittest.defaultTestLoader.loadTestsFromTestCase(getattr(importlib.import_module(module), cls)))
        scope = {row['original_id']: row for row in effective_test_scope()['records']}
        ids = [row['id'] for row in trace['records']]
        self.assertEqual([f'T{number:02d}' for number in range(1, 65)], ids)
        for row in trace['records']:
            with self.subTest(definition=row['id']):
                self.assertIn(row['status'], trace['statuses'])
                self.assertTrue(set(row['tests']) <= discovered, set(row['tests']) - discovered)
                self.assertTrue(set(row['tests']).isdisjoint(manifest['excluded']))
                if row['status'] in {'COVERED_TECHNICAL', 'PARTIAL_TECHNICAL', 'REPLACED_CURRENT_TEST'}:
                    self.assertTrue(row['tests'])
                if row['status'] in {'PARTIAL_TECHNICAL', 'MODEL_OR_EXPERT_EVALUATION', 'HOST_TEST_REQUIRED', 'BUSINESS_DECISION_PENDING'}:
                    self.assertTrue(row['open'])
                self.assertEqual(row['status'] == 'OUT_OF_SCOPE_REMOVED', scope[row['id']]['scope_status'] == 'OUT_OF_SCOPE')
        t42 = next(row for row in trace['records'] if row['id'] == 'T42')
        self.assertEqual(['test_guard.GuardTests.' + scope['T42']['current_test_id'].rsplit('.', 1)[1]], t42['tests'])

    def test_current_k29_cannot_gain_removed_tools(self):
        row = next(row for row in load_catalog() if row['id'] == 'K29')
        denied = set(effective_test_scope()['removed_actions'])
        self.assertFalse(denied.intersection(str(tool).upper() for tool in row['tools']))
        self.assertEqual('yazisma-hazirlama', row['slug'])

    def test_every_skill_uses_protocol_that_forbids_reading_sources_outside_core(self):
        # CR-13: a host read the DOCX with zipfile/lxml and reported its own findings after BILGI_GEREKLI.
        protocol = (ROOT / 'references/skill-runtime.md').read_text(encoding='utf-8')
        self.assertIn('Kaynak dosyayı zip/XML', protocol)
        self.assertIn('BILGI_GEREKLI veya bağlam engeli döndürdüyse kendi bulgunu üretme', protocol)
        self.assertIn('kapsamı daraltılmış ön inceleme', protocol)
        skills = [ROOT / 'skills' / row['slug'] / 'SKILL.md' for row in load_catalog()]
        self.assertEqual(30, len(skills))
        for path in skills:
            self.assertIn('skill-runtime.md', path.read_text(encoding='utf-8'), path.parent.name)

    def test_updater_is_absent_and_only_30_business_skills_are_registered(self):
        import json
        registry=json.loads((ROOT/"references/skill-versions.json").read_text(encoding="utf-8"))
        self.assertEqual({f"K{i:02d}" for i in range(30)},set(registry))
        self.assertFalse((ROOT/"skills/guncelleyici").exists())
        self.assertFalse((ROOT/"vendor/guncelleyici").exists())
        protocol=(ROOT/"references/skill-runtime.md").read_text(encoding="utf-8")
        self.assertNotIn("AutoInstallMissing",protocol)
        self.assertIn("sozlesme.exe",protocol)


class NativeSchemaInventoryTests(unittest.TestCase):
    setUp = fixtures.ContextTests.setUp
    rev = fixtures.ContextTests.rev
    document = fixtures.ContextTests.document

    def test_real_duckdb_has_23_named_tables_and_six_immutable_migrations(self):
        expected = {'sema_gecmisi', 'dosyalar', 'kayitlar', 'belgeler', 'belge_surumu', 'surum_ebeveynleri',
                    'isleme_calismalari', 'beyanlar', 'bilgiler', 'kanit_baglari', 'gecersizlestirmeler', 'islem_olaylari',
                    'dogrulamalar', 'icerik_birimleri', 'iliskiler', 'baglam_paketleri', 'islemler', 'islem_izinleri',
                    'eylem_kararlari', 'docx_turevleri', 'is_bilgisi_baglari', 'yukumlulukler', 'gerceklesmeler'}
        with self.store._db() as db:
            self.assertEqual('_duckdb', type(db).__module__)
            actual = {row[0] for row in db.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_type='BASE TABLE'").fetchall()}
            self.assertEqual(expected, actual)
            self.assertEqual(list(range(1, 7)), [row[0] for row in db.execute('SELECT migration_no FROM sema_gecmisi ORDER BY migration_no').fetchall()])


if __name__ == '__main__':
    unittest.main()
