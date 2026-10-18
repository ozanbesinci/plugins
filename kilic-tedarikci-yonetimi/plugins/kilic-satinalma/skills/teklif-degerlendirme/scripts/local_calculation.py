"""Calculate a disposable copy and atomically publish validated caches only."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from calculation_runtime import current,digest,evidence
from calculation_cache import preflight,transfer
from calculation_process import run_owned

def calculate_with_engine(source,output,identity,*,timeout_seconds=75):
    """Installer and runtime share the same verified calculation operation."""
    source,output=Path(source),Path(output)
    if output.exists():raise ValueError('Calculation output already exists')
    initial=digest(source)
    with tempfile.TemporaryDirectory(prefix='kilic-calc-') as temporary:
        work=Path(temporary).resolve();incoming=work/'input';incoming.mkdir()
        results=work/'output';results.mkdir();cold=incoming/'report.xlsx'
        count=preflight(source,cold)
        profile=work/'profile';profile.mkdir()
        # A fresh isolated profile never inherits user macros or link-update settings.
        (profile/'user').mkdir()
        (profile/'user/registrymodifications.xcu').write_text(
            '<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>'
            '<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>1</value></prop></item>'
            '</oor:items>',encoding='utf-8')
        command=[identity['executable'],'-env:UserInstallation='+profile.as_uri(),
                 '--headless','--norestore','--nodefault','--nofirststartwizard',
                 '--convert-to','xlsx:Calc MS Excel 2007 XML','--outdir',str(results),str(cold)]
        environment={key:value for key,value in os.environ.items()
                     if key.upper() not in {'PYTHONHOME','PYTHONPATH','PYTHONSTARTUP','SC_FORCE_CALCULATION'}}
        environment['PYTHONDONTWRITEBYTECODE']='1'
        environment['PYTHONNOUSERSITE']='1'
        # CPU calculation avoids the OpenCL self-test writing cl-test.ods locks
        # inside the immutable installation while another run verifies it.
        environment['SAL_DISABLE_OPENCL']='1'
        process=run_owned(command,cwd=work,timeout_seconds=timeout_seconds,environment=environment)
        if process['timed_out']:raise TimeoutError('Yerel hesap motoru süre sınırını aştı.')
        if process['exit_code']!=0:raise ValueError('Yerel hesap motoru başarısız: '+str(process['exit_code']))
        computed=results/cold.name
        if not computed.is_file():raise ValueError('Hesaplanan Excel kopyası oluşmadı.')
        transferred=transfer(source,computed,output)
        if digest(source)!=initial:raise ValueError('Hesap sırasında kaynak dosya değişti.')
        if transferred['formulas']!=count:raise ValueError('Hesaplanan formül sayısı uyuşmuyor.')
        return {'available':True,'status':'LOCAL_RECALCULATED','engine':evidence(identity),
                'formulas':count,'source_sha256':initial,'output_sha256':digest(output),
                'non_cache_xml_preserved':True,'native_excel_validation':False,
                'process':process}

def recalculate(path,*,timeout_seconds=75):
    path=Path(path);pending=path.with_name('.'+path.name+'.calc-'+uuid.uuid4().hex)
    try:
        identity=current()
        result=calculate_with_engine(path,pending,identity,timeout_seconds=timeout_seconds)
        if digest(path)!=result['source_sha256']:raise ValueError('Yayımdan önce Excel değişti.')
        os.replace(pending,path)
        return {**result,'path':str(path)}
    except (OSError,ValueError,KeyError,ImportError) as exc:
        return {'available':False,'status':'PENDING_LOCAL_RECALC','reason':str(exc),
                'automatic_installation':False,'source_preserved':True}
    finally:
        if pending.exists():pending.unlink()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True)
    args=parser.parse_args()
    result=recalculate(args.input);print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['available'] else 3)
