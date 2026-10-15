"""Current skill definitions, without modifying the original handoff snapshot."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_catalog(root=ROOT):
    root = Path(root)
    rows = json.loads((root/'spec/kataloglar/skiller.json').read_text(encoding='utf-8'))
    overrides = json.loads((root/'references/skill-overrides.json').read_text(encoding='utf-8'))['overrides']
    identifiers = {row['id'] for row in rows}
    allowed = {'name', 'slug', 'trigger', 'inputs', 'outputs', 'boundary', 'tools'}
    if set(overrides)-identifiers or any(set(fields)-allowed for fields in overrides.values()):
        raise ValueError('Invalid skill scope override')
    result = [dict(row, **overrides.get(row['id'], {})) for row in rows]
    slugs = [row['slug'] for row in result]
    if len(slugs) != len(set(slugs)) or any(Path(slug).name != slug or '/' in slug or '\\' in slug for slug in slugs):
        raise ValueError('Invalid skill slug')
    return result


def effective_test_scope(root=ROOT):
    """Project historical definitions through current scope, without forging runs."""
    root = Path(root)
    policy = json.loads((root/'references/release-scope.json').read_text(encoding='utf-8'))
    scenarios = json.loads((root/'spec/testler/senaryo_kabul_tanimlari.json').read_text(encoding='utf-8'))
    regressions = json.loads((root/'spec/testler/regresyon_tanimlari.json').read_text(encoding='utf-8'))
    result = []
    for row in scenarios:
        effective = dict(row, **policy['scenario_overrides'].get(row['id'], {}))
        status = 'BUSINESS_CONFIRMATION_PENDING' if row['scenario_id'] == 'S-20' else 'IN_SCOPE'
        result.append({'original_id': row['id'], 'scenario_id': row['scenario_id'], 'original': row,
                       'effective': effective, 'scope_status': status, 'execution_status': 'NOT_RUN',
                       'reason': 'Company own-policy scope requires explicit business decision' if status != 'IN_SCOPE' else
                                 ('Current K29 chat-only override' if row['id'] in policy['scenario_overrides'] else 'Current unchanged scope')})
    removed = set(policy['original_regressions_out_of_scope'])
    for row in regressions:
        entry = {'original_id': row['id'], 'original': row, 'scope_status': 'OUT_OF_SCOPE' if row['id'] in removed else 'IN_SCOPE',
                 'execution_status': 'UYGULANAMAZ' if row['id'] in removed else 'NOT_RUN',
                 'reason': 'Removed external email action; not a missing feature' if row['id'] in removed else 'Historical test definition is not an executed product test'}
        if row['id'] == 'T42':
            entry.update(scope_status='REPLACED_CURRENT_TEST', execution_status='NOT_RUN',
                         current_test_id='test_guard.GuardTests.test_real_two_process_replay_race_only_one_document_effect',
                         reason='Historical send example preserved; current scope tests document replay separately')
        result.append(entry)
    return {'schema': 'contract-effective-test-scope/v1', 'scope_version': policy['scope_version'],
            'removed_actions': policy['removed_actions'], 'records': result, 'product_acceptance': 'NOT_GRANTED'}
