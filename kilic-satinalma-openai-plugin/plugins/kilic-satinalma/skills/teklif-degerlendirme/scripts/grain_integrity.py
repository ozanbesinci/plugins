from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict


def check(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        con.execute("DELETE FROM grain_checks")
        checks: list[dict[str, Any]] = []

        def add(name: str, expected_grain: str, before: int, after: int, dbefore: int, dafter: int, status: str, critical: bool, evidence: Any) -> None:
            factor = (after / before) if before else (1.0 if after == 0 else float("inf"))
            rev = hashlib.sha256(json_text({"name":name,"before":before,"after":after,"dbefore":dbefore,"dafter":dafter,"evidence":evidence}).encode()).hexdigest()
            cid = stable_id("grain", name, rev, length=24)
            row={"check_id":cid,"check_type":"join_grain","relation_name":name,"expected_grain":expected_grain,
                 "rows_before":before,"rows_after":after,"distinct_keys_before":dbefore,"distinct_keys_after":dafter,
                 "expansion_factor":factor,"status":status,"critical":critical,"evidence_json":json_text(evidence),"revision":rev,"checked_at":utc_now()}
            checks.append(row)
            con.execute("INSERT INTO grain_checks(check_id,check_type,relation_name,expected_grain,rows_before,rows_after,distinct_keys_before,distinct_keys_after,expansion_factor,status,critical,evidence_json,revision,checked_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        [row[k] for k in ["check_id","check_type","relation_name","expected_grain","rows_before","rows_after","distinct_keys_before","distinct_keys_after","expansion_factor","status","critical","evidence_json","revision","checked_at"]])

        # Facts -> evidence must remain one row per fact when evidence IDs are unique.
        fb = con.execute("SELECT count(*) FROM facts").fetchone()[0]
        fdb = con.execute("SELECT count(DISTINCT fact_id) FROM facts").fetchone()[0]
        fa = con.execute("SELECT count(*) FROM facts f LEFT JOIN evidence e ON e.evidence_id=f.evidence_id").fetchone()[0]
        fda = con.execute("SELECT count(DISTINCT f.fact_id) FROM facts f LEFT JOIN evidence e ON e.evidence_id=f.evidence_id").fetchone()[0]
        add("facts_to_evidence", "one row per fact", fb, fa, fdb, fda, "pass" if fb==fa and fdb==fda else "fail", True, {"key":"fact_id"})

        # Requirement assessment join must not expand beyond one fact per offer/requirement grain.
        rb = con.execute("SELECT count(*) FROM facts WHERE requirement_id IS NOT NULL AND offer_id IS NOT NULL").fetchone()[0]
        rdb = con.execute("SELECT count(DISTINCT offer_id || '|' || requirement_id) FROM facts WHERE requirement_id IS NOT NULL AND offer_id IS NOT NULL").fetchone()[0]
        dup = rows_as_dict(con, "SELECT offer_id,requirement_id,count(*) AS n FROM facts WHERE requirement_id IS NOT NULL AND offer_id IS NOT NULL GROUP BY offer_id,requirement_id HAVING count(*)>1")
        add("offer_requirement_grain", "offer_id + requirement_id", rb, rb, rdb, rdb, "pass" if not dup and rb==rdb else "fail", True, {"duplicates":dup[:25]})

        # Canonical commercial facts: duplicate verified values at offer+field grain are unsafe.
        cb = con.execute("SELECT count(*) FROM facts WHERE offer_id IS NOT NULL AND requirement_id IS NULL AND evidence_status='verified'").fetchone()[0]
        cdb = con.execute("SELECT count(DISTINCT offer_id || '|' || field_key) FROM facts WHERE offer_id IS NOT NULL AND requirement_id IS NULL AND evidence_status='verified'").fetchone()[0]
        cdup = rows_as_dict(con, "SELECT offer_id,field_key,count(*) AS n FROM facts WHERE offer_id IS NOT NULL AND requirement_id IS NULL AND evidence_status='verified' GROUP BY offer_id,field_key HAVING count(*)>1")
        add("verified_offer_field_grain", "offer_id + field_key", cb, cb, cdb, cdb, "pass" if not cdup and cb==cdb else "fail", True, {"duplicates":cdup[:25]})

        # Offers must map to exactly one supplier.
        ob = con.execute("SELECT count(*) FROM offers WHERE status='active'").fetchone()[0]
        odb = con.execute("SELECT count(DISTINCT offer_id) FROM offers WHERE status='active'").fetchone()[0]
        oa = con.execute("SELECT count(*) FROM offers o LEFT JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE o.status='active'").fetchone()[0]
        oda = con.execute("SELECT count(DISTINCT o.offer_id) FROM offers o LEFT JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE o.status='active'").fetchone()[0]
        orphans = con.execute("SELECT count(*) FROM offers o LEFT JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE o.status='active' AND s.supplier_id IS NULL").fetchone()[0]
        add("offers_to_suppliers", "one supplier per offer", ob, oa, odb, oda, "pass" if ob==oa and odb==oda and orphans==0 else "fail", True, {"orphan_count":orphans})

        failed=[c for c in checks if c["critical"] and c["status"]!="pass"]
        out={"status":"PASS" if not failed else "FAIL","checks":checks,"failed":[c["relation_name"] for c in failed],"checked_at":utc_now()}
        if hasattr(con,"commit"): con.commit()
        return out
    finally:
        con.close()


def main():
    ap=argparse.ArgumentParser(description="Check canonical grain and join expansion")
    ap.add_argument("--run",required=True)
    a=ap.parse_args(); print(json.dumps(check(Path(a.run)),ensure_ascii=False,indent=2,default=str))

if __name__=="__main__": main()
