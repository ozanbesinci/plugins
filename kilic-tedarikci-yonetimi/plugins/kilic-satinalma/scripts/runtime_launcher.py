"""Explicit local entry point; this module never installs or repairs packages."""
import ast
import json
import os
from pathlib import Path
import runpy
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_registry import current,bind_run

def main(identity=None):
    identity=current() if identity is None else identity
    args=sys.argv[1:]
    if not args: raise ValueError('Komut gerekli: workflow, environment_check veya skill_startup.')
    command=args.pop(0)
    package=Path(__file__).resolve().parents[1]
    scripts=package/'skills/teklif-degerlendirme/scripts'
    allowed={p.stem:p for p in scripts.glob('*.py') if p.name!='__init__.py'}
    allowed['skill_startup']=package/'scripts/skill_startup.py'
    if command not in allowed: raise ValueError('İzinli eklenti komutu bulunamadı.')
    tree=ast.parse(allowed[command].read_text(encoding='utf-8-sig'))
    if not any(isinstance(n,ast.If) and isinstance(n.test,ast.Compare)
               and ast.dump(n.test)==ast.dump(ast.parse("__name__ == '__main__'",mode='eval').body)
               for n in tree.body):
        raise ValueError('Bu modülün desteklenen komut satırı girişi yok.')
    if '--run' in args:
        index=args.index('--run')
        if index+1>=len(args): raise ValueError('--run klasörü eksik.')
        bind_run(args[index+1],identity)
    elif '--resume-request' in args:
        index=args.index('--resume-request')
        if index+1>=len(args): raise ValueError('--resume-request dosyası eksik.')
        path=Path(args[index+1])
        bind_run(json.loads(path.read_text(encoding='utf-8'))['run'],identity)
    os.environ['TEKLIF_RUNTIME_IDENTITY']=json.dumps(identity)
    sys.path.insert(0,str(scripts))
    sys.argv=[str(allowed[command]),*args]
    runpy.run_path(str(allowed[command]),run_name='__main__')

def entry():
    try:
        identity=current()
    except (ValueError,OSError,KeyError) as exc:
        print(json.dumps({'status':'BLOCKED_ENVIRONMENT','automatic_installation':False,
                          'message':str(exc),'next_step':'Eklenti dışındaki kurulum/Kur.cmd ile ortamı hazırlayın.'},ensure_ascii=False))
        return 3
    try:
        main(identity)
        return 0
    except PermissionError as exc:
        result={'status':'BLOCKED_FILE_ACCESS','message':str(exc),
                'next_step':'Kaynağı değiştirmeden görevin izinli çalışma klasörünü çıktı hedefi olarak kullanın.'}
    except OSError as exc:
        result={'status':'BLOCKED_IO','message':str(exc),
                'next_step':'Dosya yolu, erişim ve disk durumunu kontrol edin.'}
    except (ValueError,KeyError,RuntimeError) as exc:
        result={'status':'BLOCKED_COMMAND','message':str(exc),
                'next_step':'Komut girdisini veya koşu uyumluluğunu hata mesajına göre kontrol edin.'}
    print(json.dumps({**result,'automatic_installation':False,'runtime_status':'READY'},ensure_ascii=False))
    return 3


if __name__=='__main__':
    raise SystemExit(entry())

