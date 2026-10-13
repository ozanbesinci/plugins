from __future__ import annotations

from question_waits import guard_run_operation

import argparse
import difflib
import json
from pathlib import Path
from typing import Any

from common import clean_text, json_text, stable_id, utc_now
from db import connect, rows_as_dict
from adapters.pdf_adapter import duckdb_pdf_secondary


def _row_page_text(row: dict[str, Any]) -> tuple[int | None, str]:
    page = None
    text = ""
    for key in ["page", "page_number", "pageno", "page_no"]:
        if key in row and row[key] is not None:
            try:
                page = int(row[key])
                if page == 0:
                    page = 1
            except Exception:
                pass
            break
    for key in ["text", "content", "page_text"]:
        if key in row and row[key] is not None:
            text = str(row[key])
            break
    return page, text


@guard_run_operation
def review_pdf(run_root: Path, document: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(document["source_path"])
    result = duckdb_pdf_secondary(source_path)
    if not result.get("available"):
        return {"document_id": document["document_id"], "available": False, "reason": result.get("reason")}
    secondary: dict[int, str] = {}
    for row in result.get("rows", []):
        page, text = _row_page_text(row)
        if page is not None:
            secondary[page] = text
    con = connect(run_root)
    mismatches = []
    try:
        primary_rows = rows_as_dict(
            con,
            "SELECT unit_index,text_content FROM document_units WHERE document_id=? AND unit_type='pdf_page' ORDER BY unit_index",
            [document["document_id"]],
        )
        critical_pages: set[int] = set()
        ev_rows = rows_as_dict(
            con,
            """
            SELECT e.locator_json FROM evidence e
            JOIN facts f ON f.evidence_id=e.evidence_id
            WHERE e.document_id=? AND f.critical=true
            """,
            [document["document_id"]],
        )
        for ev in ev_rows:
            try:
                loc = json.loads(ev["locator_json"] or "{}")
                if loc.get("page") is not None:
                    critical_pages.add(int(loc["page"]))
            except Exception:
                pass
        matched_pages = []
        for p in primary_rows:
            page = int(p["unit_index"])
            a = clean_text(p.get("text_content") or "")
            b = clean_text(secondary.get(page, ""))
            if not b:
                continue
            ratio = difflib.SequenceMatcher(None, a[:20000], b[:20000]).ratio() if a or b else 1.0
            if ratio < 0.9:
                mismatches.append({"page": page, "similarity": round(ratio, 4), "critical": page in critical_pages})
            else:
                matched_pages.append({"page": page, "similarity": round(ratio, 4)})
        for mm in mismatches:
            fid = stable_id("qa", document["document_id"], "secondary_pdf", str(mm["page"]), length=22)
            con.execute(
                "INSERT OR REPLACE INTO qa_findings(finding_id,artifact_id,finding_type,locator_json,severity,status,message,finding_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                [fid, None, "secondary_pdf_difference", json_text({"document_id": document["document_id"], "page": mm["page"]}), "critical" if mm["critical"] else "medium", "open", f"Primary and DuckDB PDF extraction differ on page {mm['page']} (similarity={mm['similarity']}).", stable_id("h", str(mm), length=20), utc_now()],
            )
            if mm["critical"]:
                task_id = stable_id("task", "secondary_pdf", document["document_id"], str(mm["page"]), length=24)
                payload = {"document_id": document["document_id"], "needs_visual_pages": [mm["page"]], "goal": "Resolve a critical parser disagreement on this page using the original page image."}
                con.execute(
                    """
                    INSERT OR IGNORE INTO task_queue(task_id,phase,role,task_kind,document_id,payload_json,priority,critical,status,attempts,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    [task_id, "REVIEW", "visual_exception", "visual_source_review", document["document_id"], json_text(payload), 15, True, "pending", 0, utc_now()],
                )
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    return {"document_id": document["document_id"], "available": True, "secondary_pages": len(secondary), "matched_pages": matched_pages, "mismatches": mismatches}


@guard_run_operation
def run(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        docs = rows_as_dict(con, "SELECT document_id,source_path,filename FROM documents WHERE active=true AND format_family='pdf' AND parse_status <> 'unreadable'")
    finally:
        con.close()
    results = [review_pdf(run_root, d) for d in docs]
    return {"documents": len(results), "results": results}


def main() -> None:
    ap = argparse.ArgumentParser(description="Optional DuckDB PDF secondary extraction check")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(run(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
