"""Read-only package and runtime diagnostics; installation lives outside the plugin."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from bootstrap_integrity import verify_package

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--action",choices=("probe","verify-package"),default="probe")
    args = parser.parse_args()
    try:
        integrity = verify_package(ROOT)
        from runtime_registry import current
        result = integrity if args.action == "verify-package" else current(ROOT)
        result["resume_allowed"] = result.get("status") == "READY"
        print("@@SONUC "+json.dumps(result,ensure_ascii=False))
        return 0
    except Exception as exc:
        print("@@SONUC "+json.dumps({"status":"BLOCKED","error":getattr(exc,"code","PAKET_BUTUNLUK"),
          "message":str(exc),"resume_allowed":False},ensure_ascii=False))
        return 2
if __name__ == "__main__": raise SystemExit(main())
