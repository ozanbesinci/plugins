from __future__ import annotations

import argparse
import json
import py_compile
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _frontmatter(skill: Path) -> dict[str, str]:
    text=skill.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise ValueError('SKILL.md frontmatter missing')
    parts=text.split('---\n',2)
    if len(parts)<3:
        raise ValueError('SKILL.md frontmatter not closed')
    out={}
    for line in parts[1].splitlines():
        if ':' in line:
            k,v=line.split(':',1); out[k.strip()]=v.strip().strip('"')
    return out


def check(root: Path) -> dict[str, Any]:
    errors=[]; warnings=[]; checked=0
    skill=root/'SKILL.md'; version=(root/'VERSION').read_text(encoding='utf-8').strip(); checked+=2
    fm=_frontmatter(skill)
    if set(fm)!={'name','description'}:
        errors.append(f"SKILL.md frontmatter must contain only name and description; found {sorted(fm)}")
    if fm.get('name')!='teklif-degerlendirme': errors.append('Unexpected skill name')
    if not (root/'agents'/'openai.yaml').is_file(): errors.append('agents/openai.yaml missing')
    checked+=1
    ch=(root/'CHANGELOG.md').read_text(encoding='utf-8'); checked+=1
    m=re.search(r'(?m)^## v([0-9]+\.[0-9]+\.[0-9]+)\b',ch)
    if not m or m.group(1)!=version: errors.append('VERSION and first CHANGELOG version differ')
    try:
        policy=json.loads((root/'config'/'policy.json').read_text(encoding='utf-8')); checked+=1
        if policy.get('policy_version')!=version: errors.append('policy_version differs from VERSION')
    except Exception as exc: errors.append(f'policy.json invalid: {exc}')
    for jf in sorted((root/'config').glob('*.json')):
        try: json.loads(jf.read_text(encoding='utf-8')); checked+=1
        except Exception as exc: errors.append(f'Invalid JSON {jf.relative_to(root)}: {exc}')
    try:
        bundle=json.loads((root/'config'/'task-result-schemas.json').read_text(encoding='utf-8'))
        for name, raw in bundle.get('tasks',{}).items():
            schema=dict(raw); schema['$defs']=bundle.get('$defs',{}); schema['$schema']=bundle.get('$schema','https://json-schema.org/draft/2020-12/schema')
            Draft202012Validator.check_schema(schema); checked+=1
    except Exception as exc: errors.append(f'LLM schema bundle invalid: {exc}')
    for py in sorted((root/'scripts').rglob('*.py')):
        try: py_compile.compile(str(py),doraise=True); checked+=1
        except Exception as exc: errors.append(f'Python compile failed {py.relative_to(root)}: {exc}')
    body=skill.read_text(encoding='utf-8')
    refs=set(re.findall(r'`((?:scripts|references|config)/[^`\s]+)',body))
    for rel in sorted(refs):
        rel=rel.rstrip('.,;:)')
        if any(x in rel for x in ['<','>','*']):
            continue
        if not (root/rel).exists(): errors.append(f'Referenced path missing: {rel}')
        checked+=1
    req=(root/'requirements.txt').read_text(encoding='utf-8'); checked+=1
    for required in ['duckdb','openpyxl','jsonschema']:
        if not re.search(rf'(?m)^{re.escape(required)}(?:[<>=!~]|\s|$)',req): errors.append(f'requirements.txt missing {required}')
    if len(body.splitlines())>500: warnings.append(f'SKILL.md has {len(body.splitlines())} lines; keep control plane under 500 when possible')
    return {'status':'PASS' if not errors else 'FAIL','version':version,'checked':checked,'errors':errors,'warnings':warnings}


def main():
    ap=argparse.ArgumentParser(description='Self-check teklif-degerlendirme skill before packaging')
    ap.add_argument('--root',default=str(Path(__file__).resolve().parents[1]))
    args=ap.parse_args()
    result=check(Path(args.root))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['status']=='PASS' else 1)

if __name__=='__main__': main()
