"""DuckDB metadata scan, pinned wheel installation and an isolated CSV smoke test."""
from __future__ import annotations
import argparse
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

# The historical filename is retained; reuse the package-set runtime primitives.
_spec = importlib.util.spec_from_file_location("kurulum_testi", Path(__file__).with_name("kurulum-testi.py"))
base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(base)
from islem_guvencesi import SafetyError, redact


def local_info():
    try: val = metadata.version("duckdb")
    except metadata.PackageNotFoundError: val = None
    return {"version": val, "python": sys.executable}


def validate_wheels(packages):
    if not isinstance(packages, list): raise SafetyError("Wheel planı liste olmalı.")
    names = set()
    for p in packages:
        u = urlsplit(p.get("url", ""))
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+", p.get("name", "")) or p["name"].lower() in names
                or not re.fullmatch(r"[a-fA-F0-9]{64}", p.get("sha256", ""))
                or not re.fullmatch(r"\d+(?:\.\d+)*", p.get("version", ""))
                or u.scheme != "https" or u.hostname != "files.pythonhosted.org" or u.username or u.password or u.port not in (None, 443)):
            raise SafetyError("Wheel planındaki paket/kaynak/hash geçersiz.")
        names.add(p["name"].lower())
    return packages


def resolve_target(repair=False):
    with tempfile.TemporaryDirectory(prefix="guncelleyici-resolve-") as td:
        report = Path(td) / "resolution.json"
        command = [sys.executable, "-B", "-m", "pip", "install", "--dry-run", "--report", str(report),
                   "--upgrade", "--upgrade-strategy", "only-if-needed", "--only-binary=:all:",
                   "--index-url", "https://pypi.org/simple", "--no-input", "--disable-pip-version-check", "--no-cache-dir", "duckdb"]
        if sys.prefix == sys.base_prefix: command.append("--user")
        if repair: command.append("--ignore-installed")
        proc = base.run(command, 300)
        if proc.returncode != 0 or not report.exists(): raise SafetyError("DuckDB uyumlu wheel çözümü alınamadı: " + redact(proc.stderr[-600:]))
        report_obj = json.loads(report.read_text(encoding="utf-8"))
    packages = []
    for item in report_obj.get("install", []):
        info = item.get("download_info", {})
        packages.append({"name": item["metadata"]["name"], "version": item["metadata"]["version"],
                         "sha256": info.get("archive_info", {}).get("hashes", {}).get("sha256"), "url": info.get("url")})
    validate_wheels(packages)
    desired = next((p["version"] for p in packages if p["name"].lower() == "duckdb"), local_info()["version"])
    if not desired: raise SafetyError("DuckDB hedefi belirlenemedi.")
    return {"version": desired, "packages": packages, "python": sys.executable,
            "source": "PyPI compatible wheels", "repair": repair}


def smoke():
    code = r'''
import duckdb, tempfile, pathlib, json
with tempfile.TemporaryDirectory(prefix="guncelleyici-duckdb-test-") as td:
    p = pathlib.Path(td)/"test.csv"
    p.write_text("tedarikci;tutar\nÇağ Ltd;1250,50\nİşçi A.Ş.;749,50\nÇağ Ltd;1000\n",encoding="utf-8")
    con=duckdb.connect(str(pathlib.Path(td)/"test.duckdb"),config={"autoinstall_known_extensions":False,"autoload_known_extensions":False})
    try:
        con.execute("CREATE TABLE t AS SELECT * FROM read_csv(?,delim=';',decimal_separator=',',header=true)",[str(p)])
        rows=con.execute("SELECT tedarikci,SUM(tutar) FROM t GROUP BY 1 ORDER BY 1").fetchall()
        assert [[a,float(b)] for a,b in rows]==[["Çağ Ltd",2250.5],["İşçi A.Ş.",749.5]],rows
        print(json.dumps({"version":duckdb.__version__,"status":"PASS"}))
    finally: con.close()
'''
    proc = base.run([sys.executable, "-B", "-c", code], 120)
    if proc.returncode != 0: raise SafetyError("DuckDB işlev testi başarısız: " + redact(proc.stderr[-600:]))
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    if result.get("status") != "PASS": raise SafetyError("DuckDB test sonucu geçersiz.")
    return result


def install(target):
    base.ensure_runtime()
    if os.path.normcase(target.get("python", "")) != os.path.normcase(sys.executable): raise SafetyError("DuckDB yorumlayıcısı planla farklı.")
    packages = validate_wheels(target.get("packages"))
    before = local_info()
    if not packages: raise SafetyError("Kurulum için sabit wheel listesi yok; onarım taramasını kullanın.")
    wanted = next((p for p in packages if p["name"].lower() == "duckdb"), None)
    if wanted is None or wanted["version"] != target.get("version"): raise SafetyError("DuckDB hedef sürümü wheel listesiyle farklı.")
    with tempfile.TemporaryDirectory(prefix="guncelleyici-duckdb-") as td:
        req = Path(td)/"requirements.txt"
        req.write_text("\n".join(p["name"]+"=="+p["version"]+" --hash=sha256:"+p["sha256"] for p in packages)+"\n",encoding="utf-8")
        command=[sys.executable,"-B","-m","pip","install","--require-hashes","--no-deps","--only-binary=:all:",
                 "--index-url","https://pypi.org/simple","--no-input","--disable-pip-version-check","--no-cache-dir","-r",str(req)]
        if sys.prefix==sys.base_prefix: command.append("--user")
        if target.get("repair"): command.append("--force-reinstall")
        proc=base.run(command,1200)
    if proc.returncode != 0:
        return {"key":"duckdb","durum":"BASARISIZ","ozet":"ENGEL","before":before,"recovery_required":True,
                "neden":"Pip başarısız; eski ortamın korunduğu varsayılmadı.","detail":redact((proc.stdout+proc.stderr)[-1200:])}
    test=smoke()
    if test["version"] != target["version"]: raise SafetyError("Kurulan DuckDB sürümü onaylanan hedefle aynı değil.")
    return {"key":"duckdb","durum":"KURULDU","ozet":"GEÇTİ","surum":test["version"],"health":"PASS","before":before,
            "testler":[{"name":"Turkish CSV / grouped sum","status":"PASS"}]}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paket",choices=["duckdb"])
    ap.add_argument("--yalniz-bul",action="store_true");ap.add_argument("--local-only",action="store_true")
    ap.add_argument("--repair",action="store_true");ap.add_argument("--test-only",action="store_true")
    ap.add_argument("--target-file",type=Path);ap.add_argument("--target-sha256");ap.add_argument("--rapor")
    args=ap.parse_args(); mutation_started=False
    try:
        if args.yalniz_bul or args.local_only:
            local=local_info();target=None;error=None
            if not args.local_only:
                try: target=resolve_target(args.repair)
                except (OSError,ValueError,subprocess.SubprocessError) as exc: error=str(exc)
            result={"key":"duckdb","local":local,"surum":local["version"],"target":target,
                    "hedef_surum":target["version"] if target else None,"neden":error,"health":"NOT_RUN"}
        elif args.test_only:
            test=smoke();result={"key":"duckdb","surum":test["version"],"ozet":"GEÇTİ","health":"PASS"}
        else:
            target=base.read_target(args.target_file,args.target_sha256,"duckdb")
            base.ensure_runtime();mutation_started=True;result=install(target)
        print("@@SONUC "+json.dumps(redact(result),ensure_ascii=False));return 2 if result.get("ozet")=="ENGEL" else 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print("@@SONUC "+json.dumps({"key":"duckdb","durum":"BASARISIZ","ozet":"ENGEL","health":"FAIL",
                                     "neden":redact(str(exc)),"recovery_required":mutation_started},ensure_ascii=False));return 2


if __name__=="__main__":
    if hasattr(sys.stdout,"reconfigure"):sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())