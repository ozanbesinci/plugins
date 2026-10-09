"""Validate source-bound quantity changes without changing supplier facts."""
from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation

from db import rows_as_dict


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("quantity source must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("quantity source must be numeric") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("quantity source must be finite and non-negative")
    return result


def _canonical_items(con, offer_id, *, include_pending_quantity=False):
    items = {}
    seen = {}
    for fact in rows_as_dict(con, "SELECT field_key,evidence_status,normalized_json FROM facts WHERE offer_id=?", [offer_id]):
        try:
            normalized = json.loads(fact.get("normalized_json") or "{}")
        except (TypeError, ValueError):
            continue
        for item in normalized.get("items", []) if isinstance(normalized, dict) else []:
            if isinstance(item, dict) and item.get("item_id"):
                key = str(item["item_id"])
                if key in seen and seen[key] != item:
                    raise ValueError("ambiguous canonical item identity")
                seen[key] = item
                if item.get("evidence_status") == "verified" or (
                        include_pending_quantity and fact["field_key"] == "quantity"
                        and fact["evidence_status"] in {"verified", "requires_confirmation"}
                        and item.get("evidence_status") == "requires_confirmation"):
                    items[key] = item
    return items


def _source_loci(con, item, *, expected_cell=None):
    refs = item.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("verified item has no source evidence")
    loci = set()
    for ref in refs:
        evidence = rows_as_dict(con, "SELECT document_id,unit_id,locator_json,quote,evidence_status,extraction_path,source_sha256 FROM evidence WHERE evidence_id=?", [ref])
        if len(evidence) != 1:
            continue
        ev = evidence[0]
        if ev["evidence_status"] != "verified" or ev["extraction_path"] == "vision" or not ev["unit_id"]:
            continue
        document = con.execute("SELECT sha256 FROM documents WHERE document_id=?", [ev["document_id"]]).fetchone()
        if not document or ev["source_sha256"] != document[0]:
            continue
        try:
            locator = json.loads(ev["locator_json"] or "{}")
        except (TypeError, ValueError):
            continue
        tokens = re.findall(r"\b[A-Z]{1,3}[1-9][0-9]*\b", str(locator.get("cell") or locator.get("range") or "").upper())
        if expected_cell:
            within_range = False
            target = re.fullmatch(r"([A-Z]+)([0-9]+)", expected_cell)
            span = re.fullmatch(r"([A-Z]+)([0-9]+):([A-Z]+)([0-9]+)", str(locator.get("range") or "").upper())
            if target and span:
                def column(text):
                    value = 0
                    for letter in text:
                        value = value * 26 + ord(letter) - 64
                    return value
                within_range = (column(span[1]) <= column(target[1]) <= column(span[3])
                                and int(span[2]) <= int(target[2]) <= int(span[4]))
            if expected_cell not in tokens and not within_range:
                # A cell's direct quote is sufficient when the locator names a sheet only.
                quote = str(ev.get("quote") or "")
                if not re.search(rf"\b{re.escape(expected_cell)}\s*=", quote.upper()):
                    continue
            loci.add((ev["document_id"], ev["unit_id"], re.search(r"[0-9]+$", expected_cell).group()))
        else:
            for token in tokens:
                loci.add((ev["document_id"], ev["unit_id"], re.search(r"[0-9]+$", token).group()))
    if not loci:
        raise ValueError("verified item has no matching source row evidence")
    return loci


def _cell(cells, address, *, allow_cached=False):
    matches = [c for c in cells if isinstance(c, dict) and c.get("cell") == address]
    if len(matches) != 1:
        raise ValueError("source cell is missing or ambiguous")
    cell = matches[0]
    if cell.get("is_formula"):
        if not allow_cached or not cell.get("calculated_available"):
            raise ValueError("source cell formula is not accepted")
        return cell.get("calculated_value")
    return cell.get("calculated_value") if cell.get("calculated_value") is not None else cell.get("formula_or_value")


def _source_price(con, offer_id, declaration, item, original_quantity, canonical_unit):
    source = declaration.get("source_row")
    if not isinstance(source, dict):
        raise ValueError("source_row is required")
    needed = {"unit_id", "quantity_cell", "unit_price_cell", "line_total_cell", "unit_cell"}
    if set(source) != needed:
        raise ValueError("source_row fields are incomplete")
    addresses = [source[k] for k in ("quantity_cell", "unit_price_cell", "line_total_cell", "unit_cell")]
    if any(not isinstance(x, str) or not re.fullmatch(r"[A-Z]+[1-9][0-9]*", x) for x in addresses):
        raise ValueError("invalid source cell address")
    if len({re.search(r"[0-9]+$", x).group() for x in addresses}) != 1:
        raise ValueError("source cells must share a row")
    if len(set(addresses)) != len(addresses):
        raise ValueError("source quantity, price, total and unit cells must be distinct")
    rows = rows_as_dict(con, """SELECT u.structured_json,d.document_id,d.sha256,d.offer_id,d.active
        FROM document_units u JOIN documents d ON d.document_id=u.document_id WHERE u.unit_id=?""", [source["unit_id"]])
    if len(rows) != 1 or rows[0]["offer_id"] != offer_id or not rows[0]["active"]:
        raise ValueError("source row does not belong to the active offer")
    document = rows[0]
    hashes = declaration.get("source_hashes")
    if not isinstance(hashes, dict) or hashes.get(document["document_id"]) != document["sha256"]:
        raise ValueError("source document hash does not match buyer declaration")
    quantity_locus = (document["document_id"], source["unit_id"], re.search(r"[0-9]+$", source["quantity_cell"]).group())
    if quantity_locus not in _source_loci(con, item, expected_cell=source["quantity_cell"]):
        raise ValueError("source row is not bound to the selected quantity item")
    if item.get("evidence_status") == "requires_confirmation":
        # A scope discrepancy does not invalidate readable supplier row values.
        # Reconcile every cited cell before applying the separately authorized
        # buyer quantity. The original item/fact status is never rewritten.
        for address in addresses:
            if quantity_locus not in _source_loci(con, item, expected_cell=address):
                raise ValueError("pending quantity requires verified evidence for the complete source row")
    try:
        cells = json.loads(document["structured_json"] or "{}").get("cells", [])
    except (TypeError, ValueError) as exc:
        raise ValueError("source row structure is invalid") from exc
    quantity = number(_cell(cells, source["quantity_cell"]))
    price = number(_cell(cells, source["unit_price_cell"]))
    total = number(_cell(cells, source["line_total_cell"], allow_cached=True))
    unit = str(_cell(cells, source["unit_cell"]))
    if quantity != original_quantity or total != quantity * price or unit.strip().casefold() != canonical_unit.strip().casefold():
        raise ValueError("source row does not reconcile with canonical item")
    return price, {"document_id": document["document_id"], "document_sha256": document["sha256"], **source}


def validated_rows(con, offer_id, declarations, currency):
    """Return verified source quantities/prices; monetary delta is caller-owned."""
    if not declarations:
        return []
    items = _canonical_items(con, offer_id, include_pending_quantity=True)
    rows = []
    seen = set()
    for declaration in declarations:
        item_id = str(declaration.get("quantity_item_id") or "")
        if not item_id or item_id in seen or item_id not in items:
            raise ValueError("quantity item identity is missing, duplicate or unverified")
        seen.add(item_id)
        item = items[item_id]
        old = number(item.get("quantity"))
        new = number(declaration.get("quantity"))
        unit = str(declaration.get("unit") or "").strip()
        canonical_unit = str(item.get("unit") or "").strip()
        if not unit or unit.casefold() != canonical_unit.casefold():
            raise ValueError("buyer quantity unit does not match canonical item")
        price_id = declaration.get("unit_price_item_id")
        pending = item.get("evidence_status") == "requires_confirmation"
        if pending and (price_id or not isinstance(declaration.get("source_row"), dict)):
            raise ValueError("pending quantity requires a fully evidenced source_row")
        if price_id:
            price_item = items.get(str(price_id))
            if not price_item or price_item.get("evidence_status") != "verified" or price_item.get("amount_basis") != "unit_price":
                raise ValueError("verified unit-price item is missing")
            if str(price_item.get("currency") or "").upper() != currency or str(price_item.get("unit") or "").casefold() != unit.casefold():
                raise ValueError("unit-price item currency or unit mismatch")
            if not (_source_loci(con, item) & _source_loci(con, price_item)):
                raise ValueError("unit-price item is not sourced from the quantity item row")
            price = number(price_item.get("amount"))
            source = {"unit_price_item_id": str(price_id)}
        else:
            price, source = _source_price(con, offer_id, declaration, item, old, canonical_unit)
        if pending:
            source = {**source, "verification_basis": "verified_source_cells_and_buyer_quantity",
                      "source_item_evidence_status": "requires_confirmation"}
        rows.append({"quantity_item_id": item_id, "original_quantity": str(old), "reference_quantity": str(new),
                     "unit": unit, "unit_price": str(price), "source": source,
                     "issue_id": declaration.get("issue_id"), "scope_sha256": declaration.get("scope_sha256")})
    return rows
