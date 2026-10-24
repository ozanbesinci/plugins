"""Verify shipped bytes before importing runtime or business helpers.
Self-consistency is not publisher authentication; a trusted release pin is optional.
"""
import hashlib
import json
from pathlib import Path
import re
import stat

class BootstrapIntegrityError(ValueError):
    pass

def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BootstrapIntegrityError("Duplicate JSON key")
        result[key] = value
    return result

def plain(path):
    path = Path(path).absolute()
    for node in (path, *path.parents):
        if node.exists() or node.is_symlink():
            info = node.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise BootstrapIntegrityError("Reparse/symlink path rejected")
    return path.resolve(strict=False)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def package_files(root):
    root = Path(root)
    result = {}
    for group in ("scripts", "src", "schemas", "references", "skills"):
        for p in (root/group).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts and p.name != "bootstrap-manifest.json":
                result[p.relative_to(root).as_posix()] = sha(p)
    for name in ("plugin.json", "requirements-core.txt", "requirements-readers.txt", "requirements-win-cp314.lock"):
        result[name] = sha(root/name)
    return dict(sorted(result.items()))

def verify_package(root, expected_manifest_digest=None):
    root = plain(root)
    manifest_path = plain(root/"references/bootstrap-manifest.json")
    raw = manifest_path.read_bytes()
    if len(raw) > 2*1024*1024:
        raise BootstrapIntegrityError("Manifest too large")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_manifest_digest is not None and digest != expected_manifest_digest:
        raise BootstrapIntegrityError("External manifest pin differs")
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)
    if value.get("schema") != "contract-bootstrap/v1" or not isinstance(value.get("files"), dict):
        raise BootstrapIntegrityError("Unknown bootstrap manifest")
    for name, expected in value["files"].items():
        if (not name or "\\" in name or ":" in name or name.startswith("/")
                or any(part in ("", ".", "..") for part in name.split("/"))
                or not re.fullmatch("[a-f0-9]{64}", expected)):
            raise BootstrapIntegrityError("Invalid manifest entry")
        p = plain(root/name)
        if not p.is_relative_to(root) or not p.is_file() or sha(p) != expected:
            raise BootstrapIntegrityError("Package bytes differ: " + name)
    if package_files(root) != value["files"]:
        raise BootstrapIntegrityError("Package inventory differs")
    return {"manifest_sha256": digest, "files_verified": len(value["files"]),
            "trust": "EXTERNAL_PIN_MATCHED" if expected_manifest_digest else "PACKAGE_SELF_CONSISTENCY_ONLY"}
