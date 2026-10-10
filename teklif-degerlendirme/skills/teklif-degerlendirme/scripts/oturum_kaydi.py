"""Small deterministic runtime helpers. No source text is copied into telemetry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def output_text(value):
    if isinstance(value, list):
        return "\n".join(output_text(v) for v in value)
    if isinstance(value, dict):
        return output_text(value.get("text", value.get("output", "")))
    if isinstance(value, str):
        try:
            nested = json.loads(value)
        except ValueError:
            return value
        return output_text(nested) if isinstance(nested, (dict, list)) else value
    return ""


def read_native_session(path, limit=None, seal=None):
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read() if limit is None else stream.read(limit)
    model = effort = session_id = cwd = None
    usage = None
    matched = None
    for line_number, line in enumerate(raw.splitlines(), 1):
        try:
            event = json.loads(line)
        except ValueError:
            continue  # A still-active log may have an incomplete trailing line.
        payload = event.get("payload", {})
        if event.get("type") == "session_meta":
            session_id, cwd = payload.get("id"), payload.get("cwd")
        if event.get("type") == "turn_context":
            model, effort = payload.get("model"), payload.get("effort")
        if payload.get("type") == "token_count" and payload.get("info"):
            usage = payload["info"].get("total_token_usage")
        if payload.get("type") in {"function_call_output", "custom_tool_call_output"}:
            for text in output_text(payload.get("output")).splitlines():
                if text.startswith("TEKLIF_RESULT_SEAL:"):
                    try:
                        marker = json.loads(text.split(":", 1)[1])
                    except ValueError:
                        continue
                    if seal is not None and marker == seal:
                        matched = (model, effort, event.get("timestamp"), line_number)
    if not all(isinstance(x, str) and x for x in (session_id, cwd, model, effort)):
        raise ValueError("Gerçek oturum kimliği/model/efor/çalışma dizini okunamadı.")
    if seal is not None:
        if not matched:
            raise ValueError("Bu artefaktı kabul eden gerçek araç sonucu oturumda yok; önce seal-result çalıştırın.")
        model, effort, seal_at, seal_line = matched
    return {"session_id": session_id, "cwd": cwd, "model": model, "reasoning_effort": effort,
            "log_path": str(path.resolve()), "log_bytes": len(raw),
            "log_prefix_sha256": hashlib.sha256(raw).hexdigest(), "usage_snapshot": usage,
            "seal": seal, "seal_at": matched[2] if matched else None, "seal_line": matched[3] if matched else None}


def native_receipt_valid(receipt):
    try:
        if not receipt.get("seal"):
            return False
        observed = read_native_session(receipt["log_path"], receipt["log_bytes"], receipt["seal"])
        return all(observed.get(k) == receipt.get(k) for k in
                   ("session_id", "model", "reasoning_effort", "log_prefix_sha256", "log_bytes", "seal_at", "seal_line"))
    except (OSError, ValueError, KeyError, TypeError):
        return False


