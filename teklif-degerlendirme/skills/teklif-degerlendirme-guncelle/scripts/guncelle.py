"""Paired skill release installer. No LLM, shell hooks, or arbitrary remote code."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
import time
import zipfile

REPO = "ozanbesinci/teklif-degerlendirme"
SKILLS = ("teklif-degerlendirme", "teklif-degerlendirme-guncelle")
STATE = ".teklif-install.json"
UPDATE_LOCK = ".teklif-update.lock"
ANALYSIS_LOCK = ".teklif-analysis.lock"
JOURNAL = ".teklif-transaction.json"
MANIFEST = "release-manifest.json"
MAX_DOWNLOAD = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
MAX_FILES = 2000
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


class UpdateError(ValueError):
    pass


def version(value):
    if not isinstance(value, str) or not SEMVER.fullmatch(value):
        raise UpdateError("Yalnız X.Y.Z kararlı sürümleri desteklenir.")
    return tuple(map(int, value.split(".")))


def component_versions(manifest):
    """Schema 1 paired releases remain readable; schema 2 versions are independent."""
    version(manifest.get("version"))
    if manifest.get("schema") == 1:
        return {name: manifest["version"] for name in SKILLS}
    versions = manifest.get("skill_versions")
    if (manifest.get("schema") != 2 or manifest.get("versioning") != "independent/v1"
            or not isinstance(versions, dict) or set(versions) != set(SKILLS)):
        raise UpdateError("Bağımsız skill sürüm kaydı geçersiz.")
    for item in versions.values():
        version(item)
    return versions


def assert_upgrade(old, new):
    if version(new["version"]) <= version(old["version"]):
        raise UpdateError("Yalnız daha yeni paket sürümü kurulabilir.")
    before, after = component_versions(old), component_versions(new)
    for name in SKILLS:
        # Old updater 3.x was a bundle label, not an independent semantic version.
        migration = (name == SKILLS[1] and old.get("schema") == 1 and new.get("schema") == 2
                     and version(after[SKILLS[0]]) > version(before[SKILLS[0]]))
        if not migration and version(after[name]) < version(before[name]):
            raise UpdateError(f"Skill sürümü düşürülmez: {name}")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UpdateError(f"Kayıt okunamadı: {path}") from exc
    if not isinstance(obj, dict):
        raise UpdateError("JSON nesnesi gerekli.")
    return obj


def replace_path(source, target):
    """Bounded retries for transient Windows sharing locks; persistent errors still fail."""
    for attempt in range(5):
        try:
            return os.replace(source, target)
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (2 ** attempt))


def write_json(path, obj):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".teklif-write-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(obj, out, ensure_ascii=False, sort_keys=True, indent=2)
            out.flush(); os.fsync(out.fileno())
        replace_path(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def safe_name(name):
    if not isinstance(name, str) or "\\" in name or "\x00" in name or ":" in name:
        raise UpdateError("Güvensiz ZIP yolu.")
    parts = name.split("/")
    if any(p in {"", ".", ".."} or p.endswith((".", " ")) or any(ord(c) < 32 for c in p) for p in parts):
        raise UpdateError("Güvensiz ZIP yol parçası.")
    for p in parts:
        if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", p.split(".")[0]):
            raise UpdateError("Ayrılmış Windows dosya adı.")
    if name != MANIFEST and (len(parts) < 3 or parts[0] != "skills" or parts[1] not in SKILLS):
        raise UpdateError("Paket izinli iki skill dışına çıkıyor.")
    return name


def validate_archive(data, expected_sha, expected_version=None):
    if len(data) > MAX_DOWNLOAD or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha or "") or sha(data) != expected_sha.lower():
        raise UpdateError("Paket boyutu veya SHA-256 eşleşmiyor.")
    files = {}; seen = set(); size = 0
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist()) > MAX_FILES:
                raise UpdateError("Paket dosya sayısı sınırı aşıldı.")
            for info in z.infolist():
                name = safe_name(info.filename)
                key = unicodedata.normalize("NFC", name).casefold()
                mode = info.external_attr >> 16
                if key in seen or info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG}):
                    raise UpdateError("Yinelenmiş yol, dizin veya bağlantı paketi reddedildi.")
                seen.add(key); size += info.file_size
                if size > MAX_EXPANDED or info.flag_bits & 1:
                    raise UpdateError("Açılan paket boyutu/şifreleme sınırı aşıldı.")
                files[name] = z.read(info)
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise UpdateError("Bozuk ZIP.") from exc
    try:
        manifest = json.loads(files.pop(MANIFEST).decode("utf-8"))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise UpdateError("Sürüm manifesti yok veya bozuk.") from exc
    if not isinstance(manifest, dict) or manifest.get("schema") not in {1, 2} or manifest.get("repository") != REPO:
        raise UpdateError("Manifest kaynağı/şeması geçersiz.")
    version(manifest.get("version"))
    versions = component_versions(manifest)
    if expected_version and manifest["version"] != expected_version:
        raise UpdateError("Release ve paket sürümü farklı.")
    hashes = manifest.get("files")
    if not isinstance(hashes, dict) or set(hashes) != set(files) or any(sha(files[p]) != h for p, h in hashes.items()):
        raise UpdateError("Dosya manifesti eşleşmiyor.")
    for skill in SKILLS:
        prefix = f"skills/{skill}/"
        try:
            if files[prefix + "VERSION"].decode("utf-8").strip() != versions[skill]:
                raise UpdateError(f"Skill sürümü manifestle farklı: {skill}")
            body = files[prefix + "SKILL.md"].decode("utf-8").replace("\r\n", "\n")
            front = body.split("\n---", 1)[0]
            declared_version = re.search(r'(?m)^  version: ["\x27]?([0-9]+\.[0-9]+\.[0-9]+)["\x27]?\s*$', front)
            if not body.startswith("---\n") or f"name: {skill}\n" not in front + "\n" or not declared_version or declared_version[1] != versions[skill]:
                raise UpdateError("Skill giriş dosyası geçersiz.")
        except (KeyError, UnicodeError) as exc:
            raise UpdateError("Paket zorunlu skill dosyası eksik.") from exc
    for skill in (SKILLS if manifest["schema"] == 2 else SKILLS[:1]):
        try:
            changelog = files[f"skills/{skill}/CHANGELOG.md"].decode("utf-8")
            heading = re.search(r"(?m)^## v([0-9]+\.[0-9]+\.[0-9]+)\b", changelog)
            if not heading or heading[1] != versions[skill]:
                raise UpdateError(f"CHANGELOG sürümü skill ile aynı değil: {skill}")
        except (KeyError, UnicodeError) as exc:
            raise UpdateError("CHANGELOG eksik veya bozuk.") from exc
    if version(versions[SKILLS[0]]) >= (4, 0, 0):
        required = {"requirements.txt", "config/ajan-politikasi.json",
                    "scripts/ajan_yonetimi.py", "scripts/ajan_v4.py", "scripts/kayit_temeli.py", "scripts/model_secimi.py", "scripts/butce.py",
                    "scripts/veri_kontrol.py", "scripts/teklif_motoru.py", "scripts/excel_uret.py",
                    "scripts/excel_dogrula.py", "scripts/ortam_ve_belge.py", "scripts/cikti_denetimi.py",
                    "scripts/oturum_kaydi.py", "scripts/baslangic_mesaji.py"}
        missing = sorted(p for p in required if not files.get(f"skills/{SKILLS[0]}/{p}"))
        if missing or not files.get(f"skills/{SKILLS[1]}/scripts/guncelle.py"):
            raise UpdateError("v4 çalıştırma dosyaları eksik: " + ", ".join(missing))
    return manifest, files


def tree_files(root):
    result = {}
    for skill in SKILLS:
        folder = root / skill
        if linked(folder):
            raise UpdateError("Hedef keşif bağlantısı değil, fiziksel ortak skill kökü olmalı.")
        if not folder.exists():
            continue
        for p in folder.rglob("*"):
            if linked(p):
                raise UpdateError("Skill ağacında bağlantı var; işlem durdu.")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                result["skills/" + p.relative_to(root).as_posix()] = sha(p.read_bytes())
    return result


def verify_install(root):
    state = read_json(root / STATE)
    version(state.get("version"))
    if state.get("schema") not in {1, 2} or state.get("repository") != REPO or not isinstance(state.get("files"), dict):
        raise UpdateError("Kurulum kayıt şeması bozuk.")
    versions = component_versions(state)
    for path in state["files"]:
        safe_name(path)
    if tree_files(root) != state["files"]:
        raise UpdateError("Yerel dosya değişmiş, eksilmiş veya yönetilmeyen dosya eklenmiş; üzerine yazılmaz.")
    for skill in SKILLS:
        key = f"skills/{skill}/VERSION"
        if key not in state["files"] or (root / skill / "VERSION").read_text(encoding="utf-8").strip() != versions[skill]:
            raise UpdateError("Kurulu sürümler eşleşmiyor.")
    return state


@contextlib.contextmanager
def update_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / UPDATE_LOCK
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise UpdateError("Güncelleme kilidi var; eski kilit otomatik silinmez.") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump({"pid": os.getpid()}, out)
        if (root / ANALYSIS_LOCK).exists():
            raise UpdateError("Aktif analiz var; güncelleme yapılamaz.")
        if (root / JOURNAL).exists():
            raise UpdateError("Yarım kalmış işlem günlüğü var; elle inceleme gerekli.")
        yield
    finally:
        lock.unlink(missing_ok=True)


def install(root, data, expected_sha, *, register=False, expected_version=None, replace_local=False):
    root = Path(root).resolve()
    manifest, files = validate_archive(data, expected_sha, expected_version)
    with update_lock(root):
        if register:
            if tree_files(root) != manifest["files"]:
                raise UpdateError("Kaynak kurulum paketle aynı değil; kayıt yapılamaz.")
            if (root / STATE).exists():
                old = verify_install(root)
                if version(manifest["version"]) < version(old["version"]):
                    raise UpdateError("Sürüm düşürülmez.")
            write_json(root / STATE, manifest)
            return {"status": "registered", "version": manifest["version"]}
        old = verify_install(root) if (root / STATE).exists() else None
        if replace_local:
            if register or expected_version is not None or not old or old["version"] != manifest["version"] or component_versions(old) != component_versions(manifest):
                raise UpdateError("Yerel aday değişimi yalnız aynı paket/bileşen sürümlerindeki doğrulanmış kurulum içindir.")
        elif old:
            assert_upgrade(old, manifest)
        if not old and any((root / name).exists() or linked(root / name) for name in SKILLS):
            raise UpdateError("Yönetimsiz/eski kurulum üzerine yazılmaz.")
        # Python 3.13 Windows mkdtemp uses a private 0700 DACL. Moving its children
        # into the installation can make them unreadable to sandboxed clients.
        # Inherit the chosen installation root's existing permissions instead.
        stage = root / (".teklif-stage-" + uuid.uuid4().hex)
        stage.mkdir(mode=0o755, exist_ok=False)
        moved = []; placed = []; rollback_ok = True
        try:
            for relative, content in files.items():
                dest = stage / "new" / PurePosixPath(relative).relative_to("skills")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
            if tree_files(stage / "new") != manifest["files"]:
                raise UpdateError("Hazırlanan dosyalar doğrulanamadı.")
            if old and tree_files(root) != old["files"]:
                raise UpdateError("Hazırlık sırasında yerel dosyalar değişti; işlem durdu.")
            (stage / "old").mkdir()
            write_json(root / JOURNAL, {"stage": stage.name, "from_version": old["version"] if old else None,
                                        "to_version": manifest["version"]})
            for name in SKILLS:
                target = root / name
                if target.exists():
                    replace_path(target, stage / "old" / name); moved.append(name)
                replace_path(stage / "new" / name, target); placed.append(name)
            write_json(root / STATE, manifest)
            verify_install(root)
        except BaseException:
            try:
                for name in reversed(placed):
                    replace_path(root / name, stage / "new" / name)
                for name in reversed(moved):
                    replace_path(stage / "old" / name, root / name)
                if old:
                    write_json(root / STATE, old)
                else:
                    (root / STATE).unlink(missing_ok=True)
            except OSError:
                rollback_ok = False
            raise
        finally:
            if rollback_ok:
                (root / JOURNAL).unlink(missing_ok=True)
                # Stage is generated under this explicit install root, never a user-selected tree.
                if stage.parent != root or not stage.name.startswith(".teklif-stage-") or linked(stage):
                    raise UpdateError("Geçici işlem yolu doğrulanamadı.")
                shutil.rmtree(stage)
        return {"status": "installed", "version": manifest["version"],
                "skill_versions": component_versions(manifest), "replacement": "full-tree",
                "previous_version_removed": old is not None}


def allowed_url(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == "https" and p.hostname in {"api.github.com", "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"} and not p.username and not p.password and p.port in {None, 443}


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise UpdateError("İndirme başka/güvensiz sunucuya yönlendirildi.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, limit=MAX_DOWNLOAD):
    if not allowed_url(url):
        raise UpdateError("Yalnız güvenilen HTTPS indirme adresleri kullanılabilir.")
    req = urllib.request.Request(url, headers={"User-Agent": "teklif-degerlendirme-updater", "Accept": "application/vnd.github+json"})
    with urllib.request.build_opener(SafeRedirect()).open(req, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise UpdateError("İndirme boyutu sınırı aşıldı.")
    return data


def latest_release():
    try:
        release = json.loads(download(f"https://api.github.com/repos/{REPO}/releases/latest", 2 * 1024 * 1024))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not isinstance(release, dict) or release.get("draft") is not False or release.get("prerelease") is not False:
        raise UpdateError("Kararlı Release doğrulanamadı.")
    tag = release.get("tag_name", "")
    if not isinstance(tag, str) or not tag.startswith("v"):
        raise UpdateError("Release etiketi geçersiz.")
    version(tag[1:])
    name = f"teklif-degerlendirme-{tag}.zip"
    base = f"https://github.com/{REPO}/releases/download/{tag}/"
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        raise UpdateError("Release dosyaları geçersiz.")
    for required in (name, name + ".sha256"):
        matches = [a for a in assets if isinstance(a, dict) and a.get("name") == required and a.get("browser_download_url") == base + required]
        if len(matches) != 1:
            raise UpdateError("Release paket/hash dosyası eksik veya adres farklı.")
    return {"version": tag[1:], "tag": tag, "archive_url": base + name, "checksum_url": base + name + ".sha256", "name": name}


def check(root):
    root = Path(root).resolve()
    installed = None; installed_skills = None; managed = (root / STATE).exists()
    if managed:
        state = verify_install(root)
        installed = state["version"]; installed_skills = component_versions(state)
    release = latest_release()
    if release is None:
        return {"status": "no_release_or_repository_not_accessible", "installed": installed, "managed": managed}
    newer = installed is None or version(release["version"]) > version(installed)
    return {"status": "available" if newer else "up_to_date", "installed": installed,
            "installed_skills": installed_skills, "managed": managed, "release": release}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "update", "install", "register", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--replace-local", action="store_true", help="Yalnız açık yerel geliştirmede aynı sürüm adayını yeniden kur; normal update kullanmaz.")
    args = parser.parse_args(argv)
    try:
        if args.replace_local and args.action != "install":
            raise UpdateError("--replace-local yalnız yerel install eyleminde kullanılabilir.")
        if args.action == "verify":
            state = verify_install(args.root.resolve())
            result = {"status": "verified", "version": state["version"], "skill_versions": component_versions(state)}
        elif args.action in {"install", "register"}:
            if not args.archive or not args.sha256:
                raise UpdateError("Yerel paket ve doğrulanmış --sha256 gerekli.")
            result = install(args.root, args.archive.read_bytes(), args.sha256, register=args.action == "register", replace_local=args.replace_local)
        else:
            result = check(args.root)
            if args.action == "update" and result["status"] == "available":
                rel = result["release"]
                checksum = download(rel["checksum_url"], 4096).decode("ascii").strip().split()
                if len(checksum) != 2 or checksum[1].lstrip("*") != rel["name"]:
                    raise UpdateError("Paket checksum kaydı geçersiz.")
                result = install(args.root, download(rel["archive_url"]), checksum[0], expected_version=rel["version"])
        print(json.dumps(result, ensure_ascii=False)); return 0
    except (UpdateError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)); return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
