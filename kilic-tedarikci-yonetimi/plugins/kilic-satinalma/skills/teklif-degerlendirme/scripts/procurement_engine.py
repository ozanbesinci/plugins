from __future__ import annotations

from question_waits import guard_run_operation

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, get_meta, rows_as_dict, set_state
from buyer_inputs import inputs_for
from buyer_quantity import number as buyer_number, validated_rows
from procurement_math import (
    cost_score_0_10,
    ddp_equivalent,
    dec,
    distinguishing_weight_ratio,
    fx_to_base,
    present_value_schedule,
    real_rate,
    relative_top_gap,
    sequential_discount,
    tco_present_value,
    validate_payment_schedule,
    vat_split,
    weighted_score,
)

CALC_VERSION = "5.0.18"


def _json(v: Any, default: Any = None) -> Any:
    if isinstance(v, (dict, list)):
        return v
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def _store_calc(con, offer_id: str | None, calc_type: str, inputs: dict[str, Any], result: dict[str, Any], status: str) -> str:
    ih = hashlib.sha256(json_text(inputs).encode("utf-8")).hexdigest()
    calc_id = stable_id("calc", offer_id or "global", calc_type, ih, CALC_VERSION, length=24)
    con.execute(
        """
        INSERT OR REPLACE INTO calculations(calculation_id,offer_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [calc_id, offer_id, calc_type, json_text(inputs), json_text(result), CALC_VERSION, ih, status, utc_now()],
    )
    return calc_id


def _verified_fact(con, offer_id: str, field_key: str) -> dict[str, Any] | None:
    rows = rows_as_dict(
        con,
        """SELECT * FROM facts WHERE offer_id=? AND field_key=?
        ORDER BY CASE extraction_path WHEN 'adjudicated' THEN 5 WHEN 'semantic_llm' THEN 4 WHEN 'vision' THEN 3 WHEN 'duckdb_pdf_secondary' THEN 2 ELSE 1 END DESC,updated_at DESC""",
        [offer_id, field_key],
    )
    for row in rows:
        if row["evidence_status"] == "verified":
            row["normalized"] = _json(row.get("normalized_json"), {}) or {}
            return row
    return None


def apply_hard_gates(con) -> dict[str, Any]:
    exclusions = 0
    eligible: list[str] = []
    offers = rows_as_dict(con, "SELECT offer_id,supplier_id FROM offers WHERE status='active' ORDER BY offer_id")
    for offer in offers:
        rows = rows_as_dict(
            con,
            """
            SELECT f.fact_id,f.requirement_id,f.value_text,f.evidence_status,r.category,r.critical
            FROM facts f LEFT JOIN requirements r ON r.requirement_id=f.requirement_id
            WHERE f.offer_id=? AND f.requirement_id IS NOT NULL
            """,
            [offer["offer_id"]],
        )
        failed = []
        for row in rows:
            value = (row.get("value_text") or "").casefold()
            if row.get("category") == "mandatory" and row.get("evidence_status") == "verified" and value in {"noncompliant", "uygunsuz", "fail", "failed"}:
                failed.append(row)
        if failed:
            for row in failed:
                exc_id = stable_id("exc", offer["offer_id"], row.get("requirement_id") or row["fact_id"], length=22)
                con.execute(
                    "INSERT OR REPLACE INTO exclusions(exclusion_id,offer_id,requirement_id,decision,reason,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?)",
                    [exc_id, offer["offer_id"], row.get("requirement_id"), "exclude", "Verified mandatory requirement is noncompliant.", "[]", "confirmed"],
                )
                exclusions += 1
        else:
            eligible.append(offer["offer_id"])
    return {"eligible_offers": eligible, "exclusions": exclusions}


def _fx_convert(
    amount: Decimal,
    currency: str,
    base_currency: str | None,
    fx: dict[str, Any],
    *,
    base_date: Any = None,
    assumption_acknowledged: bool = False,
) -> tuple[Decimal | None, dict[str, Any] | None]:
    if not base_currency:
        return None, None
    if currency == base_currency.upper():
        return amount, {"rate": "1", "unit": "1", "source": "same_currency", "date": base_date}
    raw = fx.get(currency)
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        rate = dec(raw.get("forex_selling") if raw.get("forex_selling") is not None else raw.get("rate"))
        unit = dec(raw.get("unit", 1))
        source = raw.get("source")
        rate_date = raw.get("date") or raw.get("base_date") or base_date
    else:
        rate = dec(raw)
        unit = Decimal(1)
        source = "user_assumption" if assumption_acknowledged else None
        rate_date = base_date
    if rate is None or unit is None:
        return None, None
    if not source or not rate_date:
        # A bare number is not decision-grade FX. Require an identified source
        # and valuation date, or an explicit recorded user assumption.
        return None, {"rate": str(rate), "unit": str(unit), "source": source, "date": rate_date, "provenance_valid": False}
    return fx_to_base(amount, rate, unit), {
        "rate": str(rate), "unit": str(unit), "source": str(source), "date": str(rate_date), "provenance_valid": True
    }


def _discount_rate(financial_params: dict[str, Any], currency: str) -> Decimal | None:
    rates = financial_params.get("discount_rates")
    if isinstance(rates, dict) and currency in rates:
        raw = rates[currency]
        if isinstance(raw, dict):
            return dec(raw.get("annual_effective_rate"))
        return dec(raw)
    rate_currency = str(financial_params.get("annual_discount_rate_currency") or "").upper()
    if rate_currency == currency:
        return dec(financial_params.get("annual_discount_rate"))
    return None


def _payment_schedule(payment_fact: dict[str, Any] | None, offer_params: dict[str, Any]) -> Any:
    supplied = offer_params.get("payment_schedule")
    if "payment_schedule" in offer_params and supplied is not None:
        return supplied
    if payment_fact:
        schedule = (payment_fact.get("normalized") or {}).get("payment_schedule")
        if isinstance(schedule, list):
            return schedule
    return None


def calculate_costs(con, financial_params: dict[str, Any]) -> dict[str, Any]:
    offers = rows_as_dict(con, "SELECT offer_id,supplier_id FROM offers WHERE status='active' ORDER BY offer_id")
    summaries: list[dict[str, Any]] = []
    base_currency = str(financial_params.get("base_currency") or "").upper() or None
    fx = financial_params.get("fx", {}) if isinstance(financial_params.get("fx", {}), dict) else {}
    base_date = financial_params.get("base_date")
    offer_parameters = financial_params.get("offer_parameters", {}) if isinstance(financial_params.get("offer_parameters", {}), dict) else {}

    for offer in offers:
        offer_id = offer["offer_id"]
        offer_params = offer_parameters.get(offer_id, {}) if isinstance(offer_parameters.get(offer_id, {}), dict) else {}
        from source_price_chain import calculate_offer_pricing, source_pricing_inputs
        pricing_inputs = source_pricing_inputs(con, offer)
        if pricing_inputs is not None:
            pricing_result = calculate_offer_pricing(pricing_inputs)
            _store_calc(con, offer_id, 'source_price_chain', pricing_inputs, pricing_result,
                        'complete' if pricing_result['complete'] else 'blocked' if pricing_result['mismatches'] else 'incomplete')
            issue_id = stable_id('issue', offer_id, 'source_price_chain_reconciliation', length=22)
            if pricing_result['mismatches']:
                previous = con.execute('SELECT created_at FROM open_issues WHERE issue_id=?', [issue_id]).fetchone()
                con.execute('INSERT OR REPLACE INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                            [issue_id, offer_id, 'critical', 'source_price_chain_reconciliation',
                             'Kaynak kalemlerinin iskonto ve KDV hesabı ile beyan tutarları uyuşmamaktadır. Geçerli fiyat ve iskonto dayanağı teyit edilmelidir.',
                             json_text(pricing_inputs['source_fact_ids']), '[]', 'open', previous[0] if previous else utc_now()])
            elif pricing_result['complete']:
                con.execute("UPDATE open_issues SET status='resolved' WHERE issue_id=? AND status='open'", [issue_id])
        total_f = _verified_fact(con, offer_id, "total")
        curr_f = _verified_fact(con, offer_id, "currency")
        buyer_currencies = inputs_for(con, offer_id, "currency")
        buyer_quantities = inputs_for(con, offer_id, "reference_quantity")
        buyer_scopes = inputs_for(con, offer_id, "scope_cost")
        commercial = {}
        commercial_inputs = {}
        for kind, fields in (("payment_terms", ("milestones",)), ("warranty_terms", ("duration_years", "scope")), ("validity_date", ("date_status", "value")), ("quote_date", ("date_status", "value"))):
            entries = inputs_for(con, offer_id, kind)
            if entries:
                values = [{key: entry[key] for key in fields} for entry in entries]
                if any(value != values[0] for value in values):
                    raise ValueError("conflicting buyer commercial declarations")
                commercial[kind] = values[0]
                commercial_inputs[kind] = entries
        if not total_f or total_f.get("value_number") is None or (not (curr_f and curr_f.get("value_text")) and len(buyer_currencies) != 1):
            result = {"known": False, "complete": False, "reason": "verified total/currency missing"}
            _store_calc(con, offer_id, "cost_summary", {}, result, "incomplete")
            summaries.append({"offer_id": offer_id, **result})
            continue

        total = dec(total_f["value_number"])
        assert total is not None
        currency_basis = "supplier_fact" if curr_f and curr_f.get("value_text") else "buyer_declaration"
        currency = str(curr_f["value_text"] if currency_basis == "supplier_fact" else buyer_currencies[0]["value"]).upper()
        if currency_basis == "supplier_fact" and buyer_currencies and any(str(x.get("value") or "").upper() != currency for x in buyer_currencies):
            raise ValueError("buyer currency conflicts with verified supplier currency")
        warnings: list[str] = []
        steps: list[dict[str, Any]] = [{"stage": "stated_total", "amount": str(total), "currency": currency}]
        if currency_basis == "buyer_declaration":
            steps.append({"stage": "buyer_currency", "currency": currency, "buyer_input": buyer_currencies[0]})

        buyer_quantity_rows: list[dict[str, Any]] = []
        buyer_quantity_adjustment = Decimal(0)
        if buyer_quantities:
            try:
                buyer_quantity_rows = validated_rows(con, offer_id, buyer_quantities, currency)
                for row in buyer_quantity_rows:
                    delta = (Decimal(row["reference_quantity"]) - Decimal(row["original_quantity"])) * Decimal(row["unit_price"])
                    row["delta"] = str(delta)
                    buyer_quantity_adjustment += delta
            except ValueError as exc:
                warnings.append(f"buyer_quantity_invalid:{exc}")
                buyer_quantity_rows = []
                buyer_quantity_adjustment = Decimal(0)

        discounts = offer_params.get("discounts")
        if isinstance(discounts, list) and discounts:
            try:
                total = sequential_discount(total, discounts)
                steps.append({"stage": "sequential_discounts", "amount": str(total), "currency": currency, "rates": discounts})
            except ValueError as exc:
                warnings.append(f"discounts_invalid:{exc}")

        scope_rows = rows_as_dict(con, "SELECT scope_id,amount,currency,status,classification,cost_role FROM scope_items WHERE offer_id=?", [offer_id])
        scope_known = Decimal(0)
        unknown_scope = 0
        for row in scope_rows:
            role = row.get("cost_role") or row.get("classification")
            if role == "included_in_price" and row.get("status") == "verified":
                continue
            supplied = [x for x in buyer_scopes if x.get("scope_id") == row["scope_id"]]
            if supplied:
                legacy_unpriced = role == "incremental_adjustment" and row.get("status") not in {"verified", "conflicting", "unreadable"}
                verified_employer_unpriced = (
                    role == "unresolved_adjustment" and row.get("classification") in {"isveren_yukumlulugu", "employer_responsibility"}
                    and row.get("status") == "verified" and row.get("amount") is None
                    and row.get("currency") is None
                )
                if len(supplied) != 1 or not (legacy_unpriced or verified_employer_unpriced):
                    warnings.append(f"buyer_scope_invalid:{row['scope_id']}")
                    unknown_scope += 1
                    continue
                try:
                    supplied_amount = buyer_number(supplied[0].get("amount"))
                    if str(supplied[0].get("currency") or "").upper() != currency:
                        raise ValueError("currency mismatch")
                    scope_known += supplied_amount
                    steps.append({"stage": "buyer_scope_cost", "scope_id": row["scope_id"], "amount": str(supplied_amount),
                                  "currency": currency, "buyer_input": supplied[0]})
                except ValueError as exc:
                    warnings.append(f"buyer_scope_invalid:{row['scope_id']}:{exc}")
                    unknown_scope += 1
                continue
            if role != "incremental_adjustment" or row.get("status") != "verified" or row.get("amount") is None:
                unknown_scope += 1
                continue
            row_currency = str(row.get("currency") or currency).upper()
            if row_currency != currency:
                unknown_scope += 1
                warnings.append(f"scope_currency_mismatch:{row.get('scope_id')}")
                continue
            amount = dec(row["amount"])
            if amount is not None:
                scope_known += amount
        for supplied in buyer_scopes:
            if not any(row["scope_id"] == supplied.get("scope_id") for row in scope_rows):
                warnings.append(f"buyer_scope_invalid:{supplied.get('scope_id')}")
                unknown_scope += 1
        acquisition = total + scope_known + buyer_quantity_adjustment
        steps.append({"stage": "scope_5A_known", "amount": str(scope_known), "currency": currency, "unknown_items": unknown_scope})
        if buyer_quantities:
            steps.append({"stage": "buyer_quantity_adjustment", "amount": str(buyer_quantity_adjustment), "currency": currency,
                          "rows": buyer_quantity_rows})

        bridge = offer_params.get("import_bridge")
        if isinstance(bridge, dict):
            try:
                b = ddp_equivalent(
                    acquisition,
                    bridge.get("included_costs", []) or [],
                    bridge.get("buyer_costs", []) or [],
                    bridge.get("non_deductible_taxes", []) or [],
                )
                acquisition = dec(b["ddp_equivalent"]) or acquisition
                steps.append({"stage": "import_ddp_bridge", **b, "currency": currency})
            except ValueError as exc:
                warnings.append(f"import_bridge_invalid:{exc}")

        vat_cfg = offer_params.get("vat")
        if isinstance(vat_cfg, dict) and vat_cfg.get("price_basis") == "net_ex_vat":
            try:
                vat = vat_split(acquisition, vat_cfg.get("rate"), vat_cfg.get("deductible_share"))
                acquisition = vat["cost_basis"]
                steps.append({"stage": "vat_cost_basis", **{k: str(v) for k, v in vat.items()}, "currency": currency})
            except ValueError as exc:
                warnings.append(f"vat_invalid:{exc}")

        payment_f = _verified_fact(con, offer_id, "payment")
        schedule = _payment_schedule(payment_f, offer_params)
        if "payment_terms" in commercial:
            # Event-based terms do not establish calendar-day cash flows.
            if offer_params.get("payment_schedule") is not None:
                raise ValueError("dated payment schedule requires reconciliation with buyer event terms")
            schedule = None
        discount_rate = _discount_rate(financial_params, currency)
        acquisition_pv: Decimal | None = None
        payment_detail: list[dict[str, Any]] = []
        if schedule is not None:
            try:
                validate_payment_schedule(acquisition, schedule)
            except ValueError as exc:
                warnings.append(f"payment_schedule_invalid:{exc}")
            else:
                if discount_rate is not None:
                    try:
                        acquisition_pv, payment_detail = present_value_schedule(acquisition, schedule, discount_rate)
                    except ValueError as exc:
                        warnings.append(f"payment_schedule_invalid:{exc}")
                else:
                    warnings.append(f"discount_rate_missing_for_{currency}")

        tco_pv: Decimal | None = None
        tco_cfg = offer_params.get("tco")
        if isinstance(tco_cfg, dict) and isinstance(tco_cfg.get("annual_costs"), list):
            tco_rate = dec(tco_cfg.get("annual_rate"))
            if tco_rate is None and tco_cfg.get("rate_basis") == "real":
                nominal = tco_cfg.get("nominal_rate")
                inflation = tco_cfg.get("inflation_rate")
                if nominal is not None and inflation is not None:
                    try:
                        tco_rate = real_rate(nominal, inflation)
                    except ValueError as exc:
                        warnings.append(f"tco_rate_invalid:{exc}")
            if tco_rate is not None:
                try:
                    tco_pv, tco_detail = tco_present_value(tco_cfg["annual_costs"], tco_rate)
                    steps.append({"stage": "tco", "present_value": str(tco_pv), "annual_rate": str(tco_rate), "detail": tco_detail, "currency": currency})
                except ValueError as exc:
                    warnings.append(f"tco_invalid:{exc}")
            else:
                warnings.append("tco_rate_missing")

        acquisition_basis = acquisition_pv if acquisition_pv is not None else acquisition
        comparable = acquisition_basis + (tco_pv or Decimal(0))
        base_amount, fx_used = _fx_convert(
            comparable,
            currency,
            base_currency,
            fx,
            base_date=base_date,
            assumption_acknowledged=bool(financial_params.get("fx_assumption_acknowledged")),
        )
        complete = unknown_scope == 0 and not any(w.startswith(("import_bridge_invalid", "vat_invalid", "payment_schedule_invalid", "tco_invalid", "buyer_quantity_invalid", "buyer_scope_invalid")) for w in warnings)
        if base_currency and base_amount is None:
            complete = False
            if fx_used and fx_used.get("provenance_valid") is False:
                warnings.append(f"fx_provenance_missing_for_{currency}")
            else:
                warnings.append(f"fx_missing_for_{currency}")

        result = {
            "known": True,
            "complete": complete,
            "stated_total": str(dec(total_f["value_number"])),
            "known_scope_adjustment": str(scope_known),
            "acquisition_cost_basis": str(acquisition),
            "acquisition_present_value": str(acquisition_pv) if acquisition_pv is not None else None,
            "tco_present_value": str(tco_pv) if tco_pv is not None else None,
            "comparable_total": str(comparable),
            "currency": currency,
            "unknown_scope_items": unknown_scope,
            "base_currency": base_currency,
            "base_date": base_date,
            "base_amount": str(base_amount) if base_amount is not None else None,
            "fx_used": fx_used,
            "payment_present_value_detail": payment_detail,
            "warnings": sorted(set(warnings)),
            "steps": steps,
        }
        inputs = {
            "total_fact": total_f["fact_id"],
            "currency_fact": curr_f["fact_id"] if curr_f else None,
            "payment_fact": payment_f["fact_id"] if payment_f else None,
            "financial_params": financial_params,
            "offer_params": offer_params,
            "scope_items": scope_rows,
        }
        if buyer_currencies or buyer_quantities or buyer_scopes:
            buyer_inputs = {"currency": buyer_currencies, "reference_quantity": buyer_quantities, "scope_cost": buyer_scopes}
            result.update({"currency_basis": currency_basis, "buyer_quantity_adjustment": str(buyer_quantity_adjustment),
                           "buyer_quantity_rows": buyer_quantity_rows, "buyer_inputs": buyer_inputs})
            inputs["buyer_inputs"] = buyer_inputs
        for kind, value in commercial.items():
            result[kind] = value
            result[(kind + "_basis" if kind in {"validity_date", "quote_date"} else kind.replace("_terms", "_basis"))] = "buyer_declaration"
        if commercial_inputs:
            result.setdefault("buyer_inputs", {}).update(commercial_inputs)
            inputs.setdefault("buyer_inputs", {}).update(commercial_inputs)
        _store_calc(con, offer_id, "cost_summary", inputs, result, "complete" if complete else "incomplete")
        summaries.append({"offer_id": offer_id, **result})
    return {"costs": summaries}


def _comparable_cost_rows(con, eligible_offers: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offer_id in eligible_offers:
        row = con.execute(
            "SELECT result_json,status FROM calculations WHERE offer_id=? AND calculation_type='cost_summary' ORDER BY updated_at DESC,calculation_id DESC LIMIT 1",
            [offer_id],
        ).fetchone()
        if not row:
            continue
        obj = _json(row[0], {}) or {}
        metric = obj.get("base_amount") if obj.get("base_currency") else obj.get("comparable_total")
        if metric is None or not obj.get("complete"):
            continue
        rows.append({
            "offer_id": offer_id,
            "metric": Decimal(str(metric)),
            "currency": obj.get("base_currency") or obj.get("currency"),
            "base_date": obj.get("base_date"),
        })
    return rows


def calculate_scoring(con, eligible_offers: list[str], scoring_params: dict[str, Any] | None = None) -> dict[str, Any]:
    if len(eligible_offers) < 2:
        result = {"status": "not_applicable", "reason": "fewer than two eligible independent offers"}
        _store_calc(con, None, "scoring", {"eligible_offers": eligible_offers}, result, "not_applicable")
        return result

    costs = _comparable_cost_rows(con, eligible_offers)
    if len(costs) < 2:
        result = {"status": "incomplete", "reason": "fewer than two comparable complete costs"}
        _store_calc(con, None, "scoring", {"eligible_offers": eligible_offers}, result, "incomplete")
        return result
    currencies = {x["currency"] for x in costs}
    dated = {x["base_date"] for x in costs if x.get("base_date")}
    if len(currencies) != 1 or len(dated) > 1:
        result = {"status": "incomplete", "reason": "cost basis mismatch", "currencies": sorted(str(x) for x in currencies), "base_dates": sorted(str(x) for x in dated)}
        _store_calc(con, None, "scoring", {"eligible_offers": eligible_offers}, result, "incomplete")
        return result

    minimum = min(x["metric"] for x in costs)
    price_scores = []
    for row in costs:
        score = cost_score_0_10(row["metric"], minimum)
        price_scores.append({"offer_id": row["offer_id"], "cost_metric": str(row["metric"]), "price_score_0_10": str(score.quantize(Decimal("0.01")))})
    cost_ranking = [x["offer_id"] for x in sorted(costs, key=lambda r: r["metric"])]
    result: dict[str, Any] = {
        "status": "cost_only",
        "method": "10_x_min_cost_over_offer_cost",
        "price_scores": price_scores,
        "cost_ranking": cost_ranking,
        "note": "Cost score is not a total decision score.",
    }

    params = scoring_params or {}
    criteria = params.get("criteria") if isinstance(params, dict) else None
    if isinstance(criteria, list) and criteria:
        usable = []
        for criterion in criteria:
            if criterion.get("monetized_in_cost"):
                continue
            weight = dec(criterion.get("weight"))
            scores = criterion.get("scores")
            if weight is None or not isinstance(scores, dict):
                continue
            usable.append({"id": criterion.get("id"), "weight": weight, "scores": scores})
        totals = []
        if usable:
            for offer_id in eligible_offers:
                rows_for_offer = []
                missing = False
                for criterion in usable:
                    raw_score = criterion["scores"].get(offer_id)
                    if raw_score is None:
                        missing = True
                        break
                    rows_for_offer.append({"weight": criterion["weight"], "score": raw_score})
                if missing:
                    continue
                try:
                    total = weighted_score(rows_for_offer)
                except ValueError:
                    continue
                totals.append({"offer_id": offer_id, "total_score_0_10": str(total.quantize(Decimal("0.001")))})
            if len(totals) >= 2:
                ratio_input = [{"weight": c["weight"], "scores": [c["scores"].get(o) for o in eligible_offers]} for c in usable]
                distinguish = distinguishing_weight_ratio(ratio_input)
                ranked = sorted(totals, key=lambda x: Decimal(x["total_score_0_10"]), reverse=True)
                gap = relative_top_gap(ranked[0]["total_score_0_10"], ranked[1]["total_score_0_10"])
                result.update({
                    "status": "weighted_complete",
                    "weighted_scores": totals,
                    "weighted_ranking": [x["offer_id"] for x in ranked],
                    "distinguishing_weight_ratio": str(distinguish.quantize(Decimal("0.0001"))),
                    "top_relative_gap": str(gap.quantize(Decimal("0.0001"))) if gap is not None else None,
                    "close_scores": bool(gap is not None and gap < Decimal("0.05")),
                    "weighted_score_is_sole_decision_basis": False,
                })

    _store_calc(con, None, "scoring", {"eligible_offers": eligible_offers, "scoring_params": scoring_params or {}}, result, "complete" if result["status"] in {"cost_only", "weighted_complete"} else result["status"])
    return result


@guard_run_operation
def run_engine(run_root: Path) -> dict[str, Any]:
    financial_params = get_meta(run_root, "financial_parameters", {}, parse_json=True) or {}
    scoring_params = get_meta(run_root, "scoring_parameters", {}, parse_json=True) or {}
    con = connect(run_root)
    try:
        gates = apply_hard_gates(con)
        costs = calculate_costs(con, financial_params)
        scoring = calculate_scoring(con, gates["eligible_offers"], scoring_params)
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    detail = {"hard_gates": gates, **costs, "scoring": scoring}
    set_state(run_root, "NORMALIZE", "PASS", {"engine": detail})
    return detail


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic procurement calculation and hard-gate engine")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(run_engine(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
