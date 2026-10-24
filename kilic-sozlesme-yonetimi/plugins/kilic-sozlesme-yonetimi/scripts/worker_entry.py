"""Trusted module bootstrap for isolated/embedded Python child processes."""
from pathlib import Path
import os
import runpy
import sys
sys.dont_write_bytecode=True
if os.name=="nt": sys._contract_dll_dir=os.add_dll_directory(sys.prefix)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
name=sys.argv[1]
if name not in {"sozlesme_cekirdek.readers.worker","sozlesme_cekirdek.verification_worker"}:
    raise SystemExit("Worker module is not allowlisted")
sys.argv=sys.argv[1:]
runpy.run_module(name,run_name="__main__")
