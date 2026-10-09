from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict


def _fact_projection(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "fact_id": row.get("fact_id"),
        "value_text": row.get("value_text"),
        "value_number": row.get("value_number"),
        "value_date": row.get("value_date"),
        "evidence_status": row.get("evidence_status"),
        "evidence_id": row.get("evidence_id"),
        "critical": bool(row.get("critical", False)),
        "offer_id": row.get("offer_id"),
        "supplier_id": row.get("supplier_id"),
        "field_key": row.get("field_key"),
        "requirement_id": row.get("requirement_id"),
        "unit": row.get("unit"),
        "currency": row.get("currency"),
    }


def _same(a: dict[str, Any], b: dict[str, Any]) -> bool:
    keys = ["value_text", "value_number", "value_date", "evidence_status"]
    return all(a.get(k) == b.get(k) for k in keys)


def compare(run_root: Path, review_id: str, generation: int = 1, chunk_size: int = 25) -> dict[str, Any]:
    con = connect(run_root)
    created = 0
    matched = 0
    task_ids: list[str] = []
    try:
        main_rows = rows_as_dict(con, "SELECT * FROM facts")
        main = {r["fact_id"]: r for r in main_rows}
        rev_rows = rows_as_dict(con, "SELECT * FROM review_facts WHERE review_id=?", [review_id])
        review = {r["fact_id"]: r for r in rev_rows}
        new_diff_ids: list[str] = []
        for fact_id in sorted(review):
            a = main.get(fact_id)
            b = review.get(fact_id)
            if a is not None and b is not None and _same(a, b):
                matched += 1
                continue
            if a is None or b is None:
                dtype = "missing_side"
            else:
                dtype = "value_or_status"
            diff_id = f"diff_{review_id}_{stable_id('d', fact_id, length=12)}"
            critical = bool((a or {}).get("critical", False))
            con.execute(
                """
                INSERT OR REPLACE INTO differences(difference_id,review_id,fact_id,difference_type,main_json,independent_json,critical,status,generation)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                [diff_id, review_id, fact_id, dtype, json_text(_fact_projection(a)), json_text(_fact_projection(b)), critical, "open", generation],
            )
            new_diff_ids.append(diff_id)
            created += 1

        # Create bounded adjudication tasks only for current open deltas.
        for i in range(0, len(new_diff_ids), chunk_size):
            chunk = new_diff_ids[i : i + chunk_size]
            if not chunk:
                continue
            payload = {"review_id": review_id, "difference_ids": chunk, "goal": "Resolve only listed differences from original evidence. Do not revisit unchanged facts."}
            task_id = stable_id("task", "ADJUDICATE", review_id, str(generation), json_text(chunk), length=24)
            con.execute(
                """
                INSERT OR IGNORE INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                [task_id, "ADJUDICATE", "adjudicator", "adjudicate_differences", json_text(payload), 40, True, "pending", 0, utc_now()],
            )
            task_ids.append(task_id)
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    return {"review_id": review_id, "matched": matched, "differences": created, "adjudication_tasks": task_ids}


def main() -> None:
    ap = argparse.ArgumentParser(description="Compare canonical facts to one independent review")
    ap.add_argument("--run", required=True)
    ap.add_argument("--review-id", required=True)
    ap.add_argument("--generation", type=int, default=1)
    args = ap.parse_args()
    print(json.dumps(compare(Path(args.run), args.review_id, args.generation), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
