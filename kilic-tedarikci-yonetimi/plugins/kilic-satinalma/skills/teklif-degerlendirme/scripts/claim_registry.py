from __future__ import annotations

from question_waits import guard_run_operation

import argparse
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from common import json_text, utc_now
from active_records import current_calculations, current_claims
from db import connect, get_meta, rows_as_dict

FACTUAL = {"observation", "calculated"}


def _arr(v: Any) -> list[Any]:
    if isinstance(v, list):
        return v
    try:
        x = json.loads(v) if v else []
        return x if isinstance(x, list) else []
    except Exception:
        return []


def _hash(x: Any) -> str:
    return hashlib.sha256(json_text(x).encode()).hexdigest()


def _decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _get_path(obj: Any, path: str) -> tuple[bool, Any]:
    cur = obj
    if not path:
        return True, cur
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return False, None
    return True, cur


def _assertion_check(assertion: dict[str, Any], facts: dict[str, dict[str, Any]], calcs: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    stype = assertion.get("source_type")
    sid = assertion.get("source_id")
    path = str(assertion.get("path") or "")
    op = assertion.get("operator")
    if stype == "fact":
        src = facts.get(str(sid))
        if not src:
            return False, f"assertion source fact missing: {sid}"
        # Limit fact assertions to canonical, reviewable fields.
        allowed = {"value_text", "value_number", "value_date", "unit", "currency", "evidence_status", "field_key"}
        if path not in allowed:
            return False, f"unsupported fact assertion path: {path}"
        actual = src.get(path)
    elif stype == "calculation":
        src = calcs.get(str(sid))
        if not src:
            return False, f"assertion source calculation missing: {sid}"
        result = src.get("_result") or {}
        ok, actual = _get_path(result, path)
        if not ok:
            return False, f"calculation assertion path missing: {sid}.{path}"
    else:
        return False, f"unsupported assertion source_type: {stype}"

    if op == "exists":
        return (actual is not None), "value missing" if actual is None else ""
    if op == "contains":
        expected = assertion.get("value_text")
        if expected is None:
            return False, "contains assertion requires value_text"
        ok = str(expected).casefold() in str(actual or "").casefold()
        return ok, "text assertion mismatch" if not ok else ""
    if op in {"equals", "approx"}:
        if assertion.get("value_number") is not None:
            a = _decimal(actual)
            e = _decimal(assertion.get("value_number"))
            if a is None or e is None:
                return False, "numeric assertion source is not numeric"
            tol = _decimal(assertion.get("tolerance")) or (Decimal("0") if op == "equals" else max(Decimal("0.01"), abs(e) * Decimal("0.0001")))
            ok = abs(a - e) <= tol
            return ok, f"numeric assertion mismatch actual={a} expected={e} tolerance={tol}" if not ok else ""
        expected = assertion.get("value_text")
        if expected is None:
            return False, f"{op} assertion requires value_number or value_text"
        ok = str(actual or "") == str(expected) if op == "equals" else str(expected).casefold() in str(actual or "").casefold()
        return ok, "text assertion mismatch" if not ok else ""
    return False, f"unsupported assertion operator: {op}"


def _numeric_tokens(text: str) -> set[str]:
    """Normalize material numeric literals from prose for support binding."""
    out: set[str] = set()
    for tok in re.findall(r"(?<!\d)[-+]?(?:\d{1,3}(?:[ .]\d{3})+(?:[.,]\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)(?!\d)", text or ""):
        s = tok.replace(" ", "")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            tail = s.rsplit(",", 1)[-1]
            s = s.replace(",", "." if len(tail) <= 2 else "")
        elif "." in s and all(len(part) == 3 for part in s.split(".")[1:]):
            s = s.replace(".", "")
        try:
            out.add(str(Decimal(s).normalize()))
        except Exception:
            pass
    return out


@guard_run_operation
def rebuild(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        rows = current_claims(con)
        facts = {r["fact_id"]: r for r in rows_as_dict(con, "SELECT * FROM facts")}
        calcs: dict[str, dict[str, Any]] = {}
        for r in current_calculations(con):
            try:
                r["_result"] = json.loads(r.get("result_json") or "{}")
            except Exception:
                r["_result"] = {}
            calcs[r["calculation_id"]] = r
        reqs = {r["requirement_id"]: r for r in rows_as_dict(con, "SELECT requirement_id FROM requirements")}
        evidence = {r["evidence_id"]: r for r in rows_as_dict(con, "SELECT evidence_id,evidence_status FROM evidence")}
        decision = str(get_meta(run_root, "decision_status", "UNKNOWN"))
        checked = []
        for row in rows:
            fids = _arr(row.get("fact_ids_json")); cids = _arr(row.get("calculation_ids_json")); rids = _arr(row.get("requirement_ids_json")); eids = _arr(row.get("evidence_ids_json")); assertions = _arr(row.get("assertions_json"))
            ctype = row["claim_type"]; caveat = row.get("caveat") or ""
            missing_f = [x for x in fids if x not in facts]; bad_f = [x for x in fids if x in facts and facts[x].get("evidence_status") != "verified"]
            missing_c = [x for x in cids if x not in calcs]; bad_c = [x for x in cids if x in calcs and calcs[x].get("status") not in {"complete", "not_applicable"}]
            missing_r = [x for x in rids if x not in reqs]
            missing_e = [x for x in eids if x not in evidence]
            bad_e = [x for x in eids if x in evidence and evidence[x].get("evidence_status") != "verified"]
            status = "verified"; reasons: list[str] = []
            assertion_results = []
            for a in assertions:
                ok, reason = _assertion_check(a, facts, calcs)
                assertion_results.append({"assertion": a, "status": "pass" if ok else "fail", "reason": reason})
            # A source limitation is a checked observation about status, not a
            # positive source value. Require exact status assertions for every
            # non-verified reference; value assertions remain forbidden there.
            limitation_facts=[]
            if ctype=='observation':
                for fid in bad_f:
                    related=[a for a in assertion_results if a['assertion'].get('source_type')=='fact' and a['assertion'].get('source_id')==fid]
                    if related and all(a['status']=='pass' and a['assertion'].get('path')=='evidence_status' and
                            a['assertion'].get('operator')=='equals' and a['assertion'].get('value_text')==facts[fid]['evidence_status'] for a in related):
                        limitation_facts.append(fid)
                bad_f=[fid for fid in bad_f if fid not in limitation_facts]
            if ctype in FACTUAL:
                if not fids and not cids:
                    status = "unsupported"; reasons.append("factual claim has no fact/calculation support")
                if missing_f or bad_f or missing_c or bad_c or missing_r or missing_e or bad_e:
                    status = "unsupported"; reasons.append("referenced support missing or unresolved")
                if ctype == "calculated" and not assertions:
                    status = "unsupported"; reasons.append("calculated claim requires deterministic assertions")
                if any(x["status"] == "fail" for x in assertion_results):
                    status = "unsupported"; reasons.append("one or more deterministic claim assertions failed")
                # A numeric sentence needs an assertion for that exact number.
                # Merely pointing at an unrelated calculation ID does not prove
                # that prose such as "total is 1 EUR" is true.
                claim_numbers = _numeric_tokens(row.get("claim_text") or "")
                asserted_numbers = set()
                for ar in assertion_results:
                    a = ar.get("assertion") or {}
                    if ar.get("status") == "pass" and a.get("value_number") is not None:
                        d = _decimal(a.get("value_number"))
                        if d is not None:
                            asserted_numbers.add(str(d.normalize()))
                unbound_claim_numbers = claim_numbers - asserted_numbers
                if unbound_claim_numbers:
                    status = "unsupported"; reasons.append(f"numeric claim literals lack exact passing assertions: {sorted(unbound_claim_numbers)}")
            elif ctype == "recommendation":
                if decision != "SUFFICIENT":
                    status = "unsupported"; reasons.append("recommendation not allowed while decision is preliminary")
                elif not fids and not cids and not rids:
                    status = "unsupported"; reasons.append("recommendation has no explicit support references")
                elif missing_f or bad_f or missing_c or bad_c or missing_r or missing_e or bad_e:
                    status = "unsupported"; reasons.append("recommendation support missing or unresolved")
                if assertions and any(x["status"] == "fail" for x in assertion_results):
                    status = "unsupported"; reasons.append("recommendation assertion failed")
                claim_numbers = _numeric_tokens(row.get("claim_text") or "")
                if claim_numbers:
                    asserted_numbers = set()
                    for ar in assertion_results:
                        a = ar.get("assertion") or {}
                        if ar.get("status") == "pass" and a.get("value_number") is not None:
                            d = _decimal(a.get("value_number"))
                            if d is not None:
                                asserted_numbers.add(str(d.normalize()))
                    if claim_numbers - asserted_numbers:
                        status = "unsupported"; reasons.append("numeric recommendation literals lack exact passing assertions")
            elif ctype in {"assumption", "hypothesis"}:
                status = "qualified" if caveat else "unsupported"
                if not caveat:
                    reasons.append("assumption/hypothesis needs an explicit caveat")
            else:
                status = "unsupported"; reasons.append("unknown claim type")
            rev = _hash({
                "type": ctype, "text": row["claim_text"], "facts": fids, "calcs": cids, "reqs": rids, "evidence": eids,
                "assertions": assertions, "assertion_results": assertion_results, "caveat": caveat,
                "fact_state": [(x, (facts.get(x) or {}).get("evidence_status")) for x in fids],
                "calc_state": [(x, (calcs.get(x) or {}).get("status")) for x in cids], "decision": decision,
            })
            con.execute("UPDATE claims SET support_status=?,revision=? WHERE claim_id=?", [status, rev, row["claim_id"]])
            checked.append({
                "claim_id": row["claim_id"], "type": ctype, "status": status, "text": row["claim_text"], "reasons": reasons,
                "missing_facts": missing_f, "bad_facts": bad_f, "missing_calculations": missing_c, "bad_calculations": bad_c,
                "missing_requirements": missing_r, "missing_evidence": missing_e, "bad_evidence": bad_e, "assertions": assertion_results,
                "source_limitation_facts":limitation_facts,
            })

        unsupported = [x for x in checked if x["status"] == "unsupported"]
        # A decision summary may not introduce an unbound material number. Every
        # numeric literal in the summary must also occur in at least one verified
        # or qualified claim text whose structured support passed.
        summary = str(get_meta(run_root, "decision_summary", "") or "")
        summary_nums = _numeric_tokens(summary)
        supported_nums: set[str] = set()
        for x in checked:
            if x["status"] in {"verified", "qualified"}:
                supported_nums |= _numeric_tokens(x.get("text") or "")
        unbound_numbers = sorted(summary_nums - supported_nums)
        if unbound_numbers:
            unsupported.append({"claim_id": "decision_summary", "type": "summary", "status": "unsupported", "reasons": ["decision summary contains unbound numeric literals"], "unbound_numbers": unbound_numbers})

        out = {"status": "PASS" if not unsupported else "FAIL", "claims": checked, "unsupported": unsupported, "summary_unbound_numbers": unbound_numbers, "checked_at": utc_now()}
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('claim_registry_status',?)", [json_text(out)])
        if hasattr(con, "commit"):
            con.commit()
        return out
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate decision-summary claim support registry")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(rebuild(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    from question_waits import run_guarded_main
    raise SystemExit(run_guarded_main(main))
