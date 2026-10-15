"""Move stale source nodes to the current reader profile without changing their meaning.

Only SOURCE_UNIT nodes whose sole stale reason is READING_PROFILE_CHANGED move.
The current reading must hold the same unit and byte-identical text at the same
view range; registration rechecks it. Anything else is reported, never guessed.
Old nodes and relations stay as history. A rerun reuses the same records.
"""
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from .errors import CoreError
from .safety import uuid_text
from .verification import validate_policy

VERSION = "rebind-1.0"
ROOT = Path(__file__).resolve().parents[2]
RELATION_KEYS = ("from_id", "to_id", "unresolved_reference", "relation", "rationale")
BUSINESS_TABLES = ("is_bilgisi_baglari", "yukumlulukler", "gerceklesmeler")


@lru_cache
def validator():
    schema = json.loads((ROOT / "schemas/rebind_result.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def rebind_context(store, case_id, *, expected_revision, policy_version="1"):
    case = uuid_text(case_id)
    validate_policy(policy_version)
    with store._db() as db:
        basis = store._case(db, case, expected_revision)
        nodes = {}
        for rid, raw in db.execute("SELECT record_id,payload FROM icerik_birimleri WHERE case_id=? ORDER BY record_id", [case]).fetchall():
            nodes[str(rid)] = (json.loads(raw)["spec"], store._context_node(db, case, str(rid), policy_version))
        graph = store._context_graph(db, case)
    candidates, skipped = {}, []
    for rid, (spec, state) in nodes.items():
        if state["state"] == "CURRENT_REGISTERED_SCOPE":
            continue
        if spec["node_kind"] == "SOURCE_UNIT" and state["reasons"] == ["READING_PROFILE_CHANGED"]:
            candidates[rid] = spec
        else:
            skipped.append({"node_id": rid, "node_kind": spec["node_kind"], "reasons": state["reasons"]})
    readings = {}
    for spec in candidates.values():
        key = (spec["version_id"], spec["target"]["format"])
        if key not in readings:
            readings[key] = store.read_document(case, key[0], format=key[1], policy_version=policy_version)
    revision = basis

    def write(register, spec):
        nonlocal revision
        # The caller's revision is the CAS basis; a concurrent writer stops the rebind.
        record = register(case, spec=spec, expected_revision=revision)
        if not record["reused"]:
            revision += 1
        return record

    mapping, unmapped = {}, []
    rows = []
    for rid, spec in candidates.items():
        reading = readings[(spec["version_id"], spec["target"]["format"])]
        if not any(unit["unit_id"] == spec["target"]["unit_id"] for unit in reading["result"]["units"]):
            unmapped.append({"node_id": rid, "reason": "UNIT_NOT_IN_CURRENT_READING"})
            continue
        try:
            _, text = store._target(reading["result"], spec["target"])
        except CoreError:  # Same unit, but the recorded range no longer fits its text.
            text = None
        if text != spec["target"]["expected_text"]:
            unmapped.append({"node_id": rid, "reason": "TEXT_CHANGED_IN_CURRENT_READING"})
            continue
        record = write(lambda c, **kw: store.register_context_node(c, policy_version=policy_version, **kw),
                       dict(spec, reading_id=reading["processing_id"]))
        mapping[rid] = record["node_id"]
        rows.append({"old_node_id": rid, "new_node_id": record["node_id"], "reused": record["reused"]})
    relations = {"created": 0, "reused": 0, "superseded": 0, "unmapped": []}
    for source, edges in sorted(graph.items()):
        for edge in edges:
            target = edge.get("to_id")
            if source not in mapping and target not in mapping:
                continue
            if edge["invalidated"]:
                relations["unmapped"].append({"relation_id": edge["relation_id"], "reason": "RELATION_INVALIDATED"})
                continue
            if source not in mapping and nodes[source][1]["state"] != "CURRENT_REGISTERED_SCOPE":
                relations["unmapped"].append({"relation_id": edge["relation_id"], "reason": "SOURCE_NOT_REBOUND"})
                continue
            if target in candidates and target not in mapping:
                relations["unmapped"].append({"relation_id": edge["relation_id"], "reason": "TARGET_NOT_REBOUND"})
                continue
            spec = {key: edge[key] for key in RELATION_KEYS if key in edge}
            spec["from_id"] = mapping.get(source, source)
            if target is not None:
                spec["to_id"] = mapping.get(target, target)
            if source not in mapping:
                # Same start node: replace the old edge so its closure no longer reaches stale content.
                spec["supersedes_relation_id"] = edge["relation_id"]
            record = write(store.register_context_relation, spec)
            relations["reused" if record["reused"] else "superseded" if source not in mapping else "created"] += 1
    review = []
    if mapping:
        with store._db() as db:
            for table in BUSINESS_TABLES:
                for rid, raw in db.execute(f"SELECT record_id,payload FROM {table} WHERE case_id=? ORDER BY record_id", [case]).fetchall():
                    if any(old in raw for old in mapping):
                        review.append({"record_id": str(rid), "table": table, "reason": "REFERENCES_REBOUND_NODE"})
    result = {"schema_version": VERSION, "case_id": case, "policy_version": policy_version, "basis_revision": basis,
              "final_revision": revision, "mapping": rows, "unmapped": unmapped, "skipped": skipped,
              "relations": relations,
              "readings": [{"version_id": key[0], "format": key[1], "processing_id": value["processing_id"], "reused": value["reused"]}
                           for key, value in sorted(readings.items())],
              "business_records_review_required": review, "old_records_retained": True,
              "semantic_change": "NONE_EXACT_TEXT_MATCH", "authority": "NOT_VERIFIED", "business_acceptance": "NOT_GRANTED"}
    if not validator().is_valid(result):
        raise CoreError("SEMA_HATASI", "Bağlam taşıma sonucu şemaya uymuyor")
    return result
