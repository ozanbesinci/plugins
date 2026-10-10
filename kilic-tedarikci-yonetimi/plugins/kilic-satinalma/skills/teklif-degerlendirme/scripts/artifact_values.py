from __future__ import annotations
import json
from typing import Any


def comparison_fact_path(fact: dict[str, Any]) -> str:
    # Compare the representation exported to this column, not a different
    # numeric/date representation carried by the same canonical fact.
    if fact.get("field_key") == "total":
        return "value_number"
    for key in ("value_text", "value_date", "value_number"):
        if fact.get(key) is not None:
            return key
    return "value_text"


def comparison_fact_value(fact: dict[str, Any]) -> Any:
    return fact.get(comparison_fact_path(fact))

def ranking_visible(meta: dict[str, Any]) -> bool:
    contract=meta.get("comparability_contract") or {}
    if isinstance(contract,str):
        contract=json.loads(contract)
    return bool(contract.get("ranking_allowed")) and meta.get("decision_status")=="SUFFICIENT"


def evidence_label(fact: dict[str, Any]) -> str:
    return {"verified":"Doğrulandı","requires_confirmation":"Teyit bekleniyor","missing":"Eksik",
            "conflicting":"Çelişkili","unreadable":"Okunamıyor","assumption":"Varsayım","excluded":"Kapsam dışı"}.get(fact.get("evidence_status"),"Teyit bekleniyor")


def pending_offer_fields(oid, facts):
    return sorted({f["field_key"] for f in facts if f.get("offer_id")==oid and f.get("critical") and f.get("evidence_status")!="verified"})


def offer_display_status(oid, facts, exclusions, meta):
    if any(e.get("offer_id")==oid and e.get("status")=="confirmed" for e in exclusions):
        return "Elendi"
    if pending_offer_fields(oid,facts):
        return "Teyit bekleniyor"
    return "Uygun" if ranking_visible(meta) else "Ön değerlendirme"
