from __future__ import annotations
import argparse, hashlib, json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from common import json_text, sha256_file, stable_id, utc_now
from active_records import current_calculations
from db import connect, rows_as_dict

D=Decimal

def dec(v:Any):
    try: return D(str(v)) if v not in (None,"") else None
    except (InvalidOperation,ValueError,TypeError): return None

def j(v,default=None):
    try: return v if isinstance(v,(dict,list)) else json.loads(v) if v is not None else default
    except Exception: return default

def build(run_root:Path,tolerance:float=0.01)->dict[str,Any]:
    con=connect(run_root)
    try:
        con.execute("DELETE FROM cost_bridges")
        rows=[r for r in current_calculations(con) if r["calculation_type"]=="cost_summary" and r["offer_id"] is not None]
        latest={r['offer_id']:r for r in rows}; bridges=[]; tol=D(str(tolerance))
        for oid,row in sorted(latest.items()):
            obj=j(row['result_json'],{}) or {}
            stated=dec(obj.get('stated_total')); comp=dec(obj.get('comparable_total'))
            if stated is None or comp is None:
                status='unverified'; components=[]; bridge_total=None; residual=None
            else:
                components=[]; current=stated
                steps=obj.get('steps') if isinstance(obj.get('steps'),list) else []
                disc=next((s for s in steps if s.get('stage')=='sequential_discounts'),None)
                if disc and dec(disc.get('amount')) is not None:
                    new=dec(disc['amount']); delta=new-current; components.append({'component':'discounts','delta':str(delta)}); current=new
                scope=dec(obj.get('known_scope_adjustment')) or D(0); components.append({'component':'known_scope_adjustment','delta':str(scope)}); current += scope
                buyer_delta=dec(obj.get('buyer_quantity_adjustment')) or D(0)
                if obj.get('buyer_quantity_rows'):
                    components.append({'component':'buyer_quantity_adjustment','delta':str(buyer_delta),'basis':'buyer_reference_quantity','rows':obj['buyer_quantity_rows']})
                    current += buyer_delta
                imp=next((s for s in steps if s.get('stage')=='import_ddp_bridge'),None)
                if imp and dec(imp.get('ddp_equivalent')) is not None:
                    new=dec(imp['ddp_equivalent']); delta=new-current; components.append({'component':'import_ddp_bridge','delta':str(delta)}); current=new
                vat=next((s for s in steps if s.get('stage')=='vat_cost_basis'),None)
                if vat and dec(vat.get('cost_basis')) is not None:
                    new=dec(vat['cost_basis']); delta=new-current; components.append({'component':'vat_cost_basis','delta':str(delta)}); current=new
                pv=dec(obj.get('acquisition_present_value'))
                if pv is not None:
                    delta=pv-current; components.append({'component':'payment_npv','delta':str(delta)}); current=pv
                tco=dec(obj.get('tco_present_value')) or D(0)
                if tco!=0: components.append({'component':'tco','delta':str(tco)}); current += tco
                bridge_total=current; residual=comp-bridge_total; status='pass' if abs(residual)<=tol else 'fail'
            rev=hashlib.sha256(json_text({'calc':row['calculation_id'],'components':components,'comparable':obj.get('comparable_total')}).encode()).hexdigest()
            bid=stable_id('bridge',oid,rev,length=24)
            con.execute("INSERT INTO cost_bridges(bridge_id,offer_id,currency,stated_total,bridge_total,comparable_total,residual,tolerance,status,components_json,calculation_id,revision,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [bid,oid,obj.get('currency'),float(stated) if stated is not None else None,float(bridge_total) if bridge_total is not None else None,float(comp) if comp is not None else None,float(residual) if residual is not None else None,float(tol),status,json_text(components),row['calculation_id'],rev,utc_now()])
            bridges.append({'bridge_id':bid,'offer_id':oid,'currency':obj.get('currency'),'base_currency':obj.get('base_currency'),'base_date':obj.get('base_date'),'base_amount':obj.get('base_amount'),'fx_used':obj.get('fx_used'),'stated_total':str(stated) if stated is not None else None,'components':components,'bridge_total':str(bridge_total) if bridge_total is not None else None,'comparable_total':str(comp) if comp is not None else None,'residual':str(residual) if residual is not None else None,'status':status})
        # Pairwise explanatory bridge is only meaningful on one currency/date
        # basis. Never subtract EUR from USD and label the residual as either.
        comparable=[b for b in bridges if b['status']=='pass' and b['comparable_total'] is not None]
        pairwise=[]
        currencies={str(b.get('currency') or '') for b in comparable}
        if len(currencies)==1 and comparable:
            base=min(comparable,key=lambda x:D(x['comparable_total']))
            for b in comparable:
                if b is base: continue
                pairwise.append({'base_offer_id':base['offer_id'],'compare_offer_id':b['offer_id'],'difference':str(D(b['comparable_total'])-D(base['comparable_total'])),'currency':b.get('currency'),'basis':'local_same_currency'})
        elif comparable:
            normalized=[b for b in comparable if b.get('base_currency') and b.get('base_amount') is not None and b.get('base_date')]
            bases={str(b.get('base_currency')) for b in normalized}; dates={str(b.get('base_date')) for b in normalized}
            if len(normalized)==len(comparable) and len(bases)==1 and len(dates)==1:
                base=min(normalized,key=lambda x:D(str(x['base_amount'])))
                for b in normalized:
                    if b is base: continue
                    pairwise.append({'base_offer_id':base['offer_id'],'compare_offer_id':b['offer_id'],'difference':str(D(str(b['base_amount']))-D(str(base['base_amount']))),'currency':b.get('base_currency'),'base_date':b.get('base_date'),'basis':'fx_normalized'})
        failed=[b for b in bridges if b['status']=='fail']
        pairwise_required=len(comparable)>=2
        pairwise_status='PASS' if (not pairwise_required or pairwise) else 'UNVERIFIED'
        out={'status':'PASS' if not failed and pairwise_status!='UNVERIFIED' else ('FAIL' if failed else 'UNVERIFIED'),'bridges':bridges,'pairwise_differences':pairwise,'pairwise_status':pairwise_status,'tolerance':float(tol),'checked_at':utc_now()}
        p=run_root/'qa'/'cost_bridge.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        sha=sha256_file(p); aid=stable_id('art','cost_bridge',sha,length=22)
        con.execute("INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)",[aid,'cost_bridge',str(p.relative_to(run_root)),sha,'[]','ready',utc_now()])
        if hasattr(con,'commit'): con.commit()
        return out
    finally: con.close()

def main():
    ap=argparse.ArgumentParser(description='Reconcile procurement cost bridge and residual')
    ap.add_argument('--run',required=True); a=ap.parse_args(); print(json.dumps(build(Path(a.run)),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
