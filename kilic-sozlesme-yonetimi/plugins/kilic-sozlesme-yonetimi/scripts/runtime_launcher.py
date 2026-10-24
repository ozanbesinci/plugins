"""Single Work entry for preparation, request execution and all core CLI commands."""
import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from bootstrap_integrity import verify_package, plain
try:
    verify_package(ROOT)
except Exception as exc:
    print('@@SONUC '+json.dumps({'status':'BLOCKED','error':'PAKET_BUTUNLUK','message':str(exc),'resume_allowed':False}))
    raise SystemExit(2)
from runtime_registry import current, read_json, RuntimeErrorDetail, user_root

def emit(value):
    print("@@SONUC "+json.dumps(value,ensure_ascii=False),flush=True)

def atomic_new(path, value):
    path = plain(path)
    data = json.dumps(value,ensure_ascii=False).encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())

def state_roots(explicit=None):
    roots = [user_root()/"sozlesme-state"]
    profile = Path(os.environ["USERPROFILE"])
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"])/"KilicSozlesme/runtime")
    roots.append(profile/"AppData/Local/KilicSozlesme/runtime")
    packages = profile/"AppData/Local/Packages"
    if packages.is_dir():
        roots.extend(p/"LocalCache/Local/KilicSozlesme/runtime" for p in packages.glob("OpenAI.Codex*") if p.is_dir())
    if explicit: roots.append(Path(explicit).absolute())  # Read old state; new claims always use the stable root.
    return list(dict.fromkeys(plain(p) for p in roots))

def run_core(args, claim=None):
    # Source path is explicitly inserted by the wrapper; -I never relies on PYTHONPATH.
    environment = dict(os.environ)
    environment.pop("SOZLESME_REQUEST_CLAIM", None)
    if claim is not None: environment["SOZLESME_REQUEST_CLAIM"] = str(claim)
    process = subprocess.run([sys.executable,"-I","-B","-X","utf8",str(ROOT/"scripts/contract_cli.py"),*args],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600,env=environment,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    if len(process.stdout)>4*1024*1024 or len(process.stderr)>65536:
        raise RuntimeErrorDetail("CLI_OUTPUT_LIMIT","Çekirdek çıktı sınırını aştı")
    try: value = json.loads(process.stdout.decode("utf-8"))
    except (ValueError,UnicodeError) as exc:
        raise RuntimeErrorDetail("CLI_PROTOCOL_ERROR","Çekirdek yapılandırılmış sonuç üretmedi") from exc
    return process.returncode,value

def request_run(args, runtime):
    path = plain(Path(args.request).absolute())
    allowed = [plain(Path(root).absolute()) for root in args.source_root]
    if (not allowed or path.suffix.lower()!=".json" or not path.is_file()
            or not any(path.is_relative_to(root) and path!=root for root in allowed)):
        raise RuntimeErrorDetail("REQUEST_INVALID","Request outside allowed source roots")
    if path.stat().st_size>65536: raise RuntimeErrorDetail("REQUEST_INVALID","Request exceeds 64 KiB")
    raw = path.read_bytes(); request = read_json(path,65536)
    identifier = str(uuid.UUID(request["request_id"]))
    if request["request_id"]!=identifier or request.get("skill_id")!=args.skill:
        raise RuntimeErrorDetail("REQUEST_INVALID","Request id/skill mismatch")
    digest = hashlib.sha256(raw).hexdigest()
    roots = state_roots(args.state_root)
    for root in roots:
        for name in ("bootstrap-active.json","active-install.json"):
            if (root/name).exists():
                raise RuntimeErrorDetail("RECOVERY_REQUIRED","Unfinished runtime transaction; no automatic retry")
        for suffix in (".json",".final.json"):
            if (root/"requests"/(identifier+suffix)).exists():
                raise RuntimeErrorDetail("RECOVERY_REQUIRED","İstek kaydı var; aynı istek körlemesine tekrarlanmadı")
    ledger = roots[0]/"requests"; plain(ledger); ledger.mkdir(parents=True,exist_ok=True)
    claim = {"schema":"contract-request-claim/v1","status":"STARTED","request_id":identifier,
        "request_sha256":digest,"skill_id":args.skill,"runtime_id":runtime["runtime_id"],
        "lock_sha256":runtime["lock_sha256"],"workspace":str(plain(args.workspace)),
        "output_root":str(plain(args.output_root)),"source_roots":[str(p) for p in allowed],
        "started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"retry_safety":"NO_BLIND_RETRY"}
    if path.read_bytes()!=raw: raise RuntimeErrorDetail("REQUEST_CHANGED","İstek yürütüm öncesinde değişti")
    atomic_new(ledger/(identifier+".json"),claim)  # FileMode CreateNew serializes same-ID launches.
    try:
        if path.read_bytes()!=raw: raise RuntimeErrorDetail("REQUEST_CHANGED","İstek değişti")
        command = ["--workspace",args.workspace,"--output-root",args.output_root]
        for p in allowed: command += ["--source-root",str(p)]
        command += ["skill-evaluate","--request",str(path)]
        code,result = run_core(command, ledger/(identifier+".json"))
        final = {"schema":"contract-request-final/v1","request_id":identifier,"request_sha256":digest,
                 "runtime_id":runtime["runtime_id"],"status":"COMPLETED" if code==0 else "FAILED",
                 "business_acceptance":"NOT_GRANTED","result":result,"process_exit_code":code}
    except Exception:
        # A claim without final is deliberately recoverable, never retried automatically.
        raise
    temporary = ledger/(identifier+"."+uuid.uuid4().hex+".tmp")
    atomic_new(temporary,final)
    os.rename(temporary,ledger/(identifier+".final.json"))  # Windows no overwrite.
    emit({"status":"COMPLETED" if code==0 else "BLOCKED","resume_allowed":False,
          "runtime_id":runtime["runtime_id"],"result":result,"business_acceptance":"NOT_GRANTED"})
    return code

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="action",required=True)
    for name in ("prepare","run"):
        p=sub.add_parser(name);p.add_argument("--skill",required=True);p.add_argument("--state-root")
        if name=="run":
            p.add_argument("--request",required=True);p.add_argument("--workspace",required=True)
            p.add_argument("--output-root",required=True);p.add_argument("--source-root",action="append",required=True)
    sub.add_parser("cli").add_argument("arguments",nargs=argparse.REMAINDER)
    try:
        args=parser.parse_args()
        verify_package(ROOT)
        runtime=current(ROOT)
        if args.action=="cli":
            values=args.arguments
            if values[:1]==["--"]: values=values[1:]
            if "skill-evaluate" in values:
                raise RuntimeErrorDetail("REQUEST_ENTRY_REQUIRED","Beceri değerlendirmesi run girişiyle başlatılmalı")
            code,value=run_core(values)
            print(json.dumps(value,ensure_ascii=False));return code
        skills=read_json(ROOT/"references/skill-versions.json")
        if args.skill not in skills: raise RuntimeErrorDetail("SKILL_UNKNOWN","Beceri kimliği geçersiz")
        meta=skills[args.skill]
        if (ROOT/"skills"/meta["slug"]/"VERSION").read_text().strip()!=meta["version"]:
            raise RuntimeErrorDetail("PAKET_BUTUNLUK","Beceri sürümü uyuşmuyor")
        print(meta["startup_message"],flush=True)
        for state in state_roots(args.state_root):
            if any((state/name).exists() for name in ("bootstrap-active.json","active-install.json")):
                raise RuntimeErrorDetail("RECOVERY_REQUIRED","Unfinished runtime transaction; no automatic retry")
        if args.action=="prepare":
            emit(dict(runtime,resume_allowed=True,startup_message=meta["startup_message"]));return 0
        return request_run(args,runtime)
    except Exception as exc:
        emit({"status":"BLOCKED","error":getattr(exc,"code","RUNTIME_MISMATCH"),
              "message":str(exc),"resume_allowed":False,"business_acceptance":"NOT_GRANTED"})
        return 2
if __name__=="__main__": raise SystemExit(main())
