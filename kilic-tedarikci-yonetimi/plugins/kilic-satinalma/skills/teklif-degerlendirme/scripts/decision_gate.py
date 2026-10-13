from __future__ import annotations

from question_waits import guard_run_operation

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from common import json_text
from generated_issues import GeneratedIssues
from active_records import current_calculations
from db import connect, get_meta, rows_as_dict, set_meta, set_state

CRITICAL_FIELDS = ["total", "currency", "payment", "delivery", "quote_date", "validity"]
BAD_STATUSES = {"missing", "unreadable", "conflicting", "requires_confirmation"}


def _active_offers(con) -> list[dict[str, Any]]:
    return rows_as_dict(con, "SELECT offer_id,supplier_id,quote_date,validity_end,status FROM offers WHERE status='active' ORDER BY offer_id")


@guard_run_operation
def run_gate(run_root: Path, analysis_date: date | None = None) -> dict[str, Any]:
    analysis_date = analysis_date or date.today()
    con = connect(run_root)
    reasons: list[dict[str, Any]] = []
    try:
        generated = GeneratedIssues(con, "decision_gate")
        def _issue(con, owner, severity, issue_type, question, fact_ids):
            key = json_text([owner, issue_type, fact_ids]) if fact_ids else issue_type
            return generated.emit(key, owner, severity, issue_type, question, fact_ids)
        offers = _active_offers(con)
        if not offers:
            reasons.append({"code": "NO_ACTIVE_OFFERS", "critical": True})
        for offer in offers:
            offer_id = offer["offer_id"]
            supplier_id = offer["supplier_id"]
            from buyer_controls import date_basis
            validity_basis = date_basis(con, offer_id, 'validity')
            quote_basis = date_basis(con, offer_id, 'quote_date')
            validity_end = (validity_basis['value']['value'] if validity_basis else offer.get('validity_end'))
            if validity_end:
                try:
                    days_left = (date.fromisoformat(str(validity_end)) - analysis_date).days
                    if days_left < 0:
                        reasons.append({"code": "EXPIRED_OFFER", "offer_id": offer_id, "critical": True, "detail": str(validity_end)})
                        _issue(con, f"FIRMA:{supplier_id}", "critical", "offer_validity", f"Confirm or renew expired offer validity for {offer_id}.", [f"{offer_id}/field/validity"])
                    elif days_left < 15:
                        reasons.append({"code": "VALIDITY_LT_15_DAYS", "offer_id": offer_id, "critical": True, "detail": days_left})
                        _issue(con, f"FIRMA:{supplier_id}", "critical", "offer_validity", f"Renew offer {offer_id}; fewer than 15 days of validity remain.", [f"{offer_id}/field/validity"])
                except Exception:
                    reasons.append({"code": "INVALID_VALIDITY_DATE", "offer_id": offer_id, "critical": True, "detail": str(validity_end)})
            quote_date = (quote_basis['value']['value'] if quote_basis else offer.get('quote_date'))
            if quote_date:
                try:
                    age_days = (analysis_date - date.fromisoformat(str(quote_date))).days
                    if age_days > 60:
                        reasons.append({"code": "OFFER_AGE_GT_60_DAYS", "offer_id": offer_id, "critical": True, "detail": age_days})
                        _issue(con, f"FIRMA:{supplier_id}", "critical", "offer_age", f"Obtain a current dated offer for {offer_id}; the offer is {age_days} days old.", [f"{offer_id}/field/quote_date"])
                    elif age_days >= 30:
                        reasons.append({"code": "OFFER_AGE_30_60_DAYS", "offer_id": offer_id, "critical": False, "detail": age_days})
                        _issue(con, f"FIRMA:{supplier_id}", "medium", "offer_age_warning", f"Confirm that pricing and terms remain current for {offer_id}; the offer is {age_days} days old.", [f"{offer_id}/field/quote_date"])
                except Exception:
                    reasons.append({"code": "INVALID_QUOTE_DATE", "offer_id": offer_id, "critical": True, "detail": str(quote_date)})
            for field in CRITICAL_FIELDS:
                if field in {'validity', 'quote_date'}:
                    basis = validity_basis if field == 'validity' else quote_basis
                    if basis:
                        unknown = basis['value']['date_status'] == 'unknown'
                        from effective_fields import unknown_quote_is_nonmaterial
                        nonmaterial = unknown and field=='quote_date' and unknown_quote_is_nonmaterial(con,offer_id)
                        reasons.append({'code':'BUYER_DATE_UNKNOWN' if unknown else 'BUYER_DATE_BASIS',
                                        'offer_id':offer_id,'field':field,'critical':unknown and not nonmaterial,'detail':basis,
                                        'rationale':('Teklif tarihi bilinmiyor; güncel geçerlilik ayrı, kapsamlı ve bağımsız kontrol edilmiş kullanıcı kanıtıyla belirlenmiştir. Teklif yaşı uydurulmaz.' if nonmaterial else None)})
                        # Unknown is an answered limitation, never a verified date.
                        # No repeated user question is generated for that answer.
                        continue
                if field == 'payment':
                    from buyer_controls import payment_basis
                    basis = payment_basis(con, offer_id)
                    if basis:
                        reasons.append({'code':'BUYER_PAYMENT_BASIS','offer_id':offer_id,'critical':False,'detail':basis})
                        continue
                if field == 'currency':
                    from buyer_controls import currency_basis
                    basis = currency_basis(con, offer_id)
                    if basis and basis['basis'] == 'buyer_declaration':
                        reasons.append({'code':'BUYER_CURRENCY_BASIS','offer_id':offer_id,'critical':False,'detail':basis})
                        continue
                row = con.execute(
                    "SELECT fact_id,evidence_status FROM facts WHERE offer_id=? AND field_key=? ORDER BY updated_at DESC LIMIT 1",
                    [offer_id, field],
                ).fetchone()
                if not row or row[1] != "verified":
                    fact_id = row[0] if row else f"{offer_id}/field/{field}"
                    status = row[1] if row else "missing"
                    reasons.append({"code": "CRITICAL_FIELD_OPEN", "offer_id": offer_id, "field": field, "status": status, "critical": True})
                    _issue(con, f"FIRMA:{supplier_id}", "critical", "critical_field", f"Confirm the {field} field for offer {offer_id}.", [fact_id])

        # Quantity comparability is a deterministic early warning when at least two offers state quantities.
        quantity_rows = rows_as_dict(
            con,
            "SELECT offer_id,fact_id,value_number FROM facts WHERE field_key='quantity' AND evidence_status='verified' AND value_number IS NOT NULL"
        )
        quantities = [(r["offer_id"], float(r["value_number"]), r["fact_id"]) for r in quantity_rows if r.get("offer_id") and float(r["value_number"]) > 0]
        if len(quantities) >= 2:
            values = [q[1] for q in quantities]
            lo, hi = min(values), max(values)
            if hi > 0 and (hi - lo) / hi > 0.05:
                reasons.append({"code": "QUANTITY_DIFFERENCE_GT_5_PERCENT", "critical": True, "detail": {"min": lo, "max": hi}})
                _issue(con, "IDARE", "high", "scope_comparability", "Confirm the common reference quantity; stated offer quantities differ by more than 5 percent.", [q[2] for q in quantities])

        # Different payment schedules need a currency-appropriate discount/financing rate before final cost equivalence.
        payment_rows = rows_as_dict(
            con,
            """SELECT f.offer_id,f.value_text,f.normalized_json,c.value_text AS currency
            FROM facts f LEFT JOIN facts c ON c.offer_id=f.offer_id AND c.field_key='currency'
            WHERE f.field_key='payment' AND f.evidence_status='verified'"""
        )
        signatures = set()
        currencies = set()
        from buyer_controls import payment_basis, currency_basis
        payment_by_offer = {row["offer_id"]: row for row in payment_rows}
        for offer in offers:
            basis = payment_basis(con, offer["offer_id"])
            if basis:
                cb = currency_basis(con, offer["offer_id"])
                payment_by_offer[offer["offer_id"]] = {"offer_id": offer["offer_id"],
                    "value_text": None, "normalized_json": json_text({"buyer_milestones":basis["value"]}),
                    "currency": (cb or {}).get("value")}
        for row in payment_by_offer.values():
            try:
                norm = json.loads(row.get("normalized_json") or "{}")
            except Exception:
                norm = {}
            schedule = norm.get("payment_schedule")
            signatures.add(json_text(norm["buyer_milestones"]) if "buyer_milestones" in norm else
                           (json_text(schedule) if isinstance(schedule, list) else str(row.get("value_text") or "").casefold()))
            if row.get("currency"):
                currencies.add(str(row["currency"]).upper())
        if len(signatures) > 1:
            fp = get_meta(run_root, "financial_parameters", {}, parse_json=True) or {}
            rate_map = fp.get("discount_rates", {}) if isinstance(fp.get("discount_rates", {}), dict) else {}
            single_rate_currency = str(fp.get("annual_discount_rate_currency") or "").upper()
            missing_rate = []
            for currency in sorted(currencies):
                has_rate = currency in rate_map or (single_rate_currency == currency and fp.get("annual_discount_rate") is not None)
                if not has_rate:
                    missing_rate.append(currency)
            if missing_rate:
                reasons.append({"code": "PAYMENT_COMPARABILITY_RATE_MISSING", "critical": True, "currencies": missing_rate})
                _issue(con, "IDARE", "critical", "payment_comparability", f"Provide annual effective discount/financing rate for {', '.join(missing_rate)} to compare different payment schedules.", [])

        bad_req_rows = rows_as_dict(
            con,
            """
            SELECT fact_id,offer_id,supplier_id,requirement_id,evidence_status
            FROM facts
            WHERE critical=true AND requirement_id IS NOT NULL
              AND evidence_status<>'verified'
            """,
        )
        for r in bad_req_rows:
            reasons.append({"code": "CRITICAL_REQUIREMENT_UNRESOLVED", "offer_id": r.get("offer_id"), "requirement_id": r.get("requirement_id"), "critical": True})
            owner = f"FIRMA:{r['supplier_id']}" if r.get("supplier_id") else "IDARE"
            _issue(con, owner, "critical", "requirement_unresolved", f"Resolve critical requirement {r.get('requirement_id')} for offer {r.get('offer_id') or 'N/A'}.", [r["fact_id"]])

        unreadable_critical = rows_as_dict(
            con,
            """
            SELECT d.document_id,d.filename,d.document_role
            FROM documents d
            WHERE d.active=true AND d.parse_status='unreadable' AND d.document_role IN ('offer','specification')
            """,
        )
        for d in unreadable_critical:
            reasons.append({"code": "CRITICAL_SOURCE_UNREADABLE", "document_id": d["document_id"], "critical": True})
            _issue(con, "IDARE", "critical", "source_unreadable", f"Provide a readable version of critical source {d['filename']}.", [])

        comparability = get_meta(run_root, "comparability_contract", {}, parse_json=True) or {}
        if comparability and not comparability.get("ranking_allowed", False):
            reasons.append({"code": "COMPARABILITY_CONTRACT_FAILED", "critical": True, "dimensions": comparability.get("failed_dimensions", [])})
            _issue(con, "IDARE", "critical", "comparability_contract", "Resolve the comparison basis before ranking or final supplier recommendation.", [])

        grain_fail = con.execute("SELECT count(*) FROM grain_checks WHERE critical=true AND status<>'pass'").fetchone()[0]
        if grain_fail:
            reasons.append({"code": "GRAIN_INTEGRITY_FAILED", "count": grain_fail, "critical": True})

        # Every active offer must have a latest decision-grade cost calculation.
        # An invalid payment/TCO/FX input may still leave a numeric fallback in
        # result_json; that fallback must never make the decision sufficient.
        latest_cost_rows = [r for r in current_calculations(con) if r["calculation_type"] == "cost_summary" and r["offer_id"] is not None]
        latest_cost = {}
        for row in latest_cost_rows:
            latest_cost[row["offer_id"]] = row
        bad_costs = []
        for offer in offers:
            row = latest_cost.get(offer["offer_id"])
            if not row:
                bad_costs.append({"offer_id": offer["offer_id"], "reason": "missing_cost_summary"})
                continue
            try:
                obj = json.loads(row.get("result_json") or "{}")
            except Exception:
                obj = {}
            if row.get("status") != "complete" or not obj.get("complete"):
                bad_costs.append({"offer_id": offer["offer_id"], "calculation_id": row.get("calculation_id"), "status": row.get("status"), "warnings": obj.get("warnings", [])})
        if bad_costs:
            reasons.append({"code": "COST_CALCULATION_INCOMPLETE", "count": len(bad_costs), "critical": True, "detail": bad_costs})
            _issue(con, "IDARE", "critical", "cost_calculation", "Resolve incomplete or invalid cost calculations before ranking or final recommendation.", [])

        independent_fail = con.execute("SELECT count(*) FROM independent_calculations WHERE status<>'pass'").fetchone()[0]
        if independent_fail:
            reasons.append({"code": "INDEPENDENT_RECOMPUTE_NOT_VERIFIED", "count": independent_fail, "critical": True})

        bridge_fail = con.execute("SELECT count(*) FROM cost_bridges WHERE status<>'pass'").fetchone()[0]
        if bridge_fail:
            reasons.append({"code": "COST_BRIDGE_NOT_VERIFIED", "count": bridge_fail, "critical": True})

        dq_critical = con.execute("SELECT count(*) FROM data_quality_findings WHERE status='open' AND severity='critical'").fetchone()[0]
        if dq_critical:
            reasons.append({"code": "CRITICAL_DATA_QUALITY", "count": dq_critical, "critical": True})

        generated.finish()
        scope_rows = rows_as_dict(
            con,
            "SELECT issue_id FROM open_issues WHERE status='open' AND issue_type='scope_comparability' AND severity IN ('critical','high')",
        )
        if scope_rows:
            reasons.append({"code": "UNCOMPARABLE_SCOPE", "count": len(scope_rows), "critical": True})

        issue_count = con.execute("SELECT count(*) FROM open_issues WHERE status='open' AND severity='critical'").fetchone()[0]
        if issue_count:
            reasons.append({"code": "CRITICAL_OPEN_ISSUES", "count": issue_count, "critical": True})

        sufficient = not any(r.get("critical") for r in reasons)
        result = {
            "analysis_date": analysis_date.isoformat(),
            "status": "SUFFICIENT" if sufficient else "PRELIMINARY_ONLY",
            "reasons": reasons,
            "skip_expensive_final_stages": not sufficient,
            "answered_unknown_only": bool([r for r in reasons if r.get('critical')]) and
                all(r.get('code') == 'BUYER_DATE_UNKNOWN' for r in reasons if r.get('critical')),
        }
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('decision_sufficiency',?)", [json_text(result)])
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    set_meta(run_root, "decision_status", "SUFFICIENT" if sufficient else "PRELIMINARY_ONLY")
    set_state(run_root, "SUFFICIENCY", "PASS" if sufficient else "PARTIAL", result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic decision sufficiency gate")
    ap.add_argument("--run", required=True)
    ap.add_argument("--analysis-date")
    args = ap.parse_args()
    d = date.fromisoformat(args.analysis_date) if args.analysis_date else None
    print(json.dumps(run_gate(Path(args.run), d), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
