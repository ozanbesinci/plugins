"""Pin execution and dispatched response contracts before canonical writes."""
import hashlib
import json
from pathlib import Path
from common import json_text, sha256_file, utc_now
from db import connect


def execution_contract(skill_root: Path) -> dict:
    files = {}
    for folder in ('scripts', 'config'):
        for p in sorted((skill_root / folder).rglob('*')):
            if p.is_file() and p.suffix in {'.py', '.json', '.sql'} and 'tests' not in p.parts and '__pycache__' not in p.parts:
                files[p.relative_to(skill_root).as_posix()] = sha256_file(p)
    return {'schema': 'teklif-execution/v1', 'files': files, 'sha256': hashlib.sha256(json_text(files).encode()).hexdigest()}


def assert_compatible(run_root: Path, skill_root: Path) -> None:
    con = connect(run_root)
    try:
        row = con.execute("SELECT value FROM run_meta WHERE key='execution_contract'").fetchone()
        if not row:
            # Unversioned in-memory/unit fixtures have no production prepare.
            if con.execute("SELECT 1 FROM run_meta WHERE key='skill_version'").fetchone():
                raise ValueError('Run has no compatibility manifest; preserve it and prepare a fresh run')
            return
        pinned = json.loads(row[0])
        current = execution_contract(skill_root)
        if pinned.get('sha256') != current['sha256']:
            changed = sorted(k for k in set(pinned.get('files', {})) | set(current['files']) if pinned.get('files', {}).get(k) != current['files'].get(k))
            raise ValueError('Incompatible run contract; no canonical write performed. Changed: ' + ', '.join(changed))
    finally:
        con.close()


def pin_dispatch(run_root: Path, task: dict, context: Path, skill_root: Path) -> None:
    con = connect(run_root)
    try:
        row = con.execute('SELECT packet_sha256 FROM task_dispatches WHERE task_id=?', [task['task_id']]).fetchone()
        packet_sha = sha256_file(context)
        if row and row[0] != packet_sha:
            raise ValueError('Previously dispatched task packet changed; create a new task/run')
        if row:
            assert_dispatch(run_root, task['task_id'], skill_root)
            return
        con.execute('INSERT OR REPLACE INTO task_dispatches(task_id,packet_sha256,schema_sha256,execution_sha256,context_path,created_at) VALUES (?,?,?,?,?,?)',
                    [task['task_id'], packet_sha, sha256_file(skill_root/'config/task-result-schemas.json'), execution_contract(skill_root)['sha256'], str(context.relative_to(run_root)), utc_now()])
        con.commit()
    finally:
        con.close()


def business_packet(value):
    """Exclude only assessment timestamps, never source/price/input semantics."""
    volatile={'attempts','assessed_at','created_at','updated_at','generated_at','validated_at','completed_at','started_at','recorded_at','checked_at'}
    if isinstance(value,dict):
        return {k:business_packet(v) for k,v in value.items() if k not in volatile}
    if isinstance(value,list):return [business_packet(v) for v in value]
    if isinstance(value,str) and value.strip().startswith(('{','[')):
        try:return business_packet(json.loads(value))
        except json.JSONDecodeError:pass
    return value


def assert_dispatch(run_root: Path, task_id: str, skill_root: Path) -> None:
    assert_compatible(run_root, skill_root)
    con = connect(run_root)
    try:
        row = con.execute('SELECT packet_sha256,schema_sha256,execution_sha256,context_path FROM task_dispatches WHERE task_id=?', [task_id]).fetchone()
        production = con.execute("SELECT 1 FROM run_meta WHERE key='execution_contract'").fetchone()
        if not row:
            if production:
                raise ValueError('Result has no dispatched context contract')
            return
        path = run_root/row[3]
        if not path.is_file() or sha256_file(path) != row[0] or sha256_file(skill_root/'config/task-result-schemas.json') != row[1] or execution_contract(skill_root)['sha256'] != row[2]:
            raise ValueError('Stale dispatch packet/schema/execution contract; result rejected before write')
        packet = json.loads(path.read_text(encoding='utf-8'))
        if packet.get('task', {}).get('task_id') != task_id:
            raise ValueError('Dispatch task identity mismatch')
    finally:
        con.close()
