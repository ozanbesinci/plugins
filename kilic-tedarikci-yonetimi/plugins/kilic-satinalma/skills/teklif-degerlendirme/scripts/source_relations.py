"""Explicit source relationships; neither filenames nor equal prices authorize one."""
import argparse
import json
from pathlib import Path
from common import json_text, sha256_file, stable_id, utc_now
from db import connect, one_as_dict
from run_compatibility import assert_compatible


def declare(run_root: Path, source_id: str, target_id: str, relation_type: str, declaration: dict) -> str:
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    if relation_type not in {'corroborates', 'supersedes', 'independent_alternative'}:
        raise ValueError('Unsupported explicit source relationship')
    if not declaration.get('authority') or not declaration.get('reason'):
        raise ValueError('Relationship requires explicit authority and reason')
    con = connect(run_root)
    in_transaction = False
    try:
        if con.execute("SELECT 1 FROM task_queue WHERE phase='PREPARE' AND status<>'completed' LIMIT 1").fetchone():
            raise ValueError('Finish PREPARE classification before declaring source relationships')
        if con.execute("SELECT 1 FROM task_dispatches d JOIN task_queue t ON t.task_id=d.task_id WHERE t.phase<>'PREPARE' LIMIT 1").fetchone():
            raise ValueError('Source input window closed by dispatch; preserve context and prepare a fresh run')
        source = one_as_dict(con, 'SELECT * FROM documents WHERE document_id=?', [source_id])
        target = one_as_dict(con, 'SELECT * FROM documents WHERE document_id=?', [target_id])
        if not source or not target or source_id == target_id or source['supplier_id'] != target['supplier_id'] or not source['supplier_id']:
            raise ValueError('Relationship requires two distinct classified sources of the same supplier')
        if any(not d['active'] or not d['offer_id'] or not Path(d['source_path']).is_file() or sha256_file(Path(d['source_path'])) != d['sha256'] for d in (source, target)):
            raise ValueError('Relationship source is inactive, unbound or its bytes changed')
        if source['sha256'] == target['sha256']:
            raise ValueError('Identical source copies are not independent confirmation')
        if relation_type == 'supersedes' and source['offer_id'] == target['offer_id']:
            raise ValueError('Supersession requires distinct commercial offers')
        if con.execute("SELECT 1 FROM task_queue WHERE status='completed' AND phase<>'PREPARE' LIMIT 1").fetchone():
            raise ValueError('Declare relationships before extraction; preserve old reviewed state in a fresh run')
        if relation_type == 'corroborates':
            if declaration.get('same_offer_confirmed') is not True or declaration.get('independent_capture') is not True:
                raise ValueError('Corroboration needs explicit same-offer and independent-capture declarations')
            if source['format_family'] == 'image' or target['format_family'] != 'image' or source['parse_status'] != 'read':
                raise ValueError('Automatic confirmation supports a readable independent structured source for an image offer')
            if con.execute('SELECT 1 FROM source_relations WHERE source_document_id=? OR source_document_id=?', [source_id, target_id]).fetchone():
                raise ValueError('Source already participates as a corroborating source')
        rid = stable_id('relation', source_id, target_id, relation_type, json_text(declaration), length=24)
        con.execute('BEGIN TRANSACTION')
        in_transaction = True
        con.execute('INSERT INTO source_relations(relation_id,source_document_id,target_document_id,relation_type,source_sha256,target_sha256,declaration_json,previous_offer_id,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                    [rid, source_id, target_id, relation_type, source['sha256'], target['sha256'], json_text(declaration), source['offer_id'], utc_now()])
        if relation_type == 'corroborates':
            con.execute("UPDATE documents SET offer_id=?,document_role='support' WHERE document_id=?", [target['offer_id'], source_id])
            if source['offer_id'] != target['offer_id']:
                con.execute("UPDATE offers SET status='linked_support' WHERE offer_id=?", [source['offer_id']])
            ids = json.loads(con.execute('SELECT source_document_ids_json FROM offers WHERE offer_id=?', [target['offer_id']]).fetchone()[0] or '[]')
            con.execute('UPDATE offers SET source_document_ids_json=? WHERE offer_id=?', [json_text(sorted(set(ids+[source_id, target_id]))), target['offer_id']])
        elif relation_type == 'supersedes':
            con.execute("UPDATE offers SET status='superseded' WHERE offer_id=?", [target['offer_id']])
            con.execute("UPDATE documents SET active=false,revision_status='superseded' WHERE offer_id=?", [target['offer_id']])
            con.execute("UPDATE documents SET revision_status='current' WHERE document_id=?", [source_id])
        con.commit()
        return rid
    except Exception:
        if in_transaction:
            con.rollback()
        raise
    finally:
        con.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description='Declare a trusted explicit source relationship before extraction')
    p.add_argument('--run', required=True); p.add_argument('--source-document', required=True); p.add_argument('--target-document', required=True)
    p.add_argument('--relation', required=True, choices=['corroborates','supersedes','independent_alternative']); p.add_argument('--declaration', required=True)
    a = p.parse_args()
    print(declare(Path(a.run), a.source_document, a.target_document, a.relation, json.loads(Path(a.declaration).read_text(encoding='utf-8-sig'))))
