from __future__ import annotations

from question_waits import guard_run_operation

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict


def _num(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    s = str(value).strip().replace(" ", "")
    if not s or s.startswith("="):
        return None
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s or not re.search(r"\d", s):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        tail = s.rsplit(",", 1)[-1]
        s = s.replace(",", "." if len(tail) <= 2 else "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _cell_pos(coord: str) -> tuple[int, int] | None:
    m = re.fullmatch(r"([A-Z]+)(\d+)", str(coord or "").upper())
    if not m:
        return None
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return int(m.group(2)), col


def _fold(value: Any) -> str:
    table = str.maketrans({"ı":"i","İ":"i","ş":"s","Ş":"s","ğ":"g","Ğ":"g","ü":"u","Ü":"u","ö":"o","Ö":"o","ç":"c","Ç":"c"})
    return str(value or "").translate(table).casefold().strip()


def _xlsx_line_total_findings(con) -> list[dict[str, Any]]:
    """Reconcile clearly detected line-total tables to the verified grand total.

    The check intentionally fires only for a strong header signature so a
    workbook with a non-price table is not mistaken for a commercial schedule.
    """
    units = rows_as_dict(
        con,
        """SELECT u.document_id,u.unit_id,u.structured_json,d.offer_id
           FROM document_units u JOIN documents d ON d.document_id=u.document_id
           WHERE u.unit_type='xlsx_sheet' AND d.offer_id IS NOT NULL AND d.active=true""",
    )
    out: list[dict[str, Any]] = []
    for u in units:
        try:
            st = json.loads(u.get("structured_json") or "{}")
        except Exception:
            continue
        grid: dict[tuple[int,int], dict[str, Any]] = {}
        for c in st.get("cells", []):
            pos = _cell_pos(c.get("cell"))
            if pos:
                grid[pos] = c
        rows: dict[int, list[tuple[int, dict[str, Any]]]] = {}
        for (r, cidx), c in grid.items():
            rows.setdefault(r, []).append((cidx, c))
        header_row = None
        total_col = None
        for r, cells in sorted(rows.items()):
            labels = {cidx: _fold(c.get("calculated_value") if c.get("calculated_value") is not None else c.get("formula_or_value")) for cidx, c in cells}
            signals = sum(any(k in txt for k in ["miktar","quantity","qty","birim fiyat","unit price","urun","product","malzeme","item"]) for txt in labels.values())
            candidates = [cidx for cidx, txt in labels.items() if txt in {"tutar","amount","line total","satir toplami","satir toplam","toplam tutar"} or "line total" in txt]
            if signals >= 1 and candidates:
                header_row = r
                total_col = candidates[-1]
                break
        if header_row is None or total_col is None:
            continue
        line_values: list[Decimal] = []
        line_cells: list[str] = []
        for r in sorted(x for x in rows if x > header_row):
            row_texts = []
            for cidx, c in rows[r]:
                val = c.get("calculated_value") if c.get("calculated_value") is not None else c.get("formula_or_value")
                row_texts.append(_fold(val))
            if any(k in " ".join(row_texts) for k in ["genel toplam","grand total","toplam teklif","teklif bedeli"]):
                break
            cell = grid.get((r, total_col))
            if not cell or (cell.get("is_formula") and not cell.get("calculated_available")):
                continue
            val = cell.get("calculated_value") if cell.get("calculated_value") is not None else cell.get("formula_or_value")
            n = _num(val)
            if n is not None:
                line_values.append(n)
                line_cells.append(str(cell.get("cell")))
        if len(line_values) < 2:
            continue
        total_row = con.execute(
            """SELECT f.fact_id,f.value_number,e.document_id FROM facts f
               LEFT JOIN evidence e ON e.evidence_id=f.evidence_id
               WHERE f.offer_id=? AND f.field_key='total' AND f.evidence_status='verified'
               ORDER BY f.updated_at DESC LIMIT 1""",
            [u["offer_id"]],
        ).fetchone()
        if not total_row or total_row[1] is None or total_row[2] != u["document_id"]:
            continue
        line_sum = sum(line_values, Decimal(0))
        grand = Decimal(str(total_row[1]))
        tol = max(Decimal("0.01"), abs(grand) * Decimal("0.05"))
        if abs(line_sum - grand) > tol:
            out.append({
                "offer_id": u["offer_id"], "document_id": u["document_id"], "unit_id": u["unit_id"],
                "fact_id": total_row[0], "line_sum": str(line_sum), "grand_total": str(grand),
                "difference": str(grand-line_sum), "line_cells": line_cells, "line_count": len(line_values),
            })
    return out




def _numbers_in_text(text: Any) -> list[Decimal]:
    out: list[Decimal] = []
    for tok in re.findall(r"[-+]?\d[\d., ]*\d|\d", str(text or "")):
        n = _num(tok)
        if n is not None:
            out.append(n)
    return out


def _xlsx_locator_valid(unit_structured: str | None, locator_json: str | None) -> bool:
    try:
        st = json.loads(unit_structured or "{}")
        loc = json.loads(locator_json or "{}")
    except Exception:
        return False
    cells = {str(c.get("cell") or "").upper() for c in st.get("cells", []) if c.get("cell")}
    if loc.get("sheet") and st.get("title") and str(loc.get("sheet")) != str(st.get("title")):
        return False
    refs: list[str] = []
    if loc.get("cell"):
        refs.append(str(loc["cell"]).upper())
    if loc.get("range"):
        rr = str(loc["range"]).upper().split(":")
        refs.extend([x for x in rr if x])
    # A sheet-only locator is too weak for a verified scalar fact.
    return bool(refs) and all(r in cells for r in refs)

def _add(con, check_id: str, entity_type: str, entity_id: str | None, severity: str, confidence: str, risk: str, remediation: str, evidence: dict[str, Any]) -> str:
    finding_hash = stable_id("h", check_id, entity_type, entity_id or "", json_text(evidence), length=20)
    fid = stable_id("dq", check_id, entity_type, entity_id or "", finding_hash, length=22)
    con.execute(
        """INSERT OR REPLACE INTO data_quality_findings(
             finding_id,check_id,entity_type,entity_id,severity,confidence,status,evidence_json,risk,remediation,finding_hash,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        [fid, check_id, entity_type, entity_id, severity, confidence, "open", json_text(evidence), risk, remediation, finding_hash, utc_now()],
    )
    return fid


@guard_run_operation
def assess(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        con.execute("DELETE FROM data_quality_findings")
        findings: list[dict[str, Any]] = []

        def add(*args, **kwargs):
            fid = _add(con, *args, **kwargs)
            findings.append({"finding_id": fid, "check_id": args[0], "entity_type": args[1], "entity_id": args[2], "severity": args[3], "confidence": args[4], "risk": args[5]})

        # Integrity: every verified fact must have evidence and that evidence must point to a live document hash.
        bad_verified = rows_as_dict(con, """SELECT f.fact_id,f.evidence_id FROM facts f
          LEFT JOIN evidence e ON e.evidence_id=f.evidence_id
          WHERE f.evidence_status='verified' AND (f.evidence_id IS NULL OR e.evidence_id IS NULL)""")
        for r in bad_verified:
            add("verified_fact_without_evidence", "fact", r["fact_id"], "critical", "high",
                "A verified procurement fact cannot be audited to source.", "Attach valid evidence or downgrade the fact status.", r)

        stale_ev = rows_as_dict(con, """SELECT e.evidence_id,e.document_id,e.source_sha256,d.sha256 AS current_sha
          FROM evidence e JOIN documents d ON d.document_id=e.document_id
          WHERE coalesce(e.source_sha256,'')<>coalesce(d.sha256,'')""")
        for r in stale_ev:
            add("evidence_source_hash_mismatch", "evidence", r["evidence_id"], "critical", "high",
                "Evidence was derived from a different source revision.", "Invalidate and re-extract dependent facts from the current source hash.", r)

        # Verified evidence must belong to the same offer/document, resolve to
        # an actual source unit/locator, and numerically support verified scalar
        # facts. These checks also detect canonical-store tampering after ingest.
        verified_links = rows_as_dict(con, """
          SELECT f.fact_id,f.offer_id,f.field_key,f.value_number,f.value_text,f.evidence_id,
                 e.document_id,e.unit_id,e.locator_json,e.quote,e.evidence_status AS ev_status,
                 d.offer_id AS document_offer_id,d.format_family,d.active AS document_active,
                 u.document_id AS unit_document_id,u.unit_type,u.structured_json
          FROM facts f
          JOIN evidence e ON e.evidence_id=f.evidence_id
          JOIN documents d ON d.document_id=e.document_id
          LEFT JOIN document_units u ON u.unit_id=e.unit_id
          WHERE f.evidence_status='verified'
        """)
        for r in verified_links:
            if r.get("offer_id") and r.get("document_offer_id") and r.get("offer_id") != r.get("document_offer_id"):
                add("evidence_offer_mismatch", "fact", r["fact_id"], "critical", "high",
                    "Verified fact is supported by a document owned by another offer.",
                    "Rebind the fact to evidence from the same offer or downgrade it.", r)
            if r.get("unit_id") and r.get("unit_document_id") != r.get("document_id"):
                add("evidence_unit_document_mismatch", "fact", r["fact_id"], "critical", "high",
                    "Evidence unit does not belong to the cited document.",
                    "Resolve the source unit/document relationship before use.", r)
            if r.get("format_family") in {"xlsx","xlsm","xls"} and r.get("unit_type") == "xlsx_sheet":
                if not _xlsx_locator_valid(r.get("structured_json"), r.get("locator_json")):
                    add("invalid_xlsx_evidence_locator", "fact", r["fact_id"], "critical", "high",
                        "Verified spreadsheet fact cites a cell/range that cannot be resolved in the source sheet.",
                        "Use an exact existing source cell/range before marking the fact verified.", r)
            if r.get("value_number") is not None and r.get("field_key") in {"total","quantity","unit_price","price","amount"}:
                target = Decimal(str(r["value_number"]))
                nums = _numbers_in_text(r.get("quote"))
                tol = max(Decimal("0.01"), abs(target) * Decimal("0.0001"))
                if not any(abs(n-target) <= tol for n in nums):
                    add("verified_numeric_quote_mismatch", "fact", r["fact_id"], "critical", "high",
                        "Verified numeric fact is not present in its cited evidence quote.",
                        "Re-extract the value from the exact source locator or downgrade the fact.",
                        {**r, "quote_numbers": [str(x) for x in nums]})

        orphan_offer = rows_as_dict(con, """SELECT o.offer_id,o.supplier_id FROM offers o LEFT JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE s.supplier_id IS NULL""")
        for r in orphan_offer:
            add("orphan_offer_supplier", "offer", r["offer_id"], "critical", "high",
                "Offer has no supplier parent.", "Repair supplier identity before comparison.", r)

        # Uniqueness/grain: one current fact per offer+field and per offer+requirement is expected.
        dup_fields = rows_as_dict(con, """SELECT offer_id,field_key,count(*) AS n FROM facts
          WHERE offer_id IS NOT NULL AND requirement_id IS NULL GROUP BY offer_id,field_key HAVING count(*)>1""")
        for r in dup_fields:
            add("duplicate_offer_field_grain", "offer_field", f"{r['offer_id']}:{r['field_key']}", "high", "high",
                "Multiple facts occupy the same offer/field grain.", "Resolve to one canonical fact before costing or scoring.", r)
        dup_req = rows_as_dict(con, """SELECT offer_id,requirement_id,count(*) AS n FROM facts
          WHERE offer_id IS NOT NULL AND requirement_id IS NOT NULL GROUP BY offer_id,requirement_id HAVING count(*)>1""")
        for r in dup_req:
            add("duplicate_requirement_grain", "requirement_assessment", f"{r['offer_id']}:{r['requirement_id']}", "high", "high",
                "Multiple assessments occupy the same offer/requirement grain.", "Resolve duplicate assessments before compliance conclusions.", r)

        # Validity/domain checks with conservative rules only.
        bad_total = rows_as_dict(con, "SELECT fact_id,value_number FROM facts WHERE field_key='total' AND value_number IS NOT NULL AND value_number<0")
        for r in bad_total:
            add("negative_offer_total", "fact", r["fact_id"], "high", "high", "Negative quoted total is implausible for normal procurement costing.", "Confirm sign/unit or source extraction.", r)
        bad_qty = rows_as_dict(con, "SELECT fact_id,value_number FROM facts WHERE field_key='quantity' AND value_number IS NOT NULL AND value_number<=0")
        for r in bad_qty:
            add("nonpositive_quantity", "fact", r["fact_id"], "medium", "high", "Quantity is non-positive and may break scope comparability.", "Confirm quantity and unit.", r)

        for r in _xlsx_line_total_findings(con):
            add(
                "line_total_grand_total_mismatch", "offer", r["offer_id"], "critical", "high",
                "A clearly detected commercial line-total table does not reconcile to the verified grand total.",
                "Confirm exclusions/add-ons or correct the total before comparison; never rank on an unexplained mismatch.", r,
            )

        # Source authority is a prerequisite for final use of critical formal sources.
        auth = rows_as_dict(con, "SELECT document_id,authority_scope,authority_status,rationale FROM source_authority WHERE authority_status IN ('needs_input','unusable')")
        for r in auth:
            sev = "critical" if r["authority_scope"] in {"requirements", "supplier_commitment"} else "high"
            add("source_authority_unresolved", "document", r["document_id"], sev, "high",
                "Controlling source is unresolved or unusable.", "Resolve source/revision authority before final decision.", r)

        # Completeness: track critical facts, but leave commercial sufficiency to decision_gate.
        incomplete = rows_as_dict(con, "SELECT fact_id,offer_id,field_key,evidence_status FROM facts WHERE critical=true AND evidence_status IN ('missing','unreadable','conflicting','requires_confirmation')")
        for r in incomplete:
            add("critical_fact_incomplete", "fact", r["fact_id"], "high", "high",
                "Critical fact is incomplete or conflicting.", "Resolve with source evidence or RFI; do not coerce missing to zero.", r)

        # Source shape indicators from adapters: hidden spreadsheet content and partial parsing require visibility.
        docs = rows_as_dict(con, "SELECT document_id,format_family,parse_status,parse_notes FROM documents WHERE active=true")
        for r in docs:
            notes = str(r.get("parse_notes") or "")
            if "Hidden content detected" in notes:
                add("hidden_spreadsheet_content", "document", r["document_id"], "medium", "high",
                    "Source workbook contains hidden rows, columns or sheets that can hold overrides/exclusions.", "Inspect hidden content mechanically and include material items in evidence.", {"parse_notes": notes})
            if r.get("parse_status") == "partial":
                add("partial_source_parse", "document", r["document_id"], "medium", "high",
                    "Source was only partially parsed.", "Use the targeted visual/semantic fallback for unresolved regions.", {"format_family": r.get("format_family"), "parse_notes": notes})

        by_severity = {s: 0 for s in ["critical", "high", "medium", "low"]}
        for x in findings:
            by_severity[x["severity"]] = by_severity.get(x["severity"], 0) + 1
        result = {"status": "PASS" if by_severity.get("critical",0)==0 else "FAIL", "finding_count": len(findings), "by_severity": by_severity, "findings": findings}
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('data_quality',?)", [json_text(result)])
        if hasattr(con, "commit"):
            con.commit()
        return result
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Procurement canonical-store data-quality gate")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(assess(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
