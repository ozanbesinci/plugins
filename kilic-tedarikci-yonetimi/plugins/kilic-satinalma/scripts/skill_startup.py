"""Read the active package's real skill identity/version for its startup line."""
from pathlib import Path
import argparse, json, re, sys

class StartupError(ValueError):
    pass

def inside(root: Path, relative: str) -> Path:
    p=(root/relative).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():
        raise StartupError('Beceri ad/sürüm kaynağı eksik veya paket dışında.')
    return p

def render(root: Path, name: str) -> str:
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name):
        raise StartupError('Beceri kimliği geçersiz.')
    try:
        catalog=json.loads(inside(root,'config/skill-catalog.json').read_text(encoding='utf-8'))['skills']
        entry=catalog[name]
        label=entry['display_name']
        skill=inside(root,entry['skill_file']).read_text(encoding='utf-8')
        version=inside(root,entry['version_file']).read_text(encoding='utf-8').strip()
        if 'matching_version_file' in entry:
            match=inside(root,entry['matching_version_file']).read_text(encoding='utf-8').strip()
            if match!=version:raise StartupError('Beceri sürüm kaynakları uyuşmuyor.')
    except (KeyError,TypeError,json.JSONDecodeError,UnicodeError,OSError) as exc:
        raise StartupError('Gerçek beceri ad/sürüm kaynağı okunamadı.') from exc
    if not isinstance(label,str) or not label.strip() or any(c in label for c in '\n\r[]<>'):
        raise StartupError('Gerçek beceri adı geçersiz.')
    headings=[line[2:].split(' — ')[0].strip() for line in skill.splitlines() if line.startswith('# ')]
    if not headings or headings[0]!=label or not re.search(r'^name:\s*'+re.escape(name)+r'\s*$',skill,re.MULTILINE):
        raise StartupError('Beceri adı ile etkin skill kaynağı uyuşmuyor.')
    if not re.fullmatch(r'(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?',version):
        raise StartupError('Gerçek beceri VERSION kaynağı geçersiz.')
    return f'{label} skilli Kılıç Satınalma Departmanı tarafından geliştirilmiştir. Sürüm: {version}'

def main():
    parser=argparse.ArgumentParser(description='Gerçek beceri adı ve sürümü ile başlangıç satırı')
    parser.add_argument('--skill',required=True)
    args=parser.parse_args()
    try:line=render(Path(__file__).resolve().parents[1],args.skill)
    except StartupError as exc:
        print(str(exc),file=sys.stderr)
        return 3
    print(line)
    return 0

if __name__=='__main__':raise SystemExit(main())
