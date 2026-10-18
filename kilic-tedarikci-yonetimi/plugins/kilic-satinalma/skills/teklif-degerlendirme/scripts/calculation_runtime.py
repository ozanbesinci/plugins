"""Read-only selection of the separately installed, pinned calculation engine."""
import hashlib
import json
import os
from pathlib import Path
import platform
from concurrent.futures import ThreadPoolExecutor

PACKAGE=Path(__file__).resolve().parents[3]

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def inventory(root):
    """Use directory-entry attributes; avoid reopening every file for link checks."""
    files=[];pending=[Path(root)]
    while pending:
        directory=pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_symlink() or entry.is_junction():raise ValueError('Hesap motorunda bağlantılı dosya/klasör var.')
                if entry.is_dir(follow_symlinks=False):pending.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):files.append(Path(entry.path))
                else:raise ValueError('Unsupported engine filesystem entry')
    return files

def hash_files(root,paths):
    """Hash all bytes. Concurrent independent reads avoid per-file I/O latency."""
    with ThreadPoolExecutor(max_workers=16) as pool:
        hashes=pool.map(digest,paths)
        return {path.relative_to(root).as_posix():value for path,value in zip(paths,hashes)}

def profile():
    return json.loads((PACKAGE/'config/calculation-profile.json').read_text(encoding='utf-8'))

def machine_id():
    return hashlib.sha256((platform.node()+'\0'+os.environ.get('USERNAME','')).encode()).hexdigest()

def validate(record,expected,*,user_profile=None,verify_files=True):
    local=Path(user_profile or os.environ['USERPROFILE'])/'KilicPython/calculation'
    if record.get('schema')!='kilic-calculation-runtime/v1' or record.get('profile_id')!=expected['id']:
        raise ValueError('Hesap motoru kaydı bu eklentiyle uyuşmuyor.')
    if record.get('machine_id')!=machine_id():raise ValueError('Hesap motoru başka kullanıcıya ait.')
    root=Path(record['root']).resolve(strict=True)
    if root==local.resolve() or not root.is_relative_to(local.resolve()):raise ValueError('Hesap motoru kullanıcı klasörü dışında.')
    manifest=root/'engine-manifest.json'
    if digest(manifest)!=expected['manifest_sha256']:raise ValueError('Hesap motoru dosya listesi değişmiş.')
    files=json.loads(manifest.read_text(encoding='utf-8'))
    if verify_files:
        paths=inventory(root)
        if {p.relative_to(root).as_posix() for p in paths}!=set(files)|{'engine-manifest.json'}:
            raise ValueError('Hesap motoru dosya kümesi değişmiş.')
        for relative in files:
            if Path(relative).is_absolute() or '..' in Path(relative).parts:raise ValueError('Geçersiz motor yolu.')
        actual=hash_files(root,[p for p in paths if p!=manifest])
        if actual!=files:raise ValueError('Hesap motoru dosyası değişmiş.')
    return {'engine':'LibreOffice','version':expected['version'],'profile_id':expected['id'],
            'manifest_sha256':expected['manifest_sha256'],'package_sha256':expected['sha256'],
            'root':str(root),'executable':str(root/'program/soffice.com')}

def current(*,verify_files=True):
    if platform.system()!='Windows':raise ValueError('Yerel hesap motoru Windows gerektirir.')
    path=Path(os.environ['USERPROFILE'])/'KilicPython/calculation-runtime.json'
    return validate(json.loads(path.read_text(encoding='utf-8')),profile(),verify_files=verify_files)

def check():
    try:return {'status':'READY',**current(),'automatic_installation':False}
    except (OSError,ValueError,KeyError) as exc:
        return {'status':'BLOCKED_ENVIRONMENT','reason':str(exc),'automatic_installation':False,
                'next_step':'Eklenti dışındaki kurulum/Kur-Hesap.cmd ile hesap motorunu hazırlayın.'}

def evidence(identity):
    return {k:identity[k] for k in ('engine','version','profile_id','manifest_sha256','package_sha256')}
