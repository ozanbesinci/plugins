"""Apply a coordinator-supplied, actual source-selection reply before dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import sha256_file
from db import connect, rows_as_dict, set_meta
from question_waits import guard_run_operation, run_guarded_main
from run_compatibility import assert_compatible


def _read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _validated_packet(declaration, source_root):
    if declaration.get('schema') != 'teklif-source-selection/v1':
        raise ValueError('Invalid source-selection schema')
    if Path(declaration['source_root']).resolve() != source_root.resolve():
        raise ValueError('Source-selection root changed')
    artifacts = declaration.get('receipt_files', [])
    if len(artifacts) != 3 or {a['role'] for a in artifacts} != {'reply', 'handoff', 'result'}:
        raise ValueError('Actual reply, question scope and sufficiency receipts are required')
    values = {}
    for artifact in artifacts:
        path = Path(artifact['path'])
        if not path.is_file() or sha256_file(path) != artifact['sha256']:
            raise ValueError('Source-selection receipt bytes changed')
        values[artifact['role']] = _read(path)
    reply, handoff, result = (values[k] for k in ('reply', 'handoff', 'result'))
    text = reply.get('actual_user_answer')
    if reply.get('source') != 'actual_user_message_question_reply' or not isinstance(text, str) or not text.strip() or text.strip().casefold() in {'devam', 'continue'}:
        raise ValueError('An actual sufficient source-selection reply is required')
    reply_sha = next(a['sha256'] for a in artifacts if a['role'] == 'reply')
    if result.get('adequate') is not True or result.get('source_selection_only') is not True or result.get('actual_reply_sha256') != reply_sha:
        raise ValueError('Source-selection sufficiency does not match the actual reply')
    selected = declaration.get('selected_sources', [])
    if not selected or len(selected) > 64 or len({s['filename'] for s in selected}) != len(selected):
        raise ValueError('Exact, unique selected sources are required')
    expected = {s['filename']: s['sha256'] for s in selected}
    if set(reply.get('selected_source_filenames', [])) != set(expected):
        raise ValueError('Selection differs from the actual reply scope')
    questions = handoff.get('questions', [])
    if not questions or any(q.get('issue_type') != 'source_authority_conflict' for q in questions):
        raise ValueError('Source-selection questions are required')
    scoped = {s['filename']: s['sha256'] for q in questions for s in q['sources']}
    if scoped != expected:
        raise ValueError('Selection differs from pinned question source bytes')
    answers = result.get('question_responses', [])
    if {a['issue_id'] for a in answers} != {q['issue_id'] for q in questions} or any(a.get('gate', {}).get('state') != 'answered' for a in answers):
        raise ValueError('Every source-selection question must be answered')
    for name, digest in expected.items():
        if name != Path(name).name:
            raise ValueError('Source-selection currently supports exact flat filenames')
        path = (source_root / name).resolve()
        if not path.is_relative_to(source_root.resolve()) or not path.is_file() or sha256_file(path) != digest:
            raise ValueError('Selected source bytes changed')
    return values, expected


@guard_run_operation
def attach(run_root: Path, declaration_path: Path):
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    declaration = _read(declaration_path)
    con = connect(run_root)
    try:
        if con.execute('SELECT 1 FROM task_dispatches LIMIT 1').fetchone():
            raise ValueError('Source selection must precede dispatch; prepare a fresh run')
        row = con.execute("SELECT value FROM run_meta WHERE key='source_root'").fetchone()
        if not row:
            raise ValueError('Prepared source root is required')
        source_root = Path(row[0])
        _, expected = _validated_packet(declaration, source_root)
        documents = rows_as_dict(con, "SELECT document_id,filename,sha256,metadata_json FROM documents WHERE active=true AND document_role='offer'")
        selected = [d for d in documents if d['filename'] in expected]
        if len(selected) != len(expected) or any(d['sha256'] != expected[d['filename']] for d in selected):
            raise ValueError('Selected source does not match the prepared offer')
        prior = con.execute("SELECT value FROM run_meta WHERE key='source_selection_v1'").fetchone()
        if prior:
            existing = json.loads(prior[0])
            if existing.get('declaration_sha256') != sha256_file(declaration_path):
                raise ValueError('Existing source selection cannot be replaced in place')
            return {'status': 'ALREADY_ATTACHED', 'selected_documents': len(selected)}
    finally:
        con.close()
    folder = run_root / 'user_evidence' / 'source_selection'
    folder.mkdir(parents=True, exist_ok=True)
    staged = []
    for artifact in declaration['receipt_files']:
        source = Path(artifact['path'])
        target = folder / (artifact['role'] + '.json')
        target.write_bytes(source.read_bytes())
        if sha256_file(target) != artifact['sha256']:
            raise ValueError('Staged source-selection receipt hash mismatch')
        staged.append({'role': artifact['role'], 'path': str(target.relative_to(run_root)), 'sha256': artifact['sha256']})
    set_meta(run_root, 'source_selection_v1', {
        'schema': declaration['schema'], 'source_type': 'USER_INPUT',
        'source_root': str(source_root.resolve()), 'receipt_files': staged,
        'selected_sources': declaration['selected_sources'],
        'declaration_path': str(declaration_path.resolve()), 'declaration_sha256': sha256_file(declaration_path),
    })
    return {'status': 'ATTACHED_USER_SOURCE_SELECTION', 'selected_documents': len(selected), 'facts_verified': False}


def verified_document_ids(con, run_root):
    row = con.execute("SELECT value FROM run_meta WHERE key='source_selection_v1'").fetchone()
    if not row:
        return set()
    declaration = json.loads(row[0])
    if declaration.get('source_type') != 'USER_INPUT':
        raise ValueError('Invalid source-selection origin')
    artifacts = []
    for item in declaration['receipt_files']:
        path = (run_root / item['path']).resolve()
        if not path.is_relative_to(run_root.resolve()):
            raise ValueError('Source-selection receipt escapes the run')
        artifacts.append({**item, 'path': str(path)})
    packet = {**declaration, 'receipt_files': artifacts}
    _, expected = _validated_packet(packet, Path(declaration['source_root']))
    docs = rows_as_dict(con, 'SELECT document_id,filename,sha256,metadata_json FROM documents WHERE active=true')
    selected = [d for d in docs if d['filename'] in expected]
    if len(selected) != len(expected):
        raise ValueError('Selected source is no longer active')
    for doc in selected:
        relative = json.loads(doc['metadata_json'] or '{}').get('archived_source_path')
        archive = (run_root / relative).resolve() if relative else None
        if doc['sha256'] != expected[doc['filename']] or not archive or not archive.is_relative_to(run_root.resolve()) or not archive.is_file() or sha256_file(archive) != doc['sha256']:
            raise ValueError('Selected archived source bytes changed')
    return {d['document_id'] for d in selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--declaration', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(attach(args.run, args.declaration), ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(run_guarded_main(main))
