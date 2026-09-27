"""Update only teklif-degerlendirme from a verified release package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import uuid

from teklif_paket_legacy import (UpdateError, JOURNAL, REPO,
    component_versions, download, latest_release, linked, replace_path, sha,
    update_lock, validate_archive, version, write_json)

NAME = "teklif-degerlendirme"
STATE = ".guncelleyici-teklif-install.json"
OLD_STATE = ".teklif-install.json"


def tree(root):
    folder = root / NAME
    if linked(folder):
        raise UpdateError("Hedef skill bağlantı; fiziksel kökü kullanın.")
    result = {}
    if folder.exists():
        for path in folder.rglob("*"):
            if linked(path):
                raise UpdateError("Skill ağacında bağlantı var.")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                result[f"skills/{NAME}/{path.relative_to(folder).as_posix()}"] = sha(path.read_bytes())
    return result


def state_for(root):
    current = tree(root)
    path = root / STATE
    if path.exists():
        state = json.loads(path.read_text(encoding="utf-8"))
        if state.get("repository") != REPO or state.get("files") != current:
            raise UpdateError("Yerel teklif skill'i kayıtla eşleşmiyor; üzerine yazılmaz.")
        return state
    old = root / OLD_STATE
    if old.exists():
        previous = json.loads(old.read_text(encoding="utf-8"))
        subset = {k: v for k, v in previous.get("files", {}).items()
                  if k.startswith(f"skills/{NAME}/")}
        if previous.get("repository") != REPO or subset != current:
            raise UpdateError("Eski paket kaydı teklif skill'iyle eşleşmiyor.")
        return {"repository": REPO, "version": previous["skill_versions"][NAME]
                if previous.get("schema") == 2 else previous["version"], "files": subset}
    if current:
        raise UpdateError("Yönetimsiz teklif kurulumu; üzerine yazılmaz.")
    return None


def release_package(release):
    tokens = download(release["checksum_url"], 4096).decode("ascii").strip().split()
    if len(tokens) != 2 or tokens[1].lstrip("*") != release["name"]:
        raise UpdateError("Paket checksum kaydı geçersiz.")
    data = download(release["archive_url"])
    manifest, _ = validate_archive(data, tokens[0], release["version"])
    return data, tokens[0], component_versions(manifest)[NAME]


def inspect(root, prepared=None):
    warning = None
    try:
        state = state_for(root)
        installed = state["version"] if state else None
    except UpdateError as exc:
        state = None
        warning = str(exc)
        local_version = root / NAME / "VERSION"
        installed = local_version.read_text(encoding="utf-8").strip() if local_version.exists() else None
        if installed:
            version(installed)
    release = latest_release()
    if release is None:
        return {"status": "no_release", "installed": installed, "warning": warning}
    data, digest, latest = release_package(release)
    if prepared is not None:
        prepared.update(data=data, digest=digest)
    if installed is None:
        status = "available"
    else:
        status = "available" if version(latest) > version(installed) else "up_to_date"
    return {"status": status, "installed": installed, "latest": latest, "managed": warning is None,
            "warning": warning, "release": release}


def apply(root, data, digest, release_version):
    manifest, files = validate_archive(data, digest, release_version)
    selected = {key: content for key, content in files.items()
                if key.startswith(f"skills/{NAME}/")}
    new_version = component_versions(manifest)[NAME]
    if not selected or new_version != (selected[f"skills/{NAME}/VERSION"].decode().strip()):
        raise UpdateError("Teklif skill'i pakette eksik veya sürümü farklı.")
    with update_lock(root):
        old = state_for(root)
        if old and version(new_version) <= version(old["version"]):
            raise UpdateError("Teklif skill sürümü yeni değil; değişiklik yapılmadı.")
        stage = root / (".teklif-only-stage-" + uuid.uuid4().hex)
        stage.mkdir(mode=0o755)
        target = root / NAME
        previous = stage / "old"
        placed = False
        moved = False
        rollback_ok = True
        try:
            fresh = stage / NAME
            for relative, content in selected.items():
                dest = fresh / PurePosixPath(relative).relative_to(f"skills/{NAME}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
            expected = {k: sha(v) for k, v in selected.items()}
            if {f"skills/{NAME}/{p.relative_to(fresh).as_posix()}": sha(p.read_bytes())
                    for p in fresh.rglob("*") if p.is_file()} != expected:
                raise UpdateError("Hazırlanan teklif dosyaları doğrulanamadı.")
            if tree(root) != (old["files"] if old else {}):
                raise UpdateError("Hazırlık sırasında yerel skill değişti.")
            (root / JOURNAL).write_text(json.dumps({"stage": stage.name, "target": NAME}), encoding="utf-8")
            if target.exists():
                replace_path(target, previous)
                moved = True
            replace_path(fresh, target)
            placed = True
            if tree(root) != expected:
                raise UpdateError("Kurulan teklif dosyaları doğrulanamadı.")
            new_state = {"repository": REPO, "version": new_version, "files": expected}
            temporary = stage / "state.json"
            temporary.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
            replace_path(temporary, root / STATE)
            return {"status": "installed", "version": new_version, "release": release_version}
        except BaseException:
            try:
                if placed:
                    replace_path(target, stage / "failed")
                if moved:
                    replace_path(previous, target)
            except OSError:
                rollback_ok = False
            raise
        finally:
            if rollback_ok:
                (root / JOURNAL).unlink(missing_ok=True)
                shutil.rmtree(stage)


def register(root, data, digest, *, replace_local=False):
    manifest, files = validate_archive(data, digest)
    selected = {key: sha(content) for key, content in files.items()
                if key.startswith(f"skills/{NAME}/")}
    candidate = {"repository": REPO, "version": component_versions(manifest)[NAME],
                 "files": selected}
    with update_lock(root):
        if tree(root) != selected or (root / NAME / "VERSION").read_text(encoding="utf-8").strip() != candidate["version"]:
            raise UpdateError("Yerel teklif skill'i doğrulanmış paketle birebir eşleşmiyor.")
        if (root / STATE).exists():
            existing = json.loads((root / STATE).read_text(encoding="utf-8"))
            if existing != candidate:
                if not replace_local or existing.get("version") != candidate["version"]:
                    raise UpdateError("Farklı kayıt zaten var; açık yerel aday değişimi olmadan üzerine yazılmaz.")
                write_json(root / STATE, candidate)
            return {"status": "registered", "version": candidate["version"]}
        write_json(root / STATE, candidate)
        return {"status": "registered", "version": candidate["version"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "update", "verify", "register"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--replace-local", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.replace_local and args.action != "register":
            raise UpdateError("--replace-local yalnız register ile kullanılabilir.")
        if args.action == "register":
            if not args.archive or not args.sha256:
                raise UpdateError("Yerel paket ve doğrulanmış --sha256 gerekli.")
            result = register(root, args.archive.read_bytes(), args.sha256, replace_local=args.replace_local)
        elif args.action == "verify":
            state = state_for(root)
            if not state:
                raise UpdateError("Doğrulanacak teklif kurulumu bulunamadı.")
            result = {"status": "verified", "version": state["version"]}
        else:
            prepared = {}
            result = inspect(root, prepared)
            if args.action == "update" and result["status"] == "available":
                release = result["release"]
                result = apply(root, prepared["data"], prepared["digest"], release["version"])
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (UpdateError, OSError, ValueError, KeyError, UnicodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
