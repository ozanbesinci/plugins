from __future__ import annotations

import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

MAX_FILES = 2000
MAX_MEMBER_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200.0


def _safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    root = root.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"Archive path traversal blocked: {name}")
    return target


def _normalized_member(name: str) -> str:
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or any(part in {"", ".", ".."} for part in p.parts):
        raise ValueError(f"Unsafe archive member path: {name}")
    return "/".join(p.parts).casefold()


def extract_zip(path: Path, target_root: Path) -> list[Path]:
    target_root.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    seen: set[str] = set()
    total = 0
    with zipfile.ZipFile(path) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        if len(members) > MAX_FILES:
            raise ValueError(f"Archive contains too many files: {len(members)}>{MAX_FILES}")
        for member in members:
            if member.flag_bits & 0x1:
                raise ValueError(f"Encrypted archive member is not supported: {member.filename}")
            mode = (member.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                raise ValueError(f"Archive symlink blocked: {member.filename}")
            key = _normalized_member(member.filename)
            if key in seen:
                raise ValueError(f"Duplicate archive member path blocked: {member.filename}")
            seen.add(key)
            if member.file_size > MAX_MEMBER_BYTES:
                raise ValueError(f"Archive member too large: {member.filename}")
            total += int(member.file_size)
            if total > MAX_TOTAL_BYTES:
                raise ValueError("Archive uncompressed size exceeds safety limit")
            if member.compress_size == 0:
                if member.file_size > 0:
                    raise ValueError(f"Suspicious compression metadata: {member.filename}")
            elif member.file_size / member.compress_size > MAX_COMPRESSION_RATIO:
                raise ValueError(f"Suspicious archive compression ratio: {member.filename}")
            if member.filename.startswith(("/", "\\")):
                raise ValueError(f"Absolute archive path blocked: {member.filename}")
            target = _safe_target(target_root, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            if target.stat().st_size != member.file_size:
                raise ValueError(f"Archive member size mismatch after extraction: {member.filename}")
            out.append(target)
    return out
