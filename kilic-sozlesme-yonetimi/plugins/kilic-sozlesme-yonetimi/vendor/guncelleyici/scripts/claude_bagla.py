"""Bind a simple Claude Code stdio entry through its own CLI, never raw JSON writes.

Refuse custom records. Only a native .exe CLI is accepted on Windows so no cmd.exe
expansion occurs. Call only when client processes are closed; no EULA is accepted.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from islem_guvencesi import SafetyError, atomic_bytes, reject_links, digest_bytes, redact, exclusive_lock
NAME = 'powerbi-modeling'

def read_config(path):
    reject_links(path)
    if not path.exists(): return {}, None
    raw = path.read_bytes()
    obj = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(obj, dict) or not isinstance(obj.get('mcpServers', {}), dict):
        raise SafetyError('Claude Code ayar biçimi geçersiz; dokunulmadı.')
    return obj, raw

def simple_entry(entry):
    if entry is None: return True
    return (isinstance(entry, dict) and isinstance(entry.get('command'), str)
            and entry.get('args') == ['--start'] and entry.get('type', 'stdio') == 'stdio'
            and not entry.get('env') and not (set(entry)-{'type','command','args','env'}))

def bind(path, cli, executable, runner=None):
    path, cli, executable = Path(path), Path(cli), Path(executable)
    reject_links(cli); reject_links(executable)
    if cli.suffix.lower() != '.exe' or not cli.is_file() or not executable.is_file():
        raise SafetyError('Yerel claude.exe ve doğrulanmış sunucu dosyası gerekli.')
    def invoke(arguments):
        if runner: return runner(arguments)
        p = subprocess.run([str(cli), *arguments], capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=60,
                           env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        if p.returncode: raise SafetyError('Claude MCP CLI başarısız: '+redact((p.stderr+p.stdout)[-800:]))
    with exclusive_lock(path.with_name(path.name+'.guncelleyici.lock')):
        before, raw = read_config(path)
        servers=before.get('mcpServers', {}); old=servers.get(NAME)
        if not simple_entry(old):
            return {'status':'deferred','reason':'Özel Claude Code kaydı korundu; elle inceleme gerekli.'}
        if old and old['command'] == str(executable): return {'status':'unchanged'}
        backup=None
        if raw is not None:
            backup=path.with_name(path.name+'.guncelleyici-'+uuid.uuid4().hex+'.bak')
            atomic_bytes(backup,raw,require_absent=True)
        current,current_raw=read_config(path)
        if current_raw != raw: raise SafetyError('Claude ayarı hazırlanırken değişti; dokunulmadı.')
        mutation_started=False
        try:
            if old:
                mutation_started=True; invoke(['mcp','remove',NAME,'--scope','user'])
            mutation_started=True
            invoke(['mcp','add','--scope','user','--transport','stdio',NAME,'--',str(executable),'--start'])
            after,_=read_config(path); new=after.get('mcpServers',{}).get(NAME)
            others=lambda d:{k:v for k,v in d.get('mcpServers',{}).items() if k!=NAME}
            if (not simple_entry(new) or not new or new.get('command')!=str(executable)
                    or others(after)!=others(before)):
                raise SafetyError('Claude CLI sonrası MCP kayıtları doğrulanamadı.')
            return {'status':'updated' if old else 'created','backup':str(backup) if backup else None}
        except (OSError,ValueError,subprocess.SubprocessError) as original:
            recovered=not mutation_started
            if mutation_started:
                try:
                    after,_=read_config(path)
                    new=after.get('mcpServers',{}).get(NAME)
                    if new:
                        if not simple_entry(new) or new.get('command') not in (str(executable), (old or {}).get('command')):
                            raise SafetyError('Kayıt dışarıdan değişti; otomatik geri dönüş yapılmadı.')
                        invoke(['mcp','remove',NAME,'--scope','user'])
                    if old:
                        invoke(['mcp','add','--scope','user','--transport','stdio',NAME,'--',old['command'],'--start'])
                    restored,_=read_config(path); item=restored.get('mcpServers',{}).get(NAME)
                    recovered=(item is None if old is None else simple_entry(item) and bool(item) and item.get('command')==old['command'])
                    recovered=recovered and {k:v for k,v in restored.get('mcpServers',{}).items() if k!=NAME} == {k:v for k,v in servers.items() if k!=NAME}
                except (OSError,ValueError,subprocess.SubprocessError): recovered=False
            return {'status':'error','reason':redact(str(original)),'backup':str(backup) if backup else None,
                    'recovery_required':not recovered,'rollback_verified':recovered}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--path',type=Path,required=True)
    p.add_argument('--cli',type=Path,required=True);p.add_argument('--exe',type=Path,required=True)
    p.add_argument('--clients-closed',action='store_true');a=p.parse_args()
    try:
        if os.name!='nt' or not a.clients_closed: raise SafetyError('Windows ve kapalı istemci bakım oturumu gerekli.')
        result=bind(a.path,a.cli,a.exe)
        print(json.dumps(redact(result),ensure_ascii=False));return 2 if result['status']=='error' else 0
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print(json.dumps({'status':'error','error':redact(str(e))},ensure_ascii=False));return 2
if __name__=='__main__': raise SystemExit(main())