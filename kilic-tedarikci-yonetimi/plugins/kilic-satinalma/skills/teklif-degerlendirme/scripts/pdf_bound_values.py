"""Critical PDF amounts bound to supplier, offer and field, from one snapshot."""
import json
import re
from decimal import Decimal, ROUND_HALF_UP


def header(name, offer_id):
    return f"Firma: {name} | Teklif: {offer_id};"


def fields(snapshot, offer_id):
    result = []
    for fact in snapshot.get("facts", []):
        if fact.get("offer_id") == offer_id and fact.get("field_key") == "total" and fact.get("evidence_status") == "verified" and fact.get("value_number") is not None:
            result.append(("Beyan toplamı", Decimal(str(fact["value_number"])), fact.get("currency")))
    for calc in snapshot.get("calculations", []):
        if calc.get("offer_id") != offer_id or calc.get("calculation_type") != "cost_summary" or calc.get("status") != "complete":
            continue
        value = calc.get("result") or json.loads(calc.get("result_json") or "{}")
        for key, title in (("base_amount", "Baz bedel"), ("comparable_total", "Karşılaştırılabilir bedel")):
            if value.get(key) is not None:
                result.append((title, Decimal(str(value[key])), value.get("base_currency") or value.get("currency")))
    for row in snapshot.get('buyer_quantity_totals',[]):
        if row.get('offer_id')==offer_id and row.get('assurance')=='BUYER_QUANTITY_REFERENCE_ONLY':
            result.append(('Miktar esaslı ara tutar',Decimal(row['quantity_adjusted_total']),row['currency']))
    return result


def display_amount(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def check_bound_values(text, snapshot):
    """Numbers elsewhere, even within the same offer, cannot satisfy another field."""
    compact = lambda value: re.sub(r"\s+", "", str(value).casefold())
    content = compact(text)
    names = {s["supplier_id"]: s["display_name"] for s in snapshot.get("suppliers", [])}
    offers = [o for o in snapshot.get("offers", []) if o.get("status") == "active"]
    markers = {o["offer_id"]: compact(header(names.get(o["supplier_id"], o["supplier_id"]), o["offer_id"])) for o in offers}
    errors = []
    for offer in offers:
        oid = offer["offer_id"]
        marker = markers[oid]
        if content.count(marker) != 1:
            errors.append("PDF critical numeric value has no unique supplier/offer header: " + oid)
            continue
        start = content.index(marker) + len(marker)
        ends = [content.find(other, start) for other in markers.values()]
        end = min([index for index in ends if index >= 0], default=len(content))
        block = content[start:end]
        for title, expected, currency in fields(snapshot, oid):
            field = compact(title) + ":"
            if block.count(field) != 1:
                errors.append(f"PDF critical numeric value has no unique field: {oid}:{title}")
                continue
            tail = block.split(field, 1)[1]
            match = re.match(r"[-+]?\d+(?:\.\d+)?", tail)
            if not match or abs(Decimal(match.group()) - expected) > Decimal("0.01"):
                errors.append(f"PDF critical numeric value mismatch: {oid}:{title}={expected}")
            elif currency and not tail[len(match.group()):].startswith(compact(currency) + ";"):
                errors.append(f"PDF critical currency mismatch: {oid}:{title}")
    return errors
