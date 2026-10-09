"""Explicit, auditable review of one previously failed PDF page."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from common import json_text, sha256_file, stable_id, utc_now
from db import connect, one_as_dict, rows_as_dict


def _page(payload: dict, key: str) -> dict:
    pages = payload.get("pages") or []
    matches = [p for p in pages if p.get("render_key") == key]
    if len(matches) != 1:
        raise ValueError("Page is absent or duplicated in task payload")
    return matches[0]


def _current(con, run_root: Path, artifact_id: str, key: str, expected_artifact: str, expected_render: str) -> dict:
    artifact = one_as_dict(con, "SELECT * FROM artifacts WHERE artifact_id=? AND artifact_type='pdf' AND status='ready'", [artifact_id])
    if not artifact or artifact["sha256"] != expected_artifact:
        raise ValueError("Artifact identity/hash changed")
    path = run_root / artifact["relative_path"]
    if not path.is_file() or sha256_file(path) != expected_artifact:
        raise ValueError("PDF file/hash changed")
    render = one_as_dict(con, "SELECT * FROM render_hashes WHERE artifact_id=? AND render_key=?", [artifact_id, key])
    if not render or render["render_sha256"] != expected_render:
        raise ValueError("Page render hash changed")
    return artifact


def _recheck_images(payload: dict, row: dict) -> None:
    if payload.get("artifact_id") != row["artifact_id"] or payload.get("artifact_sha256") != row["artifact_sha256"]:
        raise ValueError("Recheck artifact payload changed")
    page = _page(payload, row["render_key"])
    if len(payload.get("pages") or []) != 1 or page.get("sha256") != row["render_sha256"]:
        raise ValueError("Recheck page payload changed")
    image = Path(page["image_path"])
    if not image.is_file() or sha256_file(image) != row["render_sha256"]:
        raise ValueError("Recheck page image/hash changed")
    for extra in payload.get("supplementary_images", []):
        image = Path(extra["path"])
        if not image.is_file() or sha256_file(image) != extra["sha256"]:
            raise ValueError("Recheck supplementary image/hash changed")


def create_recheck(run_root: Path, previous_task_id: str, finding_id: str, render_key: str, reason: str,
                   supplementary_images: list[Path] | None = None) -> dict:
    from run_compatibility import assert_compatible
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    reason = reason.strip()
    if len(reason) < 12:
        raise ValueError("Concrete recheck reason is required")
    con = connect(run_root)
    try:
        previous = one_as_dict(con, "SELECT * FROM task_queue WHERE task_id=? AND task_kind='artifact_visual_review' AND status='completed'", [previous_task_id])
        if not previous:
            raise ValueError("Previous completed visual task not found")
        payload = json.loads(previous["payload_json"])
        if payload.get("recheck_id"):
            raise ValueError("Recheck must cite the original completed task")
        page = _page(payload, render_key)
        artifact_id, render_sha = payload["artifact_id"], page["sha256"]
        finding = one_as_dict(con, "SELECT * FROM qa_findings WHERE finding_id=? AND artifact_id=? AND finding_type='visual_layout' AND status IN ('open','superseded')", [finding_id, artifact_id])
        if not finding or json.loads(finding["locator_json"] or "{}").get("render_key") != render_key:
            raise ValueError("Open visual finding does not match the selected page")
        prior_receipt = one_as_dict(con, "SELECT receipt_id FROM model_receipts WHERE task_id=? ORDER BY recorded_at DESC", [previous_task_id])
        if not prior_receipt:
            raise ValueError("Previous review has no model receipt")
        artifact = one_as_dict(con, "SELECT * FROM artifacts WHERE artifact_id=?", [artifact_id])
        if not artifact:
            raise ValueError("Artifact missing")
        _current(con, run_root, artifact_id, render_key, artifact["sha256"], render_sha)
        image = Path(page["image_path"])
        if not image.is_file() or sha256_file(image) != render_sha:
            raise ValueError("Page image/hash changed")
        extras = []
        for extra in supplementary_images or []:
            image_path = Path(extra).resolve()
            if not image_path.is_file():
                raise ValueError("Supplementary image missing")
            extras.append({"path": str(image_path), "sha256": sha256_file(image_path)})
        recheck_id = stable_id("vrc", previous_task_id, finding_id, render_key, reason, json_text(extras), length=24)
        task_id = stable_id("task", "visual_recheck", recheck_id, length=24)
        existing = one_as_dict(con, "SELECT * FROM visual_rechecks WHERE recheck_id=?", [recheck_id])
        if existing:
            return {"recheck_id": recheck_id, "task_id": task_id, "status": "already_created"}
        render = one_as_dict(con, "SELECT qa_status FROM render_hashes WHERE artifact_id=? AND render_key=?", [artifact_id, render_key])
        if finding["status"] != "open" or render["qa_status"] != "fail":
            raise ValueError("Page has no current open failed review")
        new_payload = {"artifact_id": artifact_id, "artifact_path": str((run_root / artifact["relative_path"]).resolve()),
                       "pages": [page], "goal": payload.get("goal"), "recheck_id": recheck_id,
                       "previous_task_id": previous_task_id, "finding_id": finding_id,
                       "artifact_sha256": artifact["sha256"], "reason": reason,
                       "supplementary_images": extras}
        con.execute("BEGIN TRANSACTION")
        con.execute("INSERT INTO visual_rechecks(recheck_id,task_id,previous_task_id,previous_task_payload_hash,previous_receipt_id,finding_id,finding_hash,artifact_id,artifact_sha256,render_key,render_sha256,reason,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [recheck_id, task_id, previous_task_id, hashlib.sha256(previous["payload_json"].encode()).hexdigest(), prior_receipt["receipt_id"], finding_id, finding["finding_hash"], artifact_id, artifact["sha256"], render_key, render_sha, reason, utc_now()])
        con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    [task_id, "QA", "visual_exception", "artifact_visual_review", json_text(new_payload), 80, True, "pending", 0, utc_now()])
        con.commit()
        return {"recheck_id": recheck_id, "task_id": task_id, "status": "pending"}
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def adopt_recheck(run_root: Path, recheck_id: str, reason: str) -> dict:
    from run_compatibility import assert_dispatch
    reason = reason.strip()
    if len(reason) < 12:
        raise ValueError("Concrete adoption reason is required")
    con = connect(run_root)
    try:
        row = one_as_dict(con, "SELECT * FROM visual_rechecks WHERE recheck_id=?", [recheck_id])
        if not row:
            raise ValueError("Unknown recheck")
        assert_dispatch(run_root, row["task_id"], Path(__file__).resolve().parents[1])
        _current(con, run_root, row["artifact_id"], row["render_key"], row["artifact_sha256"], row["render_sha256"])
        if row["adopted_at"]:
            return {"recheck_id": recheck_id, "status": "already_adopted"}
        previous = one_as_dict(con, "SELECT status,payload_json FROM task_queue WHERE task_id=?", [row["previous_task_id"]])
        if not previous or previous["status"] != "completed" or hashlib.sha256(previous["payload_json"].encode()).hexdigest() != row["previous_task_payload_hash"]:
            raise ValueError("Previous task changed")
        if not one_as_dict(con, "SELECT receipt_id FROM model_receipts WHERE receipt_id=? AND task_id=?", [row["previous_receipt_id"], row["previous_task_id"]]):
            raise ValueError("Previous model receipt changed")
        task = one_as_dict(con, "SELECT status,payload_json FROM task_queue WHERE task_id=?", [row["task_id"]])
        if not task or task["status"] != "completed" or row["result_status"] != "pass" or not row["result_sha256"]:
            raise ValueError("Completed PASS recheck is required")
        _recheck_images(json.loads(task["payload_json"]), row)
        if not one_as_dict(con, "SELECT receipt_id FROM model_receipts WHERE task_id=?", [row["task_id"]]):
            raise ValueError("Recheck has no model receipt")
        finding = one_as_dict(con, "SELECT * FROM qa_findings WHERE finding_id=? AND artifact_id=? AND status='open' AND finding_type='visual_layout'", [row["finding_id"], row["artifact_id"]])
        if not finding or finding["finding_hash"] != row["finding_hash"] or json.loads(finding["locator_json"] or "{}").get("render_key") != row["render_key"]:
            raise ValueError("Target finding is no longer open for this page")
        render = one_as_dict(con, "SELECT qa_status FROM render_hashes WHERE artifact_id=? AND render_key=?", [row["artifact_id"], row["render_key"]])
        if render["qa_status"] != "fail":
            raise ValueError("Original failed page state changed")
        other_open = any(json.loads(other["locator_json"] or "{}").get("render_key") == row["render_key"]
                         for other in rows_as_dict(con, "SELECT locator_json FROM qa_findings WHERE artifact_id=? AND finding_type='visual_layout' AND status='open' AND finding_id<>?", [row["artifact_id"], row["finding_id"]]))
        con.execute("BEGIN TRANSACTION")
        con.execute("INSERT INTO qa_finding_supersessions(finding_id,previous_artifact_id,replacement_artifact_id,replacement_sha256,render_hashes_json,superseded_at) VALUES (?,?,?,?,?,?)",
                    [row["finding_id"], row["artifact_id"], row["artifact_id"], row["artifact_sha256"], json_text({row["render_key"]: row["render_sha256"], "recheck_id": recheck_id, "previous_task_id": row["previous_task_id"], "reason": reason}), utc_now()])
        con.execute("UPDATE qa_findings SET status='superseded' WHERE finding_id=?", [row["finding_id"]])
        if not other_open:
            con.execute("UPDATE render_hashes SET qa_status='pass',qa_note=? WHERE artifact_id=? AND render_key=?", [f"Adopted recheck {recheck_id}: {reason}", row["artifact_id"], row["render_key"]])
        con.execute("UPDATE visual_rechecks SET adopted_reason=?,adopted_at=? WHERE recheck_id=?", [reason, utc_now(), recheck_id])
        con.commit()
        return {"recheck_id": recheck_id, "finding_id": row["finding_id"], "status": "adopted"}
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="action", required=True)
    create = sub.add_parser("create")
    create.add_argument("--run", required=True); create.add_argument("--previous-task-id", required=True)
    create.add_argument("--finding-id", required=True); create.add_argument("--render-key", required=True); create.add_argument("--reason", required=True)
    create.add_argument("--supplementary-image", action="append", default=[], type=Path)
    adopt = sub.add_parser("adopt")
    adopt.add_argument("--run", required=True); adopt.add_argument("--recheck-id", required=True); adopt.add_argument("--reason", required=True)
    args = ap.parse_args()
    result = create_recheck(Path(args.run), args.previous_task_id, args.finding_id, args.render_key, args.reason, args.supplementary_image) if args.action == "create" else adopt_recheck(Path(args.run), args.recheck_id, args.reason)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
