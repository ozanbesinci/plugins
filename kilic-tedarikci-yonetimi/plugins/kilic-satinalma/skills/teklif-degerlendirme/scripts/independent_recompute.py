from __future__ import annotations

from question_waits import guard_run_operation

import argparse
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from common import json_text, sha256_file, stable_id, utc_now
from active_records import current_calculations
from db import connect, rows_as_dict
from buyer_inputs import inputs_for
from buyer_quantity import number as buyer_number, validated_rows

D=Decimal


def dec(v: Any) -> Decimal | None:
    if v is None or v == "": return None
    try: return D(str(v))
    except (InvalidOperation, ValueError, TypeError): return None


def j(v: Any, default: Any=None) -> Any:
    if isinstance(v,(dict,list)): return v
    try: return json.loads(v) if v is not None else default
    except Exception: return default


def _pv(amount: Decimal, days: int, rate: Decimal) -> Decimal:
    # Deliberately independent implementation: float exponent path, then Decimal normalization.
    if not isinstance(amount, Decimal) or not amount.is_finite() or amount < 0:
        raise ValueError("payment amount must be finite and non-negative")
    if type(days) is not int or days < 0:
        raise ValueError("payment days must be a non-negative integer")
    if not isinstance(rate, Decimal) or not rate.is_finite() or rate <= -1:
        raise ValueError("discount rate must be finite and greater than -1")
    amount_float=float(amount); rate_float=float(rate)
    if not math.isfinite(amount_float) or not math.isfinite(rate_float):
        raise ValueError("payment inputs are outside the supported numeric range")
    try:
        divisor = math.pow(1.0 + rate_float, float(days) / 365.0)
        value=D(str(amount_float / divisor))
    except (ArithmeticError, InvalidOperation, ValueError) as exc:
        raise ValueError("present value is outside the supported numeric range") from exc
    if not value.is_finite():
        raise ValueError("present value must be finite")
    return value


def _rate(fin: dict[str,Any], currency: str) -> Decimal | None:
    rates=fin.get("discount_rates")
    if isinstance(rates,dict) and currency in rates:
        raw=rates[currency]
        return dec(raw.get("annual_effective_rate")) if isinstance(raw,dict) else dec(raw)
    if str(fin.get("annual_discount_rate_currency") or "").upper()==currency:
        return dec(fin.get("annual_discount_rate"))
    return None


def _recompute_cost(con, calc: dict[str,Any]) -> tuple[dict[str,Any], list[str]]:
    inp=j(calc.get("inputs_json"),{}) or {}; exp=j(calc.get("result_json"),{}) or {}
    warnings=[]
    total_id=inp.get("total_fact"); curr_id=inp.get("currency_fact"); payment_id=inp.get("payment_fact")
    total_row=con.execute("SELECT value_number FROM facts WHERE fact_id=?",[total_id]).fetchone() if total_id else None
    curr_row=con.execute("SELECT value_text FROM facts WHERE fact_id=?",[curr_id]).fetchone() if curr_id else None
    offer_id=calc.get("offer_id")
    buyer_currencies=inputs_for(con,offer_id,"currency") if offer_id else []
    buyer_quantities=inputs_for(con,offer_id,"reference_quantity") if offer_id else []
    buyer_scopes=inputs_for(con,offer_id,"scope_cost") if offer_id else []
    if not total_row or total_row[0] is None or (not (curr_row and curr_row[0]) and len(buyer_currencies)!=1):
        return {"known":False,"complete":False,"reason":"source facts missing"}, ["source_fact_missing"]
    stated=dec(total_row[0]); assert stated is not None
    currency_basis="supplier_fact" if curr_row and curr_row[0] else "buyer_declaration"
    currency=str(curr_row[0] if currency_basis=="supplier_fact" else buyer_currencies[0]["value"]).upper(); value=stated
    if currency_basis=="supplier_fact" and any(str(x.get("value") or "").upper()!=currency for x in buyer_currencies):
        raise ValueError("buyer currency conflicts with supplier currency")
    offer_params=inp.get("offer_params") if isinstance(inp.get("offer_params"),dict) else {}
    fin=inp.get("financial_params") if isinstance(inp.get("financial_params"),dict) else {}

    for raw in offer_params.get("discounts",[]) if isinstance(offer_params.get("discounts"),list) else []:
        r=dec(raw)
        if r is None or not r.is_finite() or r<0 or r>=1: warnings.append("discount_invalid"); continue
        value=value*(D(1)-r)
    buyer_rows=[]; quantity_adjustment=D(0)
    if buyer_quantities:
        try:
            buyer_rows=validated_rows(con,offer_id,buyer_quantities,currency)
            for row in buyer_rows:
                delta=(D(row["reference_quantity"])-D(row["original_quantity"]))*D(row["unit_price"])
                row["delta"]=str(delta)
                quantity_adjustment+=delta
        except ValueError:
            warnings.append("buyer_quantity_invalid")
            buyer_rows=[]
            quantity_adjustment=D(0)
    scope=D(0); unknown=0
    seen_scope=set()
    for row in inp.get("scope_items",[]) if isinstance(inp.get("scope_items"),list) else []:
        cost_role = row.get("cost_role") or row.get("classification")
        if cost_role == "included_in_price" and row.get("status") == "verified":
            continue
        supplied=[x for x in buyer_scopes if x.get("scope_id")==row.get("scope_id")]
        if supplied:
            seen_scope.add(row.get("scope_id"))
            legacy_unpriced = cost_role=="incremental_adjustment" and row.get("status") not in {"verified", "conflicting", "unreadable"}
            verified_employer_unpriced = (
                cost_role=="unresolved_adjustment" and row.get("classification") in {"isveren_yukumlulugu", "employer_responsibility"}
                and row.get("status")=="verified" and row.get("amount") is None
                and row.get("currency") is None
            )
            if len(supplied)!=1 or not (legacy_unpriced or verified_employer_unpriced):
                unknown+=1; warnings.append("buyer_scope_invalid"); continue
            try:
                amount=buyer_number(supplied[0].get("amount"))
                if str(supplied[0].get("currency") or "").upper()!=currency: raise ValueError("currency mismatch")
                scope+=amount
            except ValueError:
                unknown+=1; warnings.append("buyer_scope_invalid")
            continue
        if cost_role != "incremental_adjustment" or row.get("status") != "verified" or row.get("amount") is None:
            unknown+=1; continue
        rc=str(row.get("currency") or currency).upper()
        if rc!=currency: unknown+=1; warnings.append("scope_currency_mismatch"); continue
        a=dec(row.get("amount")); scope += a or D(0)
    for supplied in buyer_scopes:
        if supplied.get("scope_id") not in seen_scope:
            unknown+=1; warnings.append("buyer_scope_invalid")
    acquisition=value+scope+quantity_adjustment

    bridge=offer_params.get("import_bridge")
    if isinstance(bridge,dict):
        included={str(x.get("cost_id")) for x in (bridge.get("included_costs") or []) if x.get("cost_id")}
        seen=set()
        for rows in (bridge.get("buyer_costs") or [],bridge.get("non_deductible_taxes") or []):
            for row in rows:
                cid=str(row.get("cost_id") or ""); a=dec(row.get("amount"))
                if not cid or a is None: warnings.append("import_bridge_invalid"); continue
                if cid in included or cid in seen: continue
                seen.add(cid); acquisition += a

    vat=offer_params.get("vat")
    if isinstance(vat,dict) and vat.get("price_basis")=="net_ex_vat":
        rate=dec(vat.get("rate")); ded=dec(vat.get("deductible_share"))
        if rate is None or ded is None or rate<0 or ded<0 or ded>1: warnings.append("vat_invalid")
        else: acquisition = acquisition + acquisition*rate*(D(1)-ded)

    commercial = {}
    for kind in ("payment_terms", "warranty_terms"):
        declarations = inputs_for(con, offer_id, kind) if offer_id else []
        if declarations:
            fields = ("milestones",) if kind == "payment_terms" else ("duration_years", "scope")
            value = {field: declarations[0][field] for field in fields}
            if any({field: item[field] for field in fields} != value for item in declarations):
                raise ValueError("independent conflicting buyer commercial declarations")
            commercial[kind] = value
    schedule=offer_params.get("payment_schedule") if offer_params.get("payment_schedule") is not None else None
    if schedule is None and payment_id:
        prow=con.execute("SELECT normalized_json FROM facts WHERE fact_id=?",[payment_id]).fetchone()
        pn=j(prow[0],{}) if prow else {}
        schedule=pn.get("payment_schedule") if isinstance(pn,dict) and isinstance(pn.get("payment_schedule"),list) else None
    if "payment_terms" in commercial:
        if offer_params.get("payment_schedule") is not None:
            raise ValueError("independent dated and event payment terms require reconciliation")
        schedule = None
    pv=None
    rate=_rate(fin,currency)
    if schedule is not None:
        payment_rows=[]; payment_error=False
        try:
            if not isinstance(schedule,list) or not schedule: raise ValueError("empty schedule")
            ratio_sum=D(0); has_ratio=False; amount_sum=D(0)
            amount_tol=max(D("0.01"),abs(acquisition)*D("0.0001"))
            for item in schedule:
                if not isinstance(item,dict) or set(item)-{"days","ratio","amount"}: raise ValueError("payment row shape")
                days=item.get("days"); ratio_raw=item.get("ratio"); amount_raw=item.get("amount")
                if type(days) is not int or days<0 or (ratio_raw is None and amount_raw is None): raise ValueError("payment day/fields")
                if isinstance(ratio_raw,bool) or isinstance(amount_raw,bool): raise ValueError("payment numeric type")
                ratio=dec(ratio_raw); amount=dec(amount_raw)
                if ratio_raw is not None and (ratio is None or not ratio.is_finite() or ratio<0 or ratio>1): raise ValueError("payment ratio")
                if amount_raw is not None and (amount is None or not amount.is_finite() or amount<0): raise ValueError("payment amount")
                if ratio is not None:
                    ratio_sum+=ratio; has_ratio=True
                implied=acquisition*ratio if ratio is not None else None
                if amount is not None and implied is not None and abs(amount-implied)>amount_tol: raise ValueError("payment amount/ratio")
                actual_amount=amount if amount is not None else (implied or D(0))
                amount_sum+=actual_amount
                if ratio is None and amount is not None and acquisition!=0:
                    ratio_sum+=amount/acquisition
                payment_rows.append((days,actual_amount))
            if has_ratio and abs(ratio_sum-D(1))>D("0.0001"): raise ValueError("payment ratio sum")
            if abs(amount_sum-acquisition)>amount_tol: raise ValueError("payment amount sum")
        except Exception:
            payment_error=True
        if payment_error:
            warnings.append("payment_schedule_invalid")
        elif rate is not None:
            try:
                pv=sum((_pv(amount,days,rate) for days,amount in payment_rows),D(0))
            except Exception:
                warnings.append("payment_schedule_invalid")
        else:
            warnings.append("discount_rate_missing")

    tco_pv=None; tco=offer_params.get("tco")
    if isinstance(tco,dict) and isinstance(tco.get("annual_costs"),list):
        tr=dec(tco.get("annual_rate"))
        if tr is None and tco.get("rate_basis")=="real":
            nr=dec(tco.get("nominal_rate")); inf=dec(tco.get("inflation_rate"))
            if nr is not None and inf is not None and inf>-1: tr=(D(1)+nr)/(D(1)+inf)-D(1)
        if tr is None or tr<=-1: warnings.append("tco_rate_missing")
        else:
            total=D(0)
            try:
                for item in tco["annual_costs"]:
                    year=int(item.get("year")); a=dec(item.get("amount"))
                    if year<0 or a is None: raise ValueError
                    total += a if year==0 else D(str(float(a)/math.pow(1.0+float(tr),year)))
                tco_pv=total
            except Exception: warnings.append("tco_invalid")

    comparable=(pv if pv is not None else acquisition)+(tco_pv or D(0))
    base_currency=str(fin.get("base_currency") or "").upper() or None
    base_amount=None
    if base_currency:
        if currency==base_currency: base_amount=comparable
        else:
            fx=fin.get("fx",{}) if isinstance(fin.get("fx",{}),dict) else {}; raw=fx.get(currency)
            source=None; rate_date=fin.get("base_date")
            if isinstance(raw,dict):
                rr=dec(raw.get("forex_selling") if raw.get("forex_selling") is not None else raw.get("rate")); unit=dec(raw.get("unit",1)); source=raw.get("source"); rate_date=raw.get("date") or raw.get("base_date") or rate_date
            else:
                rr=dec(raw); unit=D(1); source="user_assumption" if fin.get("fx_assumption_acknowledged") is True else None
            if rr is not None and unit is not None and rr>0 and unit>0 and source and rate_date:
                base_amount=comparable*rr/unit
            else: warnings.append("fx_missing_or_unproven")
    complete=unknown==0 and not any(x in warnings for x in ["discount_invalid","import_bridge_invalid","vat_invalid","payment_schedule_invalid","tco_invalid","fx_missing_or_unproven","buyer_quantity_invalid","buyer_scope_invalid"])
    result={"known":True,"complete":complete,"stated_total":str(stated),"known_scope_adjustment":str(scope),"acquisition_cost_basis":str(acquisition),
            "acquisition_present_value":str(pv) if pv is not None else None,"tco_present_value":str(tco_pv) if tco_pv is not None else None,
            "comparable_total":str(comparable),"currency":currency,"unknown_scope_items":unknown,"base_currency":base_currency,
            "base_date":fin.get("base_date"),"base_amount":str(base_amount) if base_amount is not None else None}
    if buyer_currencies or buyer_quantities or buyer_scopes:
        result.update({"buyer_quantity_adjustment":str(quantity_adjustment),"buyer_quantity_rows":buyer_rows,"currency_basis":currency_basis})
    for kind, value in commercial.items():
        result[kind] = value
        result[kind.replace("_terms", "_basis")] = "buyer_declaration"
    return result,warnings


def _num_equal(a: Any,b: Any,tol: Decimal) -> bool:
    da,db=dec(a),dec(b)
    if da is None or db is None: return a in (None,"") and b in (None,"")
    return abs(da-db)<=tol


def _raw_eligible_offers(con) -> list[str]:
    """Independently apply the current active/verified-mandatory membership gate."""
    eligible=[]
    offers=rows_as_dict(con,"SELECT offer_id FROM offers WHERE status='active' ORDER BY offer_id")
    for offer in offers:
        rows=rows_as_dict(con,"""
            SELECT f.value_text,f.evidence_status,r.category
            FROM facts f LEFT JOIN requirements r ON r.requirement_id=f.requirement_id
            WHERE f.offer_id=? AND f.requirement_id IS NOT NULL
        """,[offer["offer_id"]])
        excluded=any(
            row.get("category")=="mandatory"
            and row.get("evidence_status")=="verified"
            and (row.get("value_text") or "").casefold() in {"noncompliant","uygunsuz","fail","failed"}
            for row in rows
        )
        if not excluded: eligible.append(offer["offer_id"])
    return eligible


def _raw_active_offers(con) -> list[str]:
    return [row["offer_id"] for row in rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active' ORDER BY offer_id")]


def _raw_verified_fact_map(con, active: list[str]) -> dict[tuple[str,str],dict[str,Any]]:
    rank={"adjudicated":5,"semantic_llm":4,"vision":3,"duckdb_pdf_secondary":2}
    out={}
    for row in rows_as_dict(con,"SELECT * FROM facts WHERE offer_id IS NOT NULL ORDER BY updated_at,fact_id"):
        if row.get("offer_id") not in set(active) or row.get("evidence_status")!="verified": continue
        key=(row["offer_id"],row["field_key"]); prev=out.get(key)
        if prev is None or rank.get(row.get("extraction_path"),1)>=rank.get(prev.get("extraction_path"),1): out[key]=row
    return out


def _raw_value(row: dict[str,Any] | None) -> Any:
    if not row: return None
    if row.get("value_number") is not None: return row["value_number"]
    return row.get("value_date") or row.get("value_text")


def _raw_financial_params(con) -> dict[str,Any]:
    row=con.execute("SELECT value FROM run_meta WHERE key='financial_parameters'").fetchone()
    value=j(row[0],{}) if row else {}
    return value if isinstance(value,dict) else {}


def _financial_context(con, latest: dict[tuple[str|None,str],dict[str,Any]], active: list[str]) -> tuple[dict[str,Any],bool,str]:
    """Resolve the parameters used for source cost reconstruction.

    Canonical run metadata wins whenever its key exists. Older direct-call runs
    have no such key, so their explicitly recorded cost-call arguments remain
    the compatibility source. Empty input objects from incomplete cost rows
    are not recorded arguments and are ignored.
    """
    row=con.execute("SELECT value FROM run_meta WHERE key='financial_parameters'").fetchone()
    if row:
        value=j(row[0],None)
        if isinstance(value,dict): return value,True,"run_meta"
        return {},False,"invalid_run_meta_financial_parameters"

    candidates=[]; invalid=False
    for offer_id in active:
        calc=latest.get((offer_id,"cost_summary"))
        if not calc: continue
        inputs=j(calc.get("inputs_json"),{})
        if not isinstance(inputs,dict) or not inputs:
            continue
        if "financial_params" not in inputs:
            continue
        value=inputs.get("financial_params")
        if isinstance(value,dict): candidates.append(value)
        else: invalid=True
    if invalid or not candidates:
        return {},False,"legacy_financial_parameters_missing_or_invalid"
    encoded={json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str) for value in candidates}
    if len(encoded)!=1:
        return {},False,"legacy_financial_parameters_conflict"
    return candidates[0],True,"legacy_cost_inputs"


def _raw_cost_from_sources(con, offer_id: str, facts: dict[tuple[str,str],dict[str,Any]], financial: dict[str,Any]) -> tuple[dict[str,Any],list[str]]:
    """Recompute a comparison cost from canonical source rows, never main calc inputs."""
    total=facts.get((offer_id,"total")); currency=facts.get((offer_id,"currency")); payment=facts.get((offer_id,"payment"))
    offer_parameters=financial.get("offer_parameters",{})
    offer_params=offer_parameters.get(offer_id,{}) if isinstance(offer_parameters,dict) else {}
    scope=rows_as_dict(con,"SELECT scope_id,amount,currency,status,classification,cost_role FROM scope_items WHERE offer_id=? ORDER BY scope_id",[offer_id])
    synthetic={"offer_id":offer_id,"inputs_json":json_text({
        "total_fact":total.get("fact_id") if total else None,
        "currency_fact":currency.get("fact_id") if currency else None,
        "payment_fact":payment.get("fact_id") if payment else None,
        "financial_params":financial,
        "offer_params":offer_params if isinstance(offer_params,dict) else {},
        "scope_items":scope,
    }),"result_json":"{}"}
    result,warnings=_recompute_cost(con,synthetic)
    if isinstance(offer_params,dict):
        discounts=offer_params.get("discounts")
        if "discounts" in offer_params and not isinstance(discounts,list):
            warnings.append("discount_invalid")
            result["complete"]=False
        for rate in discounts if isinstance(discounts,list) else []:
            parsed=dec(rate)
            if parsed is None or not parsed.is_finite() or parsed<0 or parsed>=1:
                warnings.append("discount_invalid")
                result["complete"]=False
                break
    return result,warnings


def _independent_vat_basis(text: str | None) -> str | None:
    if not text: return None
    table=str.maketrans({"ı":"i","İ":"i","ş":"s","Ş":"s","ğ":"g","Ğ":"g","ü":"u","Ü":"u","ö":"o","Ö":"o","ç":"c","Ç":"c"})
    value=" ".join(str(text).translate(table).casefold().strip().strip(".:;").split())
    aliases={
        "included":{"included","dahil","include","inclusive"},
        "excluded":{"excluded","haric","exclude","exclusive","not included","dahil degil"},
    }
    value_without_label=re.sub(r"^(kdv|vat)\s*[:=]?\s*","",value)
    for basis,terms in aliases.items():
        if value in terms or value_without_label in terms: return basis
    if re.search(r"\b(?:not|no|degil|degildir)\b",value): return None
    # Keep the independently implemented full-phrase patterns in parity with
    # the accepted canonical source vocabulary without importing its function.
    label=r"(?:kdv|vat)"; rate=r"(?:%\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*%)"; sep=r"[\s:;()]*"
    for canonical,terms in aliases.items():
        basis="(?:"+"|".join(re.escape(term) for term in sorted(terms))+ ")"
        patterns=(
            rf"^{label}{sep}{rate}{sep}{basis}$",rf"^{rate}{sep}{label}{sep}{basis}$",
            rf"^{label}{sep}{basis}{sep}{rate}$",rf"^{basis}{sep}{rate}{sep}{label}$",
            rf"^{rate}{sep}{basis}{sep}{label}$",rf"^{basis}{sep}{label}{sep}{rate}$",
            rf"^{rate}{sep}{basis}$",rf"^{basis}{sep}{rate}$",
        )
        if any(re.fullmatch(pattern,value) for pattern in patterns): return canonical
    return None


def _raw_comparison_failures(con, active: list[str], facts: dict[tuple[str,str],dict[str,Any]], costs: dict[str,dict[str,Any]], financial: dict[str,Any]) -> set[str]:
    failed:set[str]=set()
    offer_parameters=financial.get("offer_parameters",{})
    offer_parameters=offer_parameters if isinstance(offer_parameters,dict) else {}
    for field in ("total","currency"):
        missing=[]
        for oid in active:
            row=facts.get((oid,field))
            buyer_currency=inputs_for(con,oid,"currency") if field=="currency" else []
            if (not row or (field=="total" and row.get("value_number") is None) or (field=="currency" and not row.get("value_text"))) and not (field=="currency" and len(buyer_currency)==1):
                missing.append(oid)
        if missing: failed.add(field)

    quantities=[(oid,facts.get((oid,"quantity"))) for oid in active]
    qpresent=[(oid,row) for oid,row in quantities if row and row.get("value_number") not in (None,0)]
    if qpresent:
        if len(qpresent)!=len(active):
            failed.add("quantity")
        else:
            try:
                values=[float(row["value_number"]) for _,row in qpresent]
                high,low=max(values),min(values)
                tol=float((con.execute("SELECT value FROM run_meta WHERE key='comparability_quantity_tolerance'").fetchone() or [None])[0] or 0.05)
                units={oid:str(row.get("unit") or "").strip().casefold() for oid,row in qpresent}
                ratio=0.0 if high==0 else (high-low)/high
                if any(not math.isfinite(value) or value<0 for value in values) or ratio>tol or len({u for u in units.values() if u})!=1 or any(not u for u in units.values()): failed.add("quantity")
            except (TypeError,ValueError,OverflowError): failed.add("quantity")

    scopes=[(oid,facts.get((oid,"scope_signature"))) for oid in active]
    # Reconstruct identities from original cited section quotes independently;
    # do not call the main comparison implementation or consume its keys.
    section_values={}; structured=False
    for oid,row in scopes:
        norm=j((row or {}).get('normalized_json'),{})
        if not isinstance(norm,dict) or 'sections' not in norm:
            section_values[oid]=None;continue
        structured=True; parts=[]; valid=True
        sections=norm['sections']
        if not isinstance(sections,list) or not sections:
            valid=False;sections=[]
        for section in sections:
            refs=section.get('evidence_refs') if isinstance(section,dict) else None
            if not isinstance(refs,list) or not refs or len(set(refs))!=len(refs):
                valid=False;break
            for ref in refs:
                proof=con.execute('''SELECT e.quote,e.evidence_status,e.extraction_path,d.offer_id,d.active
                    FROM evidence e JOIN documents d ON e.document_id=d.document_id
                    WHERE e.evidence_id=?''',[ref]).fetchone()
                if not proof or proof[1]!='verified' or proof[2]=='vision' or proof[3]!=oid or not proof[4]:
                    valid=False;break
                raw=str(proof[0] or '').strip()
                raw=re.sub(r'^[A-Z]+\d+\s*=\s*','',raw)
                identity=' '.join(raw.casefold().split())
                if not identity:valid=False;break
                parts.append(identity)
            if not valid:break
        section_values[oid]=tuple(sorted(parts)) if valid and len(set(parts))==len(parts) else ()
    stated=[(oid,row) for oid,row in scopes if row and str(_raw_value(row) or "").strip()]
    if structured:
        if any(not value for value in section_values.values()) or len(set(section_values.values()))!=1:
            failed.add('scope_identity')
    elif stated:
        missing=[oid for oid,row in scopes if not row or not str(_raw_value(row) or "").strip()]
        values={oid:" ".join(str(_raw_value(row)).casefold().split()) for oid,row in stated}
        if missing or len(set(values.values()))!=1: failed.add("scope_identity")

    currencies={oid:str(_raw_value(facts.get((oid,"currency"))) or "").upper() for oid in active}
    for oid in active:
        if not currencies[oid]:
            declarations=inputs_for(con,oid,"currency")
            if len(declarations)==1:
                currencies[oid]=str(declarations[0].get("value") or "").upper()
    unique_currency={value for value in currencies.values() if value}
    if len(unique_currency)>1:
        base_currency=str(financial.get("base_currency") or "").upper()
        base_dates=set(); bad=[]
        fx=financial.get("fx",{}) if isinstance(financial.get("fx",{}),dict) else {}
        for oid in active:
            cost=costs.get(oid,{})
            if not cost.get("complete") or cost.get("base_amount") is None or not cost.get("base_currency"):
                bad.append(oid)
            if currencies.get(oid)!=base_currency:
                raw=fx.get(currencies.get(oid))
                source=None; rate_date=financial.get("base_date")
                if isinstance(raw,dict):
                    source=raw.get("source"); rate_date=raw.get("date") or raw.get("base_date") or rate_date
                elif raw is not None and financial.get("fx_assumption_acknowledged") is True:
                    source="user_assumption"
                if not source or not rate_date: bad.append(oid)
            if cost.get("base_date"): base_dates.add(str(cost.get("base_date")))
            if base_currency and str(cost.get("base_currency") or "").upper()!=base_currency: bad.append(oid)
        if not base_currency or bad or len(base_dates)!=1: failed.add("currency_basis")

    payment_sig={}
    for oid in active:
        row=facts.get((oid,"payment")); normalized=j((row or {}).get("normalized_json"),{}) or {}
        schedule=normalized.get("payment_schedule")
        declarations = inputs_for(con, oid, "payment_terms")
        if declarations:
            terms = declarations[0]["milestones"]
            if any(item["milestones"] != terms for item in declarations):
                raise ValueError("independent conflicting payment comparison basis")
            payment_sig[oid] = json_text({"milestones": terms})
        else:
            payment_sig[oid]=json_text(schedule) if isinstance(schedule,list) else str(_raw_value(row) or "").casefold()
    if len(set(payment_sig.values()))>1 and any(costs.get(oid,{}).get("acquisition_present_value") is None for oid in active):
        failed.add("payment_basis")

    incoterms={oid:str(_raw_value(facts.get((oid,"incoterms"))) or "").strip().upper() for oid in active}
    known={value for value in incoterms.values() if value}
    stated_incos=[value for value in incoterms.values() if value]
    if not (len(known)<=1 and len(stated_incos) in {0,len(active)}) and known:
        bad=[]
        for oid,inco in incoterms.items():
            if not inco: bad.append(oid); continue
            if inco.startswith("DDP"): continue
            params=offer_parameters.get(oid,{})
            if not isinstance(params,dict) or not isinstance(params.get("import_bridge"),dict): bad.append(oid)
        if bad: failed.add("incoterm_basis")

    raw_vat={oid:str(_raw_value(facts.get((oid,"vat"))) or "").strip() for oid in active}
    vats={oid:_independent_vat_basis(value) for oid,value in raw_vat.items()}
    unknown=[oid for oid,value in raw_vat.items() if value and vats[oid] is None]
    known_vat={value for value in vats.values() if value}
    stated_vat=[value for value in vats.values() if value]
    if unknown or len(known_vat)>1 or len(stated_vat) not in {0,len(active)}:
        bad=[]
        for oid in active:
            params=offer_parameters.get(oid,{})
            if not vats.get(oid) or not isinstance(params,dict) or not isinstance(params.get("vat"),dict): bad.append(oid)
        if bad: failed.add("vat_basis")

    if any(int(costs.get(oid,{}).get("unknown_scope_items") or 0)>0 or not costs.get(oid,{}).get("complete") for oid in active):
        failed.add("scope_basis")
    return failed


def _check_id_membership(mism: list[dict[str,Any]], field: str, actual: Any, expected: list[str]) -> bool:
    """Check a result list's exact-string, unique membership without score tolerance."""
    if not isinstance(actual,list):
        mism.append({"field":field,"reason":"expected list","expected_ids":expected,"actual":actual})
        return False
    if any(type(value) is not str for value in actual):
        mism.append({"field":field,"reason":"ids must be exact strings","actual":actual})
        return False
    if len(actual)!=len(set(actual)):
        mism.append({"field":field,"reason":"duplicate ids","actual":actual})
        return False
    if set(actual)!=set(expected):
        mism.append({"field":field,"reason":"membership mismatch","expected_ids":expected,"actual":actual})
        return False
    return True


from error_log import log_failures


def _recompute_source_price_chain(con, calc):
    """Re-read canonical source rows and use exact rational arithmetic.

    No source_price_chain/procurement_math computation or primary item list is
    used here. Input source percentages remain percent values, not fractions.
    """
    from fractions import Fraction
    from decimal import localcontext
    import unicodedata

    def fraction(raw):
        if raw is None or isinstance(raw, bool):
            raise ValueError('unknown source number')
        d = D(str(raw))
        if not d.is_finite() or d < 0:
            raise ValueError('invalid source number')
        return Fraction(str(raw))

    def display(value):
        with localcontext() as ctx:
            ctx.prec = 50
            return str(D(value.numerator) / D(value.denominator))

    def basis(raw):
        text = str(raw or '').replace('ı','i')
        text = ''.join(c for c in unicodedata.normalize('NFKD',text).casefold() if not unicodedata.combining(c))
        if 'haric degil' in text:
            return None
        if 'dahil degil' in text or 'not included' in text:
            return 'excluded'
        if re.search(r'\b(?:haric|excluded|exclude)\b',text):
            return 'excluded'
        if re.search(r'\b(?:dahil|included|include)\b',text):
            return 'included'
        return None

    facts=rows_as_dict(con,"SELECT * FROM facts WHERE offer_id=? AND evidence_status='verified' ORDER BY fact_id",[calc['offer_id']])
    raw_items=[]
    for fact in facts:
        normalized=j(fact.get('normalized_json'),{})
        if not isinstance(normalized,dict) or not isinstance(normalized.get('items',[]),list):
            continue
        raw_items.extend(item for item in normalized.get('items',[]) if isinstance(item,dict) and item.get('amount_basis') in ('unit_price','line_total'))
    rows=[];warnings=[];values={};declared={};seen=set();mismatch=False
    for item in raw_items:
        try:
            if item['item_id'] in seen:
                raise ValueError('duplicate source item')
            seen.add(item['item_id'])
            if item.get('evidence_status')!='verified' or item.get('amount_basis')!='unit_price':
                raise ValueError('source item is not a verified unit price')
            pricing=item['pricing'];q=fraction(item['quantity']);unit=fraction((pricing.get('price_unit') or {}).get('value',1));price=fraction(item['amount'])
            if q<=0 or unit<=0 or not item.get('currency'):
                raise ValueError('source quantity/unit/currency missing')
            rates=pricing['discounts']['percentages'];tax_percent=fraction(pricing['vat']['percent']);flag=pricing['vat']['basis']
            if not rates or tax_percent>100:
                raise ValueError('source percentages missing or invalid')
            raw=q*price/unit;amount=raw;normalized_rates=[]
            for percent in rates:
                rate=fraction(percent)
                if rate>=100:raise ValueError('source discount out of range')
                amount=amount*(100-rate)/100;normalized_rates.append(display(rate))
            if flag=='included':
                gross=amount;net=amount*100/(100+tax_percent)
            elif flag=='excluded':
                net=amount;gross=amount*(100+tax_percent)/100
            else:raise ValueError('source VAT basis missing')
            tax=gross-net;currency=str(item['currency']).upper()
            row={'item_id':item['item_id'],'currency':currency,'quantity':display(q),'unit_price':display(price),'price_unit':display(unit),
                 'discount_percentages':normalized_rates,'vat_percent':display(tax_percent),'price_vat_basis':flag,
                 'pre_discount_source_amount':display(raw),'discounted_source_amount':display(amount),'net':display(net),'vat':display(tax),'gross':display(gross)}
            rows.append(row);values[item['item_id']]={'net':net,'vat':tax,'gross':gross}
            source=pricing.get('stated_amounts') or {}
            for field in ('net','vat','gross'):
                if field not in source:continue
                key=(source['scope'],item['item_id'] if source['scope']=='line' else '',field)
                stated=fraction(source[field]['amount'])
                if key in declared and declared[key]!=stated:
                    warnings.append('conflicting_source_stated_amounts')
                declared[key]=stated
        except (KeyError,ValueError,TypeError,InvalidOperation,ZeroDivisionError) as exc:
            warnings.append(str(exc))
    currencies={r['currency'] for r in rows}
    if len(currencies)!=1:
        warnings.append('source currencies missing or mixed')
    totals={field:sum((v[field] for v in values.values()),Fraction(0)) for field in ('net','vat','gross')}
    reconciliations=[]
    for (scope,item_id,field),stated in declared.items():
        actual=totals[field] if scope=='offer' else values.get(item_id,{}).get(field)
        if actual is None:
            warnings.append('source line reconciliation missing');continue
        residual=actual-stated
        reconciliations.append({'scope':scope,'item_id':item_id or None,'field':field,'stated':display(stated),'calculated':display(actual),'residual':display(residual)})
        mismatch=mismatch or abs(residual)>Fraction(1,100)
    total=next((f for f in facts if f.get('field_key')=='total'),{})
    curr=next((f.get('value_text') for f in facts if f.get('field_key')=='currency'),None)
    source_basis=basis(next((f.get('value_text') for f in facts if f.get('field_key')=='vat'),None))
    if total.get('value_number') is not None and source_basis and len(currencies)==1:
        if str(curr or '').upper()!=next(iter(currencies)):
            warnings.append('source total currency differs')
        else:
            field='net' if source_basis=='excluded' else 'gross';stated=fraction(total['value_number']);residual=totals[field]-stated
            reconciliations.append({'scope':'offer','field':field,'stated':display(stated),'calculated':display(totals[field]),'residual':display(residual),'fact_id':total['fact_id']})
            mismatch=mismatch or abs(residual)>Fraction(1,100)
    complete=bool(raw_items) and len(rows)==len(raw_items) and not warnings and not mismatch
    return {'known':bool(rows),'complete':complete,'status':'mismatch' if mismatch else 'complete' if complete else 'incomplete',
            'currency':next(iter(currencies)) if len(currencies)==1 else None,'items':rows,'reconciliations':reconciliations,
            **{field+'_total':display(value) if rows else None for field,value in totals.items()}},warnings


def _source_price_differences(expected,recomputed,tolerance):
    mismatches=[]
    for field in ('known','complete','status','currency'):
        if expected.get(field)!=recomputed.get(field):mismatches.append({'field':field,'expected':expected.get(field),'recomputed':recomputed.get(field)})
    for field in ('net_total','vat_total','gross_total'):
        if not _num_equal(expected.get(field),recomputed.get(field),tolerance):mismatches.append({'field':field,'expected':expected.get(field),'recomputed':recomputed.get(field)})
    left={r['item_id']:r for r in expected.get('items',[])};right={r['item_id']:r for r in recomputed.get('items',[])}
    if set(left)!=set(right) or len(left)!=len(expected.get('items',[])) or len(right)!=len(recomputed.get('items',[])):
        mismatches.append({'field':'source_item_identity_coverage'})
    for item_id in set(left)&set(right):
        a,b=left[item_id],right[item_id]
        for field in ('currency','price_vat_basis'):
            if a.get(field)!=b.get(field):mismatches.append({'item_id':item_id,'field':field})
        for field in ('quantity','unit_price','price_unit','vat_percent','pre_discount_source_amount','discounted_source_amount','net','vat','gross'):
            tol=tolerance if field in ('pre_discount_source_amount','discounted_source_amount','net','vat','gross') else D('.00000001')
            if not _num_equal(a.get(field),b.get(field),tol):mismatches.append({'item_id':item_id,'field':field,'expected':a.get(field),'recomputed':b.get(field)})
        ar=a.get('discount_percentages',[]);br=b.get('discount_percentages',[])
        if len(ar)!=len(br) or any(not _num_equal(x,y,D('.00000001')) for x,y in zip(ar,br)):mismatches.append({'item_id':item_id,'field':'discount_stage_order'})
    def signature(r):return (r.get('scope'),r.get('item_id'),r.get('field'),r.get('fact_id'))
    a={signature(r):r for r in expected.get('reconciliations',[])};b={signature(r):r for r in recomputed.get('reconciliations',[])}
    if set(a)!=set(b):mismatches.append({'field':'source_reconciliation_coverage'})
    for key in set(a)&set(b):
        for field in ('stated','calculated','residual'):
            if not _num_equal(a[key].get(field),b[key].get(field),tolerance):mismatches.append({'field':'source_reconciliation_'+field,'identity':key})
    return mismatches


@guard_run_operation
@log_failures('independent_recompute.run')
def run(run_root: Path, amount_tolerance: float=0.01, score_tolerance: float=0.0001) -> dict[str,Any]:
    con=connect(run_root)
    try:
        con.execute("DELETE FROM independent_calculations")
        calcs=current_calculations(con)
        # Latest per offer/type/global type.
        latest={}
        for c in calcs: latest[(c.get("offer_id"),c["calculation_type"])]=c
        results=[]
        atol=D(str(amount_tolerance)); stol=D(str(score_tolerance))
        for (offer_id,ctype),calc in latest.items():
            if ctype=='source_price_chain':
                exp=j(calc.get('result_json'),{}) or {}
                rec,warns=_recompute_source_price_chain(con,calc)
                mism=_source_price_differences(exp,rec,atol)
                state='unverified' if calc.get('status')!='complete' else 'fail' if mism or warns else 'pass'
                detail={'mismatches':mism,'warnings':warns}
                ih=calc.get('input_hash') or hashlib.sha256(str(calc.get('inputs_json') or '').encode()).hexdigest()
                iid=stable_id('irecalc',calc['calculation_id'],ih,length=24)
                con.execute('INSERT INTO independent_calculations(independent_id,calculation_id,offer_id,calculation_type,method,expected_json,recomputed_json,tolerance,status,detail_json,input_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                            [iid,calc['calculation_id'],offer_id,ctype,'independent_fraction_source_prices_v1',json_text(exp),json_text(rec),float(atol),state,json_text(detail),ih,utc_now()])
                results.append({'independent_id':iid,'calculation_id':calc['calculation_id'],'offer_id':offer_id,'calculation_type':ctype,'status':state,'detail':detail})
                continue
            if ctype!="cost_summary": continue
            exp=j(calc.get("result_json"),{}) or {}
            if calc.get("status") != "complete" or not exp.get("complete"):
                status="unverified"; rec={"known":bool(exp.get("known"))}; detail={"reason":"main calculation is not complete", "main_status":calc.get("status"), "warnings":exp.get("warnings",[])}
            elif not exp.get("known"):
                status="unverified"; rec={"known":False}; detail={"reason":"main calculation incomplete"}
            else:
                rec,warns=_recompute_cost(con,calc)
                fields=["stated_total","known_scope_adjustment","acquisition_cost_basis","acquisition_present_value","tco_present_value","comparable_total","base_amount"]
                if "buyer_quantity_adjustment" in exp or "buyer_quantity_adjustment" in rec:
                    fields.append("buyer_quantity_adjustment")
                mism=[]
                for f in fields:
                    if not _num_equal(exp.get(f),rec.get(f),atol): mism.append({"field":f,"expected":exp.get(f),"recomputed":rec.get(f)})
                for f in ['known','complete','unknown_scope_items','currency','base_currency']:
                    if exp.get(f) != rec.get(f): mism.append({'field':f,'expected':exp.get(f),'recomputed':rec.get(f)})
                for f in ('currency_basis','buyer_quantity_rows','payment_basis','payment_terms','warranty_basis','warranty_terms'):
                    if f in exp or f in rec:
                        if exp.get(f) != rec.get(f): mism.append({'field':f,'expected':exp.get(f),'recomputed':rec.get(f)})
                status="pass" if not mism else "fail"; detail={"mismatches":mism,"warnings":warns}
            ih=calc.get("input_hash") or hashlib.sha256(str(calc.get("inputs_json") or "").encode()).hexdigest()
            iid=stable_id("irecalc",calc["calculation_id"],ih,length=24)
            con.execute("INSERT INTO independent_calculations(independent_id,calculation_id,offer_id,calculation_type,method,expected_json,recomputed_json,tolerance,status,detail_json,input_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [iid,calc["calculation_id"],offer_id,ctype,"independent_decimal_float_pv_v1",json_text(exp),json_text(rec),float(atol),status,json_text(detail),ih,utc_now()])
            results.append({"independent_id":iid,"calculation_id":calc["calculation_id"],"offer_id":offer_id,"calculation_type":ctype,"status":status,"detail":detail})

        # Independently derive the eligible universe before recomputing either
        # scoring grain. Do not trust recorded exclusions or main result lists.
        sc=latest.get((None,"scoring"))
        if sc:
            exp=j(sc.get("result_json"),{}) or {}
            inp=j(sc.get("inputs_json"),{}) or {}
            eligible=_raw_eligible_offers(con)
            rec={"eligible_offers":eligible,"price_scores":[]}
            mism=[]
            suppression_claim=exp.get("status")=="suppressed_by_comparability"
            comparison_meta=con.execute("SELECT 1 FROM run_meta WHERE key='comparability_contract'").fetchone()
            comparison_checks=con.execute("SELECT 1 FROM comparability_checks LIMIT 1").fetchone()
            comparison_stage=bool(comparison_meta or comparison_checks)
            if "eligible_offers" in inp:
                _check_id_membership(mism,"inputs.eligible_offers",inp.get("eligible_offers"),eligible)
            elif suppression_claim:
                mism.append({"field":"inputs.eligible_offers","reason":"suppressed result requires the complete eligible input membership"})

            raw_failed:set[str]=set()
            raw_active=_raw_active_offers(con)
            raw_facts=_raw_verified_fact_map(con,raw_active)
            raw_financial,financial_known,financial_source=_financial_context(con,latest,raw_active)
            raw_costs={}
            suppression_costs={}
            if financial_known:
                raw_costs={oid:_raw_cost_from_sources(con,oid,raw_facts,raw_financial)[0] for oid in raw_active}
            if comparison_stage:
                # Comparability suppression keeps its existing canonical-meta
                # semantics. Legacy cost-call arguments only support price
                # membership reconstruction when metadata is absent.
                suppression_financial=_raw_financial_params(con)
                suppression_costs={oid:_raw_cost_from_sources(con,oid,raw_facts,suppression_financial)[0] for oid in raw_active}
                raw_failed=_raw_comparison_failures(con,raw_active,raw_facts,suppression_costs,suppression_financial)
            expected_suppression= comparison_stage and (len(raw_active)<2 or bool(raw_failed))
            if expected_suppression and not suppression_claim:
                mism.append({"field":"status","reason":"raw comparison evidence requires suppression","expected_failed_dimensions":sorted(raw_failed),"active_offer_count":len(raw_active),"actual":exp.get("status")})
            if suppression_claim:
                rec["status"]="suppressed_by_comparability"
                rec["active_offers"]=raw_active
                rec["failed_dimensions"]=sorted(raw_failed)
                rec["comparison_stage_present"]=comparison_stage
                rec["independently_suppressible"]=bool(expected_suppression)
                rec["cost_reconstruction"]=suppression_costs
                if not comparison_stage:
                    mism.append({"field":"comparison_stage","reason":"suppression has no comparison-stage presence evidence"})
                elif not expected_suppression:
                    mism.append({"field":"status","reason":"suppression is unsupported by raw source comparison","actual":exp.get("status")})
                if sc.get("status")!="incomplete":
                    mism.append({"field":"calculation_status","expected":"incomplete","actual":sc.get("status")})
                if exp.get("ranking_allowed") is not False:
                    mism.append({"field":"ranking_allowed","expected":False,"actual":exp.get("ranking_allowed")})
                expected_dims=sorted(raw_failed)
                actual_dims=exp.get("failed_dimensions")
                if (not isinstance(actual_dims,list) or any(type(x) is not str for x in actual_dims)
                    or len(actual_dims)!=len(set(actual_dims)) or actual_dims!=expected_dims):
                    mism.append({"field":"failed_dimensions","expected":expected_dims,"actual":actual_dims})
                for field in ("price_scores","weighted_scores","cost_ranking","weighted_ranking"):
                    if field in exp and exp[field] != []:
                        mism.append({"field":field,"reason":"suppressed scoring must not contain score/ranking lists","actual":exp[field]})

            costs=[]; missing_source_cost_rows=[]
            if not suppression_claim and financial_known:
                for oid in eligible:
                    source_cost=raw_costs.get(oid,{})
                    metric=source_cost.get("base_amount") if source_cost.get("base_currency") else source_cost.get("comparable_total")
                    currency=source_cost.get("base_currency") or source_cost.get("currency")
                    source_complete=bool(source_cost.get("known") and source_cost.get("complete") and metric is not None and currency)
                    calc=latest.get((oid,"cost_summary"))
                    if source_complete:
                        # Stored rows are checked against the source-derived
                        # expected set; they never define that set.
                        if (not calc or calc.get("status")!="complete"
                            or not (j(calc.get("result_json"),{}) or {}).get("complete")):
                            mism.append({"field":"cost_summary_membership","offer_id":oid,
                                         "reason":"source-complete cost row missing or incomplete"})
                        costs.append((oid,D(str(metric)),currency,source_cost.get("base_date")))
                    elif not calc:
                        # A genuinely incomplete source may legitimately stay
                        # out of price scoring, but a missing derived row must
                        # remain visible in the aggregate audit.
                        missing_source_cost_rows.append(oid)
            rec["comparable_offers"]=[oid for oid,_,_,_ in costs]

            currencies={currency for _,_,currency,_ in costs}
            dated={date for _,_,_,date in costs if date}
            if suppression_claim:
                expected_status="suppressed_by_comparability"
            elif len(eligible)<2:
                expected_status="not_applicable"
            elif not financial_known:
                expected_status="unverified"
            elif len(costs)<2 or len(currencies)!=1 or len(dated)>1:
                expected_status="incomplete"
            else:
                expected_status="cost_only"
            sp=inp.get("scoring_params") if isinstance(inp.get("scoring_params"),dict) else {}
            criteria=sp.get("criteria") if isinstance(sp.get("criteria"),list) else []
            usable=[]
            for criterion in criteria:
                if not isinstance(criterion,dict):
                    mism.append({"field":"criteria","reason":"criterion must be an object"})
                    continue
                if criterion.get("monetized_in_cost"): continue
                weight=dec(criterion.get("weight")); scores=criterion.get("scores")
                if weight is None or not isinstance(scores,dict):
                    mism.append({"field":"criteria","reason":"invalid weight/scores","criterion":criterion.get("id")})
                    continue
                if weight<0:
                    mism.append({"field":"criteria","reason":"negative weight","criterion":criterion.get("id")})
                usable.append((str(criterion.get("id") or ""),weight,scores))

            weighted=[]
            if expected_status=="cost_only" and usable:
                for oid in eligible:
                    numerator=D(0); valid=True
                    for _,weight,scores in usable:
                        score=dec(scores.get(oid))
                        if score is None or score<0 or score>10 or weight<0:
                            valid=False; break
                        numerator+=weight*score
                    if valid and abs(sum((w for _,w,_ in usable),D(0))-D(100))<=D("0.0001"):
                        weighted.append({"offer_id":oid,"total_score_0_10":str((numerator/D(100)).quantize(D("0.001")))})
                if len(weighted)>=2: expected_status="weighted_complete"
            rec["status"]=expected_status

            if expected_status!="unverified" and exp.get("status")!=expected_status:
                mism.append({"field":"status","expected":expected_status,"actual":exp.get("status")})

            expected_price_ids=[]
            if expected_status in {"cost_only","weighted_complete"}:
                minimum=min(value for _,value,_,_ in costs)
                for oid,value,_,_ in costs:
                    score=D(10)*minimum/value
                    rec["price_scores"].append({"offer_id":oid,"price_score_0_10":str(score.quantize(D("0.01")))})
                    expected_price_ids.append(oid)
                if _check_id_membership(mism,"price_scores",[x.get("offer_id") if isinstance(x,dict) else None for x in exp.get("price_scores",[])] if isinstance(exp.get("price_scores"),list) else exp.get("price_scores"),expected_price_ids):
                    expmap={x.get("offer_id"):x.get("price_score_0_10") for x in exp.get("price_scores",[]) if isinstance(x,dict)}
                    for row in rec["price_scores"]:
                        if not _num_equal(expmap.get(row["offer_id"]),row["price_score_0_10"],stol):
                            mism.append({"field":"price_score","offer_id":row["offer_id"],"expected":expmap.get(row["offer_id"]),"recomputed":row["price_score_0_10"]})
                rec["cost_ranking"]=[oid for oid,_,_,_ in sorted(costs,key=lambda row:row[1])]
                _check_id_membership(mism,"cost_ranking",exp.get("cost_ranking"),rec["cost_ranking"])
                if exp.get("cost_ranking")!=rec["cost_ranking"]:
                    mism.append({"field":"cost_ranking","expected":rec["cost_ranking"],"actual":exp.get("cost_ranking")})
            elif expected_status!="unverified":
                for field in ("price_scores","cost_ranking","weighted_scores","weighted_ranking"):
                    if field in exp:
                        _check_id_membership(mism,field,[x.get("offer_id") if isinstance(x,dict) else None for x in exp[field]] if field in {"price_scores","weighted_scores"} and isinstance(exp[field],list) else exp[field],[])

            if expected_status=="weighted_complete":
                rec["weighted_scores"]=weighted
                rec["weighted_ranking"]=[row["offer_id"] for row in sorted(weighted,key=lambda row:D(row["total_score_0_10"]),reverse=True)]
                ids=[x.get("offer_id") if isinstance(x,dict) else None for x in exp.get("weighted_scores",[])] if isinstance(exp.get("weighted_scores"),list) else exp.get("weighted_scores")
                if _check_id_membership(mism,"weighted_scores",ids,[x["offer_id"] for x in weighted]):
                    expws={x.get("offer_id"):x.get("total_score_0_10") for x in exp.get("weighted_scores",[]) if isinstance(x,dict)}
                    for row in weighted:
                        if not _num_equal(expws.get(row["offer_id"]),row["total_score_0_10"],stol):
                            mism.append({"field":"weighted_score","offer_id":row["offer_id"],"expected":expws.get(row["offer_id"]),"recomputed":row["total_score_0_10"]})
                ranking=exp.get("weighted_ranking")
                if not isinstance(ranking,list) or ranking!=rec["weighted_ranking"]:
                    mism.append({"field":"weighted_ranking","expected":rec["weighted_ranking"],"actual":ranking})
                ordered=sorted((D(row["total_score_0_10"]) for row in weighted),reverse=True)
                gap=(ordered[0]-ordered[1])/ordered[0] if ordered and len(ordered)>=2 and ordered[0]>0 else None
                rec["top_relative_gap"]=str(gap.quantize(D("0.0001"))) if gap is not None else None
                if not _num_equal(exp.get("top_relative_gap"),rec["top_relative_gap"],stol):
                    mism.append({"field":"top_relative_gap","expected":rec["top_relative_gap"],"actual":exp.get("top_relative_gap")})
                total_w=sum((weight for _,weight,_ in usable),D(0)); distinguishing=D(0)
                for _,weight,scores in usable:
                    values=[dec(scores.get(oid)) for oid in eligible]; values=[value for value in values if value is not None]
                    if len(values)>=2 and len(set(values))>1: distinguishing+=weight
                ratio=distinguishing/total_w if total_w else D(0)
                rec["distinguishing_weight_ratio"]=str(ratio.quantize(D("0.0001")))
                if not _num_equal(exp.get("distinguishing_weight_ratio"),rec["distinguishing_weight_ratio"],stol):
                    mism.append({"field":"distinguishing_weight_ratio","expected":rec["distinguishing_weight_ratio"],"actual":exp.get("distinguishing_weight_ratio")})
            elif expected_status!="unverified" and any(field in exp and exp[field] not in (None,[]) for field in ("weighted_scores","weighted_ranking")):
                mism.append({"field":"weighted_scores","reason":"unexpected weighted results for status","status":expected_status})

            status="fail" if mism else ("unverified" if expected_status in {"incomplete","unverified"} else "pass")
            iid=stable_id("irecalc",sc["calculation_id"],sc.get("input_hash") or "",length=24)
            con.execute("INSERT INTO independent_calculations(independent_id,calculation_id,offer_id,calculation_type,method,expected_json,recomputed_json,tolerance,status,detail_json,input_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        [iid,sc["calculation_id"],None,"scoring","independent_scoring_v3",json_text(exp),json_text(rec),float(stol),status,json_text({"mismatches":mism}),sc.get("input_hash") or "",utc_now()])
            results.append({"independent_id":iid,"calculation_id":sc["calculation_id"],"offer_id":None,"calculation_type":"scoring","status":status,"detail":{"mismatches":mism}})
            if missing_source_cost_rows:
                results.append({"independent_id":None,"calculation_id":sc["calculation_id"],"offer_id":None,
                                "calculation_type":"source_cost_membership","status":"unverified",
                                "detail":{"reason":"source cost incomplete and derived row missing","offer_ids":missing_source_cost_rows,
                                          "financial_parameter_source":financial_source}})

        failed=[x for x in results if x["status"]=="fail"]
        unverified=[x for x in results if x["status"]=="unverified"]
        out={"status":"PASS" if results and not failed and not unverified else ("FAIL" if failed else "UNVERIFIED"),"failed":failed,"unverified":unverified,"checks":results,"checked_at":utc_now(),
             "note":"Independent recomputation uses a separate implementation and does not call procurement_math helpers."}
        p=run_root/"qa"/"independent_recompute.json"; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        sha=sha256_file(p); aid=stable_id("art","independent_recompute",sha,length=22)
        con.execute("INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)",
                    [aid,"independent_recompute",str(p.relative_to(run_root)),sha,"[]","ready",utc_now()])
        if hasattr(con,"commit"): con.commit()
        return out
    finally: con.close()


def main():
    ap=argparse.ArgumentParser(description="Independently recompute critical procurement calculations")
    ap.add_argument("--run",required=True); a=ap.parse_args(); print(json.dumps(run(Path(a.run)),ensure_ascii=False,indent=2,default=str))
if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
