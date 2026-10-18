"""Stdlib-only selector; execute only the runtime validated for this package."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        raise ValueError('Eklenti başlatıcısının yolu eksik.')
    launcher = Path(sys.argv[1]).resolve(strict=True)
    if launcher.name != 'runtime_launcher.py':
        raise ValueError('Geçersiz eklenti başlatıcısı.')
    spec = importlib.util.spec_from_file_location('kilic_runtime_registry',
                                                launcher.with_name('runtime_registry.py'))
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    record = registry.recorded()
    registry.validate(record, registry.profile())
    return subprocess.call([record['python'],'-X','utf8','-I','-B',str(launcher),*sys.argv[2:]])

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'BLOCKED','reason':str(error),
                          'action':'Ayrı Kılıç Python kurulumunu çalıştırın.'},ensure_ascii=False))
        raise SystemExit(3)
