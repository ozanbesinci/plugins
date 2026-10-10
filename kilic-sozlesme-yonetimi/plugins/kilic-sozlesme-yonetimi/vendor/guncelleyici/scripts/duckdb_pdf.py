"""Optional DuckDB PDF extension: plan bytes, verify in a new process, then commit.

No extension is loaded during scan. No unsigned mode, no bulk extension update,
no DuckDB downgrade, no OCR claim and no upload of user PDFs.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.parse
import uuid

from islem_guvencesi import SafetyError, atomic_bytes, atomic_json, digest_bytes, reject_links, redact, exclusive_lock

MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
HOST = "community-extensions.duckdb.org"


def source_url(engine, platform):
    if not re.fullmatch(r"\d+\.\d+\.\d+", engine) or platform != "windows_amd64":
        raise SafetyError("PDF dağıtımı için kararlı DuckDB ve windows_amd64 eşleşmesi gerekli.")
    return f"https://{HOST}/v{engine}/{platform}/pdf.duckdb_extension.gz"


def checked_download(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname != HOST or u.username or u.password or u.port not in (None, 443):
        raise SafetyError("PDF indirme kaynağı geçersiz.")
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            new = urllib.parse.urlsplit(newurl)
            if new.scheme != "https" or new.hostname != HOST or new.username or new.password or new.port not in (None, 443):
                raise SafetyError("PDF paketi farklı kaynağa yönlendirildi.")
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    request = urllib.request.Request(url, headers={"User-Agent": "guncelleyici-pdf"})
    with urllib.request.build_opener(Redirect()).open(request, timeout=45) as response:
        compressed = response.read(MAX_DOWNLOAD + 1)
    if len(compressed) > MAX_DOWNLOAD: raise SafetyError("PDF eklentisi indirme sınırı aşıldı.")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        binary = stream.read(MAX_EXPANDED + 1)
    if len(binary) > MAX_EXPANDED or not binary: raise SafetyError("PDF eklentisi açılmış boyut sınırı/geçerliliği aşıldı.")
    return binary


def worker_request(action, **values):
    command = [sys.executable, "-B", str(Path(__file__)), "--worker", action]
    for key, value in values.items(): command.extend(["--" + key.replace("_", "-"), str(value)])
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, env=env)
    if proc.returncode != 0: raise SafetyError("PDF alt süreç doğrulaması başarısız: " + redact((proc.stderr + proc.stdout)[-1200:]))
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    if result.get("status") == "error": raise SafetyError(result.get("error", "PDF worker error"))
    return result


def worker(action, args):
    import duckdb
    config = {"allow_unsigned_extensions": False, "autoinstall_known_extensions": False, "autoload_known_extensions": False}
    if args.extension_dir: config["extension_directory"] = str(args.extension_dir)
    con = duckdb.connect(config=config)
    try:
        engine = con.execute("SELECT version()").fetchone()[0].removeprefix("v")
        platform = con.execute("PRAGMA platform").fetchone()[0]
        if action == "install-test":
            if not args.archive or not args.extension_dir: raise SafetyError("İzole kurulum klasörü ve paket gerekli.")
            reject_links(args.archive)
            con.execute("INSTALL '" + str(args.archive).replace("'", "''") + "'")
        if action in {"install-test", "test"}:
            # Signature checking stays enabled. This executes trusted-by-user third-party code.
            con.execute("LOAD pdf")
            spec = importlib.util.spec_from_file_location("fixture_maker", Path(__file__).with_name("islev-testi.py"))
            fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
            with tempfile.TemporaryDirectory(prefix="guncelleyici-pdf-fixture-") as td:
                pdf = Path(td)/"test.pdf"; fixture.pdf_fixture(pdf); before = digest_bytes(pdf.read_bytes())
                rows = con.execute("SELECT page, text FROM read_pdf(?) ORDER BY page", [str(pdf)]).fetchall()
                if len(rows) != 1 or "12345" not in (rows[0][1] or ""): raise SafetyError("PDF golden metin/sayfa testi başarısız.")
                names = {x[0] for x in con.execute("SELECT DISTINCT function_name FROM duckdb_functions() WHERE function_name IN ('read_pdf','read_pdf_tables','pdf_info')").fetchall()}
                if names != {"read_pdf", "read_pdf_tables", "pdf_info"}: raise SafetyError("Beklenen PDF API'leri eksik.")
                if digest_bytes(pdf.read_bytes()) != before: raise SafetyError("PDF okuma testi kaynağı değiştirdi.")
        row = con.execute("SELECT extension_version, install_path, installed_from FROM duckdb_extensions() WHERE extension_name = 'pdf' AND installed").fetchone()
        binary = Path(row[1]) if row and row[1] else None
        location = con.execute("SELECT current_setting('extension_directory')").fetchone()[0]
        default_dir = (Path(location) if location else Path.home()/".duckdb"/"extensions") / ("v" + engine) / platform
        return {"status": "PASS" if action != "probe" else "observed", "engine": engine, "platform": platform,
                "version": row[0] if row else None, "installed_from": row[2] if row else None,
                "binary": str(binary) if binary else None, "sha256": digest_bytes(binary.read_bytes()) if binary and binary.is_file() else None,
                "destination": str(default_dir), "python": sys.executable,
                "test_scope": "one-page golden text + API presence; Turkish OCR/table accuracy not certified" if action != "probe" else None}
    finally: con.close()


def prepare(cache):
    local = worker_request("probe")
    url = source_url(local["engine"], local["platform"])
    binary = checked_download(url); digest = digest_bytes(binary)
    path = Path(cache)/"pdf"/digest/"pdf.duckdb_extension"
    reject_links(path)
    if path.exists() and digest_bytes(path.read_bytes()) != digest: raise SafetyError("PDF önbellek dosyası değişmiş.")
    if not path.exists(): atomic_bytes(path, binary, require_absent=True)
    target = {"version": digest, "sha256": digest, "archive": str(path), "url": url,
              "engine": local["engine"], "platform": local["platform"], "python": sys.executable,
              "source": "DuckDB Community (signature verified at install/load)", "destination": local["destination"],
              "license": "GPL-2.0-or-later", "optional": True}
    return {"key": "pdf", "local": local, "target": target, "surum": local["version"], "health": "NOT_RUN"}


def apply(target):
    if os.name != "nt": raise SafetyError("PDF kurulumu bu paket için Windows üzerinde yapılmalı.")
    current = worker_request("probe")
    if any(current[k] != target[k] for k in ("engine", "platform", "python", "destination")):
        raise SafetyError("DuckDB/yorumlayıcı/platform değişti; PDF için yeni tarama gerekli.")
    if target["url"] != source_url(target["engine"], target["platform"]): raise SafetyError("PDF hedef kaynağı geçersiz.")
    archive = reject_links(target["archive"])
    if digest_bytes(archive.read_bytes()) != target["sha256"]: raise SafetyError("PDF onaylanan paket hash'iyle eşleşmiyor.")
    destination = reject_links(target["destination"])
    destination.mkdir(parents=True, exist_ok=True)
    journal = destination/".pdf-update-journal.json"
    if journal.exists(): raise SafetyError("Yarım PDF işlemi var; otomatik silinmez.")
    backup = Path(os.environ["LOCALAPPDATA"])/"guncelleyici"/"pdf-backups"/uuid.uuid4().hex
    reject_links(backup); backup.mkdir(parents=True)
    with exclusive_lock(destination/".pdf-update.lock"), tempfile.TemporaryDirectory(prefix="guncelleyici-pdf-stage-") as td:
        verified = worker_request("install-test", archive=archive, extension_dir=td)
        binary = Path(verified["binary"])
        if digest_bytes(binary.read_bytes()) != target["sha256"]: raise SafetyError("Kurulan PDF dosyası onaylanan içerikten farklı.")
        files = [binary]
        info = binary.with_name(binary.name + ".info")
        if info.exists(): files.append(info)
        old = {}; installed = []; rollback_ok = True
        for file in files:
            out = destination/file.name; reject_links(out)
            old[file.name] = out.read_bytes() if out.exists() else None
            if old[file.name] is not None: atomic_bytes(backup/file.name, old[file.name], require_absent=True)
        atomic_json(journal, {"phase": "PREPARED", "backup": str(backup), "target_sha256": target["sha256"]})
        try:
            for file in files:
                out = destination/file.name
                atomic_bytes(out, file.read_bytes(), expected_hash=digest_bytes(old[file.name]) if old[file.name] is not None else None,
                             require_absent=old[file.name] is None)
                installed.append(file.name)
            final = worker_request("test")
            if final["sha256"] != target["sha256"]: raise SafetyError("PDF son konum hash'i farklı.")
            journal.unlink()
            return {"key": "pdf", "durum": "KURULDU", "ozet": "GEÇTİ", "health": "PASS", "surum": final["version"],
                    "sha256": final["sha256"], "backup": str(backup), "restart_required": True,
                    "test_scope": final["test_scope"], "neden": "Mevcut DuckDB süreçleri yeni eklenti için yeniden başlatılmalı."}
        except BaseException:
            try:
                for name in reversed(installed):
                    out = destination/name
                    if old[name] is None: out.unlink(missing_ok=True)
                    else: atomic_bytes(out, old[name])
            except (OSError, ValueError): rollback_ok = False
            if rollback_ok: journal.unlink(missing_ok=True)
            raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", nargs="?", choices=("scan", "probe", "apply", "test"))
    ap.add_argument("--worker", choices=("probe", "install-test", "test"))
    ap.add_argument("--cache", type=Path);ap.add_argument("--archive", type=Path);ap.add_argument("--extension-dir", type=Path)
    ap.add_argument("--target-file", type=Path);ap.add_argument("--target-sha256")
    args = ap.parse_args()
    mutation_requested = args.action == "apply"
    try:
        if args.worker: result = worker(args.worker, args)
        elif args.action == "scan":
            if not args.cache: raise SafetyError("Geçici önbellek dizini gerekli.")
            result = prepare(args.cache)
        elif args.action == "probe": result = {"key": "pdf", "local": worker_request("probe"), "health": "NOT_RUN"}
        elif args.action == "test": result = worker_request("test")
        elif args.action == "apply":
            spec = importlib.util.spec_from_file_location("package_runtime", Path(__file__).with_name("kurulum-testi.py"))
            runtime = importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
            result = apply(runtime.read_target(args.target_file, args.target_sha256, "pdf"))
        else: raise SafetyError("İşlem belirtilmedi.")
        print(("" if args.worker else "@@SONUC ") + json.dumps(redact(result), ensure_ascii=False)); return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, ImportError) as exc:
        result = {"key": "pdf", "status": "error", "durum": "BASARISIZ", "ozet": "ENGEL", "error": redact(str(exc)), "neden": redact(str(exc)), "health": "FAIL", "recovery_required": mutation_requested}
        print(("" if args.worker else "@@SONUC ") + json.dumps(result, ensure_ascii=False)); return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())