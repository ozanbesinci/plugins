"""Readable calculation detail rows for the workbook/PDF.

Presentation only: canonical calculation JSON stays unchanged in the reviewed
snapshot. Every leaf value becomes its own labelled row; amounts and scores are
native numeric cells so print rendering never splits their digits, and price
scores are listed next to the offer and cost they belong to.
"""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from display_values import label

HEADERS = ["Firma", "Teklif", "Hesap", "Kalem", "Değer", "Birim"]
# Fixed widths keep the whole table in one print band (sum <= print_layout.MAX_WIDTH)
# and keep supplier, offer ID and calculation name on one line.
COLUMN_WIDTHS = {"A": 20, "B": 30, "C": 19, "D": 36, "E": 22, "F": 17}
LIST_LABELS = {"payment_present_value_detail": "Ödeme", "steps": "Adım"}
MONEY_KEYS = {
    "stated_total", "known_scope_adjustment", "acquisition_cost_basis", "acquisition_present_value",
    "tco_present_value", "comparable_total", "base_amount", "amount", "present_value", "delta",
    "cost_metric", "residual", "bridge_total",
}
SCORE_KEYS = {"price_score_0_10", "total_score_0_10"}
DAY_KEYS = {"days"}
MONEY_FORMAT = "#,##0.00;[Red]-#,##0.00;0.00"
SCORE_FORMAT = "0.00"
DAY_FORMAT = "0"
# Keys whose values are identifiers/labels, never numbers.
TEXT_KEYS = {"offer_id", "currency", "base_currency", "stage", "method", "status", "note", "source", "date", "base_date", "unit_label"}


def _json(value: Any, default: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            number = Decimal(value.strip())
        except (InvalidOperation, ValueError):
            return None
        return number if number.is_finite() else None
    return None


def _text(value: Any) -> str:
    if value is None:
        return "Belirtilmedi"
    if isinstance(value, bool):
        return "Evet" if value else "Hayır"
    if isinstance(value, (list, dict)) and not value:
        return "Yok"
    return str(label(value))


def _value(key: str, value: Any, currency: str | None) -> tuple[Any, str, str | None]:
    """Return (cell value, unit, number_format)."""
    number = None if key in TEXT_KEYS else _number(value)
    if number is None:
        return _text(value), "", None
    if key in MONEY_KEYS:
        return float(number), currency or "", MONEY_FORMAT
    if key in SCORE_KEYS:
        return float(number), "Puan (0–10)", SCORE_FORMAT
    if key in DAY_KEYS:
        return float(number), "Gün", DAY_FORMAT
    return float(number), "", "General"


def _leaf_rows(prefix: str, key: str, value: Any, currency: str | None) -> list[tuple[str, Any, str, str | None]]:
    name = f"{prefix} · {label(key)}" if prefix else str(label(key))
    if isinstance(value, dict) and value:
        local_currency = value.get("currency") or currency
        rows: list[tuple[str, Any, str, str | None]] = []
        for sub_key, sub_value in value.items():
            if sub_key == "currency" and prefix:
                continue
            rows.extend(_leaf_rows(name, sub_key, sub_value, local_currency))
        return rows
    if isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
        rows = []
        for idx, item in enumerate(value, 1):
            item_currency = item.get("currency") or currency
            stage = item.get("stage")
            head = f"{LIST_LABELS.get(key, label(key))} {idx}" + (f" – {label(stage)}" if stage else "")
            head = f"{prefix} · {head}" if prefix else head
            for sub_key, sub_value in item.items():
                if sub_key in {"stage", "currency"}:
                    continue
                rows.extend(_leaf_rows(head, sub_key, sub_value, item_currency))
        return rows
    if isinstance(value, list) and value:
        return [(name, "; ".join(_text(x) for x in value), "", None)]
    cell, unit, fmt = _value(key, value, currency)
    return [(name, cell, unit, fmt)]


def calculation_rows(calcs: list[dict[str, Any]], offer_names: dict[str, str], offer_currency: dict[str, str]) -> list[dict[str, Any]]:
    """Flatten calculations into labelled rows without dropping any leaf value."""
    rows: list[dict[str, Any]] = []

    def add(calc: dict[str, Any], offer_id: str | None, item: str, value: Any, unit: str, fmt: str | None) -> None:
        rows.append({
            "calculation_id": calc.get("calculation_id"),
            "offer_id": offer_id,
            "values": [offer_names.get(offer_id, offer_id) if offer_id else "Tüm teklifler",
                       offer_id or "Tüm teklifler", calc.get("calculation_type"), item, value, unit],
            "number_format": fmt,
        })

    for calc in calcs:
        obj = _json(calc.get("result_json"), None)
        offer_id = calc.get("offer_id")
        add(calc, offer_id, "Hesap durumu", _text(calc.get("status")), "", None)
        if not isinstance(obj, dict):
            add(calc, offer_id, "Hesap sonucu", _text(calc.get("result_json")), "", None)
            continue
        per_offer: dict[str, list[tuple[str, Any, str, str | None]]] = {}
        order: list[str] = []
        ranking = [x for x in obj.get("cost_ranking", []) if isinstance(x, str)] if isinstance(obj.get("cost_ranking"), list) else []
        currency = obj.get("currency") or obj.get("base_currency") or offer_currency.get(offer_id or "")
        for key, value in obj.items():
            # Per-offer score tables: keep each offer's cost, score and rank together.
            if isinstance(value, list) and value and all(isinstance(x, dict) and x.get("offer_id") for x in value):
                for item in value:
                    oid = item["offer_id"]
                    if oid not in per_offer:
                        per_offer[oid] = []
                        order.append(oid)
                    item_currency = item.get("currency") or offer_currency.get(oid)
                    for sub_key, sub_value in item.items():
                        if sub_key in {"offer_id", "currency"}:
                            continue
                        per_offer[oid].extend(_leaf_rows("", sub_key, sub_value, item_currency))
                continue
            if key == "cost_ranking" and ranking:
                continue
            for item, cell, unit, fmt in _leaf_rows("", key, value, currency):
                add(calc, offer_id, item, cell, unit, fmt)
        for oid in ranking:
            if oid not in per_offer:
                per_offer[oid] = []
                order.append(oid)
        rank_index = {oid: idx for idx, oid in enumerate(ranking, 1)}
        first_seen = {oid: idx for idx, oid in enumerate(order)}
        order.sort(key=lambda oid: (rank_index.get(oid, len(rank_index) + 1), first_seen[oid]))
        for oid in order:
            for item, cell, unit, fmt in per_offer[oid]:
                add(calc, oid, item, cell, unit, fmt)
            if oid in rank_index:
                add(calc, oid, "Maliyet sırası", float(rank_index[oid]), f"/ {len(ranking)}", "0")
    return rows
