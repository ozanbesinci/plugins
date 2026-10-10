"""Read-only re-entry check; an old verification label is not approval."""
import json
import hashlib
from pathlib import Path
from common import json_text, sha256_file, stable_id, utc_now
from db import connect, rows_as_dict
from active_records import current_artifacts, current_calculations, current_claims
from reviewed_snapshot import load_latest


def _closed_state(con) -> str:
    tables = ['documents','document_units','suppliers','offers','requirements','evidence','facts','scope_items','source_relations','fact_confirmations','exclusions','calculations','open_issues','source_authority','data_quality_findings','comparability_checks','independent_calculations','cost_bridges','claims','scope_ledger','grain_checks','task_queue','task_dispatches','workflow_state','artifact_bindings','render_hashes','qa_findings']
    payload = {t:sorted(map(json_text,rows_as_dict(con,f'SELECT * FROM {t}'))) for t in tables}
    for table in ['model_receipts','llm_result_validations','differences','reviewed_snapshots']:
        payload[table]=sorted(map(json_text,rows_as_dict(con,f'SELECT * FROM {table}')))
    payload['run_meta'] = sorted(map(json_text,rows_as_dict(con,"SELECT key,value FROM run_meta WHERE key<>'closure_contract'")))
    return hashlib.sha256(json_text(payload).encode()).hexdigest()


def freeze_closure(run_root: Path) -> None:
    con=connect(run_root)
    try:
        payload={'schema':'teklif-closure/v1','closed_state_sha256':_closed_state(con),
                 'artifacts':{k:{'relative_path':v['relative_path'],'sha256':v['sha256']} for k,v in current_artifacts(con).items() if k!='closure_contract'}}
        path=run_root/'output/closure_contract.json'
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        sha=sha256_file(path)
        con.execute('INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)',[stable_id('art','closure',sha,length=22),'closure_contract',str(path.relative_to(run_root)),sha,'[]','ready',utc_now()])
        con.commit()
    finally:con.close()


def inspect_closure(run_root: Path) -> list[str]:
    try:
        return _inspect_closure(run_root)
    except (json.JSONDecodeError, OSError) as exc:
        return [f'closed evidence cannot be read: {type(exc).__name__}']


def _inspect_closure(run_root: Path) -> list[str]:
    errors = []
    try:
        snap, snapshot_row = load_latest(run_root)
    except (RuntimeError, ValueError, OSError):
        return ["reviewed snapshot missing or invalid"]
    con = connect(run_root)
    try:
        if con.execute("SELECT count(*) FROM task_queue WHERE status='pending'").fetchone()[0]:
            errors.append("pending model tasks")
        artifacts = current_artifacts(con)
        closure = artifacts.get('closure_contract')
        if not closure:
            return ['final closure contract missing']
        closure_path=run_root/closure['relative_path']
        if not closure_path.is_file() or sha256_file(closure_path)!=closure['sha256']:
            return ['final closure contract hash mismatch']
        contract=json.loads(closure_path.read_text(encoding='utf-8'))
        if contract.get('closed_state_sha256')!=_closed_state(con):
            errors.append('closed canonical/workflow/QA state changed')
        observed={k:{'relative_path':v['relative_path'],'sha256':v['sha256']} for k,v in artifacts.items() if k!='closure_contract'}
        if observed!=contract.get('artifacts'):
            errors.append('closed artifact inventory changed')
        required = {"xlsx", "verification", "cross_output_consistency", "provenance_survival", "coverage", "scope_ledger_final"}
        profile = con.execute("SELECT value FROM run_meta WHERE key='profile'").fetchone()
        if profile and profile[0] == "yuksek_guvence":
            required.add("pdf")
        if not required.issubset(artifacts):
            errors.append("required artifact missing")
        for kind, row in artifacts.items():
            path = run_root / row['relative_path']
            if not path.is_file() or sha256_file(path) != row['sha256']:
                errors.append(f"artifact hash mismatch: {kind}")
            if kind in {"xlsx", "pdf"} and snapshot_row['sha256'] not in json.loads(row.get('parent_hashes_json') or '[]'):
                errors.append(f"artifact snapshot mismatch: {kind}")
        # Compare the exact stable column projection frozen for each business
        # table, never generation timestamps or unrelated historical rows.
        tables = ['documents', 'suppliers', 'offers', 'requirements', 'evidence', 'facts', 'scope_items', 'exclusions', 'calculations', 'open_issues', 'source_authority', 'comparability_checks', 'independent_calculations', 'cost_bridges', 'claims', 'grain_checks', 'source_relations', 'fact_confirmations']
        for table in tables:
            frozen = snap.get(table)
            if frozen is None:
                continue
            if frozen:
                columns = ','.join(frozen[0])
                actual = current_calculations(con, columns) if table == 'calculations' else current_claims(con, columns) if table == 'claims' else rows_as_dict(con, f'SELECT {columns} FROM {table}')
            else:
                actual = current_calculations(con) if table == 'calculations' else current_claims(con) if table == 'claims' else rows_as_dict(con, f'SELECT * FROM {table}')
            if sorted(map(json_text, actual)) != sorted(map(json_text, frozen)):
                errors.append(f"live records differ from snapshot: {table}")
        for row in rows_as_dict(con,'SELECT source_path,sha256 FROM documents WHERE parent_document_id IS NULL'):
            path=Path(row['source_path']) if row['source_path'] else None
            if not path or not path.is_file() or sha256_file(path)!=row['sha256']:
                errors.append('closed source bytes changed')
        for doc in rows_as_dict(con,'SELECT document_id,sha256,metadata_json FROM documents WHERE active=true'):
            meta=json.loads(doc.get('metadata_json') or '{}')
            archived=meta.get('archived_source_path')
            path=run_root/archived if archived else None
            if not path or not path.is_file() or sha256_file(path)!=doc['sha256']:
                errors.append('closed source archive missing or changed')
        parent=con.execute("SELECT value FROM run_meta WHERE key='parent_user_response'").fetchone()
        if parent:
            response=json.loads(parent[0]); response_path=Path(str(response.get('path') or ''))
            if not response_path.is_file() or sha256_file(response_path)!=response.get('sha256'):
                errors.append('parent user response record missing or changed')
        for row in rows_as_dict(con,'SELECT task_id,context_path,packet_sha256 FROM task_dispatches'):
            path=run_root/row['context_path']
            if not path.is_file() or sha256_file(path)!=row['packet_sha256']:
                errors.append('closed dispatched context changed')
        from llm_result_validate import result_hash
        for row in rows_as_dict(con,"SELECT task_id,result_path FROM task_queue WHERE status='completed' AND result_path IS NOT NULL"):
            path=Path(row['result_path'])
            if not path.is_absolute():path=run_root/path
            expected=con.execute("SELECT result_sha256 FROM llm_result_validations WHERE task_id=? AND status='PASS' ORDER BY validated_at DESC LIMIT 1",[row['task_id']]).fetchone()
            if not expected or not path.is_file():
                errors.append('closed task result/validation missing')
            elif result_hash(json.loads(path.read_text(encoding='utf-8-sig')))!=expected[0]:
                errors.append('closed model result changed')
        return errors
    finally:
        con.close()
