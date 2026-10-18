"""Separate per-user installation. The offer plugin never installs packages."""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import sysconfig
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from native_runtime import install as install_native_runtime

def atomic_bytes(path, data):
    pending = path.with_name(path.name + '.' + uuid.uuid4().hex + '.pending')
    pending.write_bytes(data)
    os.replace(pending, path)

def main():
    profile = json.loads((HERE/'runtime-profile.json').read_text(encoding='utf-8'))
    lock = HERE/'requirements-win-cp314.lock'
    if hashlib.sha256(lock.read_bytes()).hexdigest() != profile['lock_sha256']:
        raise ValueError('Paket kilidi değişmiş.')
    for field in ('version', 'url', 'sha256'):
        if os.environ.get('KILIC_BOOTSTRAP_'+field.upper()) != profile['installer'][field]:
            raise ValueError('Kur.cmd ile kurulum profili uyuşmuyor: '+field)
    if (platform.system() != 'Windows' or sys.version_info[:2] != (3,14)
            or sys.maxsize <= 2**32 or sysconfig.get_config_var('Py_GIL_DISABLED')):
        raise ValueError('Windows Python 3.14 / 64 bit gerekli.')
    if not os.environ.get('USERPROFILE'):
        raise ValueError('Kullanıcı klasörü bulunamadı.')
    root = Path(os.environ['USERPROFILE'])/'KilicPython'
    root.mkdir(parents=True, exist_ok=True)
    identity = uuid.uuid4().hex
    environment = root/'environments'/(profile['id']+'-'+identity[:8])
    log_path = root/('kurulum-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+identity[:8]+'.log')
    print('Kurulum kaydı: '+str(log_path), flush=True)
    with log_path.open('w', encoding='utf-8') as log:
        def checked(arguments):
            log.write(subprocess.list2cmdline([str(x) for x in arguments])+'\n')
            log.flush()
            with subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding='utf-8', errors='replace') as child:
                for line in child.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                if child.wait():
                    raise ValueError('Kurulum adımı başarısız; ayrıntı: '+str(log_path))
            log.flush()
        checked([sys.executable, '-X','utf8','-I','-B','-m','venv',str(environment)])
        python = environment/'Scripts/python.exe'
        pip = [str(python),'-X','utf8','-I','-B','-m','pip','--isolated',
               '--disable-pip-version-check','install','--only-binary=:all:',
               '--require-hashes','--no-cache-dir']
        wheelhouse = os.environ.get('KILIC_WHEELHOUSE')
        if wheelhouse:
            pip.extend(['--no-index','--find-links',str(Path(wheelhouse).resolve(strict=True))])
        else:
            pip.extend(['--index-url','https://pypi.org/simple'])
        checked(pip+['-r',str(lock)])
        checked([str(python),'-X','utf8','-I','-B','-m','pip','--isolated','check'])
        install_native_runtime(environment,root)
        record = root/('pending-'+identity+'.json')
        checked([str(python),'-X','utf8','-I','-B',str(HERE/'verify_runtime.py'),
                 '--profile',str(HERE/'runtime-profile.json'),'--runtime-id',identity,
                 '--output',str(record),'--native-runtime',str(HERE/'native-runtime.json')])
        checked([str(python),'-X','utf8','-I','-B',str(HERE/'calculation_install.py'),'--prepared-environment'])
        # Native console entry preserves arguments across PowerShell/CMD boundaries.
        # It selects the registry, never a GUID folder. Publish the pointer last.
        atomic_bytes(root/'runtime_select.py', (HERE/'runtime_select.py').read_bytes())
        with tempfile.TemporaryDirectory(prefix='entry-',dir=root) as entry_dir:
            directory=Path(entry_dir)
            assert directory.resolve().parent==root.resolve()
            checked([str(python),'-X','utf8','-I','-B',str(HERE/'create_native_entry.py'),
                     '--base',str(Path(sys.executable).resolve()),'--selector',str(HERE/'runtime_select.py'),
                     '--output',str(directory)])
            atomic_bytes(root/'teklif-python.exe',(directory/'teklif-python.exe').read_bytes())
            atomic_bytes(root/'DISTLIB-LICENSE.txt',(directory/'DISTLIB-LICENSE.txt').read_bytes())
        os.replace(record, root/'teklif-runtime.json')
    print('Ortam hazır: '+str(python), flush=True)

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Kurulum başarısız: '+str(error), file=sys.stderr, flush=True)
        raise SystemExit(3)
