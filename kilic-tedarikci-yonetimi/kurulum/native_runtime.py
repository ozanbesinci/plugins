"""App-local VC DLLs from a hash-pinned Microsoft release; no global installation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

HERE=Path(__file__).resolve().parent
BOOTSTRAP=(b'import os, sys; sys._kilic_vc_directory = os.add_dll_directory('
           b'os.path.join(sys.prefix, "Scripts"))\n')
BOOTSTRAP=(b'import os, sys; sys._kilic_vc_directory = os.add_dll_directory('
           b'os.path.join(sys.prefix, "Scripts"))\n')

def checked_bytes(data, expected):
    if hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError('Microsoft yerel DLL paketi hash doğrulaması başarısız.')
    return data

def install(environment, root):
    profile=json.loads((HERE/'native-runtime.json').read_text(encoding='utf-8'))
    override=os.environ.get('KILIC_NATIVE_RUNTIME_PACKAGE')
    if override:
        data=Path(override).read_bytes()
    else:
        with urllib.request.urlopen(profile['url'],timeout=120) as response:
            if not response.url.startswith('https://download.visualstudio.microsoft.com/'):
                raise ValueError('Microsoft çalışma paketi kaynağı geçersiz.')
            data=response.read()
    checked_bytes(data,profile['sha256'])
    expand=str(Path(os.environ['SystemRoot'])/'System32/expand.exe')
    with tempfile.TemporaryDirectory(prefix='vc-local-',dir=root) as temporary:
        directory=Path(temporary)
        def extract(section,name,folder):
            meta=profile[section];chunk=data[meta['offset']:meta['offset']+meta['bytes']]
            checked_bytes(chunk,meta['sha256'])
            cabinet=directory/(section+'.cab');cabinet.write_bytes(chunk)
            folder.mkdir()
            result=subprocess.run([expand,'-F:'+name,str(cabinet),str(folder)],capture_output=True)
            if result.returncode:
                raise ValueError('Microsoft DLL arşivi açılamadı.')
        payload_dir=directory/'payload'
        extract('outer_cab',profile['minimum_payload'],payload_dir)
        minimum=payload_dir/profile['minimum_payload']
        checked_bytes(minimum.read_bytes(),profile['minimum_sha256'])
        dll_dir=directory/'dlls';dll_dir.mkdir()
        result=subprocess.run([expand,'-F:*',str(minimum),str(dll_dir)],capture_output=True)
        if result.returncode:raise ValueError('Microsoft x64 DLL arşivi açılamadı.')
        for name,wanted in profile['dlls'].items():
            value=checked_bytes((dll_dir/(name+'_amd64')).read_bytes(),wanted)
            (environment/'Scripts'/name).write_bytes(value)
        license_dir=directory/'license'
        extract('license_cab',profile['license_payload'],license_dir)
        license_data=checked_bytes((license_dir/profile['license_payload']).read_bytes(),profile['license_sha256'])
        (environment/'VC-RUNTIME-LICENSE.rtf').write_bytes(license_data)
    # Python venv redirectors can execute the base EXE. Use the documented,
    # process-local DLL directory API instead of changing PATH or the base Python.
    checked_bytes(BOOTSTRAP,profile['bootstrap_sha256'])
    (environment/'Lib/site-packages/kilic_native_runtime.pth').write_bytes(BOOTSTRAP)
    # Python venv redirectors can execute the base EXE. Use the documented,
    # process-local DLL directory API instead of changing PATH or the base Python.
    checked_bytes(BOOTSTRAP,profile['bootstrap_sha256'])
    (environment/'Lib/site-packages/kilic_native_runtime.pth').write_bytes(BOOTSTRAP)
    print('Microsoft C++ yerel DLL seti hazır: '+profile['version'],flush=True)
