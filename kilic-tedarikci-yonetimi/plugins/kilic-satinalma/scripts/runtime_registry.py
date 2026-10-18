"""Read-only validation of the separately installed per-user offer runtime."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import struct
import sys

PACKAGE = Path(__file__).resolve().parents[1]

def profile():
    return json.loads((PACKAGE/'config/runtime-profile.json').read_text(encoding='utf-8'))

def registry_path():
    local = os.environ.get('USERPROFILE')
    if not local: raise ValueError('USERPROFILE bulunamadı; yerel ortam seçilemedi.')
    return Path(local)/'KilicPython/teklif-runtime.json'

def validate(record, expected, *, executable=None, version=None, package_version=None, user_profile=None):
    """Validate current state, never trust an earlier PASS or select a newer folder."""
    if record.get('schema')!='kilic-offer-runtime/v1': raise ValueError('Ortam kayıt şeması geçersiz.')
    if record.get('profile_id')!=expected['id'] or record.get('lock_sha256')!=expected['lock_sha256']:
        raise ValueError('Kurulu ortamın paket kilidi bu eklentiyle uyuşmuyor; ayrı kurucuyu çalıştırın.')
    if not isinstance(record.get('runtime_id'),str) or not record['runtime_id'].strip():
        raise ValueError('Ortam kimliği eksik.')
    current_version = version or platform.python_version()
    if not current_version.startswith(expected['python_series']+'.'):
        raise ValueError('Python serisi bu kilitle uyumlu değil.')
    local = Path(user_profile or os.environ.get('USERPROFILE',''))/'KilicPython'
    root = Path(record['environment_root']).resolve()
    python = Path(record['python']).resolve()
    if not root.is_relative_to(local.resolve()) or root==local.resolve():
        raise ValueError('Python ortamı kullanıcının KilicPython klasörü dışında.')
    if not python.is_relative_to(root) or not python.is_file():
        raise ValueError('Kayıtlı Python ortam içinde bulunamadı.')
    if executable is not None and Path(executable).resolve()!=python:
        raise ValueError('Komut kayıtlı Python ile çalıştırılmıyor.')
    if package_version is not None:
        for name, wanted in expected['packages'].items():
            try: actual=package_version(name)
            except importlib.metadata.PackageNotFoundError: actual=None
            if actual!=wanted: raise ValueError(f'Paket kilidi uyuşmuyor: {name}; gereken {wanted}, bulunan {actual}.')
    return {k:record[k] for k in ('runtime_id','profile_id','lock_sha256','python','environment_root')}

def recorded():
    if platform.system()!='Windows' or struct.calcsize('P')!=8:
        raise ValueError('Kayıtlı teklif ortamı Windows 64 bit gerektirir.')
    record=json.loads(registry_path().read_text(encoding='utf-8-sig'))
    machine=hashlib.sha256((platform.node()+'\0'+os.environ.get('USERNAME','')).encode()).hexdigest()
    if record.get('machine_id')!=machine:raise ValueError('Ortam kaydı bu bilgisayar/kullanıcıya ait değil.')
    return record

def current():
    record=recorded()
    sys.path.insert(0,str(PACKAGE/'skills/teklif-degerlendirme/scripts'))
    from calculation_runtime import current as calculation_current
    # Bind engine identity here; full content verification precedes every calculation.
    calculation=calculation_current(verify_files=False)
    return {**validate(record,profile(),executable=sys.executable,package_version=importlib.metadata.version),
            'machine_id':record['machine_id'],'calculation_runtime':calculation}

def bind_run(run, identity):
    """A continuation cannot silently switch computers, interpreters or locks."""
    path=Path(run)/'runtime_binding.json'
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8'))!=identity:
            raise ValueError('Koşu başka bir yerel Python ortamına bağlı; aynı bilgisayar/ortamla devam edin.')
        return
    Path(run).mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(identity,stream,ensure_ascii=False,indent=2)

