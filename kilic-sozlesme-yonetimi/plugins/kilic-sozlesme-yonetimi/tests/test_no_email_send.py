"""User removed sending: even a previously trusted/signed path must not send."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from sozlesme_cekirdek import Store, CoreError
from sozlesme_cekirdek.guard import SyntheticGuardRuntime, action_request, validator
from sozlesme_cekirdek.safety import hash_file, hash_value, canonical
from sozlesme_cekirdek.workflows import evaluate
from sozlesme_cekirdek.catalog import load_catalog
from guard_fixtures import Backend, Clock, Host, KEY, request
from reader_fixtures import docx_bytes

ROOT = Path(__file__).resolve().parents[1]


class RemovedEmailTests(unittest.TestCase):
    def setUp(self):
        area = ROOT / 'tests/.runtime'
        area.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='no-send-', dir=area)
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name)
        self.sources = self.area / 'sources'
        self.sources.mkdir()
        self.source = self.sources / 'Kaynak.docx'
        self.source.write_bytes(docx_bytes())
        self.store = Store(self.area / 'work', source_roots=[self.sources], output_root=self.area)
        self.case = self.store.create_case('Gönderim kaldırıldı')
        document = self.store.create_document(self.case, 'Sentetik', expected_revision=0)
        self.version = self.store.ingest(self.case, document, self.source, expected_revision=self.store.case_revision(self.case))['version_id']
        self.sha = hash_file(self.source)
        self.host = Host(self.case)
        self.backend = Backend()
        self.runtime = SyntheticGuardRuntime(self.store, identity_provider=self.host, backend=self.backend, signing_key=KEY, clock=Clock())
        self.legacy = request(self.case, self.version, self.sha, mail=True)

    def skill_request(self, skill='K29', output='CHAT'):
        return dict(request_id=str(uuid4()), case_id=self.case, skill_id=skill, intent='Cevap taslağı hazırla',
            context_version=self.store.case_revision(self.case), selected_versions=[self.version], root_ids=[], max_context_bytes=65536,
            policy_version='1', requested_output=output)

    def assert_no_effect(self):
        self.assertEqual(0, self.backend.prepared)
        self.assertFalse(hasattr(self.backend, 'send_email'))
        self.assertFalse(hasattr(self.backend, 'verify_email'))
        self.assertEqual(self.sha, hash_file(self.source))
        with self.store._db() as db:
            self.assertEqual(0, db.execute('SELECT count(*) FROM islem_izinleri').fetchone()[0])
        self.assertFalse((self.store.root / 'ciktilar').exists())

    def test_current_schema_rejects_legacy_mail_payload(self):
        self.assertFalse(validator('p4_action_request').is_valid(self.legacy))
        self.assert_no_effect()

    def test_default_agent_gate_denies_send_without_any_adapter_lookup(self):
        result = self.store.evaluate_action(request=self.legacy)
        self.assertEqual('BLOCK', result['decision'])
        self.assertIn('ABSOLUTE_PROHIBITION', result['reasons'])
        self.assert_no_effect()

    def test_even_authenticated_company_actor_cannot_reenable_send(self):
        self.host.identity = replace(self.host.identity, allowed_actions=frozenset({'SEND_EMAIL'}),
            explicit_request_digest=hash_value(self.legacy), corporate_authorized=True, authenticated=True)
        self.assertEqual('BLOCK', self.runtime.evaluate(request=self.legacy)['decision'])
        self.assert_no_effect()

    def test_direct_request_normalization_returns_removed_error(self):
        with self.assertRaises(CoreError) as caught:
            action_request(self.legacy)
        self.assertEqual('EPOSTA_GONDERIM_KALDIRILDI', caught.exception.code)
        self.assert_no_effect()

    def test_permission_issuer_cannot_issue_for_removed_send(self):
        with self.assertRaises(CoreError) as caught:
            self.runtime.issue_permission(request=self.legacy, expected_revision=self.store.case_revision(self.case))
        self.assertEqual('EPOSTA_GONDERIM_KALDIRILDI', caught.exception.code)
        self.assert_no_effect()

    def test_execution_denies_removed_send_before_permission_or_backend(self):
        result = self.runtime.execute(request=self.legacy, permission_id=str(uuid4()))
        self.assertEqual('BLOCKED', result['state'])
        self.assertIn('EPOSTA_GONDERIM_KALDIRILDI', result['decision']['reasons'])
        self.assert_no_effect()

    def test_document_permission_cannot_be_repurposed_for_send(self):
        doc = request(self.case, self.version, self.sha)
        self.host.authorize(doc)
        permit = self.runtime.issue_permission(request=doc, expected_revision=self.store.case_revision(self.case))['permission_id']
        legacy = copy.deepcopy(self.legacy)
        legacy['plan']['operation_id'] = doc['plan']['operation_id']
        self.assertEqual('BLOCKED', self.runtime.execute(request=legacy, permission_id=permit)['state'])
        self.assertEqual(0, self.backend.prepared)
        # A denied unrelated action does not destroy an authorized document operation.
        self.assertEqual('SIMULATION_COMMITTED', self.runtime.execute(request=doc, permission_id=permit)['state'])
        self.assertEqual(self.sha, hash_file(self.source))

    def test_skill_output_cannot_request_send(self):
        with self.assertRaises(CoreError) as caught:
            evaluate(self.store, self.skill_request(output='EMAIL_SEND'))
        self.assertEqual('EPOSTA_GONDERIM_KALDIRILDI', caught.exception.code)
        self.assert_no_effect()

    def test_correspondence_draft_keeps_real_name_version_and_no_send(self):
        result = evaluate(self.store, self.skill_request())
        self.assertEqual('Yazışma Hazırlama', result['skill_name'])
        self.assertTrue(result['chat_response'].startswith(result['startup_message']))
        self.assertEqual([], result['output_ids'])
        self.assertEqual('DISABLED', result['action_execution'])
        self.assertTrue(any('gönderme' in item for item in result['work_plan']))
        self.assert_no_effect()

    def test_router_selects_only_draft_skill_for_s27(self):
        req = self.skill_request('K00')
        req['scenario_id'] = 'S-27'
        result = evaluate(self.store, req)
        self.assertEqual(['K29'], result['selected_skills'])
        self.assertEqual('DISABLED', result['action_execution'])
        self.assert_no_effect()

    def test_unknown_send_alias_and_mailbox_draft_are_schema_rejected(self):
        for alias in ['SEND', 'SEND_MAIL', 'SMTP', 'MAILBOX_DRAFT']:
            denied = copy.deepcopy(self.legacy)
            denied['plan']['action_type'] = alias
            self.assertEqual('BLOCK', self.runtime.evaluate(request=denied)['decision'])
        req = self.skill_request()
        req['mailbox_draft'] = True
        with self.assertRaises(CoreError):
            evaluate(self.store, req)
        self.assert_no_effect()

    def test_model_fields_cannot_restore_send_capability(self):
        for value in [{'approved': True}, {'permission_id': str(uuid4())}, {'enable_email': True}]:
            denied = dict(self.legacy, **value)
            self.assertEqual('BLOCK', self.runtime.evaluate(request=denied)['decision'])
        self.assert_no_effect()

    def test_real_cli_rejects_send_command_and_mail_request(self):
        path = self.sources / 'removed-mail.json'
        path.write_text(canonical(self.legacy), encoding='utf-8')
        base = [sys.executable, '-m', 'sozlesme_cekirdek', '--workspace', str(self.area/'work'), '--output-root', str(self.area), '--source-root', str(self.sources)]
        result = subprocess.run(base+['action-evaluate','--request',str(path)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(0, result.returncode, result.stdout+result.stderr)
        self.assertEqual('BLOCK', json.loads(result.stdout)['result']['decision'])
        result = subprocess.run(base+['send-email'], capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(2, result.returncode)
        self.assert_no_effect()

    def test_shipped_metadata_has_no_send_capability_or_old_skill_folder(self):
        registry = json.loads((ROOT/'references/skill-versions.json').read_text(encoding='utf-8'))
        self.assertEqual('yazisma-hazirlama', registry['K29']['slug'])
        self.assertFalse((ROOT/'skills/yazisma-hazirlama-gonderme').exists())
        schema = json.loads((ROOT/'schemas/p6_skill_request.schema.json').read_text())
        self.assertNotIn('EMAIL_SEND', schema['properties']['requested_output']['enum'])
        self.assertNotIn('SEND_EMAIL', validator('p4_action_request').schema['properties']['plan']['properties']['action_type']['enum'])
        self.assert_no_effect()

    def test_original_catalog_is_preserved_and_current_k29_overrides_it(self):
        original = json.loads((ROOT/'spec/kataloglar/skiller.json').read_text(encoding='utf-8'))
        self.assertEqual('yazisma-hazirlama-gonderme', original[-1]['slug'])
        provenance = json.loads((ROOT/'reports/p0-environment.json').read_text(encoding='utf-8'))
        digest = next(row['sha256'] for row in provenance['packet']['files'] if row['path']=='kataloglar/skiller.json')
        self.assertEqual(digest, hash_file(ROOT/'spec/kataloglar/skiller.json'))
        active = load_catalog()
        self.assertEqual('yazisma-hazirlama', active[-1]['slug'])
        self.assertEqual('Yalnız sohbet içinde yazışma taslağı', active[-1]['outputs'])
        self.assertEqual(original[:-1], active[:-1])


if __name__ == '__main__':
    unittest.main()
