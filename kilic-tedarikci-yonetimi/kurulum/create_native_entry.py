"""Create the same native Windows console entry type used by pip."""
import argparse
import importlib.metadata
from pathlib import Path
from pip._vendor.distlib.scripts import ScriptMaker

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',required=True)
    parser.add_argument('--selector',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    destination=Path(args.output)
    destination.mkdir(parents=True,exist_ok=True)
    maker=ScriptMaker(None,str(destination))
    maker.executable='"'+str(Path(args.base).resolve(strict=True))+'"'
    maker.variants={''};maker.clobber=True
    maker.script_template=Path(args.selector).read_text(encoding='utf-8')
    maker.make('teklif-python = runtime_select:main',
               options={'interpreter_args':['-X','utf8','-I','-B']})
    distribution=importlib.metadata.distribution('pip')
    licenses=[p for p in distribution.files if str(p).replace('\\','/').endswith('distlib/LICENSE.txt')]
    if not licenses:raise ValueError('Windows komut başlatıcısının lisansı bulunamadı.')
    (destination/'DISTLIB-LICENSE.txt').write_bytes(distribution.locate_file(licenses[0]).read_bytes())
    print('Yerel Windows Python komut başlatıcısı hazır.',flush=True)

if __name__=='__main__':main()
