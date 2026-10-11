from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import json_text, sha256_file, stable_id, utc_now
from active_records import current_calculations, current_claims
from db import connect, get_meta, get_state, rows_as_dict
from llm_result_validate import result_hash
from reviewed_snapshot import load_latest


from error_log import log_failures


@log_failures('validate_run.validate')
def validate(run_root: Path) -> dict[str, Any]:
    from run_compatibility import assert_compatible
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    if any(s.get('phase')=='COMPLETE' and s.get('status') in {'PASS','PARTIAL'} for s in get_state(run_root)):
        from closure_integrity import inspect_closure
        errors=inspect_closure(run_root)
        if errors:
            return {'status':'BLOCKED','blocking_reasons':errors,'preserved_completed_run':True}
        # Revalidation of a sealed run is read-only, including validated_at.
        return json.loads((run_root/'output/verification.json').read_text(encoding='utf-8'))
    profile = str(get_meta(run_root, "profile", "standart"))
    suff_raw = get_meta(run_root, "decision_sufficiency", "{}")
    try:
        suff = json.loads(suff_raw)
    except Exception:
        suff = {}
    con = connect(run_root)
    blocking: list[str] = []
    from official_delivery import inspect_official
    official = inspect_official(run_root)
    if official["delivery_status"] == "FAILED":
        blocking.append("Official paired delivery failed: " + official["error"])
    preliminary: list[str] = []
    from user_question_gate import waiting as user_input_waiting
    wait = user_input_waiting(run_root)
    if wait:
        blocking.append(f"{wait['open_question_count']} critical business questions remain open")
    parent_answer = get_meta(run_root, 'parent_user_response', None, parse_json=True)
    if parent_answer:
        path = Path(str(parent_answer.get('path') or ''))
        if not path.is_file() or sha256_file(path) != parent_answer.get('sha256'):
            blocking.append('parent user response record missing or changed')
    try:
        pending_tasks = con.execute("SELECT count(*) FROM task_queue WHERE status='pending'").fetchone()[0]
        if pending_tasks:
            blocking.append(f"{pending_tasks} model tasks are still pending")
        missing_receipts = con.execute(
            """SELECT count(*) FROM task_queue t
               LEFT JOIN model_receipts r ON r.task_id=t.task_id
               WHERE t.status='completed' AND r.task_id IS NULL"""
        ).fetchone()[0]
        if missing_receipts:
            blocking.append(f"{missing_receipts} completed model tasks are missing model/effort receipts")
        incomplete_usage = con.execute(
            """SELECT count(*) FROM task_queue t JOIN model_receipts r ON r.task_id=t.task_id
               WHERE t.status='completed' AND (r.input_tokens IS NULL OR r.output_tokens IS NULL)"""
        ).fetchone()[0]
        if incomplete_usage:
            blocking.append(f"{incomplete_usage} completed model tasks are missing token usage receipts")

        missing_schema_validation = con.execute(
            """SELECT count(*) FROM task_queue t
               LEFT JOIN (
                 SELECT task_id, max(CASE WHEN status='PASS' THEN 1 ELSE 0 END) AS has_pass
                 FROM llm_result_validations GROUP BY task_id
               ) v ON v.task_id=t.task_id
               WHERE t.status='completed' AND coalesce(v.has_pass,0)=0"""
        ).fetchone()[0]
        if missing_schema_validation:
            blocking.append(f"{missing_schema_validation} completed model tasks lack a passing JSON-schema validation")

        completed = rows_as_dict(con, "SELECT task_id,result_path FROM task_queue WHERE status='completed' AND result_path IS NOT NULL")
        for task in completed:
            rp = Path(str(task.get("result_path") or ""))
            if not rp.is_absolute():
                candidate = run_root / rp
                if candidate.exists():
                    rp = candidate
            if not rp.exists():
                blocking.append(f"Completed model task result file is missing: {task['task_id']}")
                continue
            validations = rows_as_dict(con, "SELECT result_sha256 FROM llm_result_validations WHERE task_id=? AND status='PASS' ORDER BY validated_at DESC", [task["task_id"]])
            if validations and validations[0].get("result_sha256"):
                try:
                    current_result = json.loads(rp.read_text(encoding="utf-8-sig"))
                    current_hash = result_hash(current_result)
                except Exception:
                    current_hash = ""
                if current_hash != validations[0]["result_sha256"]:
                    blocking.append(f"Completed model task result changed after schema validation: {task['task_id']}")
        open_diffs = con.execute("SELECT count(*) FROM differences WHERE status='open'").fetchone()[0]
        if open_diffs:
            blocking.append(f"{open_diffs} adjudication differences remain open")

        # Preserve the exact bytes used for evidence so a later source-file
        # edit cannot silently rewrite history.
        for d in rows_as_dict(con, "SELECT document_id,sha256,metadata_json FROM documents WHERE active=true"):
            try:
                meta = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                meta = {}
            rel = meta.get("archived_source_path")
            if not rel:
                blocking.append(f"Archived source copy is missing for document {d['document_id']}")
                continue
            ap = run_root / str(rel)
            if not ap.exists() or sha256_file(ap) != d.get("sha256"):
                blocking.append(f"Archived source hash cannot be verified for document {d['document_id']}")

        snapshot_sha = None
        try:
            _, snapshot_row = load_latest(run_root)
            snapshot_sha = snapshot_row["sha256"]
            if snapshot_row.get("status") == "PRELIMINARY":
                preliminary.append("Reviewed snapshot is preliminary")
        except (RuntimeError, ValueError, OSError) as exc:
            blocking.append(f"Reviewed snapshot cannot be verified: {exc}")

        independent_fail = con.execute("SELECT count(*) FROM independent_calculations WHERE status='fail'").fetchone()[0]
        if independent_fail:
            blocking.append(f"{independent_fail} independent recomputation check(s) failed")
        independent_unverified = con.execute("SELECT count(*) FROM independent_calculations WHERE status='unverified'").fetchone()[0]
        if independent_unverified:
            preliminary.append(f"{independent_unverified} independent recomputation check(s) remain unverified")
        expected_independent = sum(r["status"]=="complete" and r["calculation_type"] in {"cost_summary","scoring"} for r in current_calculations(con))
        actual_independent = con.execute("SELECT count(*) FROM independent_calculations").fetchone()[0]
        if expected_independent and actual_independent < expected_independent:
            blocking.append(f"Independent recomputation coverage is incomplete: {actual_independent}/{expected_independent}")

        grain_fail = con.execute("SELECT count(*) FROM grain_checks WHERE critical=true AND status<>'pass'").fetchone()[0]
        if grain_fail:
            blocking.append(f"{grain_fail} critical grain/join integrity check(s) failed")

        bridge_fail = con.execute("SELECT count(*) FROM cost_bridges WHERE status='fail'").fetchone()[0]
        if bridge_fail:
            blocking.append(f"{bridge_fail} cost bridge residual check(s) failed")
        bridge_unverified = con.execute("SELECT count(*) FROM cost_bridges WHERE status='unverified'").fetchone()[0]
        if bridge_unverified:
            preliminary.append(f"{bridge_unverified} cost bridge check(s) remain unverified")

        unsupported_claims = sum(c["support_status"] == "unsupported" for c in current_claims(con))
        if unsupported_claims:
            blocking.append(f"{unsupported_claims} decision claim(s) are unsupported")

        comparability = get_meta(run_root, "comparability_contract", {}, parse_json=True) or {}
        if comparability and not comparability.get("ranking_allowed", False):
            preliminary.append("Comparison contract does not allow supplier ranking")
        xlsx = rows_as_dict(con, "SELECT * FROM artifacts WHERE artifact_type='xlsx' AND status='ready' ORDER BY created_at DESC")
        if not xlsx:
            blocking.append("Final XLSX artifact is missing")
        else:
            p = run_root / xlsx[0]["relative_path"]
            if not p.exists() or sha256_file(p) != xlsx[0]["sha256"]:
                blocking.append("Final XLSX artifact hash cannot be verified")
            try:
                parents = json.loads(xlsx[0].get("parent_hashes_json") or "[]")
            except Exception:
                parents = []
            if snapshot_sha and snapshot_sha not in parents:
                blocking.append("Final XLSX is not bound to the reviewed snapshot")
            bindings = con.execute("SELECT count(*) FROM artifact_bindings WHERE artifact_id=? AND snapshot_sha256=?", [xlsx[0]["artifact_id"], snapshot_sha or ""]).fetchone()[0]
            if not bindings:
                blocking.append("Final XLSX has no reviewed-snapshot artifact bindings")
        if profile in {"hizli", "standart", "yuksek_guvence"}:
            pdf = rows_as_dict(con, "SELECT * FROM artifacts WHERE artifact_type='pdf' AND status='ready' ORDER BY created_at DESC")
            if not pdf:
                blocking.append("Mandatory final PDF artifact is missing")
            else:
                p = run_root / pdf[0]["relative_path"]
                if not p.exists() or sha256_file(p) != pdf[0]["sha256"]:
                    blocking.append("Final PDF artifact hash cannot be verified")
                pending_visual = con.execute("SELECT count(*) FROM render_hashes WHERE artifact_id=? AND qa_status<>'pass'", [pdf[0]["artifact_id"]]).fetchone()[0]
                if pending_visual:
                    blocking.append(f"{pending_visual} PDF pages have incomplete/failed visual QA")
        qa_critical = rows_as_dict(con, "SELECT message FROM qa_findings WHERE severity='critical' AND status='open'")
        for row in qa_critical:
            blocking.append(row["message"])

        structural_dq = rows_as_dict(
            con,
            """SELECT check_id,entity_id,risk FROM data_quality_findings
               WHERE status='open' AND severity='critical'"""
        )
        for row in structural_dq:
            blocking.append(f"Data-quality gate failed: {row['check_id']} ({row.get('entity_id') or 'run'})")

        consistency = rows_as_dict(con, "SELECT relative_path FROM artifacts WHERE artifact_type='cross_output_consistency' AND status='ready' ORDER BY created_at DESC")
        if not consistency:
            blocking.append("Cross-output consistency artifact is missing")
        else:
            cp = run_root / consistency[0]["relative_path"]
            try:
                consistency_obj = json.loads(cp.read_text(encoding='utf-8'))
            except Exception:
                consistency_obj = {}
            if consistency_obj.get('status') != 'PASS':
                blocking.append("Cross-output consistency check did not pass")

        provenance_artifacts = rows_as_dict(con, "SELECT relative_path FROM artifacts WHERE artifact_type='provenance_survival' AND status='ready' ORDER BY created_at DESC")
        if not provenance_artifacts:
            blocking.append("Provenance-survival artifact is missing")
        else:
            pp = run_root / provenance_artifacts[0]["relative_path"]
            try:
                provenance_obj = json.loads(pp.read_text(encoding='utf-8'))
            except Exception:
                provenance_obj = {}
            if provenance_obj.get('status') != 'PASS':
                blocking.append("Provenance-survival check did not pass")

        final_scope = rows_as_dict(con, "SELECT relative_path FROM artifacts WHERE artifact_type='scope_ledger_final' AND status='ready' ORDER BY created_at DESC")
        if not final_scope:
            blocking.append("Final run scope ledger is missing")
        else:
            try:
                scope_obj = json.loads((run_root / final_scope[0]['relative_path']).read_text(encoding='utf-8'))
            except Exception:
                scope_obj = {}
            if scope_obj.get('blocking_gaps'):
                preliminary.append(f"Run scope ledger has {len(scope_obj.get('blocking_gaps') or [])} blocking gap(s)")

        coverage_artifacts = rows_as_dict(con, "SELECT relative_path FROM artifacts WHERE artifact_type='coverage' AND status='ready' ORDER BY created_at DESC")
        if not coverage_artifacts:
            blocking.append("Revision-aware coverage record is missing")
        else:
            cov_path = run_root / coverage_artifacts[0]["relative_path"]
            try:
                coverage_obj = json.loads(cov_path.read_text(encoding='utf-8'))
            except Exception:
                coverage_obj = {}
            if coverage_obj.get('blocking_gaps'):
                blocking.append(f"Coverage record has {len(coverage_obj.get('blocking_gaps') or [])} blocking gap(s)")
            if coverage_obj.get('inventoryComplete') is False:
                preliminary.append("Validation coverage inventory is incomplete")
        critical_issues = con.execute("SELECT count(*) FROM open_issues WHERE status='open' AND severity='critical'").fetchone()[0]
        if critical_issues:
            preliminary.append(f"{critical_issues} critical RFI/issues remain open")
        if suff.get("status") != "SUFFICIENT":
            preliminary.append("Decision sufficiency gate is PRELIMINARY_ONLY")
        recommendation = get_meta(run_root, "decision_recommendation", "null")
        try:
            rec_obj = json.loads(recommendation)
        except Exception:
            rec_obj = recommendation
        if preliminary and rec_obj is not None:
            blocking.append("Recommendation is non-null while preliminary conditions exist")
        if blocking:
            status = "BLOCKED"
        elif preliminary:
            status = "PRELIMINARY"
        else:
            status = "VERIFIED"
        result = {
            "status": status,
            "profile": profile,
            "blocking_reasons": sorted(set(blocking)),
            "preliminary_reasons": sorted(set(preliminary)),
            "decision_sufficiency": suff,
            "validated_at": utc_now(),
        }
        out = run_root / "output" / "verification.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        sha = sha256_file(out)
        aid = stable_id("art", "verification", sha, length=22)
        con.execute(
            "INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)",
            [aid, "verification", str(out.relative_to(run_root)), sha, "[]", "ready", utc_now()],
        )
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('validation_status',?)", [status])
        if hasattr(con, "commit"):
            con.commit()
        return result
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Final run verification gate")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    result = validate(Path(args.run))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("status") == "VERIFIED" else (2 if result.get("status") == "PRELIMINARY" else 3))


if __name__ == "__main__":
    main()
