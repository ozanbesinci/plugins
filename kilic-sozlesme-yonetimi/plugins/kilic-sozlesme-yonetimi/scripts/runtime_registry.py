"""Read-only runtime binding. No downloads, installers or dependency mutation."""
import hashlib
import importlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import struct
import stat
import sys
from bootstrap_integrity import plain, sha, unique

ROOT = Path(__file__).resolve().parents[1]
if os.name == 'nt': sys._contract_dll_dir = os.add_dll_directory(sys.prefix)
MODULES = {"duckdb":"duckdb","jsonschema":"jsonschema","attrs":"attrs",
 "jsonschema-specifications":"jsonschema_specifications","referencing":"referencing",
 "rpds-py":"rpds","typing-extensions":"typing_extensions","lxml":"lxml.etree",
 "openpyxl":"openpyxl","et-xmlfile":"et_xmlfile","pypdf":"pypdf",
 "pypdfium2":"pypdfium2","pillow":"PIL.Image"}

class RuntimeErrorDetail(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

def read_json(path, limit=2*1024*1024):
    raw = plain(path).read_bytes()
    if len(raw) > limit:
        raise RuntimeErrorDetail("RUNTIME_MISMATCH", "Kayıt boyutu sınırı aşıldı")
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique)

def user_root():
    profile = os.environ.get("USERPROFILE")
    if not profile or not Path(profile).is_absolute():
        raise RuntimeErrorDetail("LOCAL_ACCESS_REQUIRED", "Windows kullanıcı alanı bulunamadı")
    return plain(Path(profile)/"KilicPython")

def requirements(root=ROOT):
    pins = {}
    for name in ("requirements-core.txt", "requirements-readers.txt"):
        for line in (Path(root)/name).read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)*)", line)
            if not match: raise RuntimeErrorDetail("RUNTIME_MISMATCH", "Geçersiz paket profili")
            key = re.sub(r"[-_.]+", "-", match[1].lower())
            if key in pins: raise RuntimeErrorDetail("RUNTIME_MISMATCH", "Yinelenen paket")
            pins[key] = match[2]
    if set(pins) != set(MODULES):
        raise RuntimeErrorDetail("RUNTIME_MISMATCH", "Paket kümesi değişmiş")
    return pins

def profile(root=ROOT):
    value = read_json(Path(root)/"references/runtime-profile.json")
    if value["lock_sha256"] != sha(Path(root)/"requirements-win-cp314.lock") or value["packages"] != requirements(root):
        raise RuntimeErrorDetail("RUNTIME_MISMATCH", "Paket kilidi/profili uyuşmuyor")
    return value

def runtime_inventory(env):
    """Walk each directory once; reject links before following or hashing entries."""
    env=plain(env);result={};pending=[env]
    while pending:
        directory=pending.pop()
        for entry in os.scandir(directory):
            info=entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode) or getattr(info,"st_file_attributes",0)&0x400:
                raise RuntimeErrorDetail("REPAIR_REQUIRED","Ortam içinde bağlantılı yol")
            path=Path(entry.path)
            if stat.S_ISDIR(info.st_mode):pending.append(path)
            elif stat.S_ISREG(info.st_mode) and path!=env/"runtime-files.json":
                result[path.relative_to(env).as_posix()]=sha(path)
    return result

def probe(root=ROOT):
    spec = profile(root)
    rows = []
    for name, wanted in requirements(root).items():
        try: actual = metadata.version(name)
        except metadata.PackageNotFoundError: actual = None
        status = "MISSING" if actual is None else "PASS" if actual == wanted else "VERSION_MISMATCH"
        if status == "PASS":
            try: importlib.import_module(MODULES[name])
            except Exception: status = "BROKEN"
        rows.append({"name":name, "required":wanted, "installed":actual, "status":status})
    runtime_ok = (os.name == "nt" and sys.version_info[:3] == tuple(spec["python_version"])
                  and struct.calcsize("P") == 8 and platform.machine().upper() in ("AMD64","X86_64"))
    sql = "NOT_RUN"
    if runtime_ok and all(row["status"] == "PASS" for row in rows):
        import duckdb
        con = duckdb.connect(config={"autoinstall_known_extensions":False,"autoload_known_extensions":False,"allow_unsigned_extensions":False})
        try: sql = "PASS" if con.execute("select 2+3").fetchone() == (5,) else "FAIL"
        finally: con.close()
    return {"status":"READY" if runtime_ok and sql == "PASS" else "RUNTIME_MISMATCH",
            "python":sys.executable, "python_version":platform.python_version(),
            "runtime_ok":runtime_ok,"packages":rows,"duckdb_sql":sql,
            "pdf_extension":"OPTIONAL_NOT_REQUIRED", "lock_sha256":spec["lock_sha256"]}

def current(root=ROOT):
    if os.name != "nt":
        raise RuntimeErrorDetail("LOCAL_ACCESS_REQUIRED","Bağlı Windows bilgisayarında yerel araç erişimi gerekli")
    spec = profile(root)
    home = user_root()
    record_path = home/"sozlesme-runtime.json"
    if not record_path.is_file():
        raise RuntimeErrorDetail("SETUP_REQUIRED","Ayrı Kılıç Sözleşme kurucusunu bir kez çalıştırın; Work içinden kurulum başlatılmadı")
    record = read_json(record_path)
    if (record.get("schema") != "contract-runtime/v1" or record.get("profile_id") != spec["profile_id"]
            or record.get("lock_sha256") != spec["lock_sha256"] or not re.fullmatch("[a-f0-9]{32}",record.get("runtime_id",""))):
        raise RuntimeErrorDetail("RUNTIME_MISMATCH","Kayıtlı ortam bu plugin profiliyle uyuşmuyor")
    env = plain(record["environment_root"])
    exe = plain(record["python_executable"])
    base = plain(record["base_python_executable"])
    if (not env.is_relative_to(home/"sozlesme-envs") or env.parent != home/"sozlesme-envs" or env.name != record["runtime_id"]
            or exe != env/"python.exe" or base != exe or not exe.is_file()):
        raise RuntimeErrorDetail("RUNTIME_MISMATCH","Kayıtlı Python yolu geçersiz")
    if Path(sys.executable).resolve() != exe.resolve():
        raise RuntimeErrorDetail("RUNTIME_MISMATCH","İşlem kayıtlı Python üzerinden başlatılmadı")
    if sha(exe) != record.get("python_sha256"):
        raise RuntimeErrorDetail("REPAIR_REQUIRED","Python dosyası değişmiş")
    inventory = read_json(env/"runtime-files.json")
    if sha(env/"runtime-files.json") != record.get("inventory_sha256"):
        raise RuntimeErrorDetail("REPAIR_REQUIRED","Ortam envanteri değişmiş")
    for name, digest in inventory.items():
        if "\\" in name or ":" in name or name.startswith("/") or any(p in ("",".","..") for p in name.split("/")):
            raise RuntimeErrorDetail("REPAIR_REQUIRED","Geçersiz ortam dosyası")
    if runtime_inventory(env) != inventory:
        raise RuntimeErrorDetail("REPAIR_REQUIRED","Ortam dosyası veya dosya kümesi değişmiş")
    observed = probe(root)
    if observed["status"] != "READY":
        raise RuntimeErrorDetail("RUNTIME_MISMATCH","Gerçek Python/paket kontrolü geçmedi")
    if record.get("smoke",{}).get("status") != "PASS":
        raise RuntimeErrorDetail("REPAIR_REQUIRED","Kurulum okuyucu kontrolü eksik")
    return dict(observed, runtime_id=record["runtime_id"],profile_id=spec["profile_id"],
                execution_profile="REGISTERED",base_python=str(base))

def entry_gate(root=ROOT):
    if os.environ.get("SOZLESME_DEVELOPMENT") == "1":
        return {"execution_profile":"DEVELOPMENT","status":"DEVELOPMENT_ONLY","business_acceptance":"NOT_GRANTED"}
    return current(root)

def claim_execution(path, request, runtime, workspace, output_root, source_roots, request_bytes=None):
    """Bind direct CLI calls to the one-use canonical claim; developer mode is labelled separately."""
    identifier = request.get("request_id", "")
    import uuid
    if str(uuid.UUID(identifier)) != identifier:
        raise RuntimeErrorDetail("REQUEST_INVALID","Geçersiz istek kimliği")
    ledger = plain(user_root()/"sozlesme-state/requests")
    expected = ledger/(identifier+".json")
    supplied = os.environ.get("SOZLESME_REQUEST_CLAIM", "")
    if not supplied or plain(supplied) != expected:
        raise RuntimeErrorDetail("REQUEST_ENTRY_REQUIRED","Beceri değerlendirmesi run girişiyle başlatılmalı")
    claim = read_json(expected,65536)
    digest=hashlib.sha256(path.read_bytes() if request_bytes is None else request_bytes).hexdigest()
    if (claim.get("schema") != "contract-request-claim/v1" or claim.get("status") != "STARTED"
            or claim.get("request_id") != identifier or claim.get("request_sha256") != digest
            or claim.get("skill_id") != request.get("skill_id") or claim.get("runtime_id") != runtime["runtime_id"]
            or plain(claim["workspace"]) != plain(workspace) or plain(claim["output_root"]) != plain(output_root)
            or set(map(plain,claim["source_roots"])) != set(map(plain,source_roots))
            or (ledger/(identifier+".final.json")).exists()):
        raise RuntimeErrorDetail("REQUEST_CHANGED","İstek ve çalışma kaydı uyuşmuyor")
    # No retry through the same inherited environment or by invoking the core twice.
    with plain(ledger/(identifier+".invoked")).open("xb") as stream:
        stream.write(claim["request_sha256"].encode("ascii"));stream.flush();os.fsync(stream.fileno())
