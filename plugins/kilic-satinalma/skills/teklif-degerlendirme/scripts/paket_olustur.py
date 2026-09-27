"""Build an isolated, deterministic offer-skill release; never publish or upload."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import zipfile

SKILLS = ("teklif-degerlendirme",)
TOP = {"SKILL.md", "VERSION", "CHANGELOG.md", "KURULUM.md", "requirements.txt"}
DIRECTORIES = {"references", "scripts", "config", "agents"}
EXTENSIONS = {".md", ".py", ".json", ".yaml", ".toml"}


def build(root: Path, output: Path, release_version=None):
    root = root.resolve(); output = output.resolve()
    if output.is_relative_to(root):
        raise ValueError("Paket çıktısı ortak skills ağacının dışında olmalı.")
    if output.exists() or output.with_suffix(output.suffix + ".sha256").exists():
        raise ValueError("Var olan paket/hash üzerine yazılmaz; yeni çıktı konumu seçin.")
    files = {}; versions = {}
    for skill in SKILLS:
        folder = root / skill
        if folder.is_symlink() or (hasattr(folder, "is_junction") and folder.is_junction()):
            raise ValueError("Kaynak skill dizini fiziksel olmalı, keşif bağlantısı değil.")
        if output.is_relative_to(folder):
            raise ValueError("Paket çıktısı skill dizininde olamaz.")
        versions[skill] = (folder / "VERSION").read_text(encoding="utf-8").strip()
        for path in sorted(folder.rglob("*")):
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError("Paket kaynağında bağlantı var.")
            if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            rel = path.relative_to(folder)
            if not ((len(rel.parts) == 1 and rel.name in TOP) or
                    (rel.parts[0] in DIRECTORIES and path.suffix in EXTENSIONS and not any(p.startswith(".") for p in rel.parts))):
                raise ValueError(f"Dağıtım izin listesi dışında dosya: {skill}/{rel.as_posix()}")
            files[f"skills/{skill}/{rel.as_posix()}"] = path.read_bytes()
    release_version = release_version or versions[SKILLS[0]]
    # Import local validator only; no downloaded script is executed.
    sys.path.insert(0, str(root / "guncelleyici" / "scripts"))
    from teklif_paket_legacy import validate_archive, version
    version(release_version)
    manifest = {"schema": 3, "repository": "ozanbesinci/teklif-degerlendirme", "version": release_version,
                "versioning": "independent/v1", "skill_versions": versions,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}}
    files["release-manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    data = buffer.getvalue(); digest = hashlib.sha256(data).hexdigest()
    validate_archive(data, digest, release_version)
    expected_name = f"teklif-degerlendirme-v{release_version}.zip"
    if output.name != expected_name:
        raise ValueError(f"Release dosya adı {expected_name} olmalı.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as file:
        file.write(data)
    with output.with_suffix(".zip.sha256").open("x", encoding="ascii") as file:
        file.write(f"{digest}  {output.name}\n")
    return {"version": release_version, "files": len(manifest["files"]), "bytes": len(data), "sha256": digest, "archive": str(output)}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--release-version", help="Paket etiketi; varsayılan ana skill sürümü. Yalnız updater değiştiğinde ayrı paket etiketi kullanılabilir.")
    args = parser.parse_args()
    print(json.dumps(build(args.skills_root, args.output, args.release_version), ensure_ascii=False))
