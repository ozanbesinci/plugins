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
