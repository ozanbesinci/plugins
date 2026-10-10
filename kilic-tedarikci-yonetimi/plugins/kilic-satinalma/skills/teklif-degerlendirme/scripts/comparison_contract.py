from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from active_records import current_calculations
from db import connect, get_meta, rows_as_dict
from normalize import vat_basis
from generated_issues import GeneratedIssues

BAD = {"missing", "unreadable", "conflicting", "requires_confirmation"}


def _j(v: Any, default: Any = None) -> Any:
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v) if v is not None else default
    except Exception:
        return default


def _verified_fact_map(con) -> dict[tuple[str, str], dict[str, Any]]:
    rows = rows_as_dict(con, "SELECT * FROM facts WHERE offer_id IS NOT NULL ORDER BY updated_at,fact_id")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    rank = {"adjudicated": 5, "semantic_llm": 4, "vision": 3, "duckdb_pdf_secondary": 2}
    for row in rows:
        key = (row["offer_id"], row["field_key"])
        if row.get("evidence_status") != "verified":
            continue
        prev = out.get(key)
        if prev is None or rank.get(row.get("extraction_path"), 1) >= rank.get(prev.get("extraction_path"), 1):
            out[key] = row
    return out


def _value(row: dict[str, Any] | None) -> Any:
    if not row:
        return None
    if row.get("value_number") is not None:
        return row["value_number"]
    return row.get("value_date") or row.get("value_text")


def _source_scope_sections(con, row: dict | None) -> tuple[str, ...] | None:
    """Compare all cited section identities, never their model paraphrases.

    None is the legacy scalar form. An empty tuple is an invalid structured
    form and must block comparison rather than falling back to the scalar.
    """
    if not row:
        return None
    normalized = _j(row.get('normalized_json'), {})
    if not isinstance(normalized, dict) or 'sections' not in normalized:
        return None
    sections = normalized['sections']
    if not isinstance(sections, list) or not sections:
        return ()
    identities = []
    for section in sections:
        if not isinstance(section, dict):
            return ()
        refs = section.get('evidence_refs')
        if not isinstance(refs, list) or not refs or len(set(refs)) != len(refs):
            return ()
        for ref in refs:
            ev = con.execute('''SELECT e.quote,e.evidence_status,e.extraction_path,d.offer_id,d.active
                FROM evidence e JOIN documents d ON d.document_id=e.document_id
                WHERE e.evidence_id=?''', [ref]).fetchone()
            if not ev or ev[1] != 'verified' or ev[2] == 'vision' or ev[3] != row['offer_id'] or not ev[4]:
                return ()
            text = re.sub(r'^[A-Z]+\d+\s*=\s*', '', str(ev[0] or '').strip())
            text = ' '.join(text.casefold().split())
            if not text:
                return ()
            identities.append(text)
    if len(set(identities)) != len(identities):
        return ()
    return tuple(sorted(identities))


def assess(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        con.execute("DELETE FROM comparability_checks")
        offers = rows_as_dict(con, "SELECT offer_id,supplier_id FROM offers WHERE status='active' ORDER BY offer_id")
        offer_ids = [o["offer_id"] for o in offers]
        facts = _verified_fact_map(con)
        from buyer_controls import currency_basis
        currency_bases = {oid: currency_basis(con, oid) for oid in offer_ids}
        financial = get_meta(run_root, "financial_parameters", {}, parse_json=True) or {}
        offer_params = financial.get("offer_parameters", {}) if isinstance(financial.get("offer_parameters", {}), dict) else {}
        cost_rows = [r for r in current_calculations(con) if r["calculation_type"] == "cost_summary"]
        costs = {r["offer_id"]: {**r, "result": _j(r.get("result_json"), {}) or {}} for r in cost_rows if r.get("offer_id")}
        checks: list[dict[str, Any]] = []

        def add(dimension: str, status: str, critical: bool, reference: Any, observed: Any, normalization: str, evidence: Any, offer_id: str | None = None) -> None:
            rev_obj = {"dimension": dimension, "offer_id": offer_id, "reference": reference, "observed": observed, "normalization": normalization, "evidence": evidence}
            rev = hashlib.sha256(json_text(rev_obj).encode()).hexdigest()
            cid = stable_id("cmp", dimension, offer_id or "global", rev, length=24)
            row = {
                "check_id": cid, "dimension": dimension, "offer_id": offer_id,
                "reference_value": None if reference is None else json_text(reference) if isinstance(reference, (dict, list)) else str(reference),
                "observed_value": None if observed is None else json_text(observed) if isinstance(observed, (dict, list)) else str(observed),
                "status": status, "critical": critical, "normalization": normalization,
                "evidence_json": json_text(evidence or []), "revision": rev, "assessed_at": utc_now(),
            }
            checks.append(row)
            con.execute(
                "INSERT INTO comparability_checks(check_id,dimension,offer_id,reference_value,observed_value,status,critical,normalization,evidence_json,revision,assessed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [row[k] for k in ["check_id","dimension","offer_id","reference_value","observed_value","status","critical","normalization","evidence_json","revision","assessed_at"]],
            )

        # Core price facts must exist for every active offer.
        for field in ("total", "currency"):
            if field == 'currency' and any(v and v['basis']=='buyer_declaration' for v in currency_bases.values()):
                missing = [oid for oid in offer_ids if not currency_bases[oid]]
                add(field, "pass" if not missing else "fail", True, "sourced_or_explicit_buyer_basis", {"missing":missing,"bases":currency_bases}, "explicit buyer currency when source is missing", [v['reference'] for v in currency_bases.values() if v])
            else:
                missing = [oid for oid in offer_ids if (oid, field) not in facts]
                add(field, "pass" if not missing else "fail", True, "verified_for_all_offers", {"missing": missing}, "none", [facts[(oid, field)]["fact_id"] for oid in offer_ids if (oid, field) in facts])

        # Quantity is a comparability dimension only when at least one offer states it.
        qrows = [(oid, facts.get((oid, "quantity"))) for oid in offer_ids]
        qpresent = [(oid, r) for oid, r in qrows if r and r.get("value_number") not in (None, 0)]
        if qpresent:
            if len(qpresent) != len(offer_ids):
                add("quantity", "fail", True, "same_reference_quantity_or_normalization", {"missing": [oid for oid, r in qrows if not r]}, "required", [r["fact_id"] for _, r in qpresent])
            else:
                vals = [float(r["value_number"]) for _, r in qpresent]
                hi, lo = max(vals), min(vals)
                tol = float((get_meta(run_root, "comparability_quantity_tolerance", None) or 0.05))
                ratio = 0.0 if hi == 0 else (hi - lo) / hi
                unit_map = {oid: str(r.get("unit") or "").strip().casefold() for oid, r in qpresent}
                units = {u for u in unit_map.values() if u}
                missing_units = [oid for oid, u in unit_map.items() if not u]
                ok = ratio <= tol and len(units) == 1 and not missing_units
                add(
                    "quantity",
                    "pass" if ok else "fail",
                    True,
                    {"relative_tolerance": tol, "explicit_common_unit_required": True},
                    {"values": dict((oid, r["value_number"]) for oid, r in qpresent), "units": unit_map, "missing_units": missing_units, "relative_gap": ratio},
                    "same quantity and explicit unit",
                    [r["fact_id"] for _, r in qpresent],
                )

        # Explicit product/scope labels must agree when suppliers state them.
        scope_rows = [(oid, facts.get((oid, "scope_signature"))) for oid in offer_ids]
        section_keys = {oid: _source_scope_sections(con, row) for oid, row in scope_rows}
        stated_scope = [(oid, r) for oid, r in scope_rows if r and str(_value(r) or "").strip()]
        if any(value is not None for value in section_keys.values()):
            missing_scope = [oid for oid, value in section_keys.items() if not value]
            scope_map = section_keys
            same_scope = len(set(section_keys.values())) == 1
            ok = not missing_scope and same_scope
            add('scope_identity', 'pass' if ok else 'fail', True,
                'same_verified_source_sections', {'values': scope_map, 'missing': missing_scope},
                'all section identities bound to active verified same-offer source evidence',
                [r['fact_id'] for _, r in scope_rows if r])
        elif stated_scope:
            missing_scope = [oid for oid, r in scope_rows if not r or not str(_value(r) or "").strip()]
            scope_map = {oid: " ".join(str(_value(r)).casefold().split()) for oid, r in stated_scope}
            same_scope = len(set(scope_map.values())) == 1
            ok = not missing_scope and same_scope
            add(
                "scope_identity",
                "pass" if ok else "fail",
                True,
                "same_explicit_product_or_scope",
                {"values": scope_map, "missing": missing_scope},
                "explicit scope identity",
                [r["fact_id"] for _, r in stated_scope],
            )

        # Currency differences are acceptable only after complete conversion to one base currency/date.
        currencies = {oid: (currency_bases[oid] or {}).get('value','') for oid in offer_ids}
        uniq_cur = {v for v in currencies.values() if v}
        if len(uniq_cur) <= 1:
            add("currency_basis", "pass", True, "single_currency", currencies, "none", [facts[(oid,"currency")]["fact_id"] for oid in offer_ids if (oid,"currency") in facts])
        else:
            base_cur = str(financial.get("base_currency") or "").upper()
            base_dates = set()
            bad: list[str] = []
            for oid in offer_ids:
                c = (costs.get(oid) or {}).get("result", {})
                if not c.get("complete") or c.get("base_amount") is None or not c.get("base_currency"):
                    bad.append(oid)
                fx_used = c.get("fx_used") or {}
                if currencies.get(oid) != base_cur and (
                    not fx_used.get("source") or not fx_used.get("date") or fx_used.get("provenance_valid") is False
                ):
                    bad.append(oid)
                if c.get("base_date"):
                    base_dates.add(str(c.get("base_date")))
                if base_cur and str(c.get("base_currency") or "").upper() != base_cur:
                    bad.append(oid)
            ok = bool(base_cur) and not bad and len(base_dates) == 1
            add("currency_basis", "pass" if ok else "fail", True, {"base_currency": base_cur or None, "single_base_date": True, "fx_source_required": True}, {"offer_currencies": currencies, "bad_offers": sorted(set(bad)), "base_dates": sorted(base_dates)}, "FX normalization", [costs[oid]["calculation_id"] for oid in offer_ids if oid in costs])

        # Different payment terms require PV normalization for every offer.
        payment_sig: dict[str, str] = {}
        for oid in offer_ids:
            f = facts.get((oid, "payment"))
            norm = _j((f or {}).get("normalized_json"), {}) or {}
            schedule = norm.get("payment_schedule")
            from buyer_controls import payment_basis
            basis = payment_basis(con, oid)
            payment_sig[oid] = json_text(basis["value"]) if basis else (json_text(schedule) if isinstance(schedule, list) else str(_value(f) or "").casefold())
        if len(set(payment_sig.values())) <= 1:
            add("payment_basis", "pass", True, "same_payment_terms", payment_sig, "none", [facts[(oid,"payment")]["fact_id"] for oid in offer_ids if (oid,"payment") in facts])
        else:
            bad = [oid for oid in offer_ids if (costs.get(oid) or {}).get("result", {}).get("acquisition_present_value") is None]
            add("payment_basis", "pass" if not bad else "fail", True, "present_value_normalized", {"signatures": payment_sig, "missing_pv": bad}, "NPV normalization", [costs[oid]["calculation_id"] for oid in offer_ids if oid in costs])

        # Different Incoterms require an explicit bridge except already-delivered DDP basis.
        incos = {oid: str(_value(facts.get((oid, "incoterms"))) or "").strip().upper() for oid in offer_ids}
        known_incos = {v for v in incos.values() if v}
        if len(known_incos) <= 1 and len([v for v in incos.values() if v]) in {0, len(offer_ids)}:
            add("incoterm_basis", "pass", True, "same_or_not_stated", incos, "none", [facts[(oid,"incoterms")]["fact_id"] for oid in offer_ids if (oid,"incoterms") in facts])
        elif known_incos:
            bad = []
            for oid, inco in incos.items():
                if not inco:
                    bad.append(oid); continue
                if inco.startswith("DDP"):
                    continue
                p = offer_params.get(oid, {}) if isinstance(offer_params.get(oid, {}), dict) else {}
                if not isinstance(p.get("import_bridge"), dict):
                    bad.append(oid)
            add("incoterm_basis", "pass" if not bad else "fail", True, "DDP-equivalent", {"incoterms": incos, "missing_bridge": bad}, "import/DDP bridge", [costs[oid]["calculation_id"] for oid in offer_ids if oid in costs])

        # VAT basis differences require explicit tax normalization.
        raw_vats = {oid: str(_value(facts.get((oid, "vat"))) or "").strip() for oid in offer_ids}
        vats = {oid: vat_basis(value) for oid, value in raw_vats.items()}
        unknown_vat = [oid for oid, value in raw_vats.items() if value and vats[oid] is None]
        known_vat = {v for v in vats.values() if v}
        stated_vat = [v for v in vats.values() if v]
        if not unknown_vat and len(known_vat) <= 1 and len(stated_vat) in {0, len(offer_ids)}:
            add("vat_basis", "pass", True, "same_or_not_stated_vat_basis", vats, "none", [facts[(oid,"vat")]["fact_id"] for oid in offer_ids if (oid,"vat") in facts])
        else:
            bad = []
            for oid in offer_ids:
                p = offer_params.get(oid, {}) if isinstance(offer_params.get(oid, {}), dict) else {}
                if not vats.get(oid) or not isinstance(p.get("vat"), dict):
                    bad.append(oid)
            add("vat_basis", "pass" if not bad else "fail", True, "cost-basis VAT normalization", {"vat_terms": vats, "missing_or_unnormalized_vat": bad}, "VAT cost basis", [costs[oid]["calculation_id"] for oid in offer_ids if oid in costs])

        # Unknown scope blocks ranking.
        scope_bad = []
        for oid in offer_ids:
            c = (costs.get(oid) or {}).get("result", {})
            if int(c.get("unknown_scope_items") or 0) > 0 or not c.get("complete"):
                scope_bad.append(oid)
        add("scope_basis", "pass" if not scope_bad else "fail", True, "complete_known_scope", {"incomplete_offers": scope_bad}, "5A known-scope normalization", [costs[oid]["calculation_id"] for oid in offer_ids if oid in costs])

        failed = [c for c in checks if c["critical"] and c["status"] != "pass"]
        ranking_allowed = len(offer_ids) >= 2 and not failed
        result = {
            "status": "PASS" if ranking_allowed else "FAIL",
            "ranking_allowed": ranking_allowed,
            "active_offers": offer_ids,
            "failed_dimensions": sorted({c["dimension"] for c in failed}),
            "checks": checks,
            "assessed_at": utc_now(),
        }
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES (?,?)", ["comparability_contract", json_text(result)])

        if not ranking_allowed:
            # Prevent downstream LLM/report logic from treating a provisional score as decision-grade.
            rows = [r for r in current_calculations(con) if r["offer_id"] is None and r["calculation_type"] == "scoring"]
            if rows:
                suppressed = {"status": "suppressed_by_comparability", "ranking_allowed": False, "failed_dimensions": result["failed_dimensions"], "note": "Ranking suppressed until comparison contract passes."}
                con.execute("UPDATE calculations SET result_json=?,status=?,updated_at=? WHERE calculation_id=?", [json_text(suppressed), "incomplete", utc_now(), rows[0]["calculation_id"]])
        generated = GeneratedIssues(con, "comparison_contract")
        for dim in result["failed_dimensions"]:
            q = f"Resolve comparison basis for {dim} before ranking or final supplier recommendation."
            generated.emit(dim, "IDARE", "critical", "comparability_contract", q, [])
        # An absent optional dimension is not proof that its earlier question was resolved.
        generated.finish({c["dimension"] for c in checks})
        if hasattr(con, "commit"):
            con.commit()
        return result
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build procurement comparison-basis contract")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(assess(Path(args.run)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
