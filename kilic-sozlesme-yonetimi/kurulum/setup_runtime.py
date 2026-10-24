"""Runs exclusively inside a new, app-owned embedded Python; atomic activation."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
sys.dont_write_bytecode=True

def main():
    p=argparse.ArgumentParser();p.add_argument("--plugin-root",required=True);p.add_argument("--runtime-id",required=True);p.add_argument("--check-only",action="store_true")
    args=p.parse_args();root=Path(args.plugin_root).resolve()
    sys.path.insert(0,str(root/"scripts"))
    from bootstrap_integrity import plain,sha,verify_package
    verify_package(root)
    from runtime_registry import profile,user_root
    from runtime_smoke import smoke
    env=plain(Path(sys.executable).parent);home=user_root()
    if env.parent!=home/"sozlesme-envs" or env.name!=args.runtime_id or str(uuid.UUID(hex=args.runtime_id)).replace("-","")!=args.runtime_id:
        raise ValueError("Unexpected installation path")
    result=smoke()
    if args.check_only:print(json.dumps(result));return
    files={p.relative_to(env).as_posix():sha(p) for p in sorted(env.rglob("*"))
           if p.is_file() and p != env/"runtime-files.json"}
    inventory=env/"runtime-files.json"
    with inventory.open("x",encoding="utf-8") as stream:
        json.dump(files,stream,sort_keys=True);stream.flush();os.fsync(stream.fileno())
    spec=profile(root)
    record={"schema":"contract-runtime/v1","runtime_id":args.runtime_id,"profile_id":spec["profile_id"],
        "lock_sha256":spec["lock_sha256"],"environment_root":str(env),"python_executable":sys.executable,
        "base_python_executable":sys.executable,"python_sha256":sha(sys.executable),
        "inventory_sha256":sha(inventory),"python_version":list(sys.version_info[:3]),"architecture":"win-amd64",
        "packages":spec["packages"],"smoke":result,"verified_at":dt.datetime.now(dt.timezone.utc).isoformat()}
    target=plain(home/"sozlesme-runtime.json");temporary=plain(home/("sozlesme-runtime."+args.runtime_id+".tmp"))
    with temporary.open("x",encoding="utf-8") as stream:
        json.dump(record,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,target)
    print(json.dumps({"status":"INSTALLED","runtime_id":args.runtime_id,"smoke":result}))
if __name__=="__main__":main()
