"""Distinct component versions and immutable behavior-affecting reader build identity."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
from pathlib import Path
import struct
import sys
from .errors import CoreError
from .safety import hash_value

ROOT = Path(__file__).resolve().parents[2]


def _reader_files(root=ROOT):
    root = Path(root)
    paths = list((root / "src/sozlesme_cekirdek/readers").glob("*.py"))
    paths += [root / "src/sozlesme_cekirdek/verification.py", root / "src/sozlesme_cekirdek/runtime_identity.py",
              root / "scripts/worker_entry.py",
              root / "schemas/p2_reading.schema.json", root / "requirements-core.txt", root / "requirements-readers.txt"]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


_LOADED_READER_FILES = _reader_files()

# Optional packages a format's reader can actually pick up at runtime (openpyxl: numpy/defusedxml;
# pypdf: cryptography, pypdfium2: numpy). DOCX/EML readers import neither, so unrelated host
# packages must not stale their readings (CR-10).
OPTIONAL_DEPENDENCIES = {"DOCX": (), "EML": (), "XLSX": ("numpy", "defusedxml"), "PDF": ("numpy", "cryptography")}


def reader_build_identity(root=ROOT, kind=None):
    if kind is not None and kind not in OPTIONAL_DEPENDENCIES:
        raise CoreError("DOSYA_TURU", "Yalnız DOCX/PDF/XLSX/EML destekleniyor")
    files = _reader_files(root)
    if Path(root).resolve() == ROOT.resolve() and files != _LOADED_READER_FILES:
        raise CoreError("PAKET_DEGISTI", "Çalışan reader paketi değişti; immutable paket ve süreç yeniden başlatması gerekli")
    dependencies = {}
    for filename in ["requirements-core.txt", "requirements-readers.txt"]:
        for line in (Path(root) / filename).read_text(encoding="utf-8").splitlines():
            if line.strip():
                name, _ = line.split("==", 1)
                try:
                    dependencies[name.lower().replace("_", "-")] = importlib.metadata.version(name)
                except importlib.metadata.PackageNotFoundError as exc:
                    raise CoreError("CONFIG_REQUIRED", "Reader build bağımlılığı eksik") from exc
    optional = {}
    names = sorted({n for group in OPTIONAL_DEPENDENCIES.values() for n in group}) if kind is None else OPTIONAL_DEPENDENCIES[kind]
    for name in names:
        try:
            optional[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            optional[name] = None
    return hash_value({"method": "reader-build/v3", "format": kind, "files": files, "python_abi": sys.implementation.cache_tag,
                       "python_version": list(sys.version_info[:3]), "pointer_bits": struct.calcsize("P") * 8,
                       "dependencies": dependencies, "optional_dependencies": optional})


def component_policy(root=ROOT):
    root = Path(root)
    policy = json.loads((root / "references/component-identity.json").read_text(encoding="utf-8"))
    plugin = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    if policy["schema"] != "contract-component-policy/v2" or policy["plugin_version"] != plugin["version"]:
        raise CoreError("PAKET_KIMLIGI", "Bileşen manifesti gerçek paketle uyuşmuyor")
    return policy


def component_identity(root=ROOT):
    root = Path(root)
    policy = component_policy(root)
    paths = [p for group in ["src", "schemas", "references", "skills", "scripts"] for p in (root / group).rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".md", ".png", ".svg"}]
    paths += [root / name for name in ["plugin.json", "requirements-core.txt", "requirements-readers.txt"]]
    files = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    return {"schema": "contract-component-identity/v2", "plugin_version": policy["plugin_version"],
            "core_version": policy["core_version"], "result_schema_version": policy["result_schema_version"],
            "runtime_profile": policy["runtime_profile"], "source_digest": hash_value(files),
            "source_commit": None, "source_commit_attestation": "UNVERIFIED", "python_abi": sys.implementation.cache_tag}
