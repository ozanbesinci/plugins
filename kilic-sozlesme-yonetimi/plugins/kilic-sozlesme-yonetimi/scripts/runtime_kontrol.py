"""Stdlib bootstrap and isolated missing-dependency adapter to Güncelleyici 2.3.0.

No import of sozlesme_cekirdek, DuckDB or jsonschema at startup. Existing shared
packages are never installed into. No Python/Node processes are closed.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import uuid
import venv
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
UPDATER=ROOT/'vendor/guncelleyici'
sys.path.insert(0,str(UPDATER/'scripts'))
from islem_guvencesi import SafetyError, atomic_json, exclusive_lock, reject_links, redact

MODULES={'duckdb':'duckdb','jsonschema':'jsonschema','attrs':'attrs',
         'jsonschema-specifications':'jsonschema_specifications','referencing':'referencing',
         'rpds-py':'rpds','typing-extensions':'typing_extensions','lxml':'lxml.etree',
         'openpyxl':'openpyxl','et-xmlfile':'et_xmlfile','pypdf':'pypdf',
         'pypdfium2':'pypdfium2','pillow':'PIL.Image'}
MAX_ENV_PATH_UNITS=140

def validate_env_path(path):
    # Pinned wheels include long resource paths (e.g. lxml XSL). Reserve space
    # before creating an environment; no registry/policy change for long paths.
    if len(str(Path(path).absolute()).encode('utf-16-le'))//2>MAX_ENV_PATH_UNITS:
        raise SafetyError('İzole Python ortam yolu çok uzun; kısa RuntimeStateRoot gerekli (en fazla140 UTF-16 birimi venv kökü)')

def normalized(name): return re.sub(r'[-_.]+','-',name.lower())

def requirements():
    pins={}
    for name in ('requirements-core.txt','requirements-readers.txt'):
        for line in (ROOT/name).read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            match=re.fullmatch(r'([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)*)',line)
            if not match: raise SafetyError('Sabit runtime paket satırı geçersiz')
            key=normalized(match[1])
            if key not in MODULES or key in pins: raise SafetyError('Bilinmeyen/yinelenen runtime paketi')
            pins[key]=match[2]
    if set(pins)!=set(MODULES): raise SafetyError('Runtime paket kümesi eksik')
    return pins

def pin_hash():
    return hashlib.sha256(json.dumps(requirements(),sort_keys=True).encode()).hexdigest()

def load_updater(name):
    path=UPDATER/'scripts'/name
    spec=importlib.util.spec_from_file_location('updater_'+path.stem.replace('-','_'),path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def verify_upstream():
    manifest=json.loads((UPDATER/'MANIFEST.sha256.json').read_text(encoding='utf-8'))
    if manifest['version']!='2.3.0' or (UPDATER/'VERSION').read_text().strip()!='2.3.0':
        raise SafetyError('Güncelleyici 2.3.0 gerekli')
    for name,digest in manifest['files'].items():
        path=reject_links(UPDATER/name)
        if not path.is_relative_to(UPDATER) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise SafetyError('Güncelleyici motor dosyası değişti: '+name)

def pdf_probe():
    import duckdb
    config={'allow_unsigned_extensions':False,'autoinstall_known_extensions':False,'autoload_known_extensions':False}
    extension_root=os.environ.get('SOZLESME_PDF_EXTENSION_ROOT')
    if extension_root: config['extension_directory']=str(reject_links(extension_root))
    con=duckdb.connect(config=config)
    try:
        if con.execute('SELECT 2+3').fetchone()[0]!=5: raise SafetyError('DuckDB SQL smoke başarısız')
        row=con.execute("SELECT install_path FROM duckdb_extensions() WHERE extension_name='pdf' AND installed").fetchone()
        if not row: return {'status':'MISSING','installed':False}
        path=reject_links(row[0])
        if not path.is_file(): return {'status':'BROKEN','installed':True,'reason':'Eklenti kaydı var; ikili bulunamadı'}
        con.execute('LOAD pdf')
        names={x[0] for x in con.execute("SELECT DISTINCT function_name FROM duckdb_functions() WHERE function_name IN ('read_pdf','read_pdf_tables','pdf_info')").fetchall()}
        if names!={'read_pdf','read_pdf_tables','pdf_info'}: raise SafetyError('PDF API eksik')
        return {'status':'PASS','installed':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'engine':duckdb.__version__,'scope':'SIGNED_LOAD_AND_API_PRESENCE'}
    except Exception as exc:
        return {'status':'BROKEN','installed':True,'reason':redact(str(exc))[-600:]}
    finally: con.close()

def probe():
    runtime_ok=os.name=='nt' and sys.version_info[:2]==(3,14) and struct.calcsize('P')==8
    packages=[]
    for name,version in requirements().items():
        try: current=metadata.version(name)
        except metadata.PackageNotFoundError: current=None
        status='MISSING' if current is None else ('VERSION_MISMATCH' if current!=version else 'PASS')
        if status=='PASS':
            try: importlib.import_module(MODULES[name])
            except Exception: status='BROKEN'
        packages.append({'name':name,'installed':current,'required':version,'status':status})
    deps_ok=all(row['status']=='PASS' for row in packages)
    pdf=pdf_probe() if deps_ok and runtime_ok else {'status':'DEFERRED','installed':None}
    return {'status':'READY' if deps_ok and runtime_ok and pdf['status']=='PASS' else 'DEPENDENCIES_REQUIRED',
            'python':sys.executable,'python_version':sys.version.split()[0],'runtime_ok':runtime_ok,
            'packages':packages,'pdf':pdf,'pins_sha256':pin_hash(),'updater_version':'2.3.0',
            'extension_root':os.environ.get('SOZLESME_PDF_EXTENSION_ROOT')}

def child_json(python,action,*extra,timeout=240):
    command=[str(python),'-B','-X','utf8',str(Path(__file__).resolve()),'--action',action,*map(str,extra)]
    process=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    lines=[line[8:] for line in process.stdout.splitlines() if line.startswith('@@SONUC ')]
    if not lines: raise SafetyError('Runtime alt süreç sonucu eksik')
    result=json.loads(lines[-1])
    if process.returncode!=0 or result.get('status')=='ERROR': raise SafetyError(result.get('message','Runtime doğrulanamadı'))
    return result

def validate_resolution(items,pins):
    wheels=[]
    for item in items:
        info=item.get('download_info',{}); meta=item.get('metadata',{})
        wheels.append({'name':normalized(meta.get('name','')),'version':meta.get('version'),
            'url':info.get('url',''),'sha256':info.get('archive_info',{}).get('hashes',{}).get('sha256','')})
    load_updater('python-paket-kur.py').validate_wheels(wheels)
    if {p['name']:p['version'] for p in wheels}!=pins or any(not urlsplit(p['url']).path.endswith('.whl') for p in wheels):
        raise SafetyError('PyPI çözümü sabit paket/sürüm kümesiyle farklı')
    return wheels

def install_packages(python,state):
    base=load_updater('kurulum-testi.py')
    pins=requirements()
    resolution=state/'wheel-resolution.json'
    command=[str(python),'-B','-m','pip','install','--dry-run','--ignore-installed','--no-deps',
             '--report',str(resolution),'--only-binary=:all:','--index-url','https://pypi.org/simple',
             '--no-input','--disable-pip-version-check','--no-cache-dir']+[name+'=='+version for name,version in pins.items()]
    resolved=base.run(command,600)
    (state/'resolve-console.log').write_text(redact(resolved.stdout+'\n'+resolved.stderr),encoding='utf-8')
    if resolved.returncode or not resolution.is_file(): raise SafetyError('PyPI sabit wheel çözümü başarısız')
    wheels=validate_resolution(json.loads(resolution.read_text(encoding='utf-8'))['install'],pins)
    plan={'schema':'sozlesme-private-wheels/v1','python':str(python),'pins_sha256':pin_hash(),'packages':wheels}
    atomic_json(state/'wheel-plan.json',plan,require_absent=True)
    plan_digest=hashlib.sha256((state/'wheel-plan.json').read_bytes()).hexdigest()
    locked=state/'requirements-hashed.txt'
    locked.write_text('\n'.join(p['name']+'=='+p['version']+' --hash=sha256:'+p['sha256'] for p in wheels)+'\n',encoding='utf-8')
    # New venv only; never --user, --upgrade or --force-reinstall into existing packages.
    if hashlib.sha256((state/'wheel-plan.json').read_bytes()).hexdigest()!=plan_digest: raise SafetyError('Wheel planı değişti')
    run=base.run([str(python),'-B','-m','pip','install','--require-hashes','--no-deps','--only-binary=:all:',
                  '--index-url','https://pypi.org/simple','--no-input','--disable-pip-version-check',
                  '--no-cache-dir','-r',str(locked)],1200)
    (state/'pip-install-console.log').write_text(redact(run.stdout+'\n'+run.stderr),encoding='utf-8')
    if run.returncode: raise SafetyError('İzole Python paket kurulumu başarısız')
    checked=base.run([str(python),'-B','-m','pip','check'],90)
    (state/'pip-check-console.log').write_text(redact(checked.stdout+'\n'+checked.stderr),encoding='utf-8')
    if checked.returncode: raise SafetyError('İzole Python bağımlılık tutarlılığı başarısız')
    return {'plan_sha256':plan_digest,'packages':wheels}

def install_pdf(state):
    pdf=load_updater('duckdb_pdf.py')
    extension_root=os.environ.get('SOZLESME_PDF_EXTENSION_ROOT')
    if extension_root:
        extension_root=str(reject_links(extension_root))
        original_worker=pdf.worker_request
        def scoped_worker(action,**values):
            values.setdefault('extension_dir',extension_root)
            return original_worker(action,**values)
        pdf.worker_request=scoped_worker
    observed=pdf_probe()
    if observed['status']=='PASS': return {'status':'UNCHANGED','probe':observed}
    if observed['installed']: raise SafetyError('Mevcut PDF eklentisi bozuk; otomatik onarım/üzerine yazma yok')
    planned=pdf.prepare(state/'pdf-cache')
    if planned['local'].get('binary'): raise SafetyError('PDF taramasında mevcut ikili bulundu; değiştirilmedi')
    target=planned['target']
    atomic_json(state/'pdf-plan.json',target,require_absent=True)
    digest=hashlib.sha256((state/'pdf-plan.json').read_bytes()).hexdigest()
    if pdf.worker_request('probe').get('binary'): raise SafetyError('PDF planından sonra ikili oluşturuldu')
    if hashlib.sha256((state/'pdf-plan.json').read_bytes()).hexdigest()!=digest: raise SafetyError('PDF planı değişti')
    result=pdf.apply(target)
    if result.get('health')!='PASS': raise SafetyError('PDF kurulum sonrası işlev testi başarısız')
    return {'status':'INSTALLED','plan_sha256':digest,'result':result}

def install_missing(state_root):
    verify_upstream()
    state_root=reject_links(state_root)
    if not (os.name=='nt' and sys.version_info[:2]==(3,14) and struct.calcsize('P')==8):
        raise SafetyError('Yerel Windows amd64 Python3.14 gerekli')
    with exclusive_lock(state_root/'runtime-install.lock'):
        journal=state_root/'active-install.json'
        if journal.exists(): raise SafetyError('Yarım runtime kurulumu var; otomatik tekrar/silme yok')
        before=probe()
        if before['status']=='READY': return dict(before,installation='UNCHANGED')
        if before['pdf'].get('installed') and before['pdf']['status']=='BROKEN': raise SafetyError('Mevcut PDF bozuk; otomatik onarım yok')
        session=state_root/'sessions'/uuid.uuid4().hex
        session.mkdir(parents=True)
        atomic_json(journal,{'phase':'STARTED','session':str(session),'pins_sha256':pin_hash()},require_absent=True)
        python=Path(sys.executable); packages=None
        # Journal is retained on any failure. Failed private environments are never reused.
        if any(row['status']!='PASS' for row in before['packages']):
            env=state_root/'environments'/uuid.uuid4().hex[:12]
            reject_links(env)
            validate_env_path(env)
            venv.EnvBuilder(with_pip=True,clear=False).create(env)
            python=env/'Scripts/python.exe'
            packages=install_packages(python,session)
        # A new PDF is scoped to this plugin, including the default-runtime case.
        # No shared extension file or in-use DLL is overwritten.
        extension_root=state_root/'extensions'/pin_hash()
        os.environ['SOZLESME_PDF_EXTENSION_ROOT']=str(reject_links(extension_root))
        extension=child_json(python,'pdf-child','--state-root',session,timeout=900)
        after=child_json(python,'probe')
        if after['status']!='READY': raise SafetyError('Kurulum sonrası bütün bağımlılıklar doğrulanamadı')
        atomic_json(session/'result.json',{'status':'READY','before':before,'after':after,'packages':packages,'pdf':extension})
        atomic_json(state_root/'active-runtime.json',{'python':str(python),'pins_sha256':pin_hash(),
            'extension_root':str(extension_root),'mode':'PRIVATE_ENV' if python!=Path(sys.executable) else 'REGISTERED_RUNTIME'})
        journal.unlink()
        return dict(after,installation='INSTALLED',report=str(session/'result.json'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--action',choices=['probe','install','pdf-child','verify-upstream'],required=True)
    parser.add_argument('--state-root',type=Path)
    parser.add_argument('--auto-install-missing',action='store_true')
    args=parser.parse_args()
    try:
        verify_upstream()
        if args.action=='probe': result=probe()
        elif args.action=='verify-upstream': result={'status':'PASS','updater_version':'2.3.0'}
        elif args.action=='pdf-child':
            if not args.state_root: raise SafetyError('Kurulum oturumu gerekli')
            result=install_pdf(reject_links(args.state_root))
        else:
            if not args.auto_install_missing or not args.state_root: raise SafetyError('Eksik bileşen kurulum yetkisi/kökü gerekli')
            result=install_missing(args.state_root)
        print('@@SONUC '+json.dumps(redact(result),ensure_ascii=False)); return 0
    except Exception as exc:
        print('@@SONUC '+json.dumps({'status':'ERROR','message':redact(str(exc)),
              'resume_allowed':False,'recovery_required':args.action in {'install','pdf-child'}},ensure_ascii=False)); return 2

if __name__=='__main__': raise SystemExit(main())
