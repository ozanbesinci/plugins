"""Pinned package-set installation and functional checks (Python 3.14 / Windows x64).

Scan only reads installed metadata; it never writes a persistent result file.
The apply target is explicit and hash-bound. Shared --user installs require an
operator-controlled maintenance window; they are not advertised as transactional.
"""
from __future__ import annotations
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import sys
import tempfile

from islem_guvencesi import SafetyError, digest_bytes, redact, aggregate_checks, reject_links

DESTEK_SERI = (3, 14)
# Loaded from the checked-in lock, not a rolling PyPI version list.
LOCK_PATH = Path(__file__).resolve().parents[1] / "config" / "paket-seti.json"

def package_set():
    obj = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    if obj.get("schema") != "guncelleyici-package-set/v1" or len(obj.get("packages", [])) != 12:
        raise SafetyError("On iki paketli kilit dosyası gerekli.")
    names = set()
    for p in obj["packages"]:
        if not isinstance(p, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", p.get("name", "")):
            raise SafetyError("Geçersiz paket adı.")
        if p["name"] in names or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", p.get("version", "")):
            raise SafetyError("Yinelenen paket/geçersiz sabit sürüm.")
        names.add(p["name"])
        if not p.get("hashes") or any(not re.fullmatch(r"[a-f0-9]{64}", h) for h in p["hashes"]):
            raise SafetyError("Paket SHA-256 kaydı geçersiz.")
    return obj["packages"]

# Backwards compatibility for library inventory importers.
PAKETLER = [(p["name"], p["version"], p["hashes"]) for p in package_set()]


def local_info():
    versions = {}
    for name, _, _ in PAKETLER:
        try:
            dist = metadata.distribution(name)
            versions[name] = {"version": dist.version, "location": str(dist.locate_file(""))}
        except metadata.PackageNotFoundError:
            versions[name] = {"version": None, "location": None}
    return {"python": sys.executable, "python_version": platform.python_version(),
            "bits": struct.calcsize("P") * 8, "venv": sys.prefix != sys.base_prefix, "packages": versions}


def target_info():
    return {"version": digest_bytes(LOCK_PATH.read_bytes()), "packages": package_set(),
            "source": "skill pinned wheel SHA-256 set", "python": sys.executable,
            "python_series": "3.14", "architecture": "amd64", "repair": False}


def read_target(path, expected, key):
    if not path or not expected:
        raise SafetyError("Onaylanan hedef dosyası/hash gerekli.")
    reject_links(path)
    raw = Path(path).read_bytes()
    if digest_bytes(raw) != expected:
        raise SafetyError("Hedef dosyası değişti.")
    obj = json.loads(raw.decode("utf-8-sig"))
    if obj.get("key") != key or not isinstance(obj.get("target"), dict):
        raise SafetyError("Hedef bileşeni geçersiz.")
    token = os.environ.get("GUNCELLEYICI_RUN_TOKEN")
    if not token or obj.get("run_token") != token:
        raise SafetyError("Kurulum yalnız onaylı sohbet uygulama işlemi içinden başlatılır.")
    return obj["target"]


def pip_environment():
    env = dict(os.environ)
    # Deliberate proxy and CA configuration is preserved; package-source overrides are not.
    for key in tuple(env):
        if key.startswith("PIP_") and key not in {"PIP_CERT", "PIP_CLIENT_CERT", "PIP_PROXY"}:
            env.pop(key, None)
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    return env


def run(command, timeout=300):
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=pip_environment())


def ensure_runtime():
    if os.name != "nt" or sys.version_info[:2] != DESTEK_SERI or struct.calcsize("P") * 8 != 64:
        raise SafetyError("Kurulum Windows x64 / Python 3.14 gerektirir.")
    if os.environ.get("GUNCELLEYICI_MAINTENANCE") != "confirmed":
        raise SafetyError("Paylaşılan Python için bakım penceresi onayı gerekli.")


def functional_checks():
    command = [sys.executable, "-B", str(Path(__file__).with_name("islev-testi.py"))]
    with tempfile.TemporaryDirectory(prefix="guncelleyici-test-") as td:
        proc = run(command + [td], 300)
        checks = []
        for line in proc.stdout.splitlines():
            if line.startswith("@@T "):
                item = json.loads(line[4:])
                checks.append(item)
        if proc.returncode != 0 or not checks:
            checks.append({"name": "functional-test-process", "status": "FAIL", "detail": redact(proc.stderr[-600:])})
        return checks


def install(target):
    ensure_runtime()
    if target.get("packages") != package_set() or os.path.normcase(target.get("python", "")) != os.path.normcase(sys.executable):
        raise SafetyError("Onaylanan paket seti/yorumlayıcı değişti.")
    before = local_info()
    command = [sys.executable, "-B", "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
               "--only-binary=:all:", "--require-hashes", "--index-url", "https://pypi.org/simple", "--timeout", "60", "--no-cache-dir"]
    if sys.prefix == sys.base_prefix: command.append("--user")
    if target.get("repair"): command.append("--force-reinstall")
    with tempfile.TemporaryDirectory(prefix="guncelleyici-pip-") as td:
        requirements = Path(td) / "requirements.txt"
        requirements.write_text("\n".join(p["name"] + "==" + p["version"] + " " + " ".join("--hash=sha256:" + h for h in p["hashes"]) for p in package_set()) + "\n", encoding="utf-8")
        proc = run(command + ["-r", str(requirements)], 1200)
    if proc.returncode != 0:
        return {"key": "libraries", "durum": "BASARISIZ", "ozet": "ENGEL", "health": "FAIL",
                "before": before, "after": local_info(), "recovery_required": True,
                "neden": "Paket kurulumu başarısız; önceki durumun aynen korunduğu varsayılmadı.",
                "detail": redact((proc.stdout + proc.stderr)[-1600:])}
    # Fresh process metadata, never a cached importlib view after installation.
    probe = run([sys.executable, "-B", str(Path(__file__)), "--local-only"], 60)
    if probe.returncode != 0: raise SafetyError("Kurulum sonrası bağımsız paket gözlemi başarısız.")
    after = json.loads(probe.stdout.split("@@SONUC ")[-1])["local"]
    checks = functional_checks()
    matched = sum(after["packages"][p["name"]]["version"] == p["version"] for p in package_set())
    if matched != 12: checks.append({"name": "exact-package-set", "status": "FAIL", "detail": f"{matched}/12"})
    dep = run([sys.executable, "-B", "-m", "pip", "check", "--disable-pip-version-check"], 120)
    checks.append({"name": "pip-check", "status": "PASS" if dep.returncode == 0 else "WARNING", "detail": redact((dep.stdout + dep.stderr)[-800:])})
    state = aggregate_checks(checks)
    return {"key": "libraries", "durum": "KURULDU", "surum": f"{matched}/12 hedefte", "before": before,
            "after": after, "testler": checks, "health": state,
            "ozet": "GEÇTİ" if state == "PASS" else "ENGEL" if state == "FAIL" else "UYARI",
            "recovery_required": state == "FAIL", "neden": "" if state == "PASS" else "Paketler kuruldu; işlev/bağımlılık kontrollerini inceleyin."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yalniz-bul", action="store_true")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--kurma", action="store_true")
    ap.add_argument("--target-file", type=Path)
    ap.add_argument("--target-sha256")
    ap.add_argument("--rapor-klasoru")
    args = ap.parse_args()
    mutation_requested = bool(args.target_file) and not (args.local_only or args.yalniz_bul or args.kurma)
    try:
        if args.local_only or args.yalniz_bul:
            local = local_info()
            matched = sum(local["packages"][p["name"]]["version"] == p["version"] for p in package_set())
            result = {"key": "libraries", "local": local, "surum": f"{matched}/12 hedefte",
                      "matched": matched, "target": None if args.local_only else target_info(), "health": "NOT_RUN"}
        elif args.kurma:
            checks = functional_checks(); state = aggregate_checks(checks)
            result = {"key": "libraries", "health": state, "testler": checks,
                      "ozet": "GEÇTİ" if state == "PASS" else "ENGEL" if state == "FAIL" else "UYARI"}
        else:
            result = install(read_target(args.target_file, args.target_sha256, "libraries"))
        print("@@SONUC " + json.dumps(redact(result), ensure_ascii=False))
        return 2 if result.get("ozet") == "ENGEL" else 0
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        print("@@SONUC " + json.dumps({"key": "libraries", "durum": "BASARISIZ", "ozet": "ENGEL", "neden": redact(str(exc)), "health": "FAIL", "recovery_required": mutation_requested}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
