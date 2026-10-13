from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from common import dump_json, iter_source_files, json_text, sha256_file, utc_now
from active_records import current_artifacts
from db import connect, get_meta, get_state, init_db, rows_as_dict, set_meta, set_state
from field_extract import extract as extract_fields
from ingest import ingest_source
from normalize import normalize
from procurement_engine import run_engine
from decision_gate import run_gate
from task_queue import generate_decision_summary_task, generate_initial_tasks, generate_review_tasks, generate_specialist_tasks, pending_tasks
from context_packet import task_packet
from compare_reviews import compare as compare_review
from source_authority import refresh as refresh_source_authority
from data_quality import assess as assess_data_quality
from comparison_contract import assess as assess_comparability
from independent_recompute import run as independent_recompute
from cost_bridge import build as build_cost_bridge
from grain_integrity import check as check_grain_integrity
from scope_ledger import build as build_scope_ledger
from error_log import log_failures, log_error
from user_question_gate import waiting as user_input_waiting
from report_hooks import terminal_reports

PHASES = ["PREPARE", "INGEST", "REQUIREMENTS", "EXTRACT", "NORMALIZE", "SUFFICIENCY", "REVIEW", "ADJUDICATE", "REPORT", "QA", "COMPLETE"]


def _policy(skill_root: Path) -> dict[str, Any]:
    return json.loads((skill_root / "config" / "policy.json").read_text(encoding="utf-8"))


def _version(skill_root: Path) -> str:
    return (skill_root / "VERSION").read_text(encoding="utf-8").strip()


def _profile(run_root: Path) -> str:
    return str(get_meta(run_root, "profile", "standart"))


def _analysis_date(run_root: Path) -> date:
    raw = get_meta(run_root, "analysis_date", None)
    return date.fromisoformat(raw) if raw else date.today()


def _task_contexts(run_root: Path, policy: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from question_waits import assert_task_allowed
    for task in tasks:
        assert_task_allowed(run_root, task)
    out = []
    cfg = policy["context_packet"]
    task_dir = run_root / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        packet = task_packet(run_root, task["task_id"], int(cfg["max_units"]), int(cfg["max_chars"]))
        path = task_dir / task["task_id"] / "context.json"
        if path.exists():
            from run_compatibility import business_packet
            if json_text(business_packet(json.loads(path.read_text(encoding='utf-8')))) != json_text(business_packet(packet)):
                raise ValueError('Previously dispatched task packet changed; preserved original context without rewrite')
        else:
            dump_json(path, packet)
        from run_compatibility import pin_dispatch
        pin_dispatch(run_root, task, path, Path(__file__).resolve().parents[1])
        role_cfg = policy["roles"].get(task["role"], {"engine": "llm"})
        out.append({
            "task_id": task["task_id"],
            "phase": task["phase"],
            "role": task["role"],
            "task_kind": task["task_kind"],
            "critical": bool(task["critical"]),
            "context_path": str(path),
            "user_wait_control": {"state_path":str((run_root/'user_wait_control'/'state.json').resolve()),
                                  "task_id":task['task_id'], "policy":"dependent_tasks_only_no_timeout"},
            "model_policy": role_cfg,
            "security_envelope": packet.get("security_envelope", {}),
        })
    return out



def _token_budget(run_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    profile = _profile(run_root)
    cap = int(policy.get("profiles", {}).get(profile, {}).get("max_input_tokens", 0) or 0)
    con = connect(run_root)
    try:
        row = con.execute(
            "SELECT coalesce(sum(input_tokens),0),coalesce(sum(cached_input_tokens),0),coalesce(sum(output_tokens),0),"
            "sum(CASE WHEN input_tokens IS NULL OR output_tokens IS NULL THEN 1 ELSE 0 END) FROM model_receipts"
        ).fetchone()
    finally:
        con.close()
    input_tokens = int(row[0] or 0)
    cached = int(row[1] or 0)
    output = int(row[2] or 0)
    unknown_receipts = int(row[3] or 0)
    ratio = (input_tokens / cap) if cap else 0.0
    return {
        "profile": profile, "input_tokens": input_tokens, "cached_input_tokens": cached,
        "output_tokens": output, "max_input_tokens": cap, "ratio": round(ratio, 6),
        "usage_unknown": bool(unknown_receipts), "unknown_receipts": unknown_receipts,
        "warning": bool(unknown_receipts or (cap and ratio >= float(policy.get("budget_warning_ratio", 0.8)))),
        "hard_stop": bool(unknown_receipts or (cap and ratio >= float(policy.get("budget_hard_stop_ratio", 1.0)))),
    }


def _needs_llm_response(run_root: Path, policy: dict[str, Any], pending: list[dict[str, Any]], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    # Priorities order tasks only within a phase. Never pin a later business
    # packet while classification/requirements can still change its inputs.
    pending_total = len(pending)
    unknown = {t['phase'] for t in pending} - set(PHASES)
    if unknown:
        raise ValueError('Unknown task phase: ' + ', '.join(sorted(unknown)))
    earliest = min((PHASES.index(t['phase']) for t in pending), default=None)
    pending = [t for t in pending if PHASES.index(t['phase']) == earliest]
    max_attempts = int(policy.get("max_task_attempts", 2))
    exhausted = [t for t in pending if int(t.get("attempts") or 0) >= max_attempts]
    if exhausted:
        return {
            "status": "MANUAL_REVIEW_REQUIRED",
            "reason": "model task retry limit reached",
            "tasks": [{"task_id": t["task_id"], "task_kind": t["task_kind"], "attempts": t.get("attempts", 0)} for t in exhausted],
        }
    budget = _token_budget(run_root, policy)
    override_raw = str(get_meta(run_root, "budget_override", "false")).strip().lower()
    override = override_raw in {"1", "true", "yes", "allow"}
    if budget["hard_stop"] and not override:
        return {
            "status": "BUDGET_EXHAUSTED",
            "reason": "profile input-token safety cap reached; no new model task dispatched",
            "budget": budget,
            "pending_total": pending_total,
        }
    max_tasks = int(policy.get("max_concurrent_llm_tasks", 3))
    selected = pending[:max_tasks]
    out = {
        "status": "NEEDS_LLM",
        "tasks": _task_contexts(run_root, policy, selected),
        "pending_total": pending_total,
        "budget": budget,
    }
    if extra:
        out.update(extra)
    return out


def _refresh_deterministic_controls(run_root: Path) -> dict[str, Any]:
    """Refresh all deterministic decision controls after canonical facts/calculations change."""
    engine = run_engine(run_root)
    comparability = assess_comparability(run_root)
    independent = independent_recompute(run_root)
    bridge = build_cost_bridge(run_root)
    grain = check_grain_integrity(run_root)
    data_quality = assess_data_quality(run_root)
    from buyer_controls import resolve_answered_questions
    buyer_resolutions = resolve_answered_questions(run_root)
    scope = build_scope_ledger(run_root, final=False)
    return {
        "engine": engine, "comparability": comparability, "independent_recompute": independent,
        "cost_bridge": bridge, "grain_integrity": grain, "data_quality": data_quality, "scope_ledger": scope,
        "buyer_resolutions": buyer_resolutions,
    }

@log_failures('workflow.prepare')
@terminal_reports(run_arg=1)
def prepare(source: Path, run_root: Path, profile: str, analysis_date_value: date | None = None, financial_params: dict[str, Any] | None = None, scoring_params: dict[str, Any] | None = None, user_response_record: Path | None = None, user_response_sha256: str | None = None, supplier_folder_declaration: Path | None = None) -> dict[str, Any]:
    skill_root = Path(__file__).resolve().parents[1]
    if user_response_record is not None:
        if not user_response_sha256 or not user_response_record.is_file() or sha256_file(user_response_record) != user_response_sha256:
            raise ValueError('Kullanıcı yanıtı kaydı/hash eşleşmiyor; yeni koşu başlatılmadı')
        from user_question_gate import source_manifest
        parent_response=json.loads(user_response_record.read_text(encoding='utf-8'))
        expected=parent_response.get('authorized_resume')
        actual={'schema':'teklif-resume/v1','source':str(source.resolve()),'run':str(run_root.resolve()),
                'profile':profile,'analysis_date':(analysis_date_value or date.today()).isoformat(),
                'financial_parameters':financial_params or None,'scoring_parameters':scoring_params or None,
                'skill_version':_version(skill_root)}
        if supplier_folder_declaration is not None:
            actual['supplier_folder_declaration'] = str(supplier_folder_declaration.resolve())
            actual['supplier_folder_declaration_sha256'] = sha256_file(supplier_folder_declaration)
        if not isinstance(expected,dict) or expected != actual or parent_response.get('authorized_source_manifest') != source_manifest(source):
            raise ValueError('Kullanıcı yanıtının yetkili yeni koşu girdileri veya kaynak baytları değişti')
    if (run_root/'analysis.duckdb').exists() or (run_root/'analysis.test.sqlite').exists():
        raise ValueError('prepare requires a fresh run directory; existing analysis preserved')
    run_root.mkdir(parents=True, exist_ok=True)
    resume_request = {
        "schema": "teklif-resume/v1",
        "source": str(source.resolve()),
        "run": str(run_root.resolve()),
        "profile": profile,
        "analysis_date": (analysis_date_value or date.today()).isoformat(),
        "financial_parameters": financial_params,
        "scoring_parameters": scoring_params,
        "skill_version": _version(skill_root),
    }
    if supplier_folder_declaration is not None:
        resume_request["supplier_folder_declaration"] = str(supplier_folder_declaration.resolve())
        resume_request["supplier_folder_declaration_sha256"] = sha256_file(supplier_folder_declaration)
    # Production runs must pass runtime preflight before any source inventory or analysis starts.
    # SQLite bypass exists only for this skill's deterministic test suite.
    if os.environ.get("TEKLIF_TEST_SQLITE") != "1":
        from environment_check import check as environment_check
        env = environment_check(skill_root / "requirements.txt", require_pdf_extension=False)
        dump_json(run_root / "environment.json", env)
        if env.get("status") != "READY":
            # Fail closed: no inventory, no analysis and no installation attempt.
            # The resume file only lets the same request restart after someone
            # with authority has installed the listed components.
            dump_json(run_root / "resume_request.json", resume_request)
            return {
                "status": "BLOCKED_ENVIRONMENT",
                "reason": "runtime dependencies are not ready; analysis was not started",
                "environment_report": str(run_root / "environment.json"),
                "missing_components": env.get("missing_components", []),
                "blocking_reasons": env.get("blocking_reasons", []),
                "user_message": env.get("user_message"),
                "automatic_installation": False,
                "installation_performed": False,
                "resume_request": str(run_root / "resume_request.json"),
                "resume_command": f'python "{Path(__file__).resolve()}" prepare --resume-request "{run_root / "resume_request.json"}"',
            }
    init_db(run_root, skill_root)
    from run_compatibility import execution_contract
    set_meta(run_root, 'execution_contract', execution_contract(skill_root))
    policy_bytes = (skill_root / "config" / "policy.json").read_bytes()
    set_meta(run_root, "skill_version", _version(skill_root))
    set_meta(run_root, "profile", profile)
    set_meta(run_root, "source_root", str(source.resolve()))
    set_meta(run_root, "analysis_date", (analysis_date_value or date.today()).isoformat())
    set_meta(run_root, "policy_sha256", hashlib.sha256(policy_bytes).hexdigest())
    if financial_params is not None:
        set_meta(run_root, "financial_parameters", financial_params)
    if scoring_params is not None:
        set_meta(run_root, "scoring_parameters", scoring_params)
    if user_response_record is not None:
        set_meta(run_root, 'parent_user_response', {'path':str(user_response_record.resolve()),'sha256':user_response_sha256})
    expected_sources=[]
    source_resolved=source.resolve()
    for p in sorted(iter_source_files(source_resolved, run_root), key=lambda x:str(x).casefold()):
        try:
            rel=str(p.resolve().relative_to(source_resolved)) if source_resolved.is_dir() else p.name
        except Exception:
            rel=p.name
        expected_sources.append({"relative_path":rel,"sha256":sha256_file(p),"size_bytes":p.stat().st_size})
    folder_mappings = None
    declaration_sha = None
    if supplier_folder_declaration is not None:
        declaration_sha = sha256_file(supplier_folder_declaration)
        raw = json.loads(supplier_folder_declaration.read_text(encoding="utf-8-sig"))
        folder_mappings = raw.get("mappings")
        if raw.get("schema") != "supplier-folder-declaration/v1" or raw.get("legal_entity_verified") is not False or not isinstance(folder_mappings, dict) or not folder_mappings:
            raise ValueError("Supplier folder declaration is invalid")
        source_names = [item["relative_path"].replace("\\", "/") for item in expected_sources]
        for folder, name in folder_mappings.items():
            if not isinstance(folder, str) or not isinstance(name, str) or not name.strip() or name.strip() != folder.strip("/").rsplit("/", 1)[-1]:
                raise ValueError("Supplier folder declaration name/path mismatch")
            if not any(path.startswith(folder.strip("/") + "/") for path in source_names):
                raise ValueError("Supplier folder declaration has no matching source")
        declaration = {"source": "user_declaration", "mappings": folder_mappings,
                       "legal_entity_verified": False, "declaration_file_sha256": declaration_sha,
                       "declaration_file_path": str(supplier_folder_declaration.resolve())}
        set_meta(run_root, "supplier_folder_declaration_v1", declaration)
    run_contract={"schema":"teklif-run-contract/v1","source_root":str(source_resolved),"profile":profile,"analysis_date":(analysis_date_value or date.today()).isoformat(),"expected_sources":expected_sources,"expected_outputs":["xlsx","pdf"]}
    if declaration_sha is not None:
        run_contract["supplier_folder_declaration_sha256"] = declaration_sha
    dump_json(run_root/"run_contract.json",run_contract)
    set_meta(run_root,"run_contract",run_contract)
    set_state(run_root, "PREPARE", "PASS", {"profile": profile, "source": str(source.resolve())})
    inventory = ingest_source(source, run_root, folder_mappings=folder_mappings)
    refresh_source_authority(run_root)
    fields = extract_fields(run_root)
    norm = normalize(run_root)
    authority = refresh_source_authority(run_root)
    controls = _refresh_deterministic_controls(run_root)
    engine = controls["engine"]
    data_quality = controls["data_quality"]
    tasks = generate_initial_tasks(run_root, profile)
    spec_count = sum(1 for x in inventory if x.get("document_role") == "specification")
    if spec_count:
        set_state(run_root, "REQUIREMENTS", "RUNNING" if tasks.get("requirements_extraction") else "PASS", {"spec_documents": spec_count})
    else:
        set_state(run_root, "REQUIREMENTS", "SKIPPED", {"reason": "no specification classified"})
    prepared = {
        "status": "PREPARED",
        "run": str(run_root),
        "profile": profile,
        "inventory_path": str(run_root / "inventory.json"),
        "documents": len(inventory),
        "deterministic_fields": fields,
        "normalization": norm,
        "engine": engine,
        "source_authority": {"controlling": authority.get("controlling",0), "unresolved": authority.get("unresolved",0)},
        "data_quality": {"status": data_quality.get("status"), "finding_count": data_quality.get("finding_count",0), "by_severity": data_quality.get("by_severity",{})},
        "tasks_created": tasks,
    }
    if not any(t['phase'] == 'PREPARE' for t in pending_tasks(run_root)):
        wait = user_input_waiting(run_root)
        if wait:
            return {**prepared, **wait}
    return prepared


def _pending_by_phase(run_root: Path) -> list[dict[str, Any]]:
    return pending_tasks(run_root)


def _independent_early_extraction(run_root: Path, pending: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Permit source-independent reading while unresolved revisions still block decisions."""
    candidates = [task for task in pending if task.get("task_kind") in
                  {"offer_semantic_fields", "requirements_extraction"}]
    if not candidates:
        return []
    con = connect(run_root)
    try:
        statuses = {row["document_id"]: row["authority_status"] for row in rows_as_dict(
            con, "SELECT document_id,authority_status FROM source_authority")}
    finally:
        con.close()
    safe = []
    for task in candidates:
        if task.get("document_id"):
            document_ids = [task["document_id"]]
        else:
            try:
                document_ids = json.loads(task.get("payload_json") or "{}").get("document_ids")
            except (TypeError, ValueError):
                document_ids = None
        if isinstance(document_ids, list) and document_ids and all(
            isinstance(did, str) and statuses.get(did) == "controlling" for did in document_ids
        ):
            from question_waits import task_waits
            if not task_waits(run_root, task):
                safe.append(task)
    return safe


def _completed_review_tasks(run_root: Path) -> list[dict[str, Any]]:
    con = connect(run_root)
    try:
        return rows_as_dict(
            con,
            "SELECT task_id FROM task_queue WHERE task_kind='independent_fact_review' AND status='completed' ORDER BY task_id",
        )
    finally:
        con.close()


def _ensure_review_diffs(run_root: Path) -> list[dict[str, Any]]:
    results = []
    for row in _completed_review_tasks(run_root):
        review_id = row["task_id"]
        con = connect(run_root)
        try:
            has = con.execute("SELECT count(*) FROM differences WHERE review_id=?", [review_id]).fetchone()[0]
        finally:
            con.close()
        if not has:
            results.append(compare_review(run_root, review_id))
    return results


def _open_differences(run_root: Path) -> int:
    con = connect(run_root)
    try:
        return int(con.execute("SELECT count(*) FROM differences WHERE status='open'").fetchone()[0])
    finally:
        con.close()


def _has_any_task(run_root: Path, kind: str) -> bool:
    con = connect(run_root)
    try:
        return bool(con.execute("SELECT count(*) FROM task_queue WHERE task_kind=?", [kind]).fetchone()[0])
    finally:
        con.close()


def _all_tasks_done(run_root: Path, kinds: list[str]) -> bool:
    con = connect(run_root)
    try:
        placeholders = ",".join("?" for _ in kinds)
        total = con.execute(f"SELECT count(*) FROM task_queue WHERE task_kind IN ({placeholders})", kinds).fetchone()[0]
        pending = con.execute(f"SELECT count(*) FROM task_queue WHERE task_kind IN ({placeholders}) AND status<>'completed'", kinds).fetchone()[0]
        return total > 0 and pending == 0
    finally:
        con.close()


def _needs_decision_summary(run_root: Path) -> bool:
    return get_meta(run_root, "decision_summary", None) is None


def _artifact_exists(run_root: Path, artifact_type: str) -> bool:
    con = connect(run_root)
    try:
        return bool(con.execute("SELECT count(*) FROM artifacts WHERE artifact_type=? AND status='ready'", [artifact_type]).fetchone()[0])
    finally:
        con.close()


def _artifact_bound_to_snapshot(run_root: Path, artifact_type: str, snapshot_sha: str) -> bool:
    con = connect(run_root)
    try:
        row = current_artifacts(con).get(artifact_type)
        for row in ([row] if row else []):
            try:
                parents = json.loads(row.get("parent_hashes_json") or "[]")
            except Exception:
                parents = []
            p = run_root / row["relative_path"]
            if snapshot_sha in parents and p.exists():
                from common import sha256_file
                if sha256_file(p) == row.get("sha256"):
                    return True
        return False
    finally:
        con.close()


def _completed_verified_result(run_root: Path) -> dict[str, Any] | None:
    """Return an already completed PASS/PARTIAL run without mutating it."""
    states = {x.get("phase"): x for x in get_state(run_root)}
    complete = states.get("COMPLETE")
    if not complete or complete.get("status") not in {"PASS", "PARTIAL"}:
        return None
    vp = run_root / "output" / "verification.json"
    if not vp.exists():
        return None
    try:
        obj = json.loads(vp.read_text(encoding="utf-8"))
    except Exception:
        return None
    if obj.get("status") not in {"VERIFIED", "PRELIMINARY"}:
        return None
    from closure_integrity import inspect_closure
    if inspect_closure(run_root):
        return None
    return {"status": obj["status"], "reused_completed_run": True, "validation": obj}


@log_failures('workflow.advance')
@terminal_reports(run_arg=0)
def advance(run_root: Path) -> dict[str, Any]:
    # Do not repeat answer-dependent whole-run processing after displaying an
    # ask. Existing unrelated source tasks may still be dispatched/recorded.
    from question_waits import active as active_question_waits
    active_waits = active_question_waits(run_root)
    if active_waits:
        wait = user_input_waiting(run_root)
        if wait:
            policy = _policy(Path(__file__).resolve().parents[1])
            independent = _independent_early_extraction(run_root, _pending_by_phase(run_root))
            if independent:
                response = _needs_llm_response(run_root, policy, independent)
                if response.get('status') == 'NEEDS_LLM':
                    return {**response, 'questions':wait['questions'],
                            'open_question_count':wait['open_question_count'],
                            'remaining_question_count':wait['remaining_question_count'],
                            'user_input_pending':True, 'wait_policy':wait['wait_policy'],
                            'deliverable_artifacts':False}
            return wait
        if any(row['state'] == 'new_run_required' for row in active_waits):
            # The user already answered. Preserve the rerun barrier without
            # repeating the question or entering whole-run processing.
            return {'status':'NEW_RUN_REQUIRED', 'deliverable_artifacts':False,
                    'reason':'Kullanıcı yanıtı kaydedildi; değişen girdiler için yeni koşu gerekir.'}
    from run_compatibility import assert_compatible
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    completed = _completed_verified_result(run_root)
    if completed:
        return completed
    if any(s.get("phase") == "COMPLETE" and s.get("status") in {"PASS", "PARTIAL"} for s in get_state(run_root)):
        return {"status": "BLOCKED", "reason": "Completed-run integrity failed; preserved without mutation"}
    skill_root = Path(__file__).resolve().parents[1]
    policy = _policy(skill_root)
    profile = _profile(run_root)
    # Always regenerate deterministic derivatives after newly recorded model results.
    extract_fields(run_root)
    normalize(run_root)
    refresh_source_authority(run_root)
    from evidence_confirmation import confirm
    confirm(run_root)
    _refresh_deterministic_controls(run_root)
    generate_initial_tasks(run_root, profile)

    pending = [t for t in _pending_by_phase(run_root) if t['task_kind'] != 'decision_summary']
    # PREPARE classification may resolve a source question. An unresolved
    # revision blocks extraction from that source and every later decision.
    # Independent controlling sources may still be read, with the user
    # question visible in the same response.
    if not any(t['phase'] == 'PREPARE' for t in pending):
        wait = user_input_waiting(run_root)
        if wait:
            independent = _independent_early_extraction(run_root, pending)
            if independent:
                response = _needs_llm_response(run_root, policy, independent)
                if response.get("status") == "NEEDS_LLM":
                    return {**response, "questions": wait["questions"],
                            "open_question_count": wait["open_question_count"],
                            "remaining_question_count": wait["remaining_question_count"],
                            "user_input_pending": True, "wait_policy":wait['wait_policy'], "deliverable_artifacts": False}
                return {**wait, "independent_dispatch": response}
            return wait
    if pending:
        return _needs_llm_response(run_root, policy, pending)

    # Explicitly close the extraction phases once their bounded tasks are complete.
    if _has_any_task(run_root, "requirements_extraction"):
        set_state(run_root, "REQUIREMENTS", "PASS", {"tasks_complete": True})
    elif not any(x.get("phase") == "REQUIREMENTS" for x in get_state(run_root)):
        set_state(run_root, "REQUIREMENTS", "SKIPPED", {"reason": "no specification extraction task"})
    set_state(run_root, "EXTRACT", "PASS", {"tasks_complete": True})

    # Initial semantic extraction is complete. Recompute gate before expensive review.
    gate = run_gate(run_root, _analysis_date(run_root))
    if gate["status"] != "SUFFICIENT":
        wait = user_input_waiting(run_root)
        if wait:
            return {**wait, 'gate':gate}
        set_state(run_root, "REVIEW", "SKIPPED", {"reason": "sufficiency gate did not pass"})
        set_state(run_root, "ADJUDICATE", "SKIPPED", {"reason": "sufficiency gate did not pass"})
        if gate.get('answered_unknown_only'):
            # A completed unknown answer is a decision limitation, not a repeated
            # question. Report only an explicit preliminary outcome, no selection.
            if _needs_decision_summary(run_root):
                generate_decision_summary_task(run_root)
                return _needs_llm_response(run_root, policy, _pending_by_phase(run_root), {"gate":gate})
            retry = _summary_retry_step(run_root, policy)
            if retry:
                return retry
            return _finish_outputs(run_root, preliminary=True)
        return {"status":"BLOCKED","reason":"decision sufficiency is unresolved without an actionable user question",
                "gate":gate,"deliverable_artifacts":False}

    # High-assurance specialist review is exception-driven, never a full-document reread.
    if profile == "yuksek_guvence":
        generate_specialist_tasks(run_root)
        pending = [t for t in _pending_by_phase(run_root) if t['task_kind'] != 'decision_summary']
        if pending:
            return _needs_llm_response(run_root, policy, pending, {"gate": gate})

    # Optional secondary PDF parser before model independent review.
    if profile in {"standart", "yuksek_guvence"} and not get_meta(run_root, "secondary_pdf_review_done", None):
        try:
            from secondary_review import run as secondary_run
            secondary = secondary_run(run_root)
        except Exception as exc:
            log_error('workflow.secondary_review',status='ERROR',exception=exc)
            secondary = {"error": str(exc)}
        set_meta(run_root, "secondary_pdf_review_done", secondary)

    # Generate bounded independent review once per stable fact set.
    if profile in {"standart", "yuksek_guvence"}:
        generate_review_tasks(run_root, profile)
        pending = [t for t in _pending_by_phase(run_root) if t['task_kind'] != 'decision_summary']
        if pending:
            set_state(run_root, "REVIEW", "RUNNING", {"pending": len(pending)})
            return _needs_llm_response(run_root, policy, pending, {"gate": gate})
        review_results = _ensure_review_diffs(run_root)
        if review_results:
            set_state(run_root, "REVIEW", "PASS", {"comparisons": review_results})
        wait = user_input_waiting(run_root)
        if wait:
            set_state(run_root, "REVIEW", "BLOCKED", {"reason": "critical business input arose during review"})
            return {**wait, 'gate': gate}
        open_diff = _open_differences(run_root)
        if open_diff:
            pending = [t for t in _pending_by_phase(run_root) if t['task_kind'] != 'decision_summary']
            if pending:
                set_state(run_root, "ADJUDICATE", "RUNNING", {"open_differences": open_diff})
                return _needs_llm_response(run_root, policy, pending, {"gate": gate})
            # If differences remain open with no task, do not silently continue.
            return {"status": "BLOCKED", "reason": "open differences without adjudication task", "open_differences": open_diff}
        set_state(run_root, "ADJUDICATE", "PASS", {"open_differences": 0})
    else:
        set_state(run_root, "REVIEW", "SKIPPED", {"profile": profile})
        set_state(run_root, "ADJUDICATE", "SKIPPED", {"profile": profile})

    # Recompute after adjudication and gate again.
    normalize(run_root)
    refresh_source_authority(run_root)
    _refresh_deterministic_controls(run_root)
    gate = run_gate(run_root, _analysis_date(run_root))
    wait = user_input_waiting(run_root)
    if wait:
        return {**wait, 'gate':gate}
    if gate['status'] != 'SUFFICIENT':
        return {'status':'BLOCKED','reason':'post-review sufficiency gate did not pass',
                'gate':gate,'deliverable_artifacts':False}
    if _needs_decision_summary(run_root):
        generate_decision_summary_task(run_root)
        pending = _pending_by_phase(run_root)
        if pending:
            return _needs_llm_response(run_root, policy, pending, {"gate": gate})
    summary_retry = _summary_retry_step(run_root, policy)
    if summary_retry:
        return summary_retry
    return _finish_outputs(run_root, preliminary=gate["status"] != "SUFFICIENT")


def _summary_retry_step(run_root: Path, policy: dict[str, Any]) -> dict[str, Any] | None:
    from task_queue import retry_decision_summary
    result = retry_decision_summary(run_root)
    if result["status"] == "NO_RETRY_REQUIRED":
        return None
    if result["status"] == "RETRY_PENDING":
        return _needs_llm_response(run_root, policy, _pending_by_phase(run_root), {"summary_retry": result})
    return result


@terminal_reports(run_arg=0)
def _finish_outputs(run_root: Path, preliminary: bool) -> dict[str, Any]:
    wait = user_input_waiting(run_root)
    if wait:
        return wait
    sufficiency = get_meta(run_root, 'decision_sufficiency', {}, parse_json=True) or {}
    if preliminary and not sufficiency.get('answered_unknown_only'):
        return {'status':'BLOCKED','reason':'decision inputs are insufficient for report output',
                'deliverable_artifacts':False}
    from claim_registry import rebuild as rebuild_claim_registry
    from reviewed_snapshot import freeze as freeze_snapshot
    claim_registry = rebuild_claim_registry(run_root)
    build_scope_ledger(run_root, final=False)
    snapshot = freeze_snapshot(run_root)
    if snapshot.get("status") == "BLOCKED" or not snapshot.get("frozen"):
        result = {"status": "BLOCKED", "preliminary": preliminary, "claim_registry": claim_registry, "reviewed_snapshot": snapshot}
        set_state(run_root, "REPORT", "BLOCKED", result)
        set_state(run_root, "QA", "SKIPPED", {"reason": "pre-output reviewed snapshot gate blocked"})
        set_state(run_root, "COMPLETE", "BLOCKED", result)
        return result
    from official_delivery import inspect_official
    official = inspect_official(run_root, snapshot["sha256"])
    legacy_pair = official["delivery_status"] == "NOT_CREATED" and all(
        _artifact_bound_to_snapshot(run_root, kind, snapshot["sha256"]) for kind in ("xlsx", "pdf", "decision_snapshot"))
    if official["delivery_status"] != "READY" and not legacy_pair:
        from report_export import export_report
        from official_delivery import PairValidationError
        try:
            report = export_report(run_root)
        except PairValidationError as exc:
            result = {"status": "BLOCKED", "reason": "Resmî rapor çiftinin doğrulaması başarısız: " + str(exc), "deliverable_artifacts": False}
            set_state(run_root, "REPORT", "BLOCKED", result)
            return result
    else:
        report = {"reused": True, "reviewed_snapshot": snapshot, "official_report_delivery": official}
    wait = user_input_waiting(run_root)
    if wait:
        set_state(run_root, "REPORT", "BLOCKED", {"reason": "critical business input arose during report export"})
        set_state(run_root, "QA", "SKIPPED", {"reason": "report export raised a business question"})
        set_state(run_root, "COMPLETE", "BLOCKED", {"reason": "critical business input is pending"})
        return {**wait, 'report': report}
    set_state(run_root, "REPORT", "PASS", report)

    from qa import run_qa
    qa_result = run_qa(run_root)
    wait = user_input_waiting(run_root)
    if wait:
        set_state(run_root, "QA", "BLOCKED", {"reason": "critical business input arose during QA", "qa": qa_result})
        set_state(run_root, "COMPLETE", "BLOCKED", {"reason": "critical business input is pending"})
        return {**wait, 'report': report, 'qa': qa_result}
    if qa_result.get("status") == "NEEDS_VISUAL_QA":
        set_state(run_root, "QA", "RUNNING", qa_result)
        policy = _policy(Path(__file__).resolve().parents[1])
        pending = _pending_by_phase(run_root)
        if pending:
            return _needs_llm_response(run_root, policy, pending, {"qa": qa_result})
    set_state(run_root, "QA", "PASS" if qa_result.get("status") == "PASS" else "BLOCKED", qa_result)

    final_scope = build_scope_ledger(run_root, final=True)
    from coverage import build as build_coverage
    coverage = build_coverage(run_root)
    from validate_run import validate
    validation = validate(run_root)
    validation["coverage"] = {"blocking_gaps": coverage.get("blocking_gaps", []), "categories": coverage.get("categories", {})}
    final_status = validation["status"]
    set_state(run_root, "COMPLETE", "PASS" if final_status == "VERIFIED" else ("PARTIAL" if final_status == "PRELIMINARY" else "BLOCKED"), validation)
    if final_status in {'VERIFIED','PRELIMINARY'}:
        from closure_integrity import freeze_closure
        freeze_closure(run_root)
    return {"status": final_status, "preliminary": preliminary, "report": report, "qa": qa_result, "scope_ledger": final_scope, "validation": validation}


def status(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        tasks = rows_as_dict(con, "SELECT status,count(*) AS n FROM task_queue GROUP BY status ORDER BY status")
        docs = con.execute("SELECT count(*) FROM documents").fetchone()[0]
        offers = con.execute("SELECT count(*) FROM offers WHERE status='active'").fetchone()[0]
        facts = con.execute("SELECT count(*) FROM facts").fetchone()[0]
        issues = con.execute("SELECT count(*) FROM open_issues WHERE status='open'").fetchone()[0]
        diffs = con.execute("SELECT count(*) FROM differences WHERE status='open'").fetchone()[0]
        dq_critical = con.execute("SELECT count(*) FROM data_quality_findings WHERE status='open' AND severity='critical'").fetchone()[0]
        authority_unresolved = con.execute("SELECT count(*) FROM source_authority WHERE authority_status IN ('needs_input','unusable')").fetchone()[0]
        artifacts = rows_as_dict(con, "SELECT artifact_type,relative_path,status FROM artifacts ORDER BY artifact_type")
    finally:
        con.close()
    policy = _policy(Path(__file__).resolve().parents[1])
    question_state = user_input_waiting(run_root)
    states = get_state(run_root)
    complete = next((x for x in states if x.get('phase') == 'COMPLETE'), None)
    expected_verification = {'PASS': 'VERIFIED', 'PARTIAL': 'PRELIMINARY'}
    delivery_reason = None
    if question_state:
        delivery_reason = 'critical business input is pending'
    elif not complete or complete.get('status') not in expected_verification:
        delivery_reason = 'final validation has not completed'
    else:
        verification_path = run_root / 'output' / 'verification.json'
        try:
            verification = json.loads(verification_path.read_text(encoding='utf-8'))
            if verification.get('status') != expected_verification[complete['status']]:
                delivery_reason = 'final verification status does not match completion state'
            else:
                from closure_integrity import inspect_closure
                if inspect_closure(run_root):
                    delivery_reason = 'completed run integrity failed'
        except (OSError, ValueError, TypeError):
            delivery_reason = 'final verification cannot be read'
    if delivery_reason:
        artifacts = [{**item, 'deliverable': False, 'delivery_reason': delivery_reason} for item in artifacts]
    from report_delivery import inspect_preliminary
    preliminary_delivery = inspect_preliminary(run_root)
    return {
        "profile": _profile(run_root),
        "budget": _token_budget(run_root, policy),
        "states": states,
        "documents": docs,
        "active_offers": offers,
        "facts": facts,
        "open_issues": issues,
        "open_differences": diffs,
        "critical_data_quality_findings": dq_critical,
        "unresolved_source_authority": authority_unresolved,
        "tasks": tasks,
        "artifacts": artifacts,
        "user_input": question_state,
        "deliverable_artifacts": delivery_reason is None,
        "delivery_reason": delivery_reason,
        "preliminary_report_delivery": preliminary_delivery,
        "report_delivery_status": "READY" if delivery_reason is None else preliminary_delivery["delivery_status"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic-first procurement workflow controller")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--source")
    p.add_argument("--run")
    p.add_argument("--profile", choices=["hizli", "standart", "yuksek_guvence"])
    p.add_argument("--analysis-date")
    p.add_argument("--financial-params")
    p.add_argument("--scoring-params")
    p.add_argument("--resume-request")
    p.add_argument("--supplier-folder-declaration")
    p = sub.add_parser("next")
    p.add_argument("--run", required=True)
    p = sub.add_parser("status")
    p.add_argument("--run", required=True)
    p = sub.add_parser("budget-override")
    p.add_argument("--run", required=True)
    p.add_argument("--allow", choices=["true", "false"], required=True)
    args = ap.parse_args()
    if args.cmd == "prepare":
        if args.resume_request:
            rr = json.loads(Path(args.resume_request).read_text(encoding="utf-8-sig"))
            if rr.get('schema') != 'teklif-resume/v1' or rr.get('skill_version') != _version(Path(__file__).resolve().parents[1]):
                raise ValueError('Resume request schema/skill version incompatible; no analysis started')
            source = Path(rr["source"]); run = Path(rr["run"]); profile = rr["profile"]
            params = rr.get("financial_parameters"); scoring = rr.get("scoring_parameters")
            d = date.fromisoformat(rr["analysis_date"]) if rr.get("analysis_date") else None
            response_record = Path(rr['user_response_record']) if rr.get('user_response_record') else None
            response_sha = rr.get('user_response_sha256')
            folder_declaration = Path(rr['supplier_folder_declaration']) if rr.get('supplier_folder_declaration') else None
            if folder_declaration is not None and sha256_file(folder_declaration) != rr.get('supplier_folder_declaration_sha256'):
                raise ValueError('Supplier folder declaration changed since resume request')
        else:
            if not args.source or not args.run or not args.profile:
                ap.error("prepare requires --source, --run and --profile, or --resume-request")
            source = Path(args.source); run = Path(args.run); profile = args.profile
            params = json.loads(Path(args.financial_params).read_text(encoding="utf-8-sig")) if args.financial_params else None
            scoring = json.loads(Path(args.scoring_params).read_text(encoding="utf-8-sig")) if args.scoring_params else None
            d = date.fromisoformat(args.analysis_date) if args.analysis_date else None
            response_record = None; response_sha = None
            folder_declaration = Path(args.supplier_folder_declaration) if args.supplier_folder_declaration else None
        result = prepare(source, run, profile, d, params, scoring, response_record, response_sha, folder_declaration)
    elif args.cmd == "next":
        result = advance(Path(args.run))
    elif args.cmd == "budget-override":
        set_meta(Path(args.run), "budget_override", args.allow)
        result = {"status": "OK", "budget_override": args.allow == "true"}
    else:
        result = status(Path(args.run))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    s = str(result.get("status") or "")
    if s in {"PRELIMINARY"}:
        raise SystemExit(2)
    if s in {"BLOCKED_ENVIRONMENT"}:
        raise SystemExit(3)
    if s in {"BLOCKED", "MANUAL_REVIEW_REQUIRED", "BUDGET_EXHAUSTED"}:
        raise SystemExit(4)


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
