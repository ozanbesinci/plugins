from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict, set_state


def _fold(text: str) -> str:
    table = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})
    return text.translate(table).casefold()


def vat_basis(text: str | None) -> str | None:
    if not text:
        return None
    value = re.sub(r"\s+", " ", _fold(text).strip().strip(".:;"))
    aliases = {
        "included": {"included", "dahil", "include", "inclusive"},
        # Preserve these two established complete aliases. Other negated forms
        # remain unresolved instead of being inferred by inverse polarity.
        "excluded": {"excluded", "haric", "exclude", "exclusive", "not included", "dahil degil"},
    }
    value_without_label = re.sub(r"^(kdv|vat)\s*[:=]?\s*", "", value)
    for basis, terms in aliases.items():
        if value in terms or value_without_label in terms:
            return basis
    # Do not infer a basis from other negated or qualified phrases (for example
    # "hariç değil", "excluded not" or "dahil değildir").
    if re.search(r"\b(?:not|no|degil|degildir)\b", value):
        return None

    # Only accept a basis adjacent to an explicit percentage and optional VAT
    # label. Anchoring the full phrase prevents incidental words or mixed terms
    # from being treated as a known basis.
    label = r"(?:kdv|vat)"
    rate = r"(?:%\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*%)"
    sep = r"[\s:;()]*"
    for canonical, terms in aliases.items():
        basis = "(?:" + "|".join(re.escape(term) for term in sorted(terms)) + ")"
        patterns = (
            rf"^{label}{sep}{rate}{sep}{basis}$",
            rf"^{rate}{sep}{label}{sep}{basis}$",
            rf"^{label}{sep}{basis}{sep}{rate}$",
            rf"^{basis}{sep}{rate}{sep}{label}$",
            rf"^{rate}{sep}{basis}{sep}{label}$",
            rf"^{basis}{sep}{label}{sep}{rate}$",
            rf"^{rate}{sep}{basis}$",
            rf"^{basis}{sep}{rate}$",
        )
        if any(re.fullmatch(pattern, value) for pattern in patterns):
            return canonical
    return None


def _duration_days(text: str | None) -> int | None:
    if not text:
        return None
    f = _fold(text)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(gun|day|days|hafta|week|weeks|ay|month|months|yil|year|years)", f)
    if not m:
        return None
    n = float(m.group(1).replace(",", "."))
    unit = m.group(2)
    if unit in {"gun", "day", "days"}:
        return round(n)
    if unit in {"hafta", "week", "weeks"}:
        return round(n * 7)
    if unit in {"ay", "month", "months"}:
        return round(n * 30)
    if unit in {"yil", "year", "years"}:
        return round(n * 365)
    return None



def _payment_schedule(text: str | None, delivery_days: int | None) -> list[dict[str, Any]] | None:
    if not text:
        return None
    f = _fold(text)
    # Common simple cases first.
    if any(k in f for k in ["pesin", "cash", "100% advance", "%100 advance"]) and not re.search(r"%\s*\d+", f):
        return [{"ratio": 1.0, "days": 0}]
    if any(k in f for k in ["teslimde", "on delivery", "at delivery"]) and not re.search(r"%\s*\d+", f) and delivery_days is not None:
        return [{"ratio": 1.0, "days": int(delivery_days)}]
    parts = re.split(r"[,;+]", f)
    rows: list[dict[str, Any]] = []
    for part in parts:
        m = re.search(r"%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%", part)
        if not m:
            continue
        raw = m.group(1) or m.group(2)
        ratio = float(raw.replace(",", ".")) / 100.0
        days = None
        if any(k in part for k in ["pesin", "avans", "advance", "siparis", "order"]):
            days = 0
        else:
            dm = re.search(r"(\d+)\s*(gun|day|days)", part)
            if dm:
                days = int(dm.group(1))
                # "60 days after delivery" is not day 60 from order date.
                # Add the normalized delivery lead time when the phrase is
                # explicitly delivery-relative.
                if any(k in part for k in ["teslimden", "teslim sonrasi", "teslim sonrası", "after delivery"]):
                    if delivery_days is None:
                        return None
                    days += int(delivery_days)
            elif any(k in part for k in ["teslim", "delivery"]) and delivery_days is not None:
                days = int(delivery_days)
        if days is None:
            return None
        rows.append({"ratio": ratio, "days": days})
    if rows and abs(sum(r["ratio"] for r in rows) - 1.0) <= 0.001:
        return rows
    return None


def _upsert_issue(con, owner: str, severity: str, issue_type: str, question: str, fact_ids: list[str] | None = None) -> str:
    issue_id = stable_id("issue", owner, issue_type, question, length=22)
    con.execute(
        """
        INSERT OR REPLACE INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [issue_id, owner, severity, issue_type, question, json_text(fact_ids or []), "[]", "open", utc_now()],
    )
    return issue_id


def normalize(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    derived = 0
    revision_updates = 0
    issues = 0
    try:
        offers = rows_as_dict(con, "SELECT offer_id,supplier_id,revision_label,status FROM offers ORDER BY supplier_id,offer_id")
        for offer in offers:
            offer_id = offer["offer_id"]
            quote = con.execute("SELECT value_date FROM facts WHERE offer_id=? AND field_key='quote_date'", [offer_id]).fetchone()
            validity = con.execute("SELECT value_text,value_date FROM facts WHERE offer_id=? AND field_key='validity'", [offer_id]).fetchone()
            quote_date = quote[0] if quote and quote[0] else None
            validity_end = validity[1] if validity and validity[1] else None
            if not validity_end and quote_date and validity and validity[0]:
                days = _duration_days(validity[0])
                if days is not None:
                    validity_end = (date.fromisoformat(str(quote_date)) + timedelta(days=days)).isoformat()
                    derived += 1
            con.execute("UPDATE offers SET quote_date=?, validity_end=? WHERE offer_id=?", [quote_date, validity_end, offer_id])

            vat = con.execute("SELECT fact_id,value_text,normalized_json FROM facts WHERE offer_id=? AND field_key='vat'", [offer_id]).fetchone()
            if vat:
                try:
                    vobj = json.loads(vat[2] or "{}")
                except Exception:
                    vobj = {}
                basis = vat_basis(vat[1])
                if basis:
                    vobj["vat_basis"] = basis
                else:
                    vobj.pop("vat_basis", None)
                con.execute("UPDATE facts SET normalized_json=?,updated_at=? WHERE fact_id=?", [json_text(vobj), utc_now(), vat[0]])

            delivery_days = None
            for field, normalized_key in [("delivery", "days"), ("warranty", "months")]:
                row = con.execute("SELECT fact_id,value_text,normalized_json FROM facts WHERE offer_id=? AND field_key=?", [offer_id, field]).fetchone()
                if not row or not row[1]:
                    continue
                days = _duration_days(row[1])
                if days is None:
                    continue
                value = round(days / 30) if field == "warranty" else days
                if field == "delivery":
                    delivery_days = days
                try:
                    obj = json.loads(row[2] or "{}")
                except Exception:
                    obj = {}
                obj[normalized_key] = value
                con.execute("UPDATE facts SET normalized_json=?,updated_at=? WHERE fact_id=?", [json_text(obj), utc_now(), row[0]])
                derived += 1

            payment = con.execute("SELECT fact_id,value_text,normalized_json FROM facts WHERE offer_id=? AND field_key='payment'", [offer_id]).fetchone()
            if payment and payment[1]:
                try:
                    pobj = json.loads(payment[2] or "{}")
                except Exception:
                    pobj = {}
                if not isinstance(pobj.get("payment_schedule"), list):
                    schedule = _payment_schedule(payment[1], delivery_days)
                    if schedule:
                        pobj["payment_schedule"] = schedule
                        con.execute("UPDATE facts SET normalized_json=?,updated_at=? WHERE fact_id=?", [json_text(pobj), utc_now(), payment[0]])
                        derived += 1

        # Revision precedence is never inferred from filename/date alone.
        # Only an explicitly marked current source may supersede another offer.
        suppliers = rows_as_dict(con, "SELECT supplier_id FROM suppliers ORDER BY supplier_id")
        for supplier in suppliers:
            rows = rows_as_dict(
                con,
                """SELECT o.offer_id,o.revision_label,o.quote_date,o.status,
                          max(CASE WHEN d.revision_status='current' THEN 1 ELSE 0 END) AS explicit_current
                   FROM offers o LEFT JOIN documents d ON d.offer_id=o.offer_id AND d.active=true
                   WHERE o.supplier_id=? AND o.status='active'
                   GROUP BY o.offer_id,o.revision_label,o.quote_date,o.status
                   ORDER BY o.offer_id""",
                [supplier["supplier_id"]],
            )
            if len(rows) <= 1:
                continue
            q = f"Confirm the relationship between independent offers/revisions for supplier {supplier['supplier_id']}; a current document does not supersede unrelated offers."
            _upsert_issue(con, f"FIRMA:{supplier['supplier_id']}", "critical", "revision_relation", q, [])
            issues += 1

        # Mark low-confidence supplier identification for review.
        docs = rows_as_dict(con, "SELECT document_id,supplier_id,metadata_json,filename FROM documents WHERE active=true AND document_role='offer'")
        for d in docs:
            try:
                meta = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                meta = {}
            # Metadata from parser does not carry supplier confidence in old runs; use filename-derived identity as provisional.
            if d.get("supplier_id"):
                status = con.execute("SELECT identification_status FROM suppliers WHERE supplier_id=?", [d["supplier_id"]]).fetchone()
                if status and status[0] == "provisional":
                    q = f"Confirm supplier identity for offer document {d['filename']}."
                    _upsert_issue(con, f"FIRMA:{d['supplier_id']}", "medium", "supplier_identity", q, [])
                    issues += 1

        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    detail = {"derived_values": derived, "superseded_offers": revision_updates, "issues_created": issues}
    set_state(run_root, "NORMALIZE", "PASS", detail)
    return detail


def main() -> None:
    ap = argparse.ArgumentParser(description="Normalize canonical procurement data")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(normalize(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
