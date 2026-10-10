"""Read per-session cumulative totals once; missing telemetry is never zero."""
import datetime as dt
import json
from pathlib import Path
from model_secimi import PROFILES, timestamp


def read_session(path):
    identity = model = effort = cwd = parent_id = None
    usage, seals = None, []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(raw)
        except ValueError:
            continue  # Active logs can end with a partial line.
        p = event.get("payload", {})
        if event.get("type") == "session_meta":
            identity, cwd = p.get("id"), p.get("cwd")
            source = p.get("source", {})
            if isinstance(source, dict):
                sub = source.get("subagent")
                spawn = sub.get("thread_spawn") if isinstance(sub, dict) else None
                parent_id = spawn.get("parent_thread_id") if isinstance(spawn, dict) else None
        if event.get("type") == "turn_context":
            model, effort = p.get("model"), p.get("effort")
        if p.get("type") == "token_count" and p.get("info"):
            candidate = p["info"].get("total_token_usage")
            if isinstance(candidate, dict):
                usage = candidate
    if not identity or not model or not effort:
        raise ValueError("Gerçek oturum kimliği/model/efor okunamadı.")
    return {"session_id": identity, "model": model, "reasoning_effort": effort,
            "cwd": cwd, "parent_id": parent_id, "usage": usage, "log_path": str(Path(path).resolve())}


def budget(manifest, now=None):
    if manifest.get('closed_at') and manifest.get('budget_final'):
        return manifest['budget_final']
    now = now or dt.datetime.now(dt.timezone.utc)
    limits = PROFILES[manifest["profile"]]
    sessions = {}
    missing = []
    for binding in manifest.get("sessions", []):
        try:
            session = read_session(binding["log_path"])
            if session["session_id"] != binding["session_id"]:
                raise ValueError("Oturum kimliği değişti.")
            if session["session_id"] in sessions:
                continue
            total = session["usage"]
            baseline = binding.get("baseline", {})
            if not isinstance(total, dict):
                raise ValueError("Token sayacı yok.")
            values = {}
            for key in ("input_tokens", "output_tokens"):
                v, base = total.get(key), baseline.get(key, 0)
                if type(v) is not int or type(base) is not int or v < base or base < 0:
                    raise ValueError("Birikimli token sayacı eksik/geriye gitti.")
                values[key] = v - base
            sessions[session["session_id"]] = values
        except (OSError, ValueError, KeyError, TypeError) as error:
            missing.append({"session_id": binding.get("session_id"), "reason": str(error)})
    expected = {t.get("session_id") for t in manifest.get("tasks", []) if t.get("session_id")}
    missing_ids = expected - set(sessions)
    for identity in missing_ids:
        if identity not in {m["session_id"] for m in missing}:
            missing.append({"session_id": identity, "reason": "Görev oturumu bütçeye bağlı değil."})
    inputs = sum(s["input_tokens"] for s in sessions.values())
    outputs = sum(s["output_tokens"] for s in sessions.values())
    end = timestamp(manifest["closed_at"]) if manifest.get("closed_at") else now
    wall = max(0, int((end - timestamp(manifest["created_at"])).total_seconds()))
    ratio = max(inputs / limits["max_input_tokens"], wall / limits["max_wall_seconds"])
    status = "EXHAUSTED" if ratio >= 1 else "UNVERIFIED" if missing else "ASK_AT_80" if ratio >= .8 else "AVAILABLE"
    if not manifest.get("sessions"):
        status = "UNVERIFIED"
    return {"status": status, "limits": limits, "input_tokens": inputs, "output_tokens": outputs,
            "wall_seconds": wall, "sessions_counted": len(sessions), "missing": missing,
            "scope": "Registered main session delta plus each child session cumulative total once"}
