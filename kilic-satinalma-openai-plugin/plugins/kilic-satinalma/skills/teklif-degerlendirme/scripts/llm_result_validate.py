from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from common import json_text, stable_id, utc_now


class ResultValidationError(ValueError):
    def __init__(self, task_kind: str, errors: list[str]):
        self.task_kind = task_kind
        self.errors = errors
        super().__init__(f"LLM result failed schema validation for {task_kind}: " + " | ".join(errors[:8]))


def _bundle(skill_root: Path) -> dict[str, Any]:
    path = skill_root / "config" / "task-result-schemas.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or not isinstance(obj.get("tasks"), dict) or not isinstance(obj.get("$defs"), dict):
        raise ValueError("task-result-schemas.json is invalid")
    return obj


def result_hash(result: dict[str, Any]) -> str:
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_result(skill_root: Path, task_kind: str, result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ResultValidationError(task_kind, ["result must be a JSON object"])
    bundle = _bundle(skill_root)
    raw_schema = bundle["tasks"].get(task_kind)
    if not isinstance(raw_schema, dict):
        raise ResultValidationError(task_kind, ["no schema registered for task kind"])
    schema = dict(raw_schema)
    schema["$schema"] = bundle.get("$schema", "https://json-schema.org/draft/2020-12/schema")
    schema["$defs"] = bundle["$defs"]
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(result), key=lambda e: list(e.absolute_path)):
        loc = "/".join(str(x) for x in err.absolute_path) or "$"
        errors.append(f"{loc}: {err.message}")
    if errors:
        raise ResultValidationError(task_kind, errors)
    return {
        "status": "PASS",
        "task_kind": task_kind,
        "schema_version": str(bundle.get("schema_version", "unknown")),
        "result_sha256": result_hash(result),
    }


def record_validation(con, task_id: str, task_kind: str, receipt: dict[str, Any] | None, errors: list[str] | None = None) -> str:
    status = "PASS" if receipt else "FAIL"
    schema_version = str((receipt or {}).get("schema_version") or "5.0.5")
    result_sha = str((receipt or {}).get("result_sha256") or "")
    validation_id = stable_id("val", task_id, task_kind, status, result_sha, json_text(errors or []), length=24)
    con.execute(
        """
        INSERT OR REPLACE INTO llm_result_validations(
          validation_id,task_id,task_kind,schema_version,result_sha256,status,errors_json,validated_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        [validation_id, task_id, task_kind, schema_version, result_sha, status, json_text(errors or []), utc_now()],
    )
    return validation_id


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate a bounded LLM result against the task JSON schema")
    ap.add_argument("--task-kind", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    try:
        result = validate_result(Path(args.skill_root), args.task_kind, payload)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except ResultValidationError as exc:
        print(json.dumps({"status": "FAIL", "task_kind": exc.task_kind, "errors": exc.errors}, ensure_ascii=False, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
