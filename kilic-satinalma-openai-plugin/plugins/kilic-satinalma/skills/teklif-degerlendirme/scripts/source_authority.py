from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict


ROLE_SCOPE = {
    "specification": ("requirements", "owner_specification"),
    "offer": ("supplier_commitment", "supplier_offer"),
    "boq": ("scope_quantity", "boq"),
    "correspondence": ("supplemental", "supplier_correspondence"),
    "support": ("supplemental", "supporting_document"),
    "unrelated": ("none", "unrelated"),
    "unknown": ("unknown", "unclassified"),
}


def _issue(con, owner: str, severity: str, issue_type: str, question: str, evidence_ids: list[str] | None = None) -> str:
    iid = stable_id("issue", owner, issue_type, question, length=22)
    con.execute(
        """
        INSERT OR REPLACE INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        [iid, owner, severity, issue_type, question, "[]", json_text(evidence_ids or []), "open", utc_now()],
    )
    return iid


def _close_old_issues(con) -> None:
    con.execute(
    "UPDATE open_issues SET status='resolved',resolved_at=? WHERE status='open' AND issue_type IN ('source_authority_conflict','revision_relation','supplier_identity_unresolved')",
        [utc_now()],
    )


_REVISION_MARKER = re.compile(r"(?<![a-z])(?:revize|revizyon|revision|rev)(?![a-z])(?:[-_. ]*[a-z]?\d{1,3})?", re.IGNORECASE)


def _filename_revision_root(filename: str) -> tuple[str | None, bool]:
    """Return a normalized filename root and whether the filename says revision."""
    stem = Path(filename or "").stem.casefold()
    stem = "".join(
        char for char in unicodedata.normalize("NFKD", stem)
        if not unicodedata.combining(char)
    )
    matches = list(_REVISION_MARKER.finditer(stem))
    if not matches:
        return None, False
    root = stem[:matches[-1].start()] + " " + stem[matches[-1].end():]
    root = re.sub(r"[^a-z0-9]+", " ", root).strip()
    return (root or None), True


def refresh(run_root: Path) -> dict[str, Any]:
    con = connect(run_root)
    try:
        _close_old_issues(con)
        docs = rows_as_dict(
            con,
            """SELECT d.document_id,d.filename,d.document_role,d.supplier_id,d.offer_id,d.revision_label,d.revision_status,d.parse_status,d.active,s.identification_status
               FROM documents d LEFT JOIN suppliers s ON s.supplier_id=d.supplier_id WHERE d.active=true ORDER BY d.document_role,d.supplier_id,d.filename""",
        )
        con.execute("DELETE FROM source_authority")
        records: dict[str, dict[str, Any]] = {}
        for d in docs:
            role = d.get("document_role") or "unknown"
            scope, authority_class = ROLE_SCOPE.get(role, ("unknown", "unclassified"))
            status = "candidate"
            rank = 50
            rationale = f"Role={role}; source authority not yet uniquely resolved."
            if d.get("parse_status") == "unreadable":
                status = "unusable"; rank = 0; rationale = "Source is unreadable."
            elif role in {"correspondence", "support"}:
                status = "supplemental"; rank = 30; rationale = "Supplemental evidence; does not silently override formal specification/offer."
            elif role == "boq":
                status = "candidate"; rank = 60; rationale = "Scope/quantity source candidate."
            elif role == "unrelated":
                status = "not_applicable"; rank = 0; rationale = "Document classified unrelated."
            elif role == "unknown":
                status = "needs_classification"; rank = 10; rationale = "Document role is unresolved."
            records[d["document_id"]] = {
                "document_id": d["document_id"], "authority_scope": scope, "authority_class": authority_class,
                "authority_status": status, "precedence_rank": rank, "rationale": rationale,
            }

        # Specifications: one readable specification is controlling; multiple specifications require explicit resolution.
        specs = [d for d in docs if d.get("document_role") == "specification" and d.get("parse_status") != "unreadable"]
        if len(specs) == 1:
            r = records[specs[0]["document_id"]]; r.update(authority_status="controlling", precedence_rank=100, rationale="Only readable active specification source.")
        elif len(specs) > 1:
            explicit = [d for d in specs if str(d.get("revision_status") or "").casefold() == "current"]
            if len(explicit) == 1:
                for d in specs:
                    r=records[d["document_id"]]
                    if d["document_id"] == explicit[0]["document_id"]:
                        r.update(authority_status="controlling", precedence_rank=100, rationale="Explicitly marked current specification.")
                    else:
                        r.update(authority_status="superseded", precedence_rank=20, rationale="Another specification is explicitly marked current.")
            else:
                for d in specs:
                    records[d["document_id"]].update(authority_status="needs_input", precedence_rank=70, rationale="Multiple active specifications; controlling revision is not explicit.")
                _issue(con, "IDARE", "critical", "source_authority_conflict", "Confirm which specification/revision is controlling; multiple active specification sources are present.")

        # A formal offer is independent unless its filename explicitly identifies
        # a revision chain with the same normalized root as another offer.
        by_revision_root: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        unresolved_revision_docs: list[dict[str, Any]] = []
        for d in docs:
            if d.get("document_role") == "offer" and d.get("supplier_id") and d.get("parse_status") != "unreadable":
                filename_root, filename_is_revision = _filename_revision_root(d.get("filename") or "")
                is_revision = filename_is_revision or bool(str(d.get("revision_label") or "").strip())
                records[d["document_id"]].update(
                    authority_status="needs_input" if is_revision else "controlling",
                    precedence_rank=70 if is_revision else 100,
                    rationale=("Revision-tagged offer has no explicit matching revision pair; authority remains unresolved."
                               if is_revision else "Only this readable formal offer source; independent of other item offers."),
                )
                if is_revision:
                    unresolved_revision_docs.append(d)
                if filename_is_revision and filename_root:
                    by_revision_root[(d["supplier_id"], filename_root)].append(d)
        for (supplier_id, root), items in by_revision_root.items():
            if len(items) > 1:
                for d in items:
                    records[d["document_id"]].update(
                        authority_status="needs_input", precedence_rank=70,
                        rationale="Multiple offers share an explicit normalized filename revision root; controlling revision is unresolved.",
                    )
                filenames = ", ".join(sorted(d["filename"] for d in items))
                _issue(con, f"FIRMA:{supplier_id}", "critical", "source_authority_conflict",
                       f"Confirm the controlling revision among {filenames}; the offers share filename root '{root}'.",
                       [d["document_id"] for d in items])
        paired_revision_ids = {
            d["document_id"]
            for items in by_revision_root.values() if len(items) > 1
            for d in items
        }
        for d in unresolved_revision_docs:
            if d["document_id"] not in paired_revision_ids:
                owner = f"FIRMA:{d['supplier_id']}" if d.get("supplier_id") else "IDARE"
                _issue(con, owner, "critical", "source_authority_conflict",
                       f"Confirm whether revision-tagged source {d['filename']} is the controlling offer; no matching revision source is identified.",
                       [d["document_id"]])

        for d in docs:
            if d.get("document_role") == "offer" and d.get("identification_status") == "provisional":
                records[d["document_id"]].update(authority_status="needs_input",precedence_rank=60,rationale="Supplier identity remains provisional; filename is not independent supplier evidence.")
                _issue(con, "IDARE", "critical", "supplier_identity_unresolved", f"Confirm supplier identity for source {d['filename']} before treating it as an independent supplier offer.")

        for r in records.values():
            con.execute(
                """INSERT OR REPLACE INTO source_authority(document_id,authority_scope,authority_class,authority_status,precedence_rank,rationale,assessed_by,assessed_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                [r["document_id"], r["authority_scope"], r["authority_class"], r["authority_status"], r["precedence_rank"], r["rationale"], "deterministic_rule/v5.0.4", utc_now()],
            )
        if hasattr(con, "commit"):
            con.commit()
        unresolved = sum(1 for r in records.values() if r["authority_status"] in {"needs_input", "needs_classification", "unusable"})
        controlling = sum(1 for r in records.values() if r["authority_status"] == "controlling")
        return {"documents": len(records), "controlling": controlling, "unresolved": unresolved, "records": list(records.values())}
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build deterministic source-authority register")
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(json.dumps(refresh(Path(args.run)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
