"""Visible metadata from per-skill version sources, never from a source document."""
import json
from pathlib import Path
from .errors import CoreError

ROOT=Path(__file__).resolve().parents[2]

def skill_metadata(skill_id):
    registry=json.loads((ROOT/'references/skill-versions.json').read_text(encoding='utf-8'))
    entry=registry.get(skill_id)
    if not entry: raise CoreError('BECERI_METADATA','Beceri kimliği kayıtlı değil')
    version=(ROOT/'skills'/entry['slug']/'VERSION').read_text(encoding='utf-8').strip()
    expected=f"{entry['name']} skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: {version}"
    if entry['version']!=version or entry['developer']!='Kılıç Satınalma Departmanı' or entry['startup_message']!=expected:
        raise CoreError('BECERI_METADATA','Beceri sürüm/geliştirici kaydı farklı')
    return dict(entry)
