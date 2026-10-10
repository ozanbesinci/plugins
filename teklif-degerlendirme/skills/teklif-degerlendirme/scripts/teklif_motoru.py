"""Teklif değerlendirme için saf, belirlenimci hesap motoru.

Harici paket, ağ erişimi veya iş kuralı varsayımı kullanmaz. JSON sayıları ``Decimal``
olarak okunur; sonuçtaki her parasal/rakam değeri doğruluğu korumak için JSON stringidir.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Iterable, Mapping


ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


class CalculationError(ValueError):
    """Kullanıcının tamamlaması veya düzeltmesi gereken hesap girdisi."""


def as_decimal(value: Any, field: str) -> Decimal:
    """Sonlu bir Decimal döndürür; float ve bool bilinçli olarak kabul edilmez."""
    if isinstance(value, bool) or isinstance(value, float):
        raise CalculationError(f"{field}: Decimal uyumlu JSON sayı veya metin olmalı")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise CalculationError(f"{field}: geçerli sayı değil") from error
    if not result.is_finite():
        raise CalculationError(f"{field}: sonlu bir sayı olmalı")
    return result


def as_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise CalculationError(f"{field}: YYYY-AA-GG metni olmalı")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CalculationError(f"{field}: geçerli ISO tarih değil") from error


def positive(value: Any, field: str) -> Decimal:
    result = as_decimal(value, field)
    if result <= ZERO:
        raise CalculationError(f"{field}: sıfırdan büyük olmalı")
    return result


def rate(value: Any, field: str, *, allow_negative: bool = False) -> Decimal:
    result = as_decimal(value, field)
    if result <= -ONE:
        raise CalculationError(f"{field}: -1'den büyük olmalı")
    if not allow_negative and result < ZERO:
        raise CalculationError(f"{field}: negatif olamaz")
    return result


def require_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalculationError(f"{field}: boş olmayan metin olmalı")
    return value.strip()


def price_line(payload: Mapping[str, Any]) -> dict[str, Decimal]:
    """Miktar/birim/ardışık iskonto/KDV ayrımını hesaplar.

    ``vat_rate`` zorunludur; KDV dahil fiyat için önce iskontolu brüt tutar ayrıştırılır.
    """
    quantity = positive(payload.get("quantity"), "quantity")
    unit_price = as_decimal(payload.get("unit_price"), "unit_price")
    if unit_price < ZERO:
        raise CalculationError("unit_price: negatif olamaz")
    price_unit = positive(payload.get("price_unit", ONE), "price_unit")
    vat_rate = rate(payload.get("vat_rate"), "vat_rate")
    discounts = payload.get("discounts", [])
    if not isinstance(discounts, list):
        raise CalculationError("discounts: liste olmalı")
    factor = ONE
    for index, discount in enumerate(discounts):
        current = rate(discount, f"discounts[{index}]")
        if current >= ONE:
            raise CalculationError(f"discounts[{index}]: 1'den küçük olmalı")
        factor *= ONE - current
    gross_before_discount = quantity * unit_price / price_unit
    discounted_amount = gross_before_discount * factor
    discount_amount = gross_before_discount - discounted_amount
    includes_vat = payload.get("price_includes_vat", False)
    if not isinstance(includes_vat, bool):
        raise CalculationError("price_includes_vat: true/false olmalı")
    if includes_vat:
        total_including_vat = discounted_amount
        net_excluding_vat = total_including_vat / (ONE + vat_rate)
        vat_amount = total_including_vat - net_excluding_vat
    else:
        net_excluding_vat = discounted_amount
        vat_amount = net_excluding_vat * vat_rate
        total_including_vat = net_excluding_vat + vat_amount
    return {
        "gross_before_discount": gross_before_discount,
        "discount_amount": discount_amount,
        "net_excluding_vat": net_excluding_vat,
        "vat_amount": vat_amount,
        "total_including_vat": total_including_vat,
    }


def fx_convert(payload: Mapping[str, Any]) -> dict[str, Decimal]:
    """TCMB tarzı dönüşüm: tutar × ForexSelling / Unit."""
    amount = as_decimal(payload.get("amount"), "amount")
    forex_selling = positive(payload.get("forex_selling"), "forex_selling")
    unit = positive(payload.get("unit"), "unit")
    return {"converted_amount": amount * forex_selling / unit}


def _validate_events(events: Any, *, require_owner: bool = False) -> list[Mapping[str, Any]]:
    if not isinstance(events, list) or not events:
        raise CalculationError("events: boş olmayan liste olmalı")
    seen: set[str] = set()
    validated: list[Mapping[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, Mapping):
            raise CalculationError(f"events[{index}]: nesne olmalı")
        event_id = require_id(event.get("event_id"), f"events[{index}].event_id")
        if event_id in seen:
            raise CalculationError(f"event_id yinelenmiş: {event_id}")
        seen.add(event_id)
        if not (require_owner and event.get("known") is False):
            require_id(event.get("currency"), f"events[{index}].currency")
            as_date(event.get("payment_date"), f"events[{index}].payment_date")
        if require_owner:
            require_id(event.get("owner"), f"events[{index}].owner")
        validated.append(event)
    return validated


def dated_npv(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Akışları kendi para birimindeki yıllık efektif oranla, ACT/365'e göre indirger."""
    base_date = as_date(payload.get("base_date"), "base_date")
    annual_rates = payload.get("annual_rates")
    if not isinstance(annual_rates, Mapping) or not annual_rates:
        raise CalculationError("annual_rates: para birimi → yıllık oran nesnesi olmalı")
    parsed_rates = {require_id(k, "annual_rates para birimi"): rate(v, f"annual_rates.{k}", allow_negative=True)
                    for k, v in annual_rates.items()}
    events = _validate_events(payload.get("events"))
    by_currency: dict[str, Decimal] = {}
    rows: list[dict[str, Any]] = []
    with localcontext() as context:
        context.prec = 34
        for event in events:
            event_id = require_id(event["event_id"], "event_id")
            currency = require_id(event["currency"], "currency")
            if currency not in parsed_rates:
                raise CalculationError(f"annual_rates.{currency}: oran zorunlu; bilinmeyen oranla NBD hesaplanmaz")
            payment_date = as_date(event["payment_date"], "payment_date")
            if payment_date < base_date:
                raise CalculationError(f"{event_id}: ödeme tarihi değerleme tarihinden önce olamaz")
            amount = as_decimal(event.get("amount"), f"{event_id}.amount")
            years = Decimal((payment_date - base_date).days) / Decimal("365")
            present_value = amount / ((ONE + parsed_rates[currency]) ** years)
            by_currency[currency] = by_currency.get(currency, ZERO) + present_value
            rows.append({"event_id": event_id, "currency": currency, "years": years,
                         "nominal_amount": amount, "present_value": present_value})
    return {"convention": "annual_effective_act_365", "base_date": base_date.isoformat(),
            "events": rows, "present_value_by_currency": by_currency}


def cost_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Maliyet olaylarını bir kez sayar; eksikleri nihai toplam gibi sunmaz."""
    raw_events = _validate_events(payload.get("events"), require_owner=True)
    known_events: list[Mapping[str, Any]] = []
    unknown_ids: list[str] = []
    for event in raw_events:
        known = event.get("known")
        if not isinstance(known, bool):
            raise CalculationError(f"{event['event_id']}.known: true/false zorunlu")
        if known:
            if "amount" not in event:
                raise CalculationError(f"{event['event_id']}.amount: bilinen maliyet için zorunlu")
            known_events.append(event)
        else:
            unknown_ids.append(require_id(event["event_id"], "event_id"))
    if not known_events:
        as_date(payload.get("base_date"), "base_date")
        return {"status": "no_known_cost_inputs", "unknown_event_ids": unknown_ids,
                "known_nominal_by_currency": {}, "known_present_value_by_currency": {},
                "known_present_value_in_base_currency": None, "base_currency": payload.get("base_currency"), "events": []}
    npv = dated_npv({"base_date": payload.get("base_date"), "annual_rates": payload.get("annual_rates"),
                     "events": known_events})
    nominal_by_currency: dict[str, Decimal] = {}
    for event in known_events:
        currency = require_id(event["currency"], "currency")
        nominal_by_currency[currency] = nominal_by_currency.get(currency, ZERO) + as_decimal(event["amount"], "amount")
    result: dict[str, Any] = {
        # Bu yalnız sayı girdilerinin eksiksizliğiyle ilgilidir; kaynak/uygunluk onayı değildir.
        "status": "complete_cost_inputs" if not unknown_ids else "known_subtotal_not_final",
        "unknown_event_ids": unknown_ids,
        "known_nominal_by_currency": nominal_by_currency,
        "known_present_value_by_currency": npv["present_value_by_currency"],
        "events": npv["events"],
    }
    base_currency = payload.get("base_currency")
    fx_rates = payload.get("fx_rates")
    if (base_currency is None) != (fx_rates is None):
        raise CalculationError("base_currency ve fx_rates birlikte verilmeli veya ikisi de verilmemeli")
    if base_currency is not None:
        require_id(base_currency, "base_currency")
        if not isinstance(fx_rates, Mapping):
            raise CalculationError("fx_rates: para birimi → (forex_selling, unit) nesnesi olmalı")
        converted = ZERO
        for currency, value in npv["present_value_by_currency"].items():
            quote = fx_rates.get(currency)
            if not isinstance(quote, Mapping):
                raise CalculationError(f"fx_rates.{currency}: dönüşüm oranı zorunlu")
            converted += fx_convert({"amount": value, "forex_selling": quote.get("forex_selling"),
                                     "unit": quote.get("unit")})["converted_amount"]
        result["base_currency"] = base_currency
        result["known_present_value_in_base_currency"] = converted
    return result


def cash_peak(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Nominal, sıralı nakit hareketlerinden tepe birikimli ihtiyacı bulur."""
    events = _validate_events(payload.get("events"))
    currency = payload.get("currency")
    if currency is not None:
        require_id(currency, "currency")
    event_currencies = {require_id(event["currency"], "currency") for event in events}
    if len(event_currencies) != 1:
        raise CalculationError("cash_peak tek para biriminde çalışır; dövizler önce açık kurla çevrilmeli")
    inferred_currency = next(iter(event_currencies))
    if currency is None:
        currency = inferred_currency
    elif currency != inferred_currency:
        raise CalculationError("cash_peak tek para biriminde çalışır; dövizler önce açık kurla çevrilmeli")
    # Python sıralaması kararlıdır: aynı gün için kullanıcıdaki hareket sırası korunur.
    chronological_events = sorted(events, key=lambda event: as_date(event["payment_date"], "payment_date"))
    rows: list[dict[str, Any]] = []
    cumulative = ZERO
    peak = ZERO
    peak_date: str | None = None
    max_payment = ZERO
    for event in chronological_events:
        amount = as_decimal(event.get("amount"), f"{event['event_id']}.amount")
        event_currency = require_id(event["currency"], "currency")
        if event_currency != currency:
            raise CalculationError("cash_peak tek para biriminde çalışır; dövizler önce açık kurla çevrilmeli")
        cumulative += amount
        if amount > max_payment:
            max_payment = amount
        if cumulative > peak:
            peak = cumulative
            peak_date = str(event["payment_date"])
        rows.append({"event_id": event["event_id"], "payment_date": event["payment_date"],
                     "amount": amount, "cumulative_net_outflow": cumulative})
    available = payload.get("available_cash")
    result: dict[str, Any] = {"currency": currency, "convention": "chronological_stable_same_day_input_order",
                               "events": rows, "peak_cumulative_cash_need": peak,
                               "peak_date": peak_date, "largest_single_payment": max_payment,
                               "final_net_outflow": cumulative}
    if available is not None:
        available_decimal = as_decimal(available, "available_cash")
        if available_decimal < ZERO:
            raise CalculationError("available_cash: negatif olamaz")
        result["available_cash"] = available_decimal
        result["peak_additional_financing_need"] = max(ZERO, peak - available_decimal)
    return result


def score_suppliers(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Elemeli kapı sonrası tedarikçileri 0–10 ölçeğinde, açık yönlerle puanlar."""
    suppliers = payload.get("suppliers")
    criteria = payload.get("criteria")
    if not isinstance(suppliers, list) or not suppliers:
        raise CalculationError("suppliers: boş olmayan liste olmalı")
    if not isinstance(criteria, list) or not criteria:
        raise CalculationError("criteria: boş olmayan liste olmalı")
    supplier_ids: list[str] = []
    eligible_ids: list[str] = []
    excluded: list[str] = []
    for index, supplier in enumerate(suppliers):
        if not isinstance(supplier, Mapping):
            raise CalculationError(f"suppliers[{index}]: nesne olmalı")
        supplier_id = require_id(supplier.get("supplier_id"), f"suppliers[{index}].supplier_id")
        if supplier_id in supplier_ids:
            raise CalculationError(f"supplier_id yinelenmiş: {supplier_id}")
        eligible = supplier.get("eligible")
        if not isinstance(eligible, bool):
            raise CalculationError(f"{supplier_id}.eligible: true/false zorunlu")
        supplier_ids.append(supplier_id)
        (eligible_ids if eligible else excluded).append(supplier_id)
    if len(eligible_ids) < 2:
        raise CalculationError("Puanlama için elemeli kapıdan geçen en az iki tedarikçi gerekir")

    parsed: list[dict[str, Any]] = []
    total_weight = ZERO
    seen_criteria: set[str] = set()
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, Mapping):
            raise CalculationError(f"criteria[{index}]: nesne olmalı")
        criterion_id = require_id(criterion.get("criterion_id"), f"criteria[{index}].criterion_id")
        if criterion_id in seen_criteria:
            raise CalculationError(f"criterion_id yinelenmiş: {criterion_id}")
        seen_criteria.add(criterion_id)
        weight = as_decimal(criterion.get("weight"), f"{criterion_id}.weight")
        if weight < ZERO:
            raise CalculationError(f"{criterion_id}.weight: negatif olamaz")
        direction = criterion.get("direction")
        if direction not in {"higher", "lower", "direct"}:
            raise CalculationError(f"{criterion_id}.direction: higher, lower veya direct olmalı")
        method = criterion.get("method", "proportional")
        if method not in {"proportional", "range"}:
            raise CalculationError(f"{criterion_id}.method: proportional veya range olmalı")
        if method == "range" and len(eligible_ids) < 5:
            raise CalculationError(f"{criterion_id}: range yöntemi en az beş uygun tedarikçide kullanılabilir")
        values = criterion.get("values")
        if not isinstance(values, Mapping):
            raise CalculationError(f"{criterion_id}.values: tedarikçi → değer nesnesi olmalı")
        if set(values) != set(supplier_ids):
            raise CalculationError(f"{criterion_id}.values: elenenler dahil her tedarikçi için açık değer gerekli")
        numbers = {supplier_id: as_decimal(values[supplier_id], f"{criterion_id}.values.{supplier_id}")
                   for supplier_id in supplier_ids}
        if direction == "direct":
            if any(value < ZERO or value > Decimal("10") for value in numbers.values()):
                raise CalculationError(f"{criterion_id}: direct puanlar 0–10 aralığında olmalı")
        elif any(numbers[supplier_id] <= ZERO for supplier_id in eligible_ids):
            raise CalculationError(f"{criterion_id}: proportional/range için uygun tedarikçi değerleri sıfırdan büyük olmalı")
        total_weight += weight
        parsed.append({"criterion_id": criterion_id, "weight": weight, "direction": direction,
                       "method": method, "values": numbers})
    if total_weight != HUNDRED:
        raise CalculationError(f"Ağırlık toplamı tam 100 olmalı (gelen: {total_weight})")

    scores: dict[str, dict[str, Decimal]] = {supplier_id: {} for supplier_id in eligible_ids}
    distinguishing_weight = ZERO
    for criterion in parsed:
        values = criterion["values"]
        eligible_values = [values[supplier_id] for supplier_id in eligible_ids]
        if len(set(eligible_values)) > 1:
            distinguishing_weight += criterion["weight"]
        lowest, highest = min(eligible_values), max(eligible_values)
        for supplier_id in eligible_ids:
            value = values[supplier_id]
            if criterion["direction"] == "direct":
                score = value
            elif criterion["method"] == "proportional":
                score = Decimal("10") * (lowest / value if criterion["direction"] == "lower" else value / highest)
            elif highest == lowest:
                score = Decimal("10")
            elif criterion["direction"] == "lower":
                score = Decimal("10") * (highest - value) / (highest - lowest)
            else:
                score = Decimal("10") * (value - lowest) / (highest - lowest)
            scores[supplier_id][criterion["criterion_id"]] = score
    rows: list[dict[str, Any]] = []
    for supplier_id in eligible_ids:
        total = sum((criterion["weight"] * scores[supplier_id][criterion["criterion_id"]] / HUNDRED
                     for criterion in parsed), ZERO)
        rows.append({"supplier_id": supplier_id, "eligible": True, "criterion_scores": scores[supplier_id],
                     "total_score": total})
    rows.sort(key=lambda row: (-row["total_score"], row["supplier_id"]))
    previous_score = None
    previous_rank = None
    for index, row in enumerate(rows, start=1):
        row["rank"] = previous_rank if row["total_score"] == previous_score else index
        previous_rank = row["rank"]
        previous_score = row["total_score"]
    top_ids = [row["supplier_id"] for row in rows if row["rank"] == 1]
    rows.extend({"supplier_id": supplier_id, "eligible": False, "status": "EXCLUDED", "rank": None}
                for supplier_id in excluded)
    return {"scale": "0_to_10", "suppliers": rows, "distinguishing_weight": distinguishing_weight,
            "top_tied_supplier_ids": top_ids, "has_unique_top_score": len(top_ids) == 1,
            "distinguishing_weight_ratio": distinguishing_weight / HUNDRED,
            "non_distinguishing_weight": HUNDRED - distinguishing_weight}


def json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


OPERATIONS = {
    "price_line": price_line,
    "fx_convert": fx_convert,
    "dated_npv": dated_npv,
    "cost_summary": cost_summary,
    "cash_peak": cash_peak,
    "score_suppliers": score_suppliers,
}


def main() -> int:
    try:
        request = json.load(sys.stdin, parse_float=Decimal, parse_int=Decimal,
                            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Geçersiz JSON sabiti: {value}")))
        if not isinstance(request, Mapping):
            raise CalculationError("İstek JSON nesnesi olmalı")
        operation = request.get("operation")
        if operation not in OPERATIONS:
            raise CalculationError("operation: price_line, fx_convert, dated_npv, cost_summary, cash_peak veya score_suppliers olmalı")
        payload = request.get("payload")
        if not isinstance(payload, Mapping):
            raise CalculationError("payload: JSON nesnesi olmalı")
        result = OPERATIONS[operation](payload)
        print(json.dumps({"ok": True, "result": json_ready(result)}, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (CalculationError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False, separators=(",", ":")))
        return 2


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
