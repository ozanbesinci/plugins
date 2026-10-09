from __future__ import annotations

import json

from db import rows_as_dict


def current_calculations(con, columns='*'):
    """Current decision universe: active offers and run-wide calculations.

    Linked support/superseded history remains stored, but cannot enter a current
    cost, score, bridge or snapshot. Missing owners are integrity errors.
    """
    orphan = con.execute('SELECT calculation_id FROM calculations c WHERE c.offer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM offers o WHERE o.offer_id=c.offer_id) LIMIT 1').fetchone()
    if orphan:
        raise ValueError('Orphan calculation has no offer owner')
    rows = rows_as_dict(con, f"SELECT {columns} FROM calculations WHERE offer_id IS NULL OR EXISTS (SELECT 1 FROM offers o WHERE o.offer_id=calculations.offer_id AND o.status='active') ORDER BY updated_at DESC,calculation_id DESC")
    current = {}
    for row in rows:
        current.setdefault((row.get('offer_id'), row['calculation_type']), row)
    return sorted(current.values(), key=lambda r: (r['calculation_type'], r.get('offer_id') or '', r['calculation_id']))


def current_artifacts(con):
    rows = rows_as_dict(con, "SELECT * FROM artifacts WHERE status='ready' ORDER BY created_at DESC,artifact_id DESC")
    current = {}
    for row in rows:
        current.setdefault(row['artifact_type'], row)
    return current

def current_claims(con, columns="*"):
    """Exclude only completed ancestors explicitly replaced by this summary."""
    active = con.execute("SELECT value FROM run_meta WHERE key='decision_summary_task_id'").fetchone()
    if not active:
        return rows_as_dict(con, f"SELECT {columns} FROM claims ORDER BY claim_id")
    task_id = active[0]
    seen, superseded = set(), []
    while True:
        if task_id in seen:
            raise ValueError("Active decision summary task pointer has a cycle")
        seen.add(task_id)
        task = con.execute("SELECT task_kind,status,payload_json FROM task_queue WHERE task_id=?", [task_id]).fetchone()
        if not task or task[:2] != ("decision_summary", "completed"):
            raise ValueError("Active decision summary task pointer is invalid")
        payload = json.loads(task[2])
        parent = payload.get("retry_parent_task_id")
        if not parent:
            break
        if not isinstance(parent, str):
            raise ValueError("Active decision summary task pointer has an invalid parent")
        superseded.append(parent)
        task_id = parent
    if not superseded:
        return rows_as_dict(con, f"SELECT {columns} FROM claims ORDER BY claim_id")
    placeholders = ",".join("?" for _ in superseded)
    return rows_as_dict(con, f"SELECT {columns} FROM claims WHERE source_task_id IS NULL OR source_task_id NOT IN ({placeholders}) ORDER BY claim_id", superseded)
