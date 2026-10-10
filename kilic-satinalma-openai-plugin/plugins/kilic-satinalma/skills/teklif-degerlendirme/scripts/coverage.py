from __future__ import annotations
from active_records import current_claims

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from common import json_text, sha256_file, stable_id, utc_now
from db import connect, get_meta, rows_as_dict
from reviewed_snapshot import load_latest
from scope_ledger import buyer_currency_authority

CATEGORIES = [
    "source-authority",
    "value-accuracy",
    "evidence-integrity",
    "independent-review",
    "data-quality",
    "cross-output-consistency",
    "conclusion-support",
    "visual-qa",
    "decision-completeness",
    "comparability",
    "independent-calculation",
    "cost-bridge",
    "grain-integrity",
    "claim-support",
    "reviewed-snapshot",
    "provenance-survival",
    "scope-completeness",
]


def _hash(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _check(state: str, *evidence: str, note: str | None = None) -> dict[str, Any]:
    out = {"state": state, "evidence": [x for x in evidence if x]}
    if note:
        out["note"] = note
    return out


def build(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        profile = str(get_meta(run_root, "profile", "standart"))
        facts = rows_as_dict(con, "SELECT * FROM facts ORDER BY fact_id")
        requirements = rows_as_dict(con, "SELECT * FROM requirements ORDER BY requirement_id")
        evidence = {r["evidence_id"]: r for r in rows_as_dict(con, "SELECT * FROM evidence")}
        docs = {r["document_id"]: r for r in rows_as_dict(con, "SELECT document_id,sha256,document_role,parse_status FROM documents")}
        authority = {r["document_id"]: r for r in rows_as_dict(con, "SELECT * FROM source_authority")}
        dq = rows_as_dict(con, "SELECT * FROM data_quality_findings WHERE status='open'")
        dq_by_entity: dict[str, list[dict[str, Any]]] = {}
        for f in dq:
            if f.get("entity_id"):
                dq_by_entity.setdefault(str(f["entity_id"]), []).append(f)
        reviews = rows_as_dict(con, "SELECT review_id,fact_id,evidence_status FROM review_facts")
        reviewed = {r["fact_id"] for r in reviews}
        open_diffs = {r["fact_id"] for r in rows_as_dict(con, "SELECT fact_id FROM differences WHERE status='open' AND fact_id IS NOT NULL")}
        review_scope: set[str] = set()
        for t in rows_as_dict(con, "SELECT payload_json FROM task_queue WHERE task_kind='independent_fact_review'"):
            try:
                review_scope.update(json.loads(t["payload_json"] or "{}").get("fact_ids", []))
            except Exception:
                pass

        units: list[dict[str, Any]] = []
        for f in facts:
            ev = evidence.get(f.get("evidence_id")) if f.get("evidence_id") else None
            doc = docs.get(ev.get("document_id")) if ev else None
            auth = authority.get(ev.get("document_id")) if ev else None
            revision = _hash({
                "fact": {k: f.get(k) for k in ["fact_id","offer_id","requirement_id","field_key","value_text","value_number","value_date","unit","currency","evidence_status","critical","evidence_id","extraction_path"]},
                "source_sha256": (doc or {}).get("sha256"),
            })
            cats: dict[str, Any] = {}
            if ev:
                auth_state = (auth or {}).get("authority_status")
                if auth_state in {"controlling", "supplemental", "candidate", "superseded"}:
                    cats["source-authority"] = _check("passed", f"authority:{ev.get('document_id')}:{auth_state}")
                elif auth_state in {"needs_input", "unusable"}:
                    cats["source-authority"] = _check("failed", f"authority:{ev.get('document_id')}:{auth_state}")
                else:
                    cats["source-authority"] = _check("unverified", note="No resolved authority record for evidence source.")
            else:
                cats["source-authority"] = _check("unverified", note="Fact has no source evidence.")

            if f.get("evidence_status") == "verified":
                cats["value-accuracy"] = _check("passed", f"fact:{f['fact_id']}:verified")
            elif f.get("evidence_status") in {"conflicting", "unreadable"}:
                cats["value-accuracy"] = _check("failed", f"fact:{f['fact_id']}:{f.get('evidence_status')}")
            else:
                cats["value-accuracy"] = _check("unverified", f"fact:{f['fact_id']}:{f.get('evidence_status')}")

            if f.get("evidence_status") == "verified" and ev and doc and ev.get("source_sha256") == doc.get("sha256"):
                cats["evidence-integrity"] = _check("passed", f"evidence:{ev['evidence_id']}", f"sha256:{doc['sha256']}")
            elif f.get("evidence_status") == "verified":
                cats["evidence-integrity"] = _check("failed", f"fact:{f['fact_id']}")
            else:
                cats["evidence-integrity"] = _check("unverified", note="Non-verified fact does not have a completed evidence-integrity acceptance.")

            if f["fact_id"] in review_scope:
                if f["fact_id"] in open_diffs:
                    cats["independent-review"] = _check("failed", f"difference:{f['fact_id']}")
                elif f["fact_id"] in reviewed:
                    cats["independent-review"] = _check("passed", f"review:{f['fact_id']}")
                else:
                    cats["independent-review"] = _check("unverified", note="Fact is in independent-review scope but no completed review observation exists.")

            entity_dq = dq_by_entity.get(f["fact_id"], [])
            from effective_fields import basis as effective_basis
            qualified=(f.get('evidence_status') in {'missing','requires_confirmation'} and
                       all(x.get('check_id')=='critical_fact_incomplete' for x in entity_dq) and
                       not any(c['state']=='failed' for c in cats.values()))
            buyer_basis=effective_basis(con,f.get('offer_id'),f.get('field_key')) if qualified else None
            if buyer_basis:
                cats["data-quality"] = _check("unverified", *[f"dq:{x['finding_id']}" for x in entity_dq],
                    f"evaluation_basis:{buyer_basis['method']}", f"calculation:{buyer_basis['calculation_id']}",
                    note="Supplier source field remains unverified; exact scoped buyer declaration supports only the separate evaluation basis. Unknown dates remain unknown.")
            elif any(x.get("severity") in {"critical", "high"} for x in entity_dq):
                cats["data-quality"] = _check("failed", *[f"dq:{x['finding_id']}" for x in entity_dq])
            elif entity_dq:
                cats["data-quality"] = _check("unverified", *[f"dq:{x['finding_id']}" for x in entity_dq], note="Only medium/low quality findings observed.")
            else:
                cats["data-quality"] = _check("passed", "dq:no-observed-finding", note="No open data-quality finding observed for this fact; not a proof of exhaustive quality coverage.")

            units.append({"id": f["fact_id"], "kind": "fact", "critical": bool(f.get("critical")) and not bool(buyer_basis), "revision": revision, "categories": cats,
                          "evaluation_basis":buyer_basis,"source_limitation_retained":bool(buyer_basis)})
            if buyer_basis:
                proof='evaluation_basis_sha256:'+_hash(buyer_basis)
                units.append({'id':f['fact_id']+'/evaluation-basis','kind':'evaluation_basis','critical':bool(f.get('critical')),
                              'revision':_hash(buyer_basis),'basis':buyer_basis,
                              'categories':{
                                  'source-authority':_check('passed',proof,note=buyer_basis['rationale']),
                                  'value-accuracy':_check('passed',f"calculation:{buyer_basis['calculation_id']}",note='Effective basis checked; supplier observation retained separately.'),
                                  'evidence-integrity':_check('passed',proof),
                                  'independent-calculation':_check('passed',f"independent:{buyer_basis['independent_id']}"),
                                  'data-quality':_check('passed',proof,note='Only the separate effective basis is accepted; source limitations remain unverified.')
                              }})

        active_offers = [r["offer_id"] for r in rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active' ORDER BY offer_id")]
        for req in requirements:
            assessed = rows_as_dict(con, "SELECT fact_id,offer_id,evidence_status,value_text FROM facts WHERE requirement_id=?", [req["requirement_id"]])
            by_offer = {r.get("offer_id"): r for r in assessed}
            missing = [o for o in active_offers if o not in by_offer]
            bad = [r for r in assessed if r.get("evidence_status") in {"conflicting","unreadable","requires_confirmation"}]
            state = "passed" if not missing and not bad else ("failed" if bad else "unverified")
            ev = evidence.get(req.get("evidence_id")) if req.get("evidence_id") else None
            auth = authority.get(ev.get("document_id")) if ev else None
            authority_state = "passed" if (auth or {}).get("authority_status") == "controlling" else "unverified"
            units.append({
                "id": req["requirement_id"], "kind": "requirement", "critical": bool(req.get("critical")),
                "revision": _hash({"requirement": req, "source": (docs.get(ev.get('document_id')) if ev else None)}),
                "categories": {
                    "source-authority": _check(authority_state, f"authority:{(ev or {}).get('document_id') or 'none'}"),
                    "decision-completeness": _check(state, *[f"assessment:{x['fact_id']}" for x in assessed], note=(f"Missing offers: {missing}" if missing else None)),
                },
            })

        # Output and conclusion units.
        consistency = rows_as_dict(con, "SELECT relative_path FROM artifacts WHERE artifact_type='cross_output_consistency' AND status='ready' ORDER BY created_at DESC")
        consistency_obj = None
        if consistency:
            try:
                consistency_obj = json.loads((run_root / consistency[0]["relative_path"]).read_text(encoding="utf-8"))
            except Exception:
                consistency_obj = None
        xlsx = rows_as_dict(con, "SELECT * FROM artifacts WHERE artifact_type='xlsx' AND status='ready' ORDER BY created_at DESC")
        if xlsx:
            units.append({
                "id": xlsx[0]["artifact_id"], "kind": "artifact", "critical": True, "revision": xlsx[0]["sha256"],
                "categories": {"cross-output-consistency": _check("passed" if consistency_obj and consistency_obj.get("status")=="PASS" else "failed", "artifact:cross_output_consistency")},
            })
        pdf = rows_as_dict(con, "SELECT * FROM artifacts WHERE artifact_type='pdf' AND status='ready' ORDER BY created_at DESC")
        if pdf:
            # Absence of pending rows is not proof that any/all PDF pages were reviewed.
            visual_state = "unverified"
            visual_note = "PDF page coverage could not be determined."
            try:
                from pypdf import PdfReader
                pdf_path = run_root / pdf[0]["relative_path"]
                expected = {f"page:{i+1}" for i in range(len(PdfReader(str(pdf_path)).pages))}
                render_rows = rows_as_dict(con, "SELECT render_key,qa_status FROM render_hashes WHERE artifact_id=?", [pdf[0]["artifact_id"]])
                observed = {r["render_key"]: r["qa_status"] for r in render_rows}
                missing = expected - set(observed)
                failed = {key for key in expected if observed.get(key) in {"fail", "FAIL"}}
                if sha256_file(pdf_path) != pdf[0]["sha256"] or failed:
                    visual_state = "failed"
                elif expected and not missing and all(observed.get(key) == "pass" for key in expected):
                    visual_state = "passed"
                visual_note = f"expected_pages:{len(expected)}; reviewed_pass:{sum(observed.get(key)=='pass' for key in expected)}; missing_pages:{len(missing)}"
            except Exception as exc:
                visual_note = f"PDF page coverage unavailable: {type(exc).__name__}"
            units.append({
                "id": pdf[0]["artifact_id"], "kind": "artifact", "critical": profile=="yuksek_guvence", "revision": pdf[0]["sha256"],
                "categories": {"visual-qa": _check(visual_state, f"artifact:{pdf[0]['artifact_id']}", note=visual_note)},
            })

        summary = get_meta(run_root, "decision_summary", None)
        recommendation = get_meta(run_root, "decision_recommendation", "null")
        open_critical = con.execute("SELECT count(*) FROM open_issues WHERE status='open' AND severity='critical'").fetchone()[0]
        decision_status = get_meta(run_root, "decision_status", "UNKNOWN")
        summary_state = "passed" if summary is not None and not (decision_status=="PRELIMINARY_ONLY" and recommendation != "null") else "failed"
        units.append({
            "id": "decision-summary", "kind": "claim", "critical": True,
            "revision": _hash({"summary":summary,"recommendation":recommendation,"decision_status":decision_status,"open_critical":open_critical}),
            "categories": {"conclusion-support": _check(summary_state, f"decision_status:{decision_status}", f"open_critical:{open_critical}")},
        })

        # v5.0.4 deterministic control units.
        comp = get_meta(run_root, "comparability_contract", {}, parse_json=True) or {}
        units.append({
            "id": "comparison-contract", "kind": "control", "critical": True,
            "revision": _hash(comp),
            "categories": {"comparability": _check("passed" if comp.get("ranking_allowed") else "failed", "run_meta:comparability_contract")},
        })
        for ic in rows_as_dict(con, "SELECT independent_id,calculation_id,offer_id,calculation_type,status,input_hash FROM independent_calculations ORDER BY independent_id"):
            units.append({
                "id": ic["independent_id"], "kind": "control", "critical": True,
                "revision": _hash(ic),
                "categories": {"independent-calculation": _check("passed" if ic["status"]=="pass" else ("failed" if ic["status"]=="fail" else "unverified"), f"calculation:{ic['calculation_id']}")},
            })
        for b in rows_as_dict(con, "SELECT bridge_id,offer_id,status,residual,tolerance,revision FROM cost_bridges ORDER BY bridge_id"):
            units.append({
                "id": b["bridge_id"], "kind": "control", "critical": True, "revision": b["revision"],
                "categories": {"cost-bridge": _check("passed" if b["status"]=="pass" else ("failed" if b["status"]=="fail" else "unverified"), f"residual:{b.get('residual')}", f"tolerance:{b.get('tolerance')}")},
            })
        for g in rows_as_dict(con, "SELECT check_id,relation_name,status,critical,revision FROM grain_checks ORDER BY check_id"):
            units.append({
                "id": g["check_id"], "kind": "control", "critical": bool(g["critical"]), "revision": g["revision"],
                "categories": {"grain-integrity": _check("passed" if g["status"]=="pass" else "failed", f"grain:{g['relation_name']}")},
            })
        for c in current_claims(con, "claim_id,claim_type,support_status,revision"):
            st = "passed" if c["support_status"] in {"verified","qualified"} else "failed"
            units.append({"id":c["claim_id"],"kind":"claim","critical":c["claim_type"] in {"observation","calculated","recommendation"},"revision":c["revision"],"categories":{"claim-support":_check(st,f"claim:{c['claim_id']}:{c['support_status']}")}})
        try:
            _, active_snapshot = load_latest(run_root)
            snap = [active_snapshot]
        except (RuntimeError, ValueError, OSError):
            snap = []
        if snap:
            units.append({"id":snap[0]["snapshot_id"],"kind":"control","critical":True,"revision":snap[0]["source_revision"],"categories":{"reviewed-snapshot":_check("passed",f"sha256:{snap[0]['sha256']}")}})
        else:
            units.append({"id":"reviewed-snapshot","kind":"control","critical":True,"revision":"missing","categories":{"reviewed-snapshot":_check("failed","snapshot:missing")}})
        prov = rows_as_dict(con, "SELECT relative_path,sha256 FROM artifacts WHERE artifact_type='provenance_survival' AND status='ready' ORDER BY created_at DESC")
        if prov:
            try: pobj=json.loads((run_root/prov[0]["relative_path"]).read_text(encoding="utf-8"))
            except Exception: pobj={}
            units.append({"id":"provenance-survival","kind":"control","critical":True,"revision":prov[0]["sha256"],"categories":{"provenance-survival":_check("passed" if pobj.get("status")=="PASS" else "failed",f"artifact:{prov[0]['sha256']}")}})
        scope_art = rows_as_dict(con, "SELECT relative_path,sha256 FROM artifacts WHERE artifact_type='scope_ledger_final' AND status='ready' ORDER BY created_at DESC")
        if scope_art:
            try: sobj=json.loads((run_root/scope_art[0]["relative_path"]).read_text(encoding="utf-8"))
            except Exception: sobj={}
            st="passed" if not sobj.get("blocking_gaps") else "failed"
            units.append({"id":"scope-ledger-final","kind":"control","critical":True,"revision":scope_art[0]["sha256"],"categories":{"scope-completeness":_check(st,f"artifact:{scope_art[0]['sha256']}")}})

        category_summary: dict[str, Any] = {}
        for cat in CATEGORIES:
            applicable = [(u, u["categories"][cat]) for u in units if cat in u.get("categories", {})]
            if not applicable:
                category_summary[cat] = {"applicable": False, "observed_defects": "N/A", "assessment": "No scoped units for this category."}
                continue
            bad = sum(1 for _, c in applicable if c["state"] == "failed")
            unverified = sum(1 for _, c in applicable if c["state"] == "unverified")
            category_summary[cat] = {
                "applicable": True,
                "observed_defects": f"{bad} / {len(applicable)}",
                "unverified": unverified,
                "assessment": f"Observed defects are bad/total scoped units. 0/{len(applicable)} does not mean every unit was fully verified; {unverified} unit(s) remain unverified." if bad==0 else f"{bad} scoped unit(s) have demonstrated open defects; {unverified} additional unit(s) remain unverified.",
            }

        blocking = []
        for u in units:
            for cat, c in u.get("categories", {}).items():
                if c["state"] == "failed" and (u.get("critical") or cat in {"cross-output-consistency","conclusion-support","comparability","independent-calculation","cost-bridge","grain-integrity","claim-support","reviewed-snapshot","provenance-survival","scope-completeness"}):
                    blocking.append({"unit_id":u["id"],"category":cat,"state":"failed"})
                if profile == "yuksek_guvence" and u.get("critical") and c["state"] == "unverified" and cat in {"source-authority","evidence-integrity","independent-review","visual-qa","decision-completeness"}:
                    blocking.append({"unit_id":u["id"],"category":cat,"state":"unverified"})

        record = {
            "version": 1,
            "artifact": {"identity": str(run_root.name), "revision": _hash({"facts":[u["revision"] for u in units],"profile":profile}), "profile": profile},
            "inventoryComplete": True,
            "categories": category_summary,
            "units": units,
            "blocking_gaps": blocking,
            "generated_at": utc_now(),
        }
        out = run_root / "qa" / "coverage.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        aid=stable_id("art","coverage",sha256_file(out),length=22)
        con.execute("INSERT OR REPLACE INTO artifacts(artifact_id,artifact_type,relative_path,sha256,parent_hashes_json,status,created_at) VALUES (?,?,?,?,?,?,?)",
                    [aid,"coverage",str(out.relative_to(run_root)),sha256_file(out),"[]","ready",utc_now()])
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('coverage_record',?)", [json_text({"path":str(out.relative_to(run_root)),"blocking_gaps":blocking,"revision":record["artifact"]["revision"]})])
        if hasattr(con,"commit"): con.commit()
        return record
    finally:
        con.close()


def main() -> None:
    ap=argparse.ArgumentParser(description="Build revision-aware procurement validation coverage record")
    ap.add_argument("--run",required=True)
    args=ap.parse_args()
    print(json.dumps(build(Path(args.run)),ensure_ascii=False,indent=2,default=str))

if __name__=='__main__':
    main()
