"""Update only teklif-degerlendirme from an explicitly pinned release package."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import uuid

from teklif_paket_legacy import (UpdateError, JOURNAL, REPO, component_versions,
    download, latest_release, linked, replace_path, sha, update_lock, validate_archive,
    version, write_json, read_json, safe_name)
from islem_guvencesi import atomic_bytes, reject_links, redact

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
        reject_links(path)
        state = read_json(path)
        version(state.get("version"))
        if state.get("repository") != REPO or not isinstance(state.get("files"), dict) or state["files"] != current:
            raise UpdateError("Yerel teklif skill'i kayıtla eşleşmiyor; üzerine yazılmaz.")
        for key in state["files"]:
            safe_name(key)
            if not key.startswith(f"skills/{NAME}/"):
                raise UpdateError("Kurulum kaydı hedef skill dışına çıkıyor.")
        vf = root / NAME / "VERSION"
        if not vf.is_file() or vf.read_text(encoding="utf-8").strip() != state["version"]:
            raise UpdateError("Kurulum kaydı ile gerçek VERSION eşleşmiyor.")
        return state
    old = root / OLD_STATE
    if old.exists():
        previous = read_json(old)
        all_files = previous.get("files")
        if not isinstance(all_files, dict):
            raise UpdateError("Eski kurulum kayıt şeması bozuk.")
        subset = {k: v for k, v in all_files.items() if k.startswith(f"skills/{NAME}/")}
        if previous.get("repository") != REPO or subset != current:
            raise UpdateError("Eski paket kaydı teklif skill'iyle eşleşmiyor.")
        val = previous["skill_versions"][NAME] if previous.get("schema") == 2 else previous["version"]
        version(val)
        vf = root / NAME / "VERSION"
        if not vf.is_file() or vf.read_text(encoding="utf-8").strip() != val:
            raise UpdateError("Eski kayıt ile gerçek VERSION eşleşmiyor.")
        return {"repository": REPO, "version": val, "files": subset}
    if current:
        raise UpdateError("Yönetimsiz teklif kurulumu; üzerine yazılmaz.")
    return None


def local_info(root):
    installed, warning, managed = None, None, True
    try:
        state = state_for(root)
        installed = state["version"] if state else None
    except (UpdateError, OSError, ValueError, KeyError, TypeError) as exc:
        warning, managed = str(exc), False
        vf = root / NAME / "VERSION"
        if vf.is_file():
            installed = vf.read_text(encoding="utf-8").strip()
    return {"version": installed, "path": str(root / NAME), "managed": managed,
            "tree_sha256": sha(json.dumps(tree(root), sort_keys=True).encode()), "integrity_error": warning}


def release_package(release):
    tokens = download(release["checksum_url"], 4096).decode("ascii").strip().split()
    if len(tokens) != 2 or tokens[1].lstrip("*") != release["name"]:
        raise UpdateError("Paket checksum kaydı geçersiz.")
    data = download(release["archive_url"])
    manifest, _ = validate_archive(data, tokens[0], release["version"])
    return data, tokens[0].lower(), component_versions(manifest)[NAME]


def inspect(root, prepared=None):
    local = local_info(root)
    release = latest_release()
    if release is None:
        return {"status": "no_release", "installed": local["version"], "local": local,
                "warning": "Kararlı yayın yok veya depo erişilemiyor."}
    data, digest, latest = release_package(release)
    if prepared is not None:
        prepared.update(data=data, digest=digest)
    available = local["version"] is None or version(latest) > version(local["version"])
    return {"status": "available" if available else "up_to_date", "installed": local["version"],
            "latest": latest, "managed": local["managed"], "warning": local["integrity_error"],
            "local": local, "release": release, "archive_sha256": digest}


def apply(root, data, digest, release_version, expected_version=None):
    manifest, files = validate_archive(data, digest, release_version)
    selected = {k: v for k, v in files.items() if k.startswith(f"skills/{NAME}/")}
    new_version = component_versions(manifest)[NAME]
    if expected_version is not None and new_version != expected_version:
        raise UpdateError("Onaylanan bileşen sürümü farklı; kurulmadı.")
    if not selected or new_version != selected[f"skills/{NAME}/VERSION"].decode().strip():
        raise UpdateError("Teklif skill'i pakette eksik veya sürümü farklı.")
    with update_lock(root):
        old = state_for(root)
        if old and version(new_version) <= version(old["version"]):
            raise UpdateError("Teklif skill sürümü yeni değil; değişiklik yapılmadı.")
        stage = root / (".teklif-only-stage-" + uuid.uuid4().hex)
        stage.mkdir(mode=0o755)
        target, previous = root / NAME, stage / "old"
        old_state = (root / STATE).read_bytes() if (root / STATE).exists() else None
        placed = moved = state_written = committed = False
        rollback_ok = True
        warning = None
        backup_path = None
        try:
            fresh = stage / NAME
            for relative, content in selected.items():
                dest = fresh / PurePosixPath(relative).relative_to(f"skills/{NAME}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
            expected = {k: sha(v) for k, v in selected.items()}
            actual = {f"skills/{NAME}/{p.relative_to(fresh).as_posix()}": sha(p.read_bytes()) for p in fresh.rglob("*") if p.is_file()}
            if actual != expected or tree(root) != (old["files"] if old else {}):
                raise UpdateError("Hazırlık/yerel dosya bütünlüğü değişti.")
            write_json(root / JOURNAL, {"phase": "PREPARED", "stage": stage.name, "target": NAME,
                                       "to_version": new_version, "archive_sha256": digest})
            if old_state is not None:
                (stage / "old-state.json").write_bytes(old_state)
            if target.exists():
                replace_path(target, previous); moved = True
            replace_path(fresh, target); placed = True
            if tree(root) != expected:
                raise UpdateError("Kurulan teklif dosyaları doğrulanamadı.")
            new_state = {"repository": REPO, "version": new_version, "files": expected}
            temporary = stage / "state.json"
            write_json(temporary, new_state)
            replace_path(temporary, root / STATE); state_written = True
            state_for(root)
            write_json(root / JOURNAL, {"phase": "COMMITTED", "stage": stage.name, "target": NAME,
                                       "to_version": new_version, "archive_sha256": digest})
            committed = True
        except BaseException:
            try:
                if placed: replace_path(target, stage / "failed")
                if moved: replace_path(previous, target)
                if state_written:
                    if old_state is None: (root / STATE).unlink(missing_ok=True)
                    else: atomic_bytes(root / STATE, old_state)
            except OSError:
                rollback_ok = False
            raise
        finally:
            if committed:
                # Preserve the previous tree for a deliberate maintenance recovery.
                try:
                    backup_path = root / (".teklif-backup-" + uuid.uuid4().hex)
                    replace_path(stage, backup_path)
                    (root / JOURNAL).unlink(missing_ok=True)
                except OSError as exc:
                    warning = "Kurulum tamamlandı; yedek/temizlik incelemesi gerekli: " + str(exc)
            elif rollback_ok:
                (root / JOURNAL).unlink(missing_ok=True)
                shutil.rmtree(stage)
        return {"status": "installed", "version": new_version, "release": release_version,
                "warning": warning, "backup": str(backup_path) if backup_path else None,
                "health": "INTEGRITY_PASS", "ozet": "UYARI" if warning else "GEÇTİ"}


def register(root, data, digest, *, replace_local=False):
    manifest, files = validate_archive(data, digest)
    selected = {k: sha(v) for k, v in files.items() if k.startswith(f"skills/{NAME}/")}
    candidate = {"repository": REPO, "version": component_versions(manifest)[NAME], "files": selected}
    with update_lock(root):
        if tree(root) != selected or (root / NAME / "VERSION").read_text(encoding="utf-8").strip() != candidate["version"]:
            raise UpdateError("Yerel teklif skill'i doğrulanmış paketle birebir eşleşmiyor.")
        if (root / STATE).exists():
            existing = read_json(root / STATE)
            if existing != candidate and (not replace_local or existing.get("version") != candidate["version"]):
                raise UpdateError("Farklı kayıt var; açık yerel aday yetkisi olmadan üzerine yazılmaz.")
        write_json(root / STATE, candidate)
        return {"status": "registered", "version": candidate["version"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("check", "prepare", "probe", "update", "verify", "register"))
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--archive", type=Path)
    ap.add_argument("--sha256")
    ap.add_argument("--release")
    ap.add_argument("--expected-version")
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--replace-local", action="store_true")
    args = ap.parse_args()
    try:
        reject_links(args.root)
        root = args.root.resolve()
        if args.replace_local and args.action != "register":
            raise UpdateError("--replace-local yalnız register ile kullanılabilir.")
        if args.action in ("register", "update"):
            if not args.archive or not args.sha256:
                raise UpdateError("Onaylanan yerel paket ve SHA-256 gerekli; hedef yeniden seçilmez.")
            reject_links(args.archive)
            if args.action == "register":
                result = register(root, args.archive.read_bytes(), args.sha256, replace_local=args.replace_local)
            else:
                if not args.release or not args.expected_version:
                    raise UpdateError("Onaylanan yayın ve bileşen sürümü gerekli.")
                result = apply(root, args.archive.read_bytes(), args.sha256, args.release, args.expected_version)
        elif args.action == "verify":
            state = state_for(root)
            if not state: raise UpdateError("Doğrulanacak teklif kurulumu yok.")
            result = {"status": "verified", "version": state["version"], "health": "INTEGRITY_PASS"}
        elif args.action == "probe":
            result = {"status": "observed", "local": local_info(root)}
        else:
            prepared = {}
            result = inspect(root, prepared)
            if args.action == "prepare" and prepared:
                if not args.cache: raise UpdateError("Hazırlık için geçici önbellek dizini gerekli.")
                reject_links(args.cache); args.cache.mkdir(parents=True, exist_ok=True)
                path = args.cache / (prepared["digest"] + ".zip")
                if path.exists() and sha(path.read_bytes()) != prepared["digest"]:
                    raise UpdateError("Önbellek paketi değiştirilmiş.")
                if not path.exists(): atomic_bytes(path, prepared["data"], require_absent=True)
                result["target"] = {"version": result["latest"], "release": result["release"]["version"],
                                    "archive": str(path), "sha256": prepared["digest"],
                                    "source": "GitHub verified manifest", "url": result["release"]["archive_url"]}
        print(json.dumps(redact(result), ensure_ascii=False)); return 0
    except (UpdateError, OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print(json.dumps({"status": "error", "ozet": "ENGEL", "error": redact(str(exc)), "neden": redact(str(exc))}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())