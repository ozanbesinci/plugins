from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Iterable

D = Decimal


def dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def line_gross(quantity: Any, unit_price: Any, price_unit: Any = 1) -> Decimal:
    q = dec(quantity)
    p = dec(unit_price)
    u = dec(price_unit)
    if q is None or p is None or u is None or u <= 0:
        raise ValueError("quantity, unit_price and positive price_unit are required")
    return q * p / u


def sequential_discount(gross: Any, rates: Iterable[Any]) -> Decimal:
    value = dec(gross)
    if value is None:
        raise ValueError("gross is required")
    for raw in rates:
        rate = dec(raw)
        if rate is None or rate < 0 or rate >= 1:
            raise ValueError("discount rates must satisfy 0 <= rate < 1")
        value *= D(1) - rate
    return value


def required_order_quantity(net_need: Any, loss_rate: Any = 0, moq: Any = 0, pack: Any = 1) -> Decimal:
    need = dec(net_need)
    loss = dec(loss_rate)
    minimum = dec(moq)
    pack_size = dec(pack)
    if need is None or loss is None or minimum is None or pack_size is None:
        raise ValueError("all inputs are required")
    if need < 0 or loss < 0 or loss >= 1 or minimum < 0 or pack_size <= 0:
        raise ValueError("invalid quantity inputs")
    raw = max(minimum, need / (D(1) - loss))
    packs = (raw / pack_size).to_integral_value(rounding=ROUND_CEILING)
    return packs * pack_size


def present_value_days(amount: Any, days: int, annual_effective_rate: Any) -> Decimal:
    a = dec(amount)
    r = dec(annual_effective_rate)
    if a is None or r is None:
        raise ValueError("amount and rate are required")
    if not a.is_finite() or not r.is_finite():
        raise ValueError("amount and rate must be finite")
    if type(days) is not int or days < 0:
        raise ValueError("payment days must be a non-negative integer")
    if a < 0:
        raise ValueError("payment amount must be non-negative")
    if r <= -1:
        raise ValueError("rate must be greater than -1")
    t = D(days) / D(365)
    if days == 0:
        return a
    try:
        value = a / ((D(1) + r) ** t)
    except (InvalidOperation, ArithmeticError, ValueError) as exc:
        raise ValueError("present value is outside the supported numeric range") from exc
    if not value.is_finite():
        raise ValueError("present value must be finite")
    return value


def validate_payment_schedule(total: Any, schedule: Any) -> None:
    """Validate payment row shape and totals independently of discount-rate availability."""
    principal = dec(total)
    if principal is None or not principal.is_finite():
        raise ValueError("finite acquisition total is required")
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("payment schedule is required")
    ratio_sum = D(0)
    implied_ratio_sum = D(0)
    amount_sum = D(0)
    has_ratio = False
    amount_tolerance = max(D("0.01"), abs(principal) * D("0.0001"))
    for item in schedule:
        if not isinstance(item, dict):
            raise ValueError("each payment must be an object")
        if set(item) - {"days", "ratio", "amount"}:
            raise ValueError("payment contains an unsupported field")
        days = item.get("days")
        if type(days) is not int or days < 0:
            raise ValueError("payment days must be a non-negative integer")
        ratio_raw = item.get("ratio")
        amount_raw = item.get("amount")
        if ratio_raw is None and amount_raw is None:
            raise ValueError("each payment needs amount or ratio")
        parsed: dict[str, Decimal | None] = {"ratio": None, "amount": None}
        for name, raw in (("ratio", ratio_raw), ("amount", amount_raw)):
            if raw is None:
                continue
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str, Decimal)):
                raise ValueError(f"payment {name} must be numeric")
            value = dec(raw)
            if value is None or not value.is_finite():
                raise ValueError(f"payment {name} must be finite")
            if name == "ratio" and not D(0) <= value <= D(1):
                raise ValueError("payment ratio must be between 0 and 1")
            if name == "amount" and value < 0:
                raise ValueError("payment amount must be non-negative")
            parsed[name] = value
        ratio = parsed["ratio"]
        amount = parsed["amount"]
        if ratio is not None:
            has_ratio = True
            ratio_sum += ratio
        implied = principal * ratio if ratio is not None else None
        if amount is not None and implied is not None and abs(amount - implied) > amount_tolerance:
            raise ValueError("payment amount and ratio do not reconcile to principal")
        amount_sum += amount if amount is not None else (implied or D(0))
        if ratio is None and amount is not None and principal != 0:
            implied_ratio_sum += amount / principal
    if has_ratio and abs(ratio_sum + implied_ratio_sum - D(1)) > D("0.0001"):
        raise ValueError("payment ratios do not sum to 1")
    if abs(amount_sum - principal) > amount_tolerance:
        raise ValueError("payment amounts do not reconcile to principal")


def present_value_schedule(total: Any, schedule: list[dict[str, Any]], annual_effective_rate: Any) -> tuple[Decimal, list[dict[str, str | int | None]]]:
    principal = dec(total)
    rate = dec(annual_effective_rate)
    if principal is None or rate is None:
        raise ValueError("total and rate are required")
    validate_payment_schedule(principal, schedule)
    ratio_sum = D(0)
    pv = D(0)
    detail: list[dict[str, str | int | None]] = []
    has_ratio = False
    amount_sum = D(0)
    amount_tolerance = max(D("0.01"), abs(principal) * D("0.0001"))
    for item in schedule:
        days = item["days"]
        ratio = dec(item.get("ratio"))
        amount = dec(item.get("amount"))
        if days < 0:
            raise ValueError("payment days must be non-negative")
        if ratio is not None and (ratio < 0 or ratio > 1):
            raise ValueError("payment ratio must be between 0 and 1")
        if amount is not None and amount < 0:
            raise ValueError("payment amount must be non-negative")
        if amount is None:
            if ratio is None:
                raise ValueError("each payment needs amount or ratio")
            amount = principal * ratio
        elif ratio is not None:
            expected_amount = principal * ratio
            if abs(amount - expected_amount) > amount_tolerance:
                raise ValueError("payment amount and ratio do not reconcile to principal")
        if ratio is None and principal != 0:
            ratio = amount / principal
        if ratio is not None:
            has_ratio = True
            ratio_sum += ratio
        amount_sum += amount
        row_pv = present_value_days(amount, days, rate)
        pv += row_pv
        detail.append({
            "days": days,
            "amount": str(amount),
            "ratio": str(ratio) if ratio is not None else None,
            "present_value": str(row_pv),
        })
    if has_ratio and abs(ratio_sum - D(1)) > D("0.0001"):
        raise ValueError("payment ratios do not sum to 1")
    if abs(amount_sum - principal) > amount_tolerance:
        raise ValueError("payment amounts do not reconcile to principal")
    return pv, detail


def real_rate(nominal_rate: Any, inflation_rate: Any) -> Decimal:
    nominal = dec(nominal_rate)
    inflation = dec(inflation_rate)
    if nominal is None or inflation is None:
        raise ValueError("nominal and inflation rates are required")
    if inflation <= -1:
        raise ValueError("inflation rate must be greater than -1")
    return (D(1) + nominal) / (D(1) + inflation) - D(1)


def fx_to_base(amount: Any, forex_selling: Any, unit: Any = 1) -> Decimal:
    a = dec(amount)
    rate = dec(forex_selling)
    u = dec(unit)
    if a is None or rate is None or u is None or rate <= 0 or u <= 0:
        raise ValueError("positive amount conversion rate and unit are required")
    return a * rate / u


def vat_split(net_amount: Any, vat_rate: Any, deductible_share: Any) -> dict[str, Decimal]:
    net = dec(net_amount)
    rate = dec(vat_rate)
    deductible = dec(deductible_share)
    if net is None or rate is None or deductible is None:
        raise ValueError("net_amount, vat_rate and deductible_share are required")
    if rate < 0 or deductible < 0 or deductible > 1:
        raise ValueError("invalid VAT inputs")
    vat = net * rate
    return {
        "net": net,
        "vat": vat,
        "deductible_vat": vat * deductible,
        "non_deductible_vat": vat * (D(1) - deductible),
        "cash_gross": net + vat,
        "cost_basis": net + vat * (D(1) - deductible),
    }


def ddp_equivalent(offer_amount: Any, included_costs: list[dict[str, Any]], buyer_costs: list[dict[str, Any]], non_deductible_taxes: list[dict[str, Any]]) -> dict[str, Any]:
    base = dec(offer_amount)
    if base is None:
        raise ValueError("offer_amount is required")
    included_ids = {str(x.get("cost_id")) for x in included_costs if x.get("cost_id")}
    total = base
    detail = []
    seen: set[str] = set()
    for group, rows in (("buyer_cost", buyer_costs), ("tax", non_deductible_taxes)):
        for row in rows:
            cid = str(row.get("cost_id") or "")
            amount = dec(row.get("amount"))
            if not cid or amount is None:
                raise ValueError("every bridge item needs cost_id and amount")
            if cid in included_ids or cid in seen:
                continue
            seen.add(cid)
            total += amount
            detail.append({"cost_id": cid, "kind": group, "amount": str(amount)})
    return {"offer_amount": str(base), "added": detail, "ddp_equivalent": str(total)}


def tco_present_value(annual_costs: list[dict[str, Any]], annual_rate: Any) -> tuple[Decimal, list[dict[str, Any]]]:
    rate = dec(annual_rate)
    if rate is None or rate <= -1:
        raise ValueError("valid annual rate is required")
    total = D(0)
    detail = []
    for item in annual_costs:
        year = int(item.get("year"))
        amount = dec(item.get("amount"))
        if year < 0 or amount is None:
            raise ValueError("each annual cost needs year >= 0 and amount")
        pv = amount if year == 0 else amount / ((D(1) + rate) ** D(year))
        total += pv
        detail.append({"year": year, "amount": str(amount), "present_value": str(pv)})
    return total, detail


def cost_score_0_10(cost: Any, minimum_cost: Any) -> Decimal:
    c = dec(cost)
    m = dec(minimum_cost)
    if c is None or m is None or c <= 0 or m < 0:
        raise ValueError("positive cost and non-negative minimum cost are required")
    return D(10) * m / c


def delivery_score_0_10(days: Any, minimum_days: Any) -> Decimal:
    d = dec(days)
    m = dec(minimum_days)
    if d is None or m is None or d <= 0 or m < 0:
        raise ValueError("delivery days must be positive")
    return D(10) * m / d


def distinguishing_weight_ratio(criteria: list[dict[str, Any]]) -> Decimal:
    total = D(0)
    distinguishing = D(0)
    for criterion in criteria:
        weight = dec(criterion.get("weight"))
        values = criterion.get("scores") or []
        if weight is None or weight < 0:
            raise ValueError("criteria require non-negative weights")
        total += weight
        normalized = [dec(v) for v in values if dec(v) is not None]
        if len(normalized) >= 2 and len(set(normalized)) > 1:
            distinguishing += weight
    if total == 0:
        return D(0)
    return distinguishing / total


def weighted_score(criteria: list[dict[str, Any]]) -> Decimal:
    total_weight = D(0)
    numerator = D(0)
    for criterion in criteria:
        weight = dec(criterion.get("weight"))
        score = dec(criterion.get("score"))
        if weight is None or score is None:
            raise ValueError("criteria require weight and score")
        if weight < 0 or score < 0 or score > 10:
            raise ValueError("invalid score inputs")
        total_weight += weight
        numerator += weight * score
    if abs(total_weight - D(100)) > D("0.0001"):
        raise ValueError("weights must sum to 100")
    return numerator / D(100)


def relative_top_gap(first_score: Any, second_score: Any) -> Decimal | None:
    first = dec(first_score)
    second = dec(second_score)
    if first is None or second is None or first <= 0:
        return None
    return (first - second) / first
