"""Materialize an immutable audit package for compatibility tests, outside product source."""
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import subprocess
import tarfile


def prepare_audit_reference(repo,destination,reference,receipt):
    repo=Path(repo);destination=Path(destination)
    commit,package,tree=reference['commit'],reference['package'],reference['tree']
    for value in (commit,tree):
        if len(value)!=40 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid pinned Git object')
    if package!='kilic-sozlesme-yonetimi/plugins/kilic-sozlesme-yonetimi':raise ValueError('Unexpected audit package')
    git=['git','-c','safe.directory='+str(repo),'-C',str(repo)]
    actual=subprocess.check_output(git+['rev-parse',commit+':'+package],stderr=subprocess.DEVNULL).decode().strip()
    if actual!=tree:raise ValueError('Audit tree differs from immutable reference')
    archive=subprocess.check_output(git+['archive','--format=tar',commit+':'+package],stderr=subprocess.DEVNULL)
    if len(archive)>32*1024*1024:raise ValueError('Audit source archive budget')
    destination.mkdir(parents=True,exist_ok=False)
    files={}
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as source:
        members=source.getmembers()
        if len(members)>512 or sum(m.size for m in members)>32*1024*1024:raise ValueError('Audit source member budget')
        for member in members:
            name=PurePosixPath(member.name)
            if (name.is_absolute() or '..' in name.parts or ':' in member.name or '\\' in member.name
                    or not (member.isfile() or member.isdir())):raise ValueError('Unsafe audit source entry')
            target=destination.joinpath(*name.parts)
            if member.isdir():target.mkdir(parents=True,exist_ok=True);continue
            if member.name in files:raise ValueError('Duplicate audit source entry')
            data=source.extractfile(member).read()
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as writer:writer.write(data)
            files[member.name]=hashlib.sha256(data).hexdigest()
    record={'schema':'immutable-audit-reference/v1','commit':commit,'tree':tree,'package':package,
            'root':str(destination),'files':files,'files_digest':hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'scope':'TEST_REFERENCE_ONLY_NOT_PRODUCT_IMPORT','business_acceptance':'NOT_GRANTED'}
    Path(receipt).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    return record
