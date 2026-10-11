"""Immutable official report revisions; only a committed DB pointer is delivered."""
from pathlib import Path
import json
import tempfile
import uuid
from common import sha256_file
from report_delivery import _publish_directory, _validate_pair

REQUIRED = {"Teklif_Degerlendirme.xlsx", "Teklif_Degerlendirme.pdf",
            "decision_snapshot.json", "formula_contract.json", "report_model.json"}

class RegistrationError(OSError):
    """Registration failed: retrying a file path cannot fix this transaction."""

class PairValidationError(ValueError):
    """Files exist but do not satisfy the same model/paired artifact contract."""

def stage_revision(run_root, directory):
    if directory not in {"output", "output_fallback"}:
        raise ValueError("Unknown official report directory")
    root = run_root / directory / "revisions"
    if not root.resolve().is_relative_to(run_root.resolve()):
        raise ValueError("Official report path leaves run")
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=".official-stage-", dir=root)), root / uuid.uuid4().hex

def publish(stage, target, contract, model, snapshot_sha):
    try:
        return _publish(stage, target, contract, model, snapshot_sha)
    except ValueError as exc:
        raise PairValidationError(str(exc)) from exc

def _publish(stage, target, contract, model, snapshot_sha):
    qa = _validate_pair(stage, contract, model)
    import fitz
    from pdf_bound_values import check_bound_values
    with fitz.open(stage / "Teklif_Degerlendirme.pdf") as pdf:
        errors = check_bound_values("\n".join(p.get_text() for p in pdf), model)
    if errors:
        raise ValueError("Official PDF validation failed: " + "; ".join(errors))
    if not all((stage / name).is_file() for name in REQUIRED):
        raise ValueError("Official report revision is incomplete")
    manifest = {"schema": "teklif-official-delivery/v1", "revision": target.name,
                "snapshot_sha256": snapshot_sha, "pair_validation": "PASS", "qa": qa,
                "files": {name: sha256_file(stage / name) for name in sorted(REQUIRED)}}
    (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _publish_directory(stage, target)
    return manifest

def inspect_official(run_root, snapshot_sha=None):
    from db import connect, get_meta, rows_as_dict
    manifest = get_meta(run_root, "official_report_delivery", None, parse_json=True)
    if not manifest:
        return {"delivery_status": "NOT_CREATED", "deliverable_artifacts": False}
    try:
        relative = Path(manifest["relative_directory"])
        if len(relative.parts) != 3 or relative.parts[0] not in {"output", "output_fallback"} or relative.parts[1] != "revisions" or relative.parts[2] != manifest["revision"]:
            raise ValueError("Invalid official report pointer")
        root = run_root / relative
        if not root.resolve().is_relative_to(run_root.resolve()) or set(manifest["files"]) != REQUIRED:
            raise ValueError("Invalid official report manifest")
        if snapshot_sha and manifest["snapshot_sha256"] != snapshot_sha:
            raise ValueError("Official report belongs to another snapshot")
        for name, digest in manifest["files"].items():
            if sha256_file(root / name) != digest:
                raise ValueError("Official report file changed: " + name)
        saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        base = {key: value for key, value in manifest.items() if key not in {"artifact_ids", "relative_directory"}}
        if saved != base:
            raise ValueError("Official filesystem manifest changed")
        con = connect(run_root)
        try:
            from active_records import current_artifacts
            current = current_artifacts(con)
            for kind, name in (("xlsx", "Teklif_Degerlendirme.xlsx"), ("pdf", "Teklif_Degerlendirme.pdf"), ("decision_snapshot", "decision_snapshot.json")):
                row = current.get(kind)
                if not row or row["artifact_id"] != manifest["artifact_ids"][kind] or row["relative_path"] != str((root / name).relative_to(run_root)) or row["sha256"] != manifest["files"][name] or manifest["snapshot_sha256"] not in json.loads(row["parent_hashes_json"]):
                    raise ValueError("Official artifact group changed: " + kind)
        finally:
            con.close()
        model = json.loads((root / "report_model.json").read_text(encoding="utf-8"))
        contract = json.loads((root / "formula_contract.json").read_text(encoding="utf-8"))
        _validate_pair(root, contract, model)
        return {"delivery_status": "READY", "deliverable_artifacts": True, **manifest,
                "xlsx": str(root / "Teklif_Degerlendirme.xlsx"), "pdf": str(root / "Teklif_Degerlendirme.pdf")}
    except Exception as exc:
        return {"delivery_status": "FAILED", "deliverable_artifacts": False, "error": str(exc)}
