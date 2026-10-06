"""Best-effort error-only JSONL telemetry; stdlib, no network or raw inputs."""
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

_session = uuid4().hex
_count = 0
_write_lock = threading.Lock()
MAX_EVENTS = 100
MAX_BYTES = 1024 * 1024


def token(value, fallback="UNKNOWN"):
    value = str(value or "")
    return value if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) else fallback


def write_error(stage, code, exc=None, operation_id=None, skill_id=None,
                category="TECHNICAL_ERROR", core_version=None):
    # Never wait for another logging thread; the caller can observe a False result.
    if not _write_lock.acquire(blocking=False):
        return False
    try:
        return _write_error(stage, code, exc, operation_id, skill_id, category, core_version)
    finally:
        _write_lock.release()


def _write_error(stage, code, exc=None, operation_id=None, skill_id=None,
                 category="TECHNICAL_ERROR", core_version=None):
    """Return delivery status without changing the caller's exception/result.

    Separate process/session files avoid interprocess locks and torn shared
    appends. No success events, message text, locals, request bodies or paths.
    A per-process cap bounds error storms; historical files are not deleted.
    """
    global _count
    try:
        local = os.environ.get("LOCALAPPDATA")
        if not local or _count >= MAX_EVENTS:
            return False
        root = Path(local) / "KilicSozlesme" / "logs"
        root.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        path = root / f"errors_{now:%Y%m%d}_{os.getpid()}_{_session}.jsonl"
        frames = []
        tb = getattr(exc, "__traceback__", None)
        while tb is not None:
            frames.append({"module": token(Path(tb.tb_frame.f_code.co_filename).stem),
                           "function": token(tb.tb_frame.f_code.co_name),
                           "line": tb.tb_lineno})
            tb = tb.tb_next
        plugin = Path(__file__).resolve().parents[1]
        try:
            version = json.loads((plugin / "plugin.json").read_text(encoding="utf-8-sig"))["version"]
        except Exception:
            version = "UNKNOWN"
        event = {"schema_version": "1.0", "event_id": uuid4().hex,
                 "timestamp_utc": now.isoformat(), "session_id": _session,
                 "operation_id": token(operation_id) if operation_id else None,
                 "package_version": token(version), "core_version": core_version,
                 "skill_id": skill_id if re.fullmatch(r"K\d{2}|guncelleyici", str(skill_id)) else None,
                 "stage": token(stage), "category": token(category),
                 "error_code": token(code),
                 "exception_type": token(type(exc).__name__) if exc else None,
                 "frames": frames[-5:], "python_version": sys.version.split()[0]}
        data = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        if path.exists() and path.stat().st_size + len(data) > MAX_BYTES:
            return False
        with path.open("ab") as stream:
            stream.write(data)
        _count += 1
        return True
    except Exception:
        return False


def write_result_error(stage, result, operation_id=None, skill_id=None, core_version=None):
    """Record explicit returned failures, without logging normal partial results."""
    if not isinstance(result, dict):
        return False
    status = result.get("status")
    if status in ("TEKNIK_ENGEL", "BLOCKED", "FAILED", "ERROR", "DEPENDENCIES_REQUIRED"):
        return write_error(stage, status, operation_id=operation_id, skill_id=skill_id,
                           category="RETURNED_FAILURE", core_version=core_version)
    if result.get("decision") == "BLOCK":
        return write_error(stage, "ACTION_BLOCKED", operation_id=operation_id,
                           skill_id=skill_id, category="EXPECTED_BLOCK", core_version=core_version)
    return False
