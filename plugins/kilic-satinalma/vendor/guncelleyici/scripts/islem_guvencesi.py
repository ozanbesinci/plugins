"""Small, dependency-free safety primitives shared by the updater.

A fingerprint binds data, not user identity. Consent is supplied by the chat
entrypoint and is never inferred from defaults or a matching fingerprint.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import uuid

SCHEMA = "guncelleyici-plan/v1"
RESULT_SCHEMA = "guncelleyici-result/v1"


class SafetyError(ValueError):
    pass


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value):
    return digest_bytes(canonical(value))


def redact(value):
    if isinstance(value, dict):
        return {k: ("***" if re.search(r"(?i)(password|authorization|access_token|api_key)", k) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r"(?i)\b(https?://)[^\s/]+@", r"\1***@", value)
    return re.sub(r"(?i)([?&](?:token|access_token|key|api_key)=)[^&\s]+", r"\1***", value)


def reject_links(path, *, include_parents=True):
    """Reject symlinks, junctions and other Windows reparse points without following them."""
    path = Path(os.path.abspath(path))
    targets = [path, *path.parents] if include_parents else [path]
    for candidate in targets:
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise SafetyError(f"Bağlantı/reparse point yolu reddedildi: {candidate}")
    return path


def read_json(path):
    reject_links(path)
    with Path(path).open(encoding="utf-8-sig") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise SafetyError("JSON nesnesi gerekli.")
    return value


def atomic_bytes(path, data, *, expected_hash=None, require_absent=False):
    """Write/flush a sibling temp file and replace. Reject an observed concurrent edit.

This is not a filesystem CAS against uncooperative writers. Client configuration
changes additionally require that the affected client is not running.
"""
    path = reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if require_absent and path.exists():
        raise SafetyError("Dosya bu sırada oluşturulmuş; üzerine yazılmaz.")
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    fd, tmp_name = tempfile.mkstemp(prefix=".guncelleyici-write-", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        reject_links(path)
        if require_absent and path.exists():
            raise SafetyError("Dosya bu sırada oluşturulmuş; üzerine yazılmaz.")
        if expected_hash is not None:
            if not path.is_file() or digest_bytes(path.read_bytes()) != expected_hash:
                raise SafetyError("Dosya okunduktan sonra değişti; üzerine yazılmaz.")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def atomic_json(path, value, **kwargs):
    atomic_bytes(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n", **kwargs)


@contextlib.contextmanager
def exclusive_lock(path):
    """Per-user/installation file lock; works across Windows sessions.

An abandoned lock is never removed automatically. Only the owner removes it.
"""
    path = reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    owner = uuid.uuid4().hex
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SafetyError(f"İşlem kilidi mevcut; otomatik silinmez: {path}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"owner": owner, "pid": os.getpid(), "created_at": utcnow()}, f)
            f.flush()
            os.fsync(f.fileno())
        yield owner
    finally:
        try:
            if read_json(path).get("owner") == owner:
                path.unlink()
        except (OSError, ValueError):
            pass


def check_plan(plan, expected, selected, *, identity=None):
    if not isinstance(plan, dict) or plan.get("schema") != SCHEMA:
        raise SafetyError("Kurulum planı şeması geçersiz.")
    if not re.fullmatch(r"[a-f0-9]{64}", expected or "") or fingerprint(plan) != expected:
        raise SafetyError("Kurulum planı/parmak izi değişti; yeniden seçim gerekli.")
    if identity is not None and plan.get("identity") != identity:
        raise SafetyError("Plan farklı bilgisayar/kullanıcı/kurulum köküne ait.")
    expires = dt.datetime.fromisoformat(plan["expires_at"])
    if expires.tzinfo is None or expires <= dt.datetime.now(dt.timezone.utc):
        raise SafetyError("Planın süresi doldu; yeniden tarayın.")
    components = plan.get("components")
    if not isinstance(components, list):
        raise SafetyError("Plan bileşenleri eksik.")
    keys = [c.get("key") for c in components]
    if len(set(keys)) != len(keys) or None in keys:
        raise SafetyError("Plan bileşen anahtarı yinelenmiş/geçersiz.")
    selected = list(dict.fromkeys(selected))
    if not selected:
        raise SafetyError("Boş seçim uygulanmaz.")
    chosen = [c for c in components if c["key"] in selected]
    if len(chosen) != len(selected) or any(not c.get("selectable") for c in chosen):
        raise SafetyError("Seçilemeyen/bilinmeyen bileşen.")
    for component in chosen:
        if not isinstance(component.get("target"), dict) or not component["target"]:
            raise SafetyError("Tam hedefi olmayan bileşen uygulanamaz.")
    return chosen


def aggregate_checks(checks):
    states = [c.get("status") for c in checks]
    if not states:
        return "NOT_RUN"
    if "FAIL" in states:
        return "FAIL"
    if any(s not in {"PASS", "INFO"} for s in states):
        return "WARNING"
    return "PASS" if "PASS" in states else "NOT_RUN"


def validate_mcp_tools(response):
    if not isinstance(response, dict) or response.get("error"):
        raise SafetyError("MCP tools/list hata/geçersiz cevap.")
    result = response.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list) or not tools:
        raise SafetyError("MCP geçerli, boş olmayan araç listesi vermedi.")
    names = set()
    for tool in tools:
        if (not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                or not tool["name"].strip() or not isinstance(tool.get("inputSchema"), dict)
                or tool["name"] in names):
            raise SafetyError("MCP araç listesi şeması geçersiz.")
        names.add(tool["name"])
    return names


def config_transaction(path, transform, validate):
    """Back up exact bytes; preserve unrelated configuration and reject concurrent edits."""
    path = reject_links(path)
    existed = path.exists()
    before = path.read_bytes() if existed else b""
    after = transform(before)
    validate(after)
    if after == before and existed:
        return {"status": "unchanged", "path": str(path), "before_sha256": digest_bytes(before)}
    backup = None
    if existed:
        backup = path.with_name(path.name + ".guncelleyici-" + uuid.uuid4().hex + ".bak")
        atomic_bytes(backup, before, require_absent=True)
    atomic_bytes(path, after, expected_hash=digest_bytes(before) if existed else None, require_absent=not existed)
    try:
        written = path.read_bytes()
        if written != after:
            raise SafetyError("Yazım sonrası dosya başka süreççe değiştirildi.")
        validate(written)
    except Exception:
        # Do not overwrite somebody else's concurrent change during recovery.
        if path.exists() and digest_bytes(path.read_bytes()) == digest_bytes(after):
            if existed:
                atomic_bytes(path, before, expected_hash=digest_bytes(after))
            else:
                path.unlink()
        raise
    return {"status": "updated" if existed else "created", "path": str(path),
            "backup": str(backup) if backup else None,
            "before_sha256": digest_bytes(before), "after_sha256": digest_bytes(after)}

