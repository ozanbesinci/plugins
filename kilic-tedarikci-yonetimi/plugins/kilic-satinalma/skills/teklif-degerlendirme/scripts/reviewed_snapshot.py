from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
from common import json_text, sha256_file, stable_id, utc_now
from active_records import current_calculations, current_claims
from db import connect, get_meta, rows_as_dict


def _decode_rows(rows:list[dict[str,Any]], fields:list[str])->list[dict[str,Any]]:
    out=[]
    for row in rows:
        r=dict(row)
        for f in fields:
            if f in r and isinstance(r[f],str):
                try: r[f[:-5] if f.endswith('_json') else f]=json.loads(r[f])
                except Exception: pass
        out.append(r)
    return out


def _stable_rows(con, table:str, order:str, columns:str='*')->list[dict[str,Any]]:
    return rows_as_dict(con,f'SELECT {columns} FROM {table} ORDER BY {order}')


def decision_preflight_from_connection(con) -> dict[str, Any]:
    """Read decision limitations identically before dispatch and before output."""
    def meta(key, default):
        row=con.execute('SELECT value FROM run_meta WHERE key=?',[key]).fetchone()
        if not row: return default
        if isinstance(default,dict):
            try: return json.loads(row[0])
            except (TypeError,ValueError): return default
        return row[0]
    preliminary=[]
    if con.execute("SELECT count(*) FROM independent_calculations WHERE status='unverified'").fetchone()[0]:
        preliminary.append('independent recomputation has unverified checks')
    if con.execute("SELECT count(*) FROM cost_bridges WHERE status='unverified'").fetchone()[0]:
        preliminary.append('cost bridge has unverified checks')
    status=str(meta('decision_status','UNKNOWN'))
    if status!='SUFFICIENT': preliminary.append('decision sufficiency is preliminary')
    if not meta('comparability_contract',{}).get('ranking_allowed'):
        preliminary.append('comparison contract does not allow ranking')
    scope=meta('scope_ledger',{})
    if scope.get('status') in {'BLOCKED','PARTIAL'}:
        preliminary.append(f"scope ledger is {scope.get('status')}")
    return {'deterministic_decision_status':status,
            'decision_status':'PRELIMINARY_ONLY' if preliminary else status,
            'recommendation_must_be_null':bool(preliminary),
            'preliminary_reasons':sorted(set(preliminary)), 'scope_ledger':scope}


def freeze(run_root:Path)->dict[str,Any]:
    con=connect(run_root)
    try:
        blockers=[]; preliminary=[]
        pending=con.execute("SELECT count(*) FROM task_queue WHERE status='pending'").fetchone()[0]
        diffs=con.execute("SELECT count(*) FROM differences WHERE status='open'").fetchone()[0]
        if pending: blockers.append(f'{pending} pending model task(s)')
        if diffs: blockers.append(f'{diffs} open adjudication difference(s)')
        indep=rows_as_dict(con,"SELECT status,count(*) AS n FROM independent_calculations GROUP BY status")
        if any(r['status']=='fail' for r in indep): blockers.append('independent recomputation failed')
        if any(r['status']=='unverified' for r in indep): preliminary.append('independent recomputation has unverified checks')
        grains=rows_as_dict(con,"SELECT relation_name,status,critical FROM grain_checks ORDER BY relation_name")
        if any(r['critical'] and r['status']!='pass' for r in grains): blockers.append('critical grain/join integrity check failed')
        bridges=rows_as_dict(con,"SELECT offer_id,status,residual,tolerance FROM cost_bridges ORDER BY offer_id")
        if any(r['status']=='fail' for r in bridges): blockers.append('cost bridge residual exceeds tolerance')
        if any(r['status']=='unverified' for r in bridges): preliminary.append('cost bridge has unverified checks')
        claim_state=get_meta(run_root,'claim_registry_status',{},parse_json=True) or {}
        if claim_state.get('status')=='FAIL': blockers.append('claim registry contains unsupported claim(s)')
        dq=rows_as_dict(con,"SELECT check_id,entity_id,severity,status FROM data_quality_findings WHERE status='open' ORDER BY severity,check_id,entity_id")
        if any(r['severity']=='critical' for r in dq): blockers.append('critical data-quality finding remains open')
        decision_status=str(get_meta(run_root,'decision_status','UNKNOWN'))
        if decision_status!='SUFFICIENT': preliminary.append('decision sufficiency is preliminary')
        comp=get_meta(run_root,'comparability_contract',{},parse_json=True) or {}
        if not comp.get('ranking_allowed'): preliminary.append('comparison contract does not allow ranking')
        scope=get_meta(run_root,'scope_ledger',{},parse_json=True) or {}
        if scope.get('status') in {'BLOCKED','PARTIAL'}: preliminary.append(f"scope ledger is {scope.get('status')}")
        preliminary=decision_preflight_from_connection(con)['preliminary_reasons']
        recommendation_raw=get_meta(run_root,'decision_recommendation','null')
        try: recommendation=json.loads(recommendation_raw)
        except Exception: recommendation=recommendation_raw
        if preliminary and recommendation is not None: blockers.append('recommendation is non-null while pre-output conditions are preliminary')
        if blockers:
            result={'status':'BLOCKED','blocking_reasons':sorted(set(blockers)),'preliminary_reasons':sorted(set(preliminary)),'frozen':False}
            p=run_root/'qa'/'reviewed_snapshot_gate.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            return result

        # Stable content only: omit generation timestamps so unchanged reviewed inputs preserve the same snapshot hash.
        tables={
            'documents': _stable_rows(con,'documents','relative_path','document_id,parent_document_id,relative_path,filename,extension,mime_type,format_family,document_role,role_confidence,supplier_id,offer_id,revision_label,revision_status,sha256,size_bytes,parser_name,parser_version,parse_status,parse_notes,metadata_json,active'),
            'suppliers': _stable_rows(con,'suppliers','supplier_id'),
            'offers': _stable_rows(con,'offers','supplier_id,offer_id'),
            'requirements': _stable_rows(con,'requirements','requirement_id'),
            'evidence': _stable_rows(con,'evidence','evidence_id'),
            'facts': _stable_rows(con,'facts','offer_id,field_key,fact_id','fact_id,offer_id,supplier_id,requirement_id,field_key,value_text,value_number,value_date,unit,currency,evidence_status,critical,evidence_id,extraction_path,normalized_json'),
            'scope_items': _stable_rows(con,'scope_items','offer_id,scope_id'),
            'source_relations': _stable_rows(con,'source_relations','relation_id'),
            'fact_confirmations': _stable_rows(con,'fact_confirmations','confirmation_id'),
            'exclusions': _stable_rows(con,'exclusions','offer_id,requirement_id,exclusion_id'),
            'calculations': current_calculations(con,'calculation_id,offer_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status'),
            'open_issues': _stable_rows(con,'open_issues','status,severity,issue_id','issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status'),
            'source_authority': _stable_rows(con,'source_authority','document_id','document_id,authority_scope,authority_class,authority_status,precedence_rank,rationale,assessed_by'),
            'data_quality_findings': _stable_rows(con,'data_quality_findings','severity,check_id,entity_id','finding_id,check_id,entity_type,entity_id,severity,confidence,status,evidence_json,risk,remediation,finding_hash'),
            'comparability_checks': _stable_rows(con,'comparability_checks','dimension,offer_id,check_id','check_id,dimension,offer_id,reference_value,observed_value,status,critical,normalization,evidence_json,revision'),
            'independent_calculations': _stable_rows(con,'independent_calculations','offer_id,calculation_type,independent_id','independent_id,calculation_id,offer_id,calculation_type,method,expected_json,recomputed_json,tolerance,status,detail_json,input_hash'),
            'cost_bridges': _stable_rows(con,'cost_bridges','offer_id','bridge_id,offer_id,currency,stated_total,bridge_total,comparable_total,residual,tolerance,status,components_json,calculation_id,revision'),
            'claims': current_claims(con,'claim_id,claim_type,claim_text,support_status,fact_ids_json,calculation_ids_json,requirement_ids_json,evidence_ids_json,assertions_json,caveat,source_task_id,revision'),
            'scope_ledger': _stable_rows(con,'scope_ledger','scope_type,entity_id,scope_item_id','scope_item_id,scope_type,entity_id,label,expected_json,observed_json,status,critical,evidence_json,revision'),
            'grain_checks': _stable_rows(con,'grain_checks','relation_name,check_id','check_id,check_type,relation_name,expected_grain,rows_before,rows_after,distinct_keys_before,distinct_keys_after,expansion_factor,status,critical,evidence_json,revision'),
        }
        meta={k:get_meta(run_root,k,None) for k in ['skill_version','profile','analysis_date','policy_sha256','decision_status','decision_sufficiency','decision_summary','decision_recommendation','financial_parameters','scoring_parameters','comparability_contract','independent_confirmation_issue_resolutions','parent_user_response']}
        # Drop volatile assessment timestamps from stored JSON metadata.
        try:
            comp_meta=json.loads(meta.get('comparability_contract') or '{}')
            if isinstance(comp_meta,dict):
                comp_meta.pop('assessed_at',None)
                for check in comp_meta.get('checks',[]):
                    check.pop('assessed_at',None)
                meta['comparability_contract']=json_text(comp_meta)
        except Exception:
            pass
        payload={'schema':'teklif-reviewed-snapshot/v1','status':'PRELIMINARY' if preliminary else 'READY','preliminary_reasons':sorted(set(preliminary)),'meta':meta,**tables}
        source_revision=hashlib.sha256(json_text(payload).encode()).hexdigest()
        payload['source_revision']=source_revision
        # Content-address the immutable reviewed snapshot. If the exact stable
        # source revision was frozen before, reuse it instead of rewriting a
        # mutable singleton path.
        prior=con.execute("SELECT snapshot_id,relative_path,sha256,status FROM reviewed_snapshots WHERE source_revision=? ORDER BY created_at DESC LIMIT 1",[source_revision]).fetchone()
        if prior:
            prior_path=run_root/prior[1]
            if prior_path.exists() and sha256_file(prior_path)==prior[2]:
                con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('reviewed_snapshot',?)",[json_text({'snapshot_id':prior[0],'path':prior[1],'sha256':prior[2],'status':prior[3],'source_revision':source_revision})])
                if hasattr(con,'commit'): con.commit()
                return {'status':prior[3],'frozen':True,'snapshot_id':prior[0],'path':str(prior_path),'sha256':prior[2],'source_revision':source_revision,'preliminary_reasons':payload['preliminary_reasons'],'reused':True}
        out_dir=run_root/'reviewed'; out_dir.mkdir(parents=True,exist_ok=True); path=out_dir/f"reviewed_snapshot_{source_revision[:24]}.json"
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        sha=sha256_file(path); sid=stable_id('snapshot',source_revision,sha,length=24)
        con.execute('INSERT OR REPLACE INTO reviewed_snapshots(snapshot_id,relative_path,sha256,status,source_revision,decision_status,created_at) VALUES (?,?,?,?,?,?,?)',[sid,str(path.relative_to(run_root)),sha,payload['status'],source_revision,decision_status,utc_now()])
        aid=stable_id('art','reviewed_snapshot',sha,length=22)
        con.execute('INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)',[aid,'reviewed_snapshot',str(path.relative_to(run_root)),sha,'[]','ready',utc_now()])
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('reviewed_snapshot',?)",[json_text({'snapshot_id':sid,'path':str(path.relative_to(run_root)),'sha256':sha,'status':payload['status'],'source_revision':source_revision})])
        if hasattr(con,'commit'): con.commit()
        return {'status':payload['status'],'frozen':True,'snapshot_id':sid,'path':str(path),'sha256':sha,'source_revision':source_revision,'preliminary_reasons':payload['preliminary_reasons']}
    finally: con.close()


def load_latest(run_root:Path)->tuple[dict[str,Any],dict[str,Any]]:
    con=connect(run_root)
    try:
        pointer_row=con.execute("SELECT value FROM run_meta WHERE key='reviewed_snapshot'").fetchone()
        pointer=json.loads(pointer_row[0]) if pointer_row else None
        if pointer is not None:
            if not isinstance(pointer,dict) or not pointer.get('snapshot_id'): raise RuntimeError('invalid active reviewed snapshot pointer')
            rows=rows_as_dict(con,"SELECT * FROM reviewed_snapshots WHERE snapshot_id=?",[pointer['snapshot_id']])
            if not rows or rows[0]['sha256']!=pointer.get('sha256') or rows[0]['relative_path']!=pointer.get('path'): raise RuntimeError('active reviewed snapshot pointer mismatch')
        else:
            rows=rows_as_dict(con,"SELECT * FROM reviewed_snapshots ORDER BY created_at DESC,snapshot_id DESC")
        if not rows: raise RuntimeError('reviewed snapshot missing')
        row=rows[0]; path=run_root/row['relative_path']
        if not path.exists() or sha256_file(path)!=row['sha256']: raise RuntimeError('reviewed snapshot hash mismatch')
        return json.loads(path.read_text(encoding='utf-8')),row
    finally: con.close()

def main():
    ap=argparse.ArgumentParser(description='Freeze immutable pre-output reviewed procurement snapshot'); ap.add_argument('--run',required=True); a=ap.parse_args(); print(json.dumps(freeze(Path(a.run)),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
