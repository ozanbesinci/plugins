from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from generated_issues import is_generated_issue
from common import json_text, stable_id, utc_now
from db import connect, one_as_dict, rows_as_dict
from xlsx_locator import address as xlsx_address
from llm_result_validate import ResultValidationError, record_validation, validate_result

VALID_EVIDENCE_STATUS = {"verified", "missing", "excluded", "unreadable", "conflicting", "assumption", "requires_confirmation"}
VALID_DOC_ROLES = {"offer", "specification", "boq", "correspondence", "support", "unrelated", "unknown"}
VALID_ADJUDICATIONS = {"main", "independent", "corrected", "open"}


def require(obj: dict[str, Any], key: str):
    if key not in obj:
        raise ValueError(f"Missing required key: {key}")
    return obj[key]


def _json(v: Any, default: Any = None) -> Any:
    if isinstance(v, (dict, list)):
        return v
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def _allowed_documents(task: dict[str, Any], payload: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    if task.get("document_id"):
        out.add(task["document_id"])
    for x in payload.get("document_ids", []) or []:
        out.add(x)
    return out


def _fold_text(value: Any) -> str:
    table = str.maketrans({"ı":"i","İ":"i","ş":"s","Ş":"s","ğ":"g","Ğ":"g","ü":"u","Ü":"u","ö":"o","Ö":"o","ç":"c","Ç":"c"})
    return " ".join(str(value or "").translate(table).casefold().split())


def _payment_decimal(value: Any, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"Payment {field} must be numeric")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Payment {field} must be numeric")
    if not parsed.is_finite():
        raise ValueError(f"Payment {field} must be finite")
    return parsed


def _payment_source_facts(con, offer_id: str, result: dict[str, Any], incoming_path: str) -> dict[str,dict[str,Any]]:
    rank={"adjudicated":5,"semantic_llm":4,"vision":3,"duckdb_pdf_secondary":2}
    selected={}
    rows=rows_as_dict(con,"SELECT * FROM facts WHERE offer_id=? ORDER BY updated_at,fact_id",[offer_id])
    candidates=[row for row in rows if row.get("evidence_status")=="verified"]
    candidates.extend({**fact,"extraction_path":incoming_path} for fact in result.get("facts",[]) if (fact.get("offer_id") or offer_id)==offer_id and fact.get("evidence_status")=="verified")
    for row in candidates:
        field=row.get("field_key"); previous=selected.get(field)
        if previous is None or rank.get(row.get("extraction_path"),1)>=rank.get(previous.get("extraction_path"),1): selected[field]=row
    return selected


def _payment_source_basis(con, offer_id: str, result: dict[str, Any], incoming_path: str) -> Decimal | None:
    """Return acquisition basis only when it is reconstructable from current inputs."""
    source_facts=_payment_source_facts(con,offer_id,result,incoming_path)
    total=source_facts.get("total")
    currency_row=source_facts.get("currency")
    raw_total = total.get("value_number") if total else None
    raw_currency = currency_row.get("value_text") if currency_row else None
    if raw_total is None or not raw_currency:
        return None
    try:
        amount = Decimal(str(raw_total))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not amount.is_finite():
        return None
    currency = str(raw_currency).upper()

    meta_row = con.execute("SELECT value FROM run_meta WHERE key='financial_parameters'").fetchone()
    try:
        financial = json.loads(meta_row[0]) if meta_row and meta_row[0] else {}
    except Exception:
        return None
    if not isinstance(financial, dict):
        return None
    offer_parameters = financial.get("offer_parameters", {})
    offer_params = offer_parameters.get(offer_id, {}) if isinstance(offer_parameters, dict) else {}
    if not isinstance(offer_params, dict):
        return None

    discounts = offer_params.get("discounts", [])
    if not isinstance(discounts, list):
        return None
    for raw in discounts:
        rate = _payment_decimal(raw, "discount")
        if rate is None or rate < 0 or rate >= 1:
            return None
        amount *= Decimal(1) - rate

    scope_by_id = {row["scope_id"]: row for row in rows_as_dict(con, "SELECT scope_id,status,cost_role,classification,amount,currency FROM scope_items WHERE offer_id=?", [offer_id])}
    for item in result.get("scope_items", []):
        if (item.get("offer_id") or offer_id) == offer_id:
            scope_by_id[item.get("scope_id") or f"pending:{len(scope_by_id)}"] = item
    scope_add = Decimal(0)
    for item in scope_by_id.values():
        role = item.get("cost_role") or item.get("classification")
        if item.get("status") == "verified" and role == "included_in_price":
            continue
        if item.get("status") != "verified" or role != "incremental_adjustment" or item.get("amount") is None:
            return None
        if str(item.get("currency") or currency).upper() != currency:
            return None
        value = _payment_decimal(item.get("amount"), "scope amount")
        if value is None or value < 0:
            return None
        scope_add += value
    amount += scope_add

    bridge = offer_params.get("import_bridge")
    if bridge is not None:
        if not isinstance(bridge, dict):
            return None
        try:
            from procurement_math import ddp_equivalent, dec
            amount = dec(ddp_equivalent(amount, bridge.get("included_costs", []) or [], bridge.get("buyer_costs", []) or [], bridge.get("non_deductible_taxes", []) or [])['ddp_equivalent'])
        except (ValueError, TypeError, KeyError):
            return None
        if amount is None:
            return None
    vat = offer_params.get("vat")
    if vat is not None:
        if not isinstance(vat, dict):
            return None
        if vat.get("price_basis") == "net_ex_vat":
            try:
                from procurement_math import vat_split
                amount = vat_split(amount, vat.get("rate"), vat.get("deductible_share"))["cost_basis"]
            except (ValueError, TypeError):
                return None
    return amount


def _validate_payment_schedule(con, task, payload, fact, ev_id, schedule: Any, result: dict[str, Any], incoming_path: str) -> None:
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("Payment schedule must be a non-empty list")
    ratios: list[Decimal | None] = []
    amounts: list[Decimal | None] = []
    for item in schedule:
        if not isinstance(item, dict) or set(item) - {"days", "ratio", "amount"}:
            raise ValueError("Payment schedule row has invalid shape or unsupported aliases")
        days = item.get("days")
        if type(days) is not int or days < 0:
            raise ValueError("Payment days must be a non-negative integer")
        ratio = _payment_decimal(item.get("ratio"), "ratio")
        amount = _payment_decimal(item.get("amount"), "amount")
        if ratio is None and amount is None:
            raise ValueError("Payment row needs ratio or amount")
        if ratio is not None and not Decimal(0) <= ratio <= Decimal(1):
            raise ValueError("Payment ratio must be between 0 and 1")
        if amount is not None and amount < 0:
            raise ValueError("Payment amount must be non-negative")
        ratios.append(ratio)
        amounts.append(amount)

    has_ratio = any(value is not None for value in ratios)
    if has_ratio:
        effective_ratio = Decimal(0)
        for ratio, amount in zip(ratios, amounts):
            if ratio is not None:
                effective_ratio += ratio
            elif amount is not None:
                basis = _payment_source_basis(con, fact.get("offer_id") or task.get("offer_id"), result, incoming_path)
                if basis is None or basis == 0:
                    raise ValueError("Cannot validate an amount payment without a known acquisition basis")
                effective_ratio += amount / basis
        if abs(effective_ratio - Decimal(1)) > Decimal("0.0001"):
            raise ValueError("Payment ratios must sum to 1")

    basis = _payment_source_basis(con, fact.get("offer_id") or task.get("offer_id"), result, incoming_path)
    if any(value is not None for value in amounts):
        if basis is None:
            if fact.get("evidence_status") == "verified":
                raise ValueError("Verified amount schedule requires a known acquisition basis")
        else:
            amount_tolerance = max(Decimal("0.01"), abs(basis) * Decimal("0.0001"))
            for ratio, amount in zip(ratios, amounts):
                if ratio is not None and amount is not None and abs(amount - basis * ratio) > amount_tolerance:
                    raise ValueError("Payment amount and ratio do not reconcile to acquisition basis")
            total_amount = sum((amount if amount is not None else (basis * ratio if ratio is not None else Decimal(0)) for ratio, amount in zip(ratios, amounts)), Decimal(0))
            if abs(total_amount - basis) > amount_tolerance:
                raise ValueError("Payment amounts do not reconcile to acquisition basis")

    if fact.get("evidence_status") != "verified" or not ev_id:
        return
    ev = one_as_dict(con, "SELECT quote FROM evidence WHERE evidence_id=?", [ev_id]) or {}
    quote = str(ev.get("quote") or fact.get("value_text") or "")
    if not quote:
        raise ValueError("Verified payment schedule requires its source quote")
    resolved_offer_id=fact.get("offer_id") or task.get("offer_id")
    delivery_facts=_payment_source_facts(con,resolved_offer_id,result,incoming_path)
    delivery=[delivery_facts["delivery"]] if delivery_facts.get("delivery") else []
    delivery_days = None
    if delivery:
        from normalize import _duration_days
        delivery_days = _duration_days(str(delivery[-1].get("value_text") or ""))
    from normalize import _payment_schedule as parse_payment_schedule
    expected = parse_payment_schedule(quote, delivery_days)
    if expected is not None:
        if len(expected) != len(schedule):
            raise ValueError("Normalized payment rows do not match the sourced schedule")
        for normalized, sourced in zip(schedule, expected):
            ratio = _payment_decimal(normalized.get("ratio"), "ratio")
            if normalized.get("days") != sourced.get("days") or (ratio is not None and abs(ratio - Decimal(str(sourced["ratio"]))) > Decimal("0.0001")):
                raise ValueError("Normalized payment ratio/day does not match source wording")
            if ratio is None and normalized.get("amount") is not None:
                basis = _payment_source_basis(con, resolved_offer_id, result, incoming_path)
                amount = _payment_decimal(normalized.get("amount"), "amount")
                if basis is None or basis == 0 or amount is None or abs(amount / basis - Decimal(str(sourced["ratio"]))) > Decimal("0.0001"):
                    raise ValueError("Amount-only payment row cannot be bound to the sourced installment ratio")
    else:
        normalized_quote=_fold_text(quote)
        delivery_relative=bool(re.search(r"(?:teslimden|teslim sonrasi|after delivery)",normalized_quote))
        if delivery_relative and re.search(r"\d+\s*(?:gun|day|days)",normalized_quote) and delivery_days is None:
            raise ValueError("Delivery-relative payment date lacks a verified delivery lead-time basis")
        percent_tokens=re.findall(r"%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%",normalized_quote)
        source_ratios=[Decimal((a or b).replace(",","."))/Decimal(100) for a,b in percent_tokens]
        scheduled_ratios=[_payment_decimal(row.get("ratio"),"ratio") for row in schedule if row.get("ratio") is not None]
        day_tokens=[int(match.group(1)) for match in re.finditer(r"(\d+)\s*(?:gun|day|days)",normalized_quote)]
        if source_ratios:
            if len(source_ratios)!=len(scheduled_ratios) or any(abs(a-b)>Decimal("0.0001") for a,b in zip(source_ratios,scheduled_ratios)):
                raise ValueError("Normalized payment ratios cannot be verified from the source wording")
        elif scheduled_ratios:
            simple_full_payment=(len(schedule)==1 and any(token in normalized_quote for token in ("pesin","cash","net ")))
            if not simple_full_payment:
                raise ValueError("Normalized payment ratio cannot be verified from the source wording")
        if day_tokens:
            if len(day_tokens)!=len(schedule):
                if not (len(schedule)==1 and len(day_tokens)==1):
                    raise ValueError("Normalized payment dates cannot be matched to the source wording")
            for row, source_day in zip(schedule,day_tokens):
                effective_source_day=delivery_days + source_day if delivery_relative and delivery_days is not None else source_day
                if row.get("days") != effective_source_day and not re.search(r"(?:teslimde|on delivery|at delivery)",normalized_quote):
                    raise ValueError("Normalized payment day cannot be verified from the source wording")
        elif not any(token in normalized_quote for token in ("pesin","cash","teslimde","on delivery","at delivery","net ")):
            raise ValueError("Normalized payment schedule cannot be verified from the source wording")
        if not scheduled_ratios:
            quoted_numbers=_decimal_tokens(quote)
            for amount in amounts:
                if amount is not None and not any(abs(value-amount)<=max(Decimal("0.01"),abs(amount)*Decimal("0.0001")) for value in quoted_numbers):
                    raise ValueError("Payment amount cannot be verified from the source wording")


def _decimal_tokens(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    # Ordinary spaces separate table cells and independent values. Treating them as
    # thousands separators can merge "5.525,00 30" into a fictitious 5525.0030.
    # Non-breaking spaces remain valid thousands separators in formatted amounts.
    for token in re.findall(r"[-+]?\d+(?:[\u00a0\u202f]\d{3})*(?:[.,]\d+)*", str(text or "")):
        s = token.replace("\u00a0", "").replace("\u202f", "")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            tail = s.rsplit(",", 1)[-1]
            s = s.replace(",", "." if len(tail) <= 2 else "")
        elif s.count(".") == 1 and len(s.rsplit(".", 1)[-1]) == 3:
            s = s.replace(".", "")
        try:
            out.append(Decimal(s))
        except InvalidOperation:
            pass
    return out


def _validate_evidence_document(con, task: dict[str, Any], task_payload: dict[str, Any], document_id: str) -> dict[str, Any]:
    allowed = _allowed_documents(task, task_payload)
    if allowed and document_id not in allowed:
        raise ValueError(f"Evidence document {document_id} is outside task scope")
    doc = one_as_dict(con, "SELECT document_id,offer_id,sha256,format_family FROM documents WHERE document_id=? AND active=true", [document_id])
    if not doc:
        raise ValueError(f"Unknown/inactive evidence document: {document_id}")
    if task.get("offer_id") and doc.get("offer_id") != task.get("offer_id"):
        raise ValueError(f"Evidence document {document_id} does not belong to task offer {task.get('offer_id')}")
    return doc


def _validate_locator_and_quote(con, document_id: str, unit_id: str | None, locator: dict[str, Any], quote: str | None, path: str, status: str) -> None:
    params: list[Any] = [document_id]
    sql = "SELECT unit_id,unit_type,locator_json,text_content,structured_json FROM document_units WHERE document_id=?"
    if unit_id:
        sql += " AND unit_id=?"
        params.append(unit_id)
    units = rows_as_dict(con, sql, params)
    if unit_id and not units:
        raise ValueError(f"Evidence unit {unit_id} does not belong to document {document_id}")
    if not units:
        raise ValueError(f"Evidence document {document_id} has no parsed source unit")

    candidates = []
    for u in units:
        uloc = _json(u.get("locator_json"), {}) or {}
        if locator.get("sheet") and uloc.get("sheet") != locator.get("sheet"):
            continue
        if locator.get("page") is not None and uloc.get("page") != locator.get("page"):
            continue
        target = xlsx_address(locator) if u.get("unit_type") == "xlsx_sheet" else None
        if target:
            st = _json(u.get("structured_json"), {}) or {}
            cells = {str(c.get("cell")) for c in st.get("cells", []) if c.get("cell")}
            refs = re.findall(r"\b[A-Z]{1,3}\d+\b", target.upper())
            if refs and not all(ref in cells for ref in refs):
                continue
        candidates.append(u)
    if not candidates:
        raise ValueError(f"Evidence locator does not resolve inside document {document_id}: {locator}")

    # For verified textual evidence, require the quoted source span to actually
    # exist in the parsed unit. Vision/image evidence is verified by the image
    # task itself and may have no textual layer.
    if status == "verified" and path != "vision":
        q = _fold_text(quote)
        if not q:
            raise ValueError("Verified textual evidence requires a non-empty quote")
        matched = False
        for u in candidates:
            hay = _fold_text(u.get("text_content"))
            if q and q in hay:
                matched = True
                break
            st = _json(u.get("structured_json"), {}) or {}
            if q and any(q in _fold_text(s) for s in _structured_texts(st)):
                matched = True
                break
        if not matched:
            raise ValueError(f"Evidence quote is not present at the resolved source locator for {document_id}")


# ISO code -> forms that may appear in a quote (folded text or raw symbol).
CURRENCY_EVIDENCE = {
    "USD": ["usd", "$", "dolar", "dollar"],
    "EUR": ["eur", "€", "euro", "avro"],
    "TRY": ["try", "tl", "₺", "turk lirasi"],
    "GBP": ["gbp", "£", "sterlin", "sterling"],
}


def _structured_texts(st: Any) -> list[str]:
    """Readable texts of structured unit content: every string leaf (a multi-line table
    cell keeps its real line breaks), every table row with cells joined by spaces and each
    whole table in row order, so a verbatim quote of a cell, a row or consecutive rows
    matches. JSON serialization is never searched (it escapes newlines)."""
    out: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(st)
    tables = st.get("tables", []) if isinstance(st, dict) else []
    for table in tables if isinstance(tables, list) else []:
        rows = [" ".join("" if c is None else str(c) for c in row) for row in table if isinstance(row, list)]
        out.extend(rows)
        out.append(" ".join(rows))
    return out


def _validate_fact_evidence_semantics(con, fact: dict[str, Any], ev_id: str | None) -> None:
    if fact.get("evidence_status") != "verified":
        return
    if not ev_id:
        raise ValueError("Verified fact requires evidence")
    ev = one_as_dict(con, "SELECT * FROM evidence WHERE evidence_id=?", [ev_id])
    if not ev:
        raise ValueError(f"Unknown evidence_id referenced by verified fact: {ev_id}")
    quote = str(ev.get("quote") or "")
    field = str(fact.get("field_key") or "")
    if fact.get("value_number") is not None and field in {"total", "quantity", "unit_price", "price"}:
        target = Decimal(str(fact["value_number"]))
        nums = _decimal_tokens(quote)
        tol = max(Decimal("0.01"), abs(target) * Decimal("0.0001"))
        if not any(abs(n - target) <= tol for n in nums):
            raise ValueError(f"Evidence quote does not support numeric value for {field}: {target}")
    elif fact.get("value_text") is not None and field in {"currency", "incoterms", "vat", "payment", "delivery", "warranty", "scope_signature"}:
        needle = _fold_text(fact.get("value_text"))
        hay = _fold_text(quote)
        # VAT normalization may turn a Turkish/English phrase into included/excluded.
        if field == "currency" and needle.upper() in CURRENCY_EVIDENCE:
            if not any(alias in hay or alias in quote for alias in CURRENCY_EVIDENCE[needle.upper()]):
                raise ValueError("Evidence quote does not support currency")
        elif field == "vat" and needle in {"included", "excluded"}:
            negative_inclusion = ["dahil degil", "dahil edilmem", "dahil edilmez", "not included", "not include"]
            if needle == "included" and any(x in hay for x in negative_inclusion):
                raise ValueError("Evidence quote excludes VAT; included normalization refused")
            if needle == "excluded" and "haric degil" in hay:
                raise ValueError("Negated VAT exclusion cannot establish excluded normalization")
            aliases = {"included": ["dahil", "included", "include"], "excluded": ["haric", "excluded", "exclude", *negative_inclusion]}[needle]
            if not any(x in hay for x in aliases):
                raise ValueError("Evidence quote does not support VAT normalization")
        elif needle and needle not in hay:
            raise ValueError(f"Evidence quote does not support text value for {field}")


def _validate_existing_evidence(con, task: dict[str, Any], task_payload: dict[str, Any], evidence_id: str, fact: dict[str, Any] | None = None) -> None:
    ev = one_as_dict(con, "SELECT * FROM evidence WHERE evidence_id=?", [evidence_id])
    if not ev:
        raise ValueError(f"Unknown evidence_id: {evidence_id}")
    doc = _validate_evidence_document(con, task, task_payload, ev["document_id"])
    if ev.get("source_sha256") != doc.get("sha256"):
        raise ValueError(f"Evidence {evidence_id} is tied to a stale source hash")
    _validate_locator_and_quote(con, ev["document_id"], ev.get("unit_id"), _json(ev.get("locator_json"), {}) or {}, ev.get("quote"), ev.get("extraction_path") or "", ev.get("evidence_status") or "")
    if fact:
        _validate_fact_evidence_semantics(con, fact, evidence_id)


def _insert_evidence(con, task: dict[str, Any], task_payload: dict[str, Any], ev: dict[str, Any], path: str) -> str:
    status = require(ev, "evidence_status")
    if status not in VALID_EVIDENCE_STATUS:
        raise ValueError(f"Invalid evidence_status: {status}")
    document_id = require(ev, "document_id")
    _validate_evidence_document(con, task, task_payload, document_id)
    locator = require(ev, "locator")
    _validate_locator_and_quote(con, document_id, ev.get("unit_id"), locator, ev.get("quote"), path, status)
    local_id = ev.get("evidence_id")
    ev_id = local_id or stable_id("ev", document_id, json_text(locator), ev.get("quote", ""), task["task_id"], length=22)
    source = con.execute("SELECT sha256 FROM documents WHERE document_id=?", [document_id]).fetchone()
    if not source:
        raise ValueError(f"Unknown evidence document: {document_id}")
    # Model-supplied labels such as ev_currency are local to one task. Never
    # replace a different document's evidence just because another task used
    # the same label; facts recorded earlier would silently cite the new row.
    identity = (document_id, ev.get("unit_id"), json_text(locator), ev.get("quote"), status, path, source[0])
    def stored_identity(key):
        row = con.execute(
            "SELECT document_id,unit_id,locator_json,quote,evidence_status,extraction_path,source_sha256 "
            "FROM evidence WHERE evidence_id=?", [key],
        ).fetchone()
        return tuple(row) if row else None
    existing = stored_identity(ev_id)
    if existing == identity:
        return ev_id
    if existing:
        if not local_id:
            raise ValueError("Generated evidence identity collision")
        ev_id = stable_id("ev", task["task_id"], local_id, document_id,
                          json_text(locator), ev.get("quote", ""), length=22)
        existing = stored_identity(ev_id)
        if existing == identity:
            return ev_id
        if existing:
            raise ValueError("Task-scoped evidence identity collision")
    con.execute(
        """
        INSERT INTO evidence(evidence_id,document_id,unit_id,locator_json,quote,evidence_status,extraction_path,confidence,source_sha256)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [ev_id, document_id, ev.get("unit_id"), json_text(locator), ev.get("quote"), status, path, ev.get("confidence"), source[0]],
    )
    return ev_id


def _remember_evidence_alias(mapping: dict[str, str], alias: str | None, evidence_id: str) -> None:
    if not alias:
        return
    if alias in mapping and mapping[alias] != evidence_id:
        raise ValueError(f"Ambiguous model-local evidence reference: {alias}")
    mapping[alias] = evidence_id


def _scoped_model_row_id(con, table: str, key: str, proposed: str, task_id: str,
                         identity: dict[str, Any], prefix: str, length: int = 22) -> str:
    """Preserve a model-local label unless another source already owns it."""
    columns = list(identity)
    select = ",".join(columns)
    def stored(row_id):
        return one_as_dict(con, f"SELECT {select} FROM {table} WHERE {key}=?", [row_id])
    previous = stored(proposed)
    if not previous or all(previous[column] == identity[column] for column in columns):
        return proposed
    scoped = stable_id(prefix, task_id, proposed, json_text(identity), length=length)
    previous = stored(scoped)
    if previous and any(previous[column] != identity[column] for column in columns):
        raise ValueError(f"Task-scoped {key} identity collision")
    return scoped


def _upsert_fact(con, fact: dict[str, Any], ev_id: str | None, path: str) -> None:
    status = require(fact, "evidence_status")
    if status not in VALID_EVIDENCE_STATUS:
        raise ValueError(f"Invalid fact evidence_status: {status}")
    supplied_id = fact.get("fact_id")
    offer_id, requirement_id, field_key = fact.get("offer_id"), fact.get("requirement_id"), fact.get("field_key")
    if supplied_id:
        identity = con.execute("SELECT offer_id,requirement_id,field_key FROM facts WHERE fact_id=?", [supplied_id]).fetchone()
        if identity and tuple(identity) != (offer_id, requirement_id, field_key):
            raise ValueError("Fact identity does not match the referenced canonical record")
    # Offer fields have one canonical identity. Model-local IDs are aliases,
    # not a second storage grain that the decision engine cannot resolve.
    if offer_id and requirement_id:
        fact["fact_id"] = f"{offer_id}/requirement/{requirement_id}"
    elif offer_id and field_key:
        fact["fact_id"] = f"{offer_id}/field/{field_key}"
    fact_id = fact.get("fact_id")
    if not fact_id:
        offer_id = fact.get("offer_id")
        requirement_id = fact.get("requirement_id")
        field_key = fact.get("field_key")
        if offer_id and requirement_id:
            fact_id = f"{offer_id}/requirement/{requirement_id}"
        elif offer_id and field_key:
            fact_id = f"{offer_id}/field/{field_key}"
        else:
            raise ValueError("Fact requires fact_id or a derivable offer_id + field_key/requirement_id")
        fact["fact_id"] = fact_id
    if status == "verified" and not ev_id:
        raise ValueError(f"Verified fact {fact_id} requires evidence")
    if status == "verified":
        ev_path = con.execute('SELECT extraction_path FROM evidence WHERE evidence_id=?', [ev_id]).fetchone()
        pixel_numeric = fact.get('field_key') in {'total','quantity','unit_price','price'} or (fact.get('field_key') in {'quote_date','validity','delivery','payment','warranty','vat'} and bool(re.search(r'\d', str(fact.get('value_text') or fact.get('value_date') or fact.get('value_number') or ''))))
        if (path == 'vision' or (ev_path and ev_path[0] == 'vision')) and pixel_numeric:
            raise ValueError("Pixel number requires independent confirmation; record requires_confirmation and corroborate it separately")
        _validate_fact_evidence_semantics(con, fact, ev_id)
    # Criticality belongs to the trusted field/requirement contract. A model
    # may omit the optional flag or request false without narrowing review.
    from field_extract import CRITICAL_FIELDS
    existing = con.execute("SELECT critical FROM facts WHERE fact_id=?", [fact_id]).fetchone()
    requirement = con.execute("SELECT critical FROM requirements WHERE requirement_id=?", [fact.get("requirement_id")]).fetchone() if fact.get("requirement_id") else None
    critical = bool(existing and existing[0]) or bool(requirement and requirement[0]) or (
        fact.get("offer_id") is not None and fact.get("field_key") in CRITICAL_FIELDS and fact.get("field_key") != "scope_signature"
    ) or bool(fact.get("critical", False))
    con.execute(
        """
        INSERT OR REPLACE INTO facts(
          fact_id,offer_id,supplier_id,requirement_id,field_key,value_text,value_number,value_date,
          unit,currency,evidence_status,critical,evidence_id,extraction_path,normalized_json,updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [
            fact_id, fact.get("offer_id"), fact.get("supplier_id"), fact.get("requirement_id"), require(fact, "field_key"),
            fact.get("value_text"), fact.get("value_number"), fact.get("value_date"), fact.get("unit"), fact.get("currency"),
            status, critical, ev_id, path, json_text(fact.get("normalized", {})), utc_now(),
        ],
    )


def _record_document_classification(con, task: dict[str, Any], result: dict[str, Any]) -> dict[str, int]:
    role = require(result, "document_role")
    if role not in VALID_DOC_ROLES:
        raise ValueError(f"Invalid document_role: {role}")
    doc = one_as_dict(con, "SELECT * FROM documents WHERE document_id=?", [task["document_id"]])
    if not doc:
        raise ValueError(f"Unknown document: {task['document_id']}")
    if doc.get("format_family") == "zip" and role == "offer":
        raise ValueError("Archive container cannot be classified as a separate offer; classify its extracted members")
    supplier_id = doc.get("supplier_id")
    offer_id = doc.get("offer_id")
    if role == "offer":
        from ingest import supplier_candidate, normalize_supplier_name
        supplier_name = result.get("supplier_name")
        declaration_row = con.execute("SELECT value FROM run_meta WHERE key='supplier_folder_declaration_v1'").fetchone()
        declared_name = None
        if declaration_row:
            declaration = json.loads(declaration_row[0])
            mappings = declaration.get("mappings") if isinstance(declaration, dict) else None
            if not isinstance(mappings, dict) or declaration.get("source") != "user_declaration":
                raise ValueError("Supplier folder declaration is malformed")
            relative = str(doc.get("relative_path") or "").replace("\\", "/")
            matching_folders = [folder for folder in mappings
                                if isinstance(folder, str) and relative.startswith(folder.strip("/") + "/")]
            if matching_folders:
                declared_name = mappings[max(matching_folders, key=lambda folder: len(folder.strip("/")))]
            if declared_name is not None and (not isinstance(declared_name, str) or not declared_name.strip()):
                raise ValueError("Supplier folder declaration has an invalid name")
        if declared_name:
            supplier_name = declared_name
        if supplier_name:
            display = str(supplier_name).strip()
            normalized = normalize_supplier_name(display)
            confidence = float(result.get("supplier_confidence", 0.8)) if not declared_name else None
        else:
            display, normalized, confidence = supplier_candidate(doc.get("filename") or "offer", "")
        old_supplier_id = supplier_id
        if supplier_name:
            supplier_id = stable_id("sup", normalized or display, length=16)
        else:
            supplier_id = supplier_id or stable_id("sup", normalized or display, length=16)
        offer_id = offer_id or stable_id("off", task["document_id"], length=18)
        existing_offer = one_as_dict(con, "SELECT * FROM offers WHERE offer_id=?", [offer_id])
        if existing_offer:
            existing_ids = _json(existing_offer.get("source_document_ids_json"), None)
            if not isinstance(existing_ids, list) or any(not isinstance(x, str) for x in existing_ids):
                raise ValueError("Offer source document list is invalid")
            if existing_offer.get("supplier_id") != supplier_id and any(x != task["document_id"] for x in existing_ids):
                raise ValueError("Shared legacy offer identity cannot be rebound silently; start a fresh source-separated run")
        con.execute(
            "INSERT OR IGNORE INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES (?,?,?,?)",
            [supplier_id, display, normalized, "user_declared" if declared_name else ("confirmed" if result.get("supplier_name") else "provisional")],
        )
        if supplier_name:
            con.execute("UPDATE suppliers SET display_name=?,normalized_name=?,identification_status=? WHERE supplier_id=?", [display, normalized, "user_declared" if declared_name else "confirmed", supplier_id])
        con.execute(
            "INSERT OR IGNORE INTO offers(offer_id,supplier_id,display_name,revision_label,status,source_document_ids_json) VALUES (?,?,?,?,?,?)",
            [offer_id, supplier_id, display, doc.get("revision_label"), "active", json_text([task["document_id"]])],
        )
        con.execute("UPDATE offers SET supplier_id=?,display_name=? WHERE offer_id=?", [supplier_id, display, offer_id])
        con.execute("UPDATE facts SET supplier_id=? WHERE offer_id=?", [supplier_id, offer_id])
        if supplier_name and old_supplier_id:
            con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE owner=? AND issue_type='supplier_identity' AND status='open'", [utc_now(), f"FIRMA:{old_supplier_id}"])
    if role == "offer" and offer_id:
        row = con.execute("SELECT source_document_ids_json FROM offers WHERE offer_id=?", [offer_id]).fetchone()
        ids = _json(row[0] if row else None, None)
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            raise ValueError("Offer source document list is invalid")
        ids = list(dict.fromkeys(ids + [task["document_id"]]))
        con.execute("UPDATE offers SET source_document_ids_json=? WHERE offer_id=?", [json_text(ids), offer_id])
    con.execute(
        "UPDATE documents SET document_role=?,role_confidence=?,supplier_id=?,offer_id=? WHERE document_id=?",
        [role, result.get("confidence", 0.8), supplier_id, offer_id, task["document_id"]],
    )
    if role == "offer" and old_supplier_id and old_supplier_id != supplier_id:
        referenced = sum(con.execute(f"SELECT count(*) FROM {table} WHERE supplier_id=?", [old_supplier_id]).fetchone()[0] for table in ["documents", "offers", "facts"])
        if not referenced:
            con.execute("DELETE FROM suppliers WHERE supplier_id=?", [old_supplier_id])
    return {"documents": 1, "offer_created": 1 if role == "offer" and offer_id else 0}


def _record_requirements(con, task: dict[str, Any], task_payload: dict[str, Any], result: dict[str, Any]) -> dict[str, int]:
    requirements = result.get("requirements", [])
    evidence_map: dict[str, str] = {}
    count_e = 0
    for ev in result.get("evidence", []):
        unit = one_as_dict(con, "SELECT unit_type,text_content FROM document_units WHERE unit_id=? AND document_id=?",
                           [ev.get("unit_id"), ev.get("document_id")]) if ev.get("unit_id") else None
        document = one_as_dict(con, "SELECT format_family,parse_status FROM documents WHERE document_id=?",
                               [ev.get("document_id")]) or {}
        pixel_only = document.get("format_family") == "image" or (
            document.get("format_family") == "pdf" and
            ((unit is not None and not (unit.get("text_content") or "").strip()) or
             (unit is None and document.get("parse_status") == "partial"))
        )
        eid = _insert_evidence(con, task, task_payload, ev, "vision" if pixel_only else "semantic_llm")
        _remember_evidence_alias(evidence_map, ev.get("evidence_id"), eid)
        _remember_evidence_alias(evidence_map, ev.get("client_id"), eid)
        count_e += 1
    count_r = 0
    for req in requirements:
        text = require(req, "text")
        req_id = req.get("requirement_id") or stable_id("req", task["document_id"] or "", req.get("section", ""), text, length=20)
        req_id = _scoped_model_row_id(
            con, "requirements", "requirement_id", req_id, task["task_id"],
            {"source_document_id": task["document_id"], "source_unit_id": req.get("source_unit_id"),
             "section": req.get("section"), "text": text}, "req", length=20,
        )
        eid = evidence_map.get(req.get("evidence_id"), req.get("evidence_id")) or evidence_map.get(req.get("evidence_client_id"))
        if req.get("evidence_id"):
            _validate_existing_evidence(con, task, task_payload, eid)
        if eid and req.get("critical", False) and re.search(r"\d", text):
            cited = one_as_dict(con, "SELECT extraction_path,evidence_status FROM evidence WHERE evidence_id=?", [eid]) or {}
            if cited.get("extraction_path") == "vision" and cited.get("evidence_status") == "verified":
                raise ValueError("Critical numeric requirement from pixels requires independent confirmation")
        con.execute(
            """
            INSERT OR REPLACE INTO requirements(requirement_id,source_document_id,source_unit_id,category,section,text,critical,evidence_id)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            [req_id, task["document_id"], req.get("source_unit_id"), req.get("category", "information"), req.get("section"), text, bool(req.get("critical", False)), eid],
        )
        count_r += 1
    return {"requirements": count_r, "evidence": count_e}


def _record_facts(con, task: dict[str, Any], task_payload: dict[str, Any], result: dict[str, Any], path: str) -> dict[str, int]:
    evidence_map: dict[str, str] = {}
    count_e = 0
    for ev in result.get("evidence", []):
        eid = _insert_evidence(con, task, task_payload, ev, path)
        _remember_evidence_alias(evidence_map, ev.get("evidence_id"), eid)
        _remember_evidence_alias(evidence_map, ev.get("client_id"), eid)
        count_e += 1
    count_f = 0
    fact_aliases: dict[str, str] = {}
    for fact in result.get("facts", []):
        if task.get("offer_id") and fact.get("offer_id") not in {None, task["offer_id"]}:
            raise ValueError(f"Fact offer_id outside task scope: {fact.get('offer_id')}")
        if task.get("offer_id") and not fact.get("offer_id"):
            fact["offer_id"] = task["offer_id"]
        if fact.get("offer_id") and not fact.get("supplier_id"):
            row = con.execute("SELECT supplier_id FROM offers WHERE offer_id=?", [fact["offer_id"]]).fetchone()
            if row:
                fact["supplier_id"] = row[0]
        if fact.get("requirement_id"):
            fact.setdefault("field_key", "requirement_status")
            row = con.execute("SELECT critical FROM requirements WHERE requirement_id=?", [fact["requirement_id"]]).fetchone()
            if row is not None and "critical" not in fact:
                fact["critical"] = bool(row[0])
        ev_id = evidence_map.get(fact.get("evidence_id"), fact.get("evidence_id")) or evidence_map.get(fact.get("evidence_client_id"))
        if ev_id and fact.get("evidence_id"):
            _validate_existing_evidence(con, task, task_payload, ev_id, fact)
        def canonical_refs(value):
            if isinstance(value, list):
                return [canonical_refs(x) for x in value]
            if not isinstance(value, dict):
                return value
            out = {}
            for key, val in value.items():
                if key in {'evidence_refs', 'evidence_ids'}:
                    if not isinstance(val, list):
                        raise ValueError('Normalized evidence references must be a list')
                    refs = [evidence_map.get(x, x) for x in val]
                    for ref in refs:
                        _validate_existing_evidence(con, task, task_payload, ref)
                    out[key] = refs
                else:
                    out[key] = canonical_refs(val)
            return out
        fact['normalized'] = canonical_refs(fact.get('normalized', {}))
        payment_schedule = fact['normalized'].get('payment_schedule')
        if payment_schedule is not None:
            _validate_payment_schedule(con, task, task_payload, fact, ev_id, payment_schedule, result, path)
        item_ids = [i['item_id'] for i in fact['normalized'].get('items', [])]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError('Duplicate normalized item identity')
        for item in fact['normalized'].get('items', []):
            if item.get('evidence_status') != 'verified':
                continue
            refs = item['evidence_refs']
            for key,field in [('quantity','quantity'),('amount','price')]:
                if item.get(key) is None:
                    continue
                supported=False
                for ref in refs:
                    ev=one_as_dict(con,'SELECT extraction_path,evidence_status FROM evidence WHERE evidence_id=?',[ref]) or {}
                    if ev.get('extraction_path')=='vision' or ev.get('evidence_status')!='verified':
                        continue
                    try:
                        _validate_fact_evidence_semantics(con,{'field_key':field,'value_number':item[key],'evidence_status':'verified'},ref)
                        supported=True
                        break
                    except ValueError:
                        continue
                if not supported:
                    raise ValueError('Item value requires its own verified non-pixel evidence or independent confirmation')
        if fact.get('field_key') == 'total' and fact.get('value_number') is not None and fact['normalized'].get('items') and fact['normalized'].get('amount_basis') != 'stated_grand_total':
            raise ValueError('Item prices are not a stated grand total; keep total null and calculated item subtotal separate')
        if fact['normalized'].get('items'):
            from item_totals import calculate
            fact['normalized']['item_calculation']=calculate(fact['normalized']['items'])
        supplied_fact_id = fact.get("fact_id")
        _upsert_fact(con, fact, ev_id, path)
        if supplied_fact_id:
            fact_aliases[supplied_fact_id] = fact["fact_id"]
        count_f += 1

    def resolve_refs(refs, aliases, table, column):
        resolved = [aliases.get(ref, ref) for ref in (refs or [])]
        for ref in resolved:
            if not con.execute(f"SELECT 1 FROM {table} WHERE {column}=?", [ref]).fetchone():
                raise ValueError(f"Unknown canonical {column} reference: {ref}")
        return resolved
    count_scope = 0
    for item in result.get("scope_items", []):
        offer_id = item.get("offer_id") or task.get("offer_id")
        if task.get("offer_id") and offer_id != task.get("offer_id"):
            raise ValueError("Scope item offer_id outside task scope")
        scope_id = item.get("scope_id") or stable_id("scope", offer_id or "", item.get("classification", ""), item.get("description", ""), length=22)
        scope_id = _scoped_model_row_id(
            con, "scope_items", "scope_id", scope_id, task["task_id"],
            {"offer_id": offer_id, "classification": item.get("classification"),
             "description": item.get("description"), "cost_role": item.get("cost_role")}, "scope",
        )
        cost_role = require(item, "cost_role")
        if cost_role not in {"included_in_price", "incremental_adjustment", "unresolved_adjustment"}:
            raise ValueError("Scope item has invalid cost_role")
        scope_status = require(item, "status")
        if scope_status not in VALID_EVIDENCE_STATUS:
            raise ValueError(f"Scope item has invalid evidence status: {scope_status}")
        scope_evidence = resolve_refs(item.get("evidence_ids"), evidence_map, "evidence", "evidence_id")
        for ref in scope_evidence:
            _validate_existing_evidence(con, task, task_payload, ref)
        if item.get("status") == "verified" and not scope_evidence:
            raise ValueError("Verified scope role requires source evidence")
        if item.get('status') == 'verified' and cost_role == 'incremental_adjustment':
            if item.get('amount') is None or not item.get('currency'):
                raise ValueError('Verified incremental cost needs explicit amount and currency')
            amount_supported=currency_supported=False
            for ref in scope_evidence:
                ev=one_as_dict(con,'SELECT extraction_path,evidence_status FROM evidence WHERE evidence_id=?',[ref]) or {}
                if ev.get('extraction_path')=='vision' or ev.get('evidence_status')!='verified':
                    continue
                for field,key in [('price','amount'),('currency','currency')]:
                    value_fact={'field_key':field,'evidence_status':'verified', 'value_number' if field=='price' else 'value_text':item[key]}
                    try:
                        _validate_fact_evidence_semantics(con,value_fact,ref)
                        if field=='price':amount_supported=True
                        else:currency_supported=True
                    except ValueError:
                        continue
            if not amount_supported or not currency_supported:
                raise ValueError('Incremental cost amount/currency not supported by scoped evidence')
        con.execute(
            "INSERT OR REPLACE INTO scope_items(scope_id,offer_id,classification,description,status,amount,currency,payment_date,evidence_ids_json,critical,cost_role) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [scope_id, offer_id, require(item, "classification"), require(item, "description"), scope_status, item.get("amount"), item.get("currency"), item.get("payment_date"), json_text(scope_evidence), bool(item.get("critical", False)), cost_role],
        )
        count_scope += 1
    count_issues = 0
    for issue in result.get("open_issues", []):
        owner = require(issue, "owner")
        if not (owner == "IDARE" or owner == "TUM_FIRMALAR" or owner.startswith("FIRMA:")):
            raise ValueError(f"Invalid issue owner: {owner}")
        issue_id = issue.get("issue_id") or stable_id("issue", owner, issue.get("issue_type", "semantic"), issue.get("question", ""), length=22)
        if is_generated_issue(con, issue_id):
            issue_id = stable_id("issue", "model", task["task_id"], issue_id, length=22)
        issue_facts = resolve_refs(issue.get("fact_ids"), fact_aliases, "facts", "fact_id")
        issue_evidence = resolve_refs(issue.get("evidence_ids"), evidence_map, "evidence", "evidence_id")
        issue_id = _scoped_model_row_id(
            con, "open_issues", "issue_id", issue_id, task["task_id"],
            {"owner": owner, "issue_type": issue.get("issue_type", "semantic"),
             "question": issue["question"], "fact_ids_json": json_text(issue_facts),
             "evidence_ids_json": json_text(issue_evidence)}, "issue",
        )
        con.execute(
            "INSERT OR REPLACE INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            [issue_id, owner, issue.get("severity", "medium"), issue.get("issue_type", "semantic"), require(issue, "question"), json_text(issue_facts), json_text(issue_evidence), "open", utc_now()],
        )
        count_issues += 1
    count_exclusions = 0
    for exc in result.get("exclusions", []):
        offer_id = exc.get("offer_id") or task.get("offer_id")
        exc_id = exc.get("exclusion_id") or stable_id("exc", offer_id or "", exc.get("requirement_id", ""), exc.get("reason", ""), length=22)
        exclusion_evidence = [evidence_map.get(x, x) for x in exc.get("evidence_ids", [])]
        exc_id = _scoped_model_row_id(
            con, "exclusions", "exclusion_id", exc_id, task["task_id"],
            {"offer_id": offer_id, "requirement_id": exc.get("requirement_id"),
             "reason": exc["reason"], "evidence_ids_json": json_text(exclusion_evidence)}, "exc",
        )
        con.execute(
            "INSERT OR REPLACE INTO exclusions(exclusion_id,offer_id,requirement_id,decision,reason,evidence_ids_json,status) VALUES (?,?,?,?,?,?,?)",
            [exc_id, offer_id, exc.get("requirement_id"), exc.get("decision", "review"), require(exc, "reason"), json_text(exclusion_evidence), exc.get("status", "open")],
        )
        count_exclusions += 1
    return {"facts": count_f, "evidence": count_e, "scope_items": count_scope, "open_issues": count_issues, "exclusions": count_exclusions}


def _record_independent_review(con, task: dict[str, Any], result: dict[str, Any]) -> dict[str, int]:
    review_id = result.get("review_id") or task["task_id"]
    allowed = set((_json(task.get("payload_json"), {}) or {}).get("fact_ids", []))
    count = 0
    for fact in result.get("facts", []):
        fact_id = require(fact, "fact_id")
        if allowed and fact_id not in allowed:
            raise ValueError(f"Reviewed fact outside task scope: {fact_id}")
        status = require(fact, "evidence_status")
        if status not in VALID_EVIDENCE_STATUS:
            raise ValueError(f"Invalid review evidence_status: {status}")
        if fact.get("evidence_id"):
            current = one_as_dict(con, "SELECT * FROM facts WHERE fact_id=?", [fact_id]) or {}
            probe = dict(current); probe.update(fact); probe.setdefault("field_key", current.get("field_key"))
            _validate_existing_evidence(con, task, _json(task.get("payload_json"), {}) or {}, fact["evidence_id"], probe)
        con.execute(
            """
            INSERT OR REPLACE INTO review_facts(review_id,fact_id,value_text,value_number,value_date,evidence_status,evidence_id,review_path)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            [review_id, fact_id, fact.get("value_text"), fact.get("value_number"), fact.get("value_date"), status, fact.get("evidence_id"), "independent_llm"],
        )
        count += 1
    return {"review_facts": count, "review_id": review_id}


def _record_adjudication(con, task: dict[str, Any], result: dict[str, Any]) -> dict[str, int]:
    count = 0
    for dec in result.get("decisions", []):
        diff_id = require(dec, "difference_id")
        choice = require(dec, "decision")
        if choice not in VALID_ADJUDICATIONS:
            raise ValueError(f"Invalid adjudication decision: {choice}")
        diff = one_as_dict(con, "SELECT * FROM differences WHERE difference_id=? AND status='open'", [diff_id])
        if not diff:
            raise ValueError(f"Unknown/open difference: {diff_id}")
        replacement = dec.get("replacement")
        con.execute(
            "INSERT OR REPLACE INTO adjudications(difference_id,decision,reason,replacement_json,evidence_ids_json,adjudicated_at) VALUES (?,?,?,?,?,?)",
            [diff_id, choice, require(dec, "reason"), json_text(replacement) if replacement is not None else None, json_text(dec.get("evidence_ids", [])), utc_now()],
        )
        if choice == "corrected":
            if not isinstance(replacement, dict):
                raise ValueError(f"corrected decision requires replacement: {diff_id}")
            fact_id = diff.get("fact_id")
            if not fact_id:
                raise ValueError(f"Difference has no fact_id: {diff_id}")
            current = one_as_dict(con, "SELECT * FROM facts WHERE fact_id=?", [fact_id])
            if not current:
                raise ValueError(f"Fact not found for correction: {fact_id}")
            merged = dict(current)
            merged.update(replacement)
            merged["fact_id"] = fact_id
            if merged.get("evidence_id"):
                _validate_existing_evidence(con, {"offer_id": current.get("offer_id")}, {}, merged["evidence_id"], merged)
            _upsert_fact(con, merged, merged.get("evidence_id"), "adjudicated")
        elif choice == "independent":
            obj = _json(diff.get("independent_json"), {})
            if obj:
                obj["fact_id"] = diff.get("fact_id")
                current = one_as_dict(con, "SELECT * FROM facts WHERE fact_id=?", [obj["fact_id"]]) or {}
                obj.setdefault("offer_id", current.get("offer_id")); obj.setdefault("field_key", current.get("field_key")); obj.setdefault("supplier_id", current.get("supplier_id"))
                if obj.get("evidence_id"):
                    _validate_existing_evidence(con, {"offer_id": current.get("offer_id")}, {}, obj["evidence_id"], obj)
                _upsert_fact(con, obj, obj.get("evidence_id"), "adjudicated")
        elif choice == "open":
            issue_id = stable_id("issue", "adjudication", diff_id, length=22)
            con.execute(
                """
                INSERT OR REPLACE INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                [issue_id, "IDARE", "critical" if diff.get("critical") else "high", "adjudication_open", require(dec, "reason"), json_text([diff.get("fact_id")]), json_text(dec.get("evidence_ids", [])), "open", utc_now()],
            )
        con.execute("UPDATE differences SET status=? WHERE difference_id=?", ["open" if choice == "open" else "resolved", diff_id])
        count += 1
    return {"adjudications": count}


def _record_artifact_visual_review(con, task: dict[str, Any], result: dict[str, Any], run_root: Path) -> dict[str, int]:
    payload = _json(task.get("payload_json"), {}) or {}
    artifact_id = require(payload, "artifact_id")
    allowed = {p["render_key"]: p for p in payload["pages"]}
    if payload.get("recheck_id"):
        from visual_recheck import _current
        row = one_as_dict(con, "SELECT * FROM visual_rechecks WHERE recheck_id=? AND task_id=?", [payload["recheck_id"], task["task_id"]])
        if not row or len(allowed) != 1 or row["render_key"] not in allowed:
            raise ValueError("Recheck task/page identity mismatch")
        _current(con, run_root, artifact_id,
                 row["render_key"], row["artifact_sha256"], row["render_sha256"])
        image = Path(allowed[row["render_key"]]["image_path"])
        from common import sha256_file
        if not image.is_file() or sha256_file(image) != row["render_sha256"]:
            raise ValueError("Recheck image/hash changed")
        page = result["pages"][0]
        status = page["status"].casefold()
        note = str(page.get("observations") or page.get("note") or "")
        from llm_result_validate import result_hash
        con.execute("UPDATE visual_rechecks SET result_status=?,result_note=?,result_sha256=? WHERE recheck_id=?",
                    [status, note, result_hash(result), row["recheck_id"]])
        return {"pages_reviewed": 1, "pages_failed": int(status == "fail")}
    count = 0
    failed = 0
    for page in result.get("pages", []):
        key = require(page, "render_key")
        if key not in allowed:
            raise ValueError(f"Visual QA page outside task scope: {key}")
        status = str(require(page, "status")).casefold()
        if status not in {"pass", "fail"}:
            raise ValueError(f"Invalid visual QA status: {status}")
        note = str(page.get("observations") or page.get("note") or "")
        con.execute(
            "INSERT OR REPLACE INTO render_hashes(artifact_id,render_key,render_sha256,qa_status,qa_note) VALUES (?,?,?,?,?)",
            [artifact_id, key, allowed[key].get("sha256"), status, note],
        )
        if status == "fail":
            failed += 1
            fid = stable_id("qa", artifact_id, key, note, length=22)
            con.execute(
                "INSERT OR REPLACE INTO qa_findings(finding_id,artifact_id,finding_type,locator_json,severity,status,message,finding_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                [fid, artifact_id, "visual_layout", json_text({"render_key": key}), "critical", "open", note or f"Visual QA failed for {key}", stable_id("h", note or key, length=20), utc_now()],
            )
        count += 1
    return {"pages_reviewed": count, "pages_failed": failed}


def _validate_visual_scope(task: dict[str, Any], result: dict[str, Any]) -> None:
    payload = _json(task.get("payload_json"), {}) or {}
    expected = [p.get("render_key") for p in payload.get("pages", [])]
    returned = [p.get("render_key") for p in result.get("pages", [])]
    if not expected or len(expected) != len(set(expected)) or len(returned) != len(set(returned)) or set(returned) != set(expected):
        raise ValueError("Visual result must contain every dispatched page exactly once")


def _validate_visual_files(con, run_root: Path, task: dict[str, Any]) -> None:
    from common import sha256_file
    payload = _json(task.get("payload_json"), {}) or {}
    artifact = one_as_dict(con, "SELECT * FROM artifacts WHERE artifact_id=? AND artifact_type='pdf' AND status='ready'", [payload.get("artifact_id")])
    if not artifact or str((run_root / artifact["relative_path"]).resolve()) != payload.get("artifact_path"):
        raise ValueError("Visual task artifact identity changed")
    path = run_root / artifact["relative_path"]
    if not path.is_file() or sha256_file(path) != artifact["sha256"]:
        raise ValueError("Visual task PDF hash changed")
    if payload.get("artifact_sha256") and payload["artifact_sha256"] != artifact["sha256"]:
        raise ValueError("Recheck PDF hash changed")
    for page in payload.get("pages", []):
        key, expected = page["render_key"], page["sha256"]
        row = one_as_dict(con, "SELECT render_sha256 FROM render_hashes WHERE artifact_id=? AND render_key=?", [artifact["artifact_id"], key])
        image = Path(page["image_path"])
        if not row or row["render_sha256"] != expected or not image.is_file() or sha256_file(image) != expected:
            raise ValueError("Visual task page/image hash changed")
    for image in payload.get("supplementary_images", []):
        path = Path(image["path"])
        if not path.is_file() or sha256_file(path) != image["sha256"]:
            raise ValueError("Supplementary image hash changed")


def _record_decision_summary(con, task: dict[str, Any], result: dict[str, Any]) -> dict[str, int]:
    summary = require(result, "summary")
    recommendation = result.get("recommendation")
    claims = result.get("claims") or []
    row = con.execute("SELECT value FROM run_meta WHERE key='decision_status'").fetchone()
    if row and row[0] == "PRELIMINARY_ONLY" and recommendation is not None:
        raise ValueError("decision_summary recommendation must be null while decision_status is PRELIMINARY_ONLY")
    con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('decision_summary',?)", [summary])
    con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('decision_recommendation',?)", [json_text(recommendation)])
    con.execute("DELETE FROM claims WHERE source_task_id=?", [task["task_id"]])
    for idx, claim in enumerate(claims):
        ctype = require(claim, "type")
        text = require(claim, "text")
        fact_ids = claim.get("fact_ids") or []
        calc_ids = claim.get("calculation_ids") or []
        req_ids = claim.get("requirement_ids") or []
        evidence_ids = claim.get("evidence_ids") or []
        assertions = claim.get("assertions") or []
        caveat = claim.get("caveat")
        rev = stable_id("claimrev", ctype, text, json_text(fact_ids), json_text(calc_ids), json_text(req_ids), json_text(evidence_ids), json_text(assertions), str(caveat or ""), length=40)
        claim_id = stable_id("claim", task["task_id"], str(idx), rev, length=24)
        con.execute(
            "INSERT INTO claims(claim_id,claim_type,claim_text,support_status,fact_ids_json,calculation_ids_json,requirement_ids_json,evidence_ids_json,assertions_json,caveat,source_task_id,revision,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [claim_id, ctype, text, "pending", json_text(fact_ids), json_text(calc_ids), json_text(req_ids), json_text(evidence_ids), json_text(assertions), caveat, task["task_id"], rev, utc_now()],
        )
    return {"decision_summary": 1, "claims": len(claims)}


def _validate_fact_contract(task: dict[str, Any], payload: dict[str, Any], result: dict[str, Any]) -> None:
    """Validate consumer identities before any canonical/evidence writes."""
    kinds = {"offer_semantic_fields", "visual_source_review", "requirement_assessment", "technical_exception", "contract_exception"}
    kind = task["task_kind"]
    if kind not in kinds:
        return
    from field_extract import CRITICAL_FIELDS
    seen = set()
    returned = set()
    errors = []
    for fact in result.get("facts", []):
        offer_id = fact.get("offer_id") or task.get("offer_id")
        requirement_id = fact.get("requirement_id")
        field = fact.get("field_key")
        identity = (offer_id, requirement_id or field)
        if identity in seen:
            errors.append(f"Duplicate canonical fact identity: {identity}; preserve item details in one normalized list")
        seen.add(identity)
        if requirement_id:
            if field != "requirement_status":
                errors.append(f"Requirement fact must use requirement_status: {field}")
        elif offer_id:
            if field not in CRITICAL_FIELDS:
                errors.append(f"Unknown offer field_key: {field}; canonical fields are {CRITICAL_FIELDS}")
            returned.add(field)
    expected = set(payload.get("fields", [])) if kind == "offer_semantic_fields" else set()
    if kind == "visual_source_review" and task.get("offer_id"):
        expected = set(CRITICAL_FIELDS)
    if expected and returned != expected:
        errors.append(f"Offer field coverage mismatch: missing={sorted(expected-returned)}, unexpected={sorted(returned-expected)}")
    if errors:
        raise ResultValidationError(kind, errors)


from error_log import log_failures


@log_failures('record_results.record_task_result')
def record_task_result(
    run_root: Path,
    task_id: str,
    result: dict[str, Any],
    result_path: str | None = None,
    *,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    response_id: str | None = None,
    input_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> dict[str, Any]:
    from run_compatibility import assert_dispatch
    from question_waits import assert_task_allowed
    assert_task_allowed(run_root, task_id)
    assert_dispatch(run_root, task_id, Path(__file__).resolve().parents[1])
    con = connect(run_root)
    try:
        task = one_as_dict(con, "SELECT * FROM task_queue WHERE task_id=?", [task_id])
        if not task:
            raise ValueError(f"Unknown task_id: {task_id}")
        if task["status"] == "completed":
            return {"task_id": task_id, "status": "already_completed"}
        payload = _json(task.get("payload_json"), {})
        kind = task["task_kind"]
        if kind == "artifact_visual_review":
            _validate_visual_scope(task, result)
            _validate_visual_files(con, run_root, task)
        skill_root = Path(__file__).resolve().parents[1]
        # Receipt completeness is a precondition, not an afterthought. Never
        # mutate canonical state and only then discover that usage/model
        # metadata was missing.
        if not model_name or not reasoning_effort:
            raise ValueError("Successful model task recording requires actual model_name and reasoning_effort receipt metadata")
        if input_tokens is None or output_tokens is None:
            raise ValueError("Successful model task recording requires actual input_tokens and output_tokens")
        if int(input_tokens) < 0 or int(output_tokens) < 0 or (cached_input_tokens is not None and int(cached_input_tokens) < 0):
            raise ValueError("Token receipt values must be non-negative")
        try:
            validation_receipt = validate_result(skill_root, kind, result)
            _validate_fact_contract(task, payload, result)
        except ResultValidationError as exc:
            record_validation(con, task_id, kind, None, exc.errors)
            if hasattr(con, "commit"):
                con.commit()
            raise
        # Start one transaction for validation receipt + canonical writes +
        # model receipt + task completion. Any error rolls all of it back.
        con.execute("BEGIN TRANSACTION")
        record_validation(con, task_id, kind, validation_receipt, [])
        if kind == "document_classification":
            counts = _record_document_classification(con, task, result)
        elif kind == "requirements_extraction":
            counts = _record_requirements(con, task, payload, result)
        elif kind in {"offer_semantic_fields", "requirement_assessment"}:
            counts = _record_facts(con, task, payload, result, "semantic_llm")
        elif kind in {"technical_exception", "contract_exception"}:
            counts = _record_facts(con, task, payload, result, kind)
        elif kind == "visual_source_review":
            counts = _record_facts(con, task, payload, result, "vision")
        elif kind == "independent_fact_review":
            task["payload_json"] = json_text(payload)
            counts = _record_independent_review(con, task, result)
        elif kind == "adjudicate_differences":
            counts = _record_adjudication(con, task, result)
        elif kind == "artifact_visual_review":
            counts = _record_artifact_visual_review(con, task, result, run_root)
        elif kind == "decision_summary":
            counts = _record_decision_summary(con, task, result)
        else:
            raise ValueError(f"Unsupported task_kind: {kind}")
        if kind == "decision_summary":
            con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('decision_summary_task_id',?)", [task_id])
        receipt_id = stable_id("receipt", task_id, str(task.get("attempts", 0) + 1), model_name, response_id or "", length=24)
        con.execute(
            """
            INSERT OR REPLACE INTO model_receipts(
              receipt_id,task_id,model_name,reasoning_effort,response_id,input_tokens,cached_input_tokens,output_tokens,recorded_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [receipt_id, task_id, model_name, reasoning_effort, response_id, int(input_tokens), int(cached_input_tokens or 0), int(output_tokens), utc_now()],
        )
        con.execute(
            "UPDATE task_queue SET status='completed',attempts=attempts+1,result_path=?,completed_at=? WHERE task_id=?",
            [result_path, utc_now(), task_id],
        )
        if hasattr(con, "commit"):
            con.commit()
        return {"task_id": task_id, "status": "completed", **counts}
    except Exception:
        try:
            if hasattr(con, "rollback"):
                con.rollback()
        except Exception:
            pass
        # A rejected visual result leaves the original task and page state untouched.
        if 'kind' in locals() and kind != "artifact_visual_review":
            try:
                con.execute("UPDATE task_queue SET attempts=attempts+1 WHERE task_id=?", [task_id])
                if hasattr(con, "commit"):
                    con.commit()
            except Exception:
                pass
        raise
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate and record one bounded model result")
    ap.add_argument("--run", required=True)
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--model", required=True, help="Actual model identity used for this task")
    ap.add_argument("--effort", required=True, help="Actual reasoning effort used for this task")
    ap.add_argument("--response-id")
    ap.add_argument("--input-tokens", type=int)
    ap.add_argument("--cached-input-tokens", type=int)
    ap.add_argument("--output-tokens", type=int)
    args = ap.parse_args()
    from question_waits import assert_task_allowed
    assert_task_allowed(Path(args.run), args.task_id)
    path = Path(args.input)
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    print(json.dumps(record_task_result(
        Path(args.run), args.task_id, payload, str(path),
        model_name=args.model, reasoning_effort=args.effort, response_id=args.response_id,
        input_tokens=args.input_tokens, cached_input_tokens=args.cached_input_tokens, output_tokens=args.output_tokens,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
