from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, get_meta, rows_as_dict

BAD = {"missing", "unreadable", "conflicting", "requires_confirmation"}


def _add_task(
    con,
    phase: str,
    role: str,
    task_kind: str,
    payload: dict[str, Any],
    *,
    document_id: str | None = None,
    offer_id: str | None = None,
    requirement_id: str | None = None,
    priority: int = 100,
    critical: bool = False,
) -> str:
    key = json_text(payload)
    task_id = stable_id("task", phase, role, task_kind, document_id or "", offer_id or "", requirement_id or "", key, length=24)
    exists = con.execute("SELECT status FROM task_queue WHERE task_id=?", [task_id]).fetchone()
    if exists:
        return task_id
    con.execute(
        """
        INSERT INTO task_queue(task_id,phase,role,task_kind,document_id,offer_id,requirement_id,payload_json,priority,critical,status,attempts,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        [task_id, phase, role, task_kind, document_id, offer_id, requirement_id, key, priority, critical, "pending", 0, utc_now()],
    )
    return task_id


def _requirements_tasks(con, counts: dict[str, int], chunk_units: int = 12) -> None:
    specs = rows_as_dict(con, "SELECT document_id,filename,parse_status FROM documents WHERE active=true AND document_role='specification'")
    req_count = con.execute("SELECT count(*) FROM requirements").fetchone()[0]
    pending = con.execute("SELECT count(*) FROM task_queue WHERE task_kind='requirements_extraction' AND status IN ('pending','completed')").fetchone()[0]
    if not specs or req_count or pending:
        return
    for d in specs:
        max_unit = con.execute("SELECT coalesce(max(unit_index),0) FROM document_units WHERE document_id=?", [d["document_id"]]).fetchone()[0]
        if not max_unit:
            _add_task(
                con,
                "REQUIREMENTS",
                "visual_exception",
                "visual_source_review",
                {"document_id": d["document_id"], "goal": "Read the specification visually and extract atomic requirements with exact evidence."},
                document_id=d["document_id"],
                priority=15,
                critical=True,
            )
            counts["visual_source_review"] = counts.get("visual_source_review", 0) + 1
            continue
        for start in range(1, int(max_unit) + 1, chunk_units):
            end = min(int(max_unit), start + chunk_units - 1)
            _add_task(
                con,
                "REQUIREMENTS",
                "difficult_semantics",
                "requirements_extraction",
                {
                    "document_id": d["document_id"],
                    "unit_start": start,
                    "unit_end": end,
                    "goal": "Extract every atomic requirement in this bounded unit range with category, critical flag, exact evidence locator and short quote. Do not summarize away requirements.",
                },
                document_id=d["document_id"],
                priority=20,
                critical=True,
            )
            counts["requirements_extraction"] = counts.get("requirements_extraction", 0) + 1


def _offer_field_tasks(con, counts: dict[str, int]) -> None:
    offers = rows_as_dict(con, "SELECT offer_id,supplier_id FROM offers WHERE status='active'")
    for off in offers:
        # Offer-level fields only: requirement assessments are not offer fields. A field the
        # model already answered (even as missing/requires_confirmation) is final here; its gap
        # travels as an RFI/independent review, so it is not asked again in a loop.
        facts = rows_as_dict(con, "SELECT field_key,evidence_status,extraction_path FROM facts WHERE offer_id=? AND requirement_id IS NULL", [off["offer_id"]])
        unresolved = sorted({f["field_key"] for f in facts if f["evidence_status"] in BAD and (f.get("extraction_path") or "deterministic") == "deterministic"})
        if not unresolved:
            continue
        docs = rows_as_dict(con, "SELECT document_id,format_family,parse_status FROM documents WHERE offer_id=? AND active=true", [off["offer_id"]])
        doc_ids = [d["document_id"] for d in docs if d["parse_status"] != "unreadable" and d["format_family"] != "image"]
        if not doc_ids:
            continue
        _add_task(
            con,
            "EXTRACT",
            "semantic_extraction",
            "offer_semantic_fields",
            {
                "offer_id": off["offer_id"],
                "document_ids": doc_ids,
                "fields": unresolved,
                "goal": "Resolve only listed fields from cited evidence. Preserve missing/unreadable/conflicting when the source does not support a value. Return scope items and RFIs only when evidenced.",
            },
            offer_id=off["offer_id"],
            priority=30,
            critical=True,
        )
        counts["offer_semantic_fields"] = counts.get("offer_semantic_fields", 0) + 1


def _requirement_assessment_tasks(con, counts: dict[str, int], chunk_size: int = 20) -> None:
    reqs = rows_as_dict(con, "SELECT requirement_id,critical FROM requirements ORDER BY requirement_id")
    if not reqs:
        return
    offers = rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active'")
    for off in offers:
        existing = {r["requirement_id"] for r in rows_as_dict(con, "SELECT requirement_id FROM facts WHERE offer_id=? AND requirement_id IS NOT NULL", [off["offer_id"]])}
        pending_ids = [r["requirement_id"] for r in reqs if r["requirement_id"] not in existing]
        docs = [r["document_id"] for r in rows_as_dict(con, "SELECT document_id FROM documents WHERE offer_id=? AND active=true AND parse_status <> 'unreadable'", [off["offer_id"]])]
        for i in range(0, len(pending_ids), chunk_size):
            chunk = pending_ids[i : i + chunk_size]
            if not chunk:
                continue
            _add_task(
                con,
                "EXTRACT",
                "difficult_semantics",
                "requirement_assessment",
                {
                    "offer_id": off["offer_id"],
                    "document_ids": docs,
                    "requirement_ids": chunk,
                    "goal": "Assess only listed requirements against the offer. Use value_text compliant/noncompliant/partial/not_stated/not_applicable/conflict/requires_rfi and cite exact offer evidence where available.",
                },
                offer_id=off["offer_id"],
                priority=35,
                critical=any(r["critical"] for r in reqs if r["requirement_id"] in chunk),
            )
            counts["requirement_assessment"] = counts.get("requirement_assessment", 0) + 1


def _visual_and_classification_tasks(con, counts: dict[str, int]) -> None:
    visual_docs = rows_as_dict(
        con,
        "SELECT document_id,format_family,parse_status,metadata_json,document_role,offer_id FROM documents WHERE active=true AND document_role<>'unknown' AND (format_family='image' OR parse_status='partial')",
    )
    for d in visual_docs:
        try:
            meta = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            meta = {}
        needs = d["format_family"] == "image" or bool(meta.get("needs_visual_pages"))
        if needs:
            _add_task(
                con,
                "EXTRACT",
                "visual_exception",
                "visual_source_review",
                {
                    "document_id": d["document_id"],
                    "needs_visual_pages": meta.get("needs_visual_pages", []),
                    "goal": "Read only unresolved visual regions/pages. Return strict evidence/facts; critical numbers read from pixels require confirmation unless cross-validated.",
                },
                document_id=d["document_id"],
                offer_id=d.get("offer_id"),
                priority=25,
                critical=True,
            )
            counts["visual_source_review"] = counts.get("visual_source_review", 0) + 1

    unknown_docs = rows_as_dict(con, """SELECT d.document_id,d.filename,d.format_family,d.metadata_json FROM documents d
        LEFT JOIN suppliers s ON s.supplier_id=d.supplier_id WHERE d.active=true
        AND (d.document_role='unknown' OR (d.document_role='offer' AND s.identification_status='provisional'))""")
    for d in unknown_docs:
        try:
            metadata = json.loads(d.get("metadata_json") or "{}")
        except Exception:
            metadata = {}
        visual_pages = metadata.get("needs_visual_pages") or []
        visual = d["format_family"] == "image" or (d["format_family"] == "pdf" and bool(visual_pages))
        instructions = {"document_id": d["document_id"], "goal": "Classify document role only: offer/specification/boq/correspondence/support/unrelated."}
        if visual_pages:
            instructions["needs_visual_pages"] = visual_pages
        _add_task(
            con,
            "PREPARE",
            "visual_exception" if visual else "semantic_extraction",
            "document_classification",
            instructions,
            document_id=d["document_id"],
            priority=10,
            critical=False,
        )
        counts["document_classification"] = counts.get("document_classification", 0) + 1


def generate_initial_tasks(run_root: Path, profile: str) -> dict[str, int]:
    con = connect(run_root)
    counts: dict[str, int] = {}
    try:
        _requirements_tasks(con, counts)
        _offer_field_tasks(con, counts)
        _requirement_assessment_tasks(con, counts)
        _visual_and_classification_tasks(con, counts)
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    return counts


def _secondary_pdf_maps(run_root: Path) -> tuple[set[tuple[str, int]], set[str]]:
    meta = get_meta(run_root, "secondary_pdf_review_done", {}, parse_json=True) or {}
    matched: set[tuple[str, int]] = set()
    available_docs: set[str] = set()
    for doc in meta.get("results", []) if isinstance(meta, dict) else []:
        did = doc.get("document_id")
        if did and doc.get("available"):
            available_docs.add(did)
            bad = {int(x.get("page")) for x in doc.get("mismatches", []) if x.get("page") is not None}
            for x in doc.get("matched_pages", []):
                if x.get("page") is not None and int(x["page"]) not in bad:
                    matched.add((did, int(x["page"])))
    return matched, available_docs



def generate_specialist_tasks(run_root: Path) -> dict[str, int]:
    """Create bounded high-assurance specialist tasks only when source signals justify them."""
    con = connect(run_root)
    counts: dict[str, int] = {}
    try:
        # Technical exceptions: only non-clean requirement judgments, never the whole matrix.
        rows = rows_as_dict(con, """
            SELECT f.offer_id,f.fact_id,f.requirement_id,f.value_text,f.evidence_status
            FROM facts f
            WHERE f.requirement_id IS NOT NULL
              AND (lower(coalesce(f.value_text,'')) IN ('partial','noncompliant','conflict','requires_rfi','kismen','uygunsuz')
                   OR f.evidence_status IN ('conflicting','requires_confirmation'))
            ORDER BY f.offer_id,f.requirement_id
        """)
        by_offer: dict[str, list[str]] = {}
        for r in rows:
            if r.get('offer_id'):
                by_offer.setdefault(r['offer_id'], []).append(r['fact_id'])
        for offer_id, fact_ids in by_offer.items():
            doc_ids = [r['document_id'] for r in rows_as_dict(con, "SELECT DISTINCT e.document_id FROM facts f JOIN evidence e ON e.evidence_id=f.evidence_id WHERE f.fact_id IN (%s)" % ','.join('?' for _ in fact_ids[:30]), fact_ids[:30])] if fact_ids[:30] else []
            _add_task(con, 'REVIEW', 'technical_exception', 'technical_exception', {
                'offer_id': offer_id, 'fact_ids': fact_ids[:30], 'document_ids': doc_ids,
                'goal': 'Review only these technical exception facts against cited evidence. Return corrections/open issues only; do not re-read clean requirements.'
            }, offer_id=offer_id, priority=42, critical=True)
            counts['technical_exception'] = counts.get('technical_exception',0)+1

        # Contract exceptions: retrieve only units with contract/risk signals.
        terms = ['ceza','penalty','teminat','guarantee','garanti','warranty','fesih','termination','sorumluluk','liability','mucbir','force majeure','tahkim','arbitration','kabul','acceptance','avans','advance']
        docs = rows_as_dict(con, "SELECT document_id,offer_id FROM documents WHERE active=true AND offer_id IS NOT NULL AND parse_status<>'unreadable'")
        for d in docs:
            hit = False
            for term in terms:
                if con.execute("SELECT count(*) FROM document_units WHERE document_id=? AND lower(coalesce(text_content,'')) LIKE ?", [d['document_id'], f'%{term}%']).fetchone()[0]:
                    hit = True; break
            if not hit:
                continue
            _add_task(con, 'REVIEW', 'contract_exception', 'contract_exception', {
                'offer_id': d['offer_id'], 'document_ids': [d['document_id']], 'query_terms': terms,
                'goal': 'Review only retrieved contract-risk clauses. Identify source-backed deviations, red-line candidates and RFIs; do not invent legal requirements, rates or percentages.'
            }, document_id=d['document_id'], offer_id=d['offer_id'], priority=44, critical=False)
            counts['contract_exception'] = counts.get('contract_exception',0)+1
        if hasattr(con,'commit'): con.commit()
    finally:
        con.close()
    return counts

def generate_review_tasks(run_root: Path, profile: str, chunk_size: int = 20) -> dict[str, int]:
    if profile == "hizli":
        return {}
    matched_pdf_pages, pdf_secondary_available = _secondary_pdf_maps(run_root)
    con = connect(run_root)
    counts: dict[str, int] = {}
    try:
        offers = rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active'")
        for off in offers:
            facts = rows_as_dict(
                con,
                """SELECT f.fact_id,f.evidence_status,f.extraction_path,f.requirement_id,e.document_id,e.locator_json,d.format_family
                FROM facts f
                LEFT JOIN evidence e ON e.evidence_id=f.evidence_id
                LEFT JOIN documents d ON d.document_id=e.document_id
                WHERE f.offer_id=? AND f.critical=true AND f.evidence_status='verified'
                ORDER BY f.fact_id""",
                [off["offer_id"]],
            )
            fact_ids = []
            for fact in facts:
                path = fact.get("extraction_path")
                fmt = fact.get("format_family")
                # Semantic and visual judgments always receive independent review in standard/high profiles.
                if path in {"semantic_llm", "vision"} or fact.get("requirement_id"):
                    fact_ids.append(fact["fact_id"]); continue
                if profile == "standart":
                    # Deterministic structured extraction is accepted without a second LLM pass.
                    continue
                # High assurance: deterministic PDF facts can skip LLM review only when the independent
                # DuckDB PDF path matched the exact cited page. Structured spreadsheet/CSV facts are
                # mechanically verified and do not need a second language-model reading.
                if fmt in {"xlsx", "xls", "csv", "tsv", "docx", "doc", "text"}:
                    continue
                if fmt == "pdf" and fact.get("document_id") in pdf_secondary_available:
                    try:
                        loc = json.loads(fact.get("locator_json") or "{}")
                        page = int(loc.get("page")) if loc.get("page") is not None else None
                    except Exception:
                        page = None
                    if page is not None and (fact["document_id"], page) in matched_pdf_pages:
                        continue
                fact_ids.append(fact["fact_id"])
            for i in range(0, len(fact_ids), chunk_size):
                chunk = fact_ids[i : i + chunk_size]
                if not chunk:
                    continue
                _add_task(
                    con,
                    "REVIEW",
                    "difficult_semantics",
                    "independent_fact_review",
                    {
                        "offer_id": off["offer_id"],
                        "fact_ids": chunk,
                        "blind": True,
                        "goal": "Independently verify only listed critical facts against their original cited evidence. Do not see supplier recommendation or decision summary.",
                    },
                    offer_id=off["offer_id"],
                    priority=50,
                    critical=True,
                )
                counts["independent_fact_review"] = counts.get("independent_fact_review", 0) + 1
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    return counts

def generate_decision_summary_task(run_root: Path) -> str:
    con = connect(run_root)
    try:
        task_id = _add_task(
            con,
            "REPORT",
            "decision_summary",
            "decision_summary",
            {"goal": "Write a concise source-backed procurement decision summary from the bounded decision packet. Return structured claims. Every factual/calculated claim must cite fact_ids and/or calculation_ids from the packet; recommendations must cite support and are forbidden when decision_status is PRELIMINARY_ONLY. Assumptions/hypotheses require an explicit caveat. If decision_status is PRELIMINARY_ONLY, recommendation must be null."},
            priority=90,
            critical=False,
        )
        if hasattr(con, "commit"):
            con.commit()
        return task_id
    finally:
        con.close()


def retry_decision_summary(run_root: Path) -> dict[str, Any]:
    """Create a bounded replacement task; retain the completed invalid result."""
    from claim_registry import rebuild
    registry = rebuild(run_root)
    if registry.get("status") != "FAIL":
        return {"status": "NO_RETRY_REQUIRED"}
    policy = json.loads((Path(__file__).resolve().parents[1] / "config/policy.json").read_text(encoding="utf-8"))
    profile = str(get_meta(run_root, "profile", "standart"))
    limit = int(policy.get("profiles", {}).get(profile, {}).get("max_revisions", 0))
    con = connect(run_root)
    try:
        active = con.execute("SELECT value FROM run_meta WHERE key='decision_summary_task_id'").fetchone()
        if active:
            parent = rows_as_dict(con, "SELECT * FROM task_queue WHERE task_id=? AND task_kind='decision_summary' AND status='completed'", [active[0]])
        else:
            parent = rows_as_dict(con, "SELECT * FROM task_queue WHERE task_kind='decision_summary' AND status='completed' ORDER BY completed_at DESC,task_id DESC LIMIT 1")
        if not parent:
            return {"status": "BLOCKED", "reason": "Unsupported summary has no completed source task", "claim_registry": registry}
        parent = parent[0]
        pending = rows_as_dict(con, "SELECT task_id,payload_json FROM task_queue WHERE task_kind='decision_summary' AND status='pending'")
        for row in pending:
            if json.loads(row["payload_json"]).get("retry_parent_task_id") == parent["task_id"]:
                return {"status": "RETRY_PENDING", "task_id": row["task_id"], "claim_registry": registry}
        prior = json.loads(parent.get("payload_json") or "{}")
        revision = int(prior.get("semantic_revision", 0)) + 1
        if revision > limit:
            return {"status": "MANUAL_REVIEW_REQUIRED", "reason": "decision summary semantic revision limit reached",
                    "max_revisions": limit, "claim_registry": registry}
        feedback = [{"claim_id": x.get("claim_id"), "reasons": x.get("reasons", [])} for x in registry.get("unsupported", [])]
        payload = {"goal": "Replace the unsupported summary with a concise source-backed decision summary from the canonical packet. Every factual/calculated claim must bind existing fact/calculation IDs and assertions; omit unsupported statements. Recommendation must be null for preliminary decisions.",
                   "retry_parent_task_id": parent["task_id"], "semantic_revision": revision, "validation_feedback": feedback}
        tid = _add_task(con, "REPORT", "decision_summary", "decision_summary", payload, priority=90)
        con.commit()
        return {"status": "RETRY_PENDING", "task_id": tid, "semantic_revision": revision, "claim_registry": registry}
    finally:
        con.close()


def pending_tasks(run_root: Path) -> list[dict[str, Any]]:
    con = connect(run_root)
    try:
        return rows_as_dict(
            con,
            "SELECT task_id,phase,role,task_kind,document_id,offer_id,requirement_id,payload_json,priority,critical,attempts FROM task_queue WHERE status='pending' ORDER BY priority,critical DESC,created_at,task_id",
        )
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Create and inspect bounded LLM task queue")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("generate")
    p.add_argument("--run", required=True)
    p.add_argument("--profile", required=True, choices=["hizli", "standart", "yuksek_guvence"])
    p = sub.add_parser("review")
    p.add_argument("--run", required=True)
    p.add_argument("--profile", required=True, choices=["hizli", "standart", "yuksek_guvence"])
    p = sub.add_parser("decision")
    p.add_argument("--run", required=True)
    p = sub.add_parser("pending")
    p.add_argument("--run", required=True)
    args = ap.parse_args()
    if args.cmd == "generate":
        print(json.dumps(generate_initial_tasks(Path(args.run), args.profile), ensure_ascii=False, indent=2))
    elif args.cmd == "review":
        print(json.dumps(generate_review_tasks(Path(args.run), args.profile), ensure_ascii=False, indent=2))
    elif args.cmd == "decision":
        print(json.dumps({"task_id": generate_decision_summary_task(Path(args.run))}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(pending_tasks(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
