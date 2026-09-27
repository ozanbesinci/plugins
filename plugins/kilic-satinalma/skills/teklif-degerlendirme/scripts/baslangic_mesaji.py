"""Teklif değerlendirmesi başlarken gösterilecek tanıtım mesajını üretir."""

import sys
import argparse
import json
from pathlib import Path
import urllib.request


BASLANGIC_MESAJI = (
    "Bu skill Satınalma Departmanı çalışanlarının kullanımı için "
    "Ozan Beşinci tarafından oluşturulmuştur."
)


def main():
    # Windows konsolu ve araç çıktısında Türkçe karakterleri koru.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument('--check-release',action='store_true',help='Kararlı sürümü en fazla 3 saniyede salt okunur sorgular.')
    args=parser.parse_args()
    version=Path(__file__).resolve().parents[1].joinpath('VERSION').read_text(encoding='utf-8').strip()
    print(BASLANGIC_MESAJI)
    print('Teklif Değerlendirme sürümü: '+version)
    if args.check_release:
        try:
            request=urllib.request.Request('https://api.github.com/repos/ozanbesinci/teklif-degerlendirme/releases/latest',headers={'Accept':'application/vnd.github+json','User-Agent':'teklif-degerlendirme-version-check'})
            with urllib.request.urlopen(request,timeout=3) as response:
                release=json.loads(response.read(1024*1024))
            tag=release.get('tag_name','')
            if release.get('draft') or release.get('prerelease') or not tag.startswith('v'):
                raise ValueError('Kararlı sürüm doğrulanamadı.')
            print('GitHub kararlı sürümü: '+tag+'; bu kontrol kurulum yapmaz.')
        except (OSError,ValueError):
            print('GitHub kararlı sürüm kontrolü yapılamadı; yerel sürüm kullanılacak.')


if __name__ == "__main__":
    main()
