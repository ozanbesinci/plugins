from __future__ import annotations

from question_waits import guard_run_operation
import argparse, hashlib, json, re
from pathlib import Path
from typing import Any
from common import json_text, sha256_file, stable_id, utc_now
from db import connect, get_meta, rows_as_dict
from buyer_inputs import inputs_for
from active_records import current_calculations

BAD={'missing','unreadable','conflicting','requires_confirmation'}
REQ_FIELDS=('total','currency','payment','delivery','quote_date','validity')

def _hash(x:Any)->str: return hashlib.sha256(json_text(x).encode()).hexdigest()


BUYER_FIELDS={'currency':'currency','payment':'payment_terms','warranty':'warranty_terms','validity':'validity_date','quote_date':'quote_date'}


def buyer_authority(con, offer_id: str, field: str) -> dict[str, Any] | None:
    """Inspect a scoped buyer decision basis, separate from supplier evidence."""
    kind=BUYER_FIELDS.get(field)
    if not kind:
        return None
    try:
        declarations = inputs_for(con, offer_id, kind)
    except (ValueError, OSError):
        return None
    if len(declarations) != 1:
        return None
    item = declarations[0]
    if (item.get('offer_id')!=offer_id or item.get('kind')!=kind or
            not item.get('issue_id') or not item.get('scope_sha256') or
            not isinstance(item.get('source_hashes'),dict) or not item['source_hashes']):
        return None
    rows = [r for r in current_calculations(con) if r.get('offer_id')==offer_id and r.get('calculation_type')=='cost_summary']
    if len(rows) != 1 or rows[0].get('status') != 'complete':
        return None
    try:
        result = json.loads(rows[0]['result_json'])
    except (TypeError, ValueError):
        return None
    applied = item in (result.get('buyer_inputs') or {}).get(kind, [])
    if kind=='currency':
        applied = applied and result.get('currency_basis')=='buyer_declaration' and result.get('currency')==item.get('value') and isinstance(item.get('value'),str) and bool(re.fullmatch(r'[A-Z]{3}',item['value']))
    elif kind in {'validity_date', 'quote_date'}:
        applied = applied and result.get(kind+'_basis')=='buyer_declaration' and result.get(kind)=={'date_status':item.get('date_status'),'value':item.get('value')}
    elif kind=='payment_terms':
        applied = applied and result.get('payment_basis')=='buyer_declaration' and result.get('payment_terms')=={'milestones':item.get('milestones')}
    else:
        applied = applied and result.get('warranty_basis')=='buyer_declaration' and result.get('warranty_terms')=={'duration_years':item.get('duration_years'),'scope':item.get('scope')}
    if not applied:
        return None
    independent=rows_as_dict(con,"SELECT independent_id,calculation_id,input_hash,status FROM independent_calculations WHERE calculation_id=? AND offer_id=?",[rows[0]['calculation_id'],offer_id])
    if len(independent)!=1 or independent[0].get('status')!='pass' or independent[0].get('input_hash')!=rows[0].get('input_hash'):
        return None
    events=rows_as_dict(con,"SELECT event_type,payload_json FROM workflow_events WHERE event_type IN ('buyer_response_applied','buyer_response_applied_derived','buyer_date_basis_applied','buyer_basis_applied')")
    matched=False
    for event in events:
        try: payload=json.loads(event['payload_json'])
        except (TypeError,ValueError): continue
        if payload.get('supplier_facts_modified') is not False or payload.get('buyer_inputs')!=[item]:
            continue
        if event['event_type']=='buyer_basis_applied':
            if (payload.get('resolution_basis')=='source_hashed_buyer_basis_applied' and
                    payload.get('issue_id')==item['issue_id'] and payload.get('scope_sha256')==item['scope_sha256']):
                matched=True; break
        elif event['event_type']=='buyer_date_basis_applied':
            if (kind in {'validity_date','quote_date'} and
                    payload.get('resolution_basis')=='source_hashed_buyer_date_basis_applied' and
                    payload.get('issue_id')==item['issue_id'] and payload.get('scope_sha256')==item['scope_sha256']):
                matched=True; break
        elif event['event_type']=='buyer_response_applied':
            if payload.get('issue_id')==item['issue_id'] and payload.get('scope_sha256')==item['scope_sha256']:
                matched=True; break
        elif kind in {'currency','validity_date','quote_date'} and event['event_type']=='buyer_response_applied_derived':
            expected_basis='same_source_hashed_currency_declaration_applied' if kind=='currency' else 'same_source_hashed_buyer_terms_applied'
            if (payload.get('resolution_basis')!=expected_basis or
                    payload.get('issue_id')==item['issue_id'] or not payload.get('scope_sha256') or
                    payload.get('original_answer_issue_ids')!=[item['issue_id']]):
                continue
            issue=rows_as_dict(con,"SELECT issue_id,status,issue_type,fact_ids_json FROM open_issues WHERE issue_id=?",[payload['issue_id']])
            if len(issue)!=1 or issue[0].get('status')!='resolved' or issue[0].get('issue_type') in {'comparability_contract','scope_comparability','payment_comparability'}:
                continue
            try: refs=json.loads(issue[0]['fact_ids_json'])
            except (TypeError,ValueError): continue
            if refs==[f"{offer_id}/field/{field}"]:
                matched=True; break
    if not matched:
        return None
    return {'kind':kind,'field':field,'method':'deterministic_buyer_authority',
            'value':item.get('value') if kind=='currency' else {k:item.get(k) for k in (('milestones',) if kind=='payment_terms' else ('date_status','value') if kind in {'validity_date','quote_date'} else ('duration_years','scope'))},
            'issue_id':item['issue_id'],'scope_sha256':item['scope_sha256'],
            'source_hashes':item['source_hashes'],'calculation_id':rows[0]['calculation_id'],
            'independent_id':independent[0]['independent_id']}


def buyer_currency_authority(con, offer_id: str) -> dict[str, Any] | None:
    return buyer_authority(con,offer_id,'currency')

@guard_run_operation
def build(run_root:Path, final:bool=False)->dict[str,Any]:
    con=connect(run_root)
    try:
        con.execute('DELETE FROM scope_ledger')
        units=[]
        def add(scope_type:str, entity_id:str|None,label:str,expected:Any,observed:Any,status:str,critical:bool,evidence:Any):
            rev=_hash({'scope_type':scope_type,'entity_id':entity_id,'expected':expected,'observed':observed,'evidence':evidence})
            sid=stable_id('scope',scope_type,entity_id or label,rev,length=24)
            row={'scope_item_id':sid,'scope_type':scope_type,'entity_id':entity_id,'label':label,'expected_json':json_text(expected),'observed_json':json_text(observed),'status':status,'critical':critical,'evidence_json':json_text(evidence),'revision':rev,'updated_at':utc_now()}
            units.append(row)
            con.execute('INSERT INTO scope_ledger(scope_item_id,scope_type,entity_id,label,expected_json,observed_json,status,critical,evidence_json,revision,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',[row[k] for k in ['scope_item_id','scope_type','entity_id','label','expected_json','observed_json','status','critical','evidence_json','revision','updated_at']])
        docs=rows_as_dict(con,"SELECT document_id,relative_path,document_role,parse_status,active FROM documents WHERE active=true ORDER BY relative_path")
        contract=get_meta(run_root,'run_contract',{},parse_json=True) or {}
        expected_sources=contract.get('expected_sources') if isinstance(contract.get('expected_sources'),list) else []
        top_docs=rows_as_dict(con,"SELECT document_id,relative_path,sha256 FROM documents WHERE active=true AND parent_document_id IS NULL ORDER BY relative_path")
        top_by_path={str(x.get('relative_path')):x for x in top_docs}
        for exp in expected_sources:
            rel=str(exp.get('relative_path') or '')
            obs=top_by_path.get(rel)
            ok=bool(obs and obs.get('sha256')==exp.get('sha256'))
            add('source_inventory',rel,rel,{'sha256':exp.get('sha256'),'size_bytes':exp.get('size_bytes')},{'present':bool(obs),'document_id':obs.get('document_id') if obs else None,'sha256':obs.get('sha256') if obs else None},'pass' if ok else 'fail',True,[f"document:{obs['document_id']}"] if obs else [])
        for d in docs:
            role=d.get('document_role') or 'unknown'; parse=d.get('parse_status') or 'unknown'
            critical=role in {'offer','specification','boq','unknown'}
            status='pass'
            if role=='unknown': status='unverified'
            if parse=='unreadable' and critical: status='fail'
            add('document',d['document_id'],d['relative_path'],{'accounted':True},{'role':role,'parse_status':parse},status,critical,[f"document:{d['document_id']}"])
        offers=rows_as_dict(con,"SELECT offer_id,supplier_id,status FROM offers WHERE status='active' ORDER BY offer_id")
        facts=rows_as_dict(con,"SELECT fact_id,offer_id,field_key,evidence_status FROM facts WHERE offer_id IS NOT NULL ORDER BY fact_id")
        by={(f['offer_id'],f['field_key']):f for f in facts}
        for o in offers:
            missing=[]; bad=[]; ev=[]; buyer_basis={}; missing_source=[]
            for field in REQ_FIELDS:
                from effective_fields import basis as effective_basis
                effective=effective_basis(con,o['offer_id'],field)
                if effective:
                    buyer_basis[field]=effective
                    f=by.get((o['offer_id'],field))
                    if not f or f.get('evidence_status') in BAD:missing_source.append(field)
                    ev.extend([f"calculation:{effective['calculation_id']}",f"independent:{effective['independent_id']}"])
                    continue
                if field in {'validity','quote_date'}:
                    basis=buyer_authority(con,o['offer_id'],field)
                    if basis:
                        buyer_basis[field]=basis
                        ev.extend([f"buyer_issue:{basis['issue_id']}",f"calculation:{basis['calculation_id']}"])
                        if basis['value']['date_status']=='unknown':
                            missing_source.append(field)
                        # The effective buyer date replaces the evaluation basis,
                        # without changing the original source field/status.
                        continue
                f=by.get((o['offer_id'],field))
                if not f: missing.append(field)
                elif f.get('evidence_status') in BAD:
                    ev.append(f"fact:{f['fact_id']}")
                    if field in {'currency','payment'} and f.get('evidence_status') in {'missing','requires_confirmation'}:
                        basis=buyer_authority(con,o['offer_id'],field)
                        if basis:
                            buyer_basis[field]=basis; missing_source.append(field)
                            ev.extend([f"buyer_issue:{basis['issue_id']}",f"calculation:{basis['calculation_id']}"])
                            continue
                    bad.append(field)
                else: ev.append(f"fact:{f['fact_id']}")
            status='pass' if not missing and not bad else ('fail' if bad else 'unverified')
            add('offer',o['offer_id'],f"Offer {o['offer_id']}",{'critical_fields':list(REQ_FIELDS)},{'missing':missing,'bad':bad,'missing_source':missing_source,'buyer_basis':buyer_basis},status,True,ev)
            for field in BUYER_FIELDS:
                basis=buyer_basis.get(field) or buyer_authority(con,o['offer_id'],field)
                if basis:
                    add('buyer_authority',f"{o['offer_id']}/{field}",f"Buyer {field} basis",
                        {'offer_id':o['offer_id'],'field':field},basis,'pass',True,
                        [f"buyer_issue:{basis['issue_id']}",f"calculation:{basis['calculation_id']}",f"independent:{basis['independent_id']}"])
        reqs=rows_as_dict(con,"SELECT requirement_id,critical FROM requirements ORDER BY requirement_id")
        for r in reqs:
            assessed=rows_as_dict(con,"SELECT fact_id,offer_id,evidence_status FROM facts WHERE requirement_id=?",[r['requirement_id']])
            byoff={x.get('offer_id'):x for x in assessed}; missing=[o['offer_id'] for o in offers if o['offer_id'] not in byoff]
            bad=[x['offer_id'] for x in assessed if x.get('evidence_status') in BAD]
            status='pass' if not missing and not bad else ('fail' if bad else 'unverified')
            add('requirement',r['requirement_id'],f"Requirement {r['requirement_id']}",{'assessed_for':[o['offer_id'] for o in offers]},{'missing_offers':missing,'bad_offers':bad},status,bool(r.get('critical')),[f"fact:{x['fact_id']}" for x in assessed])
        comp=get_meta(run_root,'comparability_contract',{},parse_json=True) or {}
        add('analysis_dimension','comparability','Comparison basis',{'ranking_allowed':True},{'status':comp.get('status'),'failed_dimensions':comp.get('failed_dimensions',[])},'pass' if comp.get('ranking_allowed') else 'fail',True,['run_meta:comparability_contract'])
        if final:
            profile=str(get_meta(run_root,'profile','standart'))
            expected=['xlsx']+(['pdf'] if profile=='yuksek_guvence' else [])
            arts=rows_as_dict(con,"SELECT artifact_type,artifact_id,status FROM artifacts WHERE status='ready'")
            have={a['artifact_type'] for a in arts}
            for kind in expected:
                status='pass' if kind in have else 'fail'
                add('deliverable',kind,kind.upper(),{'required':True},{'present':kind in have},status,True,[a['artifact_id'] for a in arts if a['artifact_type']==kind])
        blocked=[u for u in units if u['critical'] and u['status']=='fail']
        partial=[u for u in units if u['status']=='unverified']
        status='BLOCKED' if blocked else ('PARTIAL' if partial else 'PASS')
        out={'status':status,'final':final,'units':units,'blocking_gaps':[{'id':u['entity_id'],'type':u['scope_type'],'label':u['label']} for u in blocked], 'unverified':[{'id':u['entity_id'],'type':u['scope_type'],'label':u['label']} for u in partial], 'generated_at':utc_now()}
        p=run_root/'qa'/('scope_ledger_final.json' if final else 'scope_ledger.json'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        sha=sha256_file(p); aid=stable_id('art','scope_ledger_final' if final else 'scope_ledger',sha,length=22)
        con.execute('INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)',[aid,'scope_ledger_final' if final else 'scope_ledger',str(p.relative_to(run_root)),sha,'[]','ready',utc_now()])
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('scope_ledger',?)",[json_text({'status':status,'path':str(p.relative_to(run_root)),'blocking_gaps':out['blocking_gaps']})])
        if hasattr(con,'commit'): con.commit()
        return out
    finally: con.close()

def main():
    ap=argparse.ArgumentParser(description='Build no-silent-omission run scope ledger'); ap.add_argument('--run',required=True); ap.add_argument('--final',action='store_true'); a=ap.parse_args(); print(json.dumps(build(Path(a.run),a.final),ensure_ascii=False,indent=2))
if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
