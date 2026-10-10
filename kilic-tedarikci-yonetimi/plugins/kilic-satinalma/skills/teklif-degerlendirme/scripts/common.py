from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "5.0.18"
PARSER_VERSION = "5.0.15"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_id(prefix: str, *parts: str, length: int = 20) -> str:
    raw = "\x1f".join(str(x) for x in parts).encode("utf-8", errors="replace")
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()[:length]}"


def json_safe(value: Any) -> Any:
    """Return a JSON-safe value without silently changing business meaning."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(json_safe(v) for v in value)
    return value


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_text(value: Any) -> str:
    return json.dumps(json_safe(value), ensure_ascii=False, separators=(",", ":"))


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def iter_source_files(source: Path, run_root: Path | None = None) -> Iterable[Path]:
    excluded_names = {".git", "__pycache__", "analiz", "analysis", "output", "outputs"}
    source = source.resolve()
    run_resolved = run_root.resolve() if run_root else None
    if source.is_file():
        yield source
        return
    for root, dirs, files in os.walk(source):
        root_path = Path(root).resolve()
        dirs[:] = [d for d in dirs if d.lower() not in excluded_names]
        if run_resolved and (root_path == run_resolved or run_resolved in root_path.parents):
            dirs[:] = []
            continue
        for name in files:
            p = root_path / name
            if run_resolved and (p == run_resolved or run_resolved in p.parents):
                continue
            yield p
