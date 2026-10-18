"""Run the unchanged native test suite in isolated processes; prove exact coverage."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

HERE=Path(__file__).resolve().parent
PACKAGE=HERE.parents[1]/'kilic-tedarikci-yonetimi/plugins/kilic-satinalma'
REL=Path('skills/teklif-degerlendirme/scripts')
OUTPUT=None
ENGINE=None
WORKERS=8

def flat(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flat(item)
        else:yield item

def worker(snapshot,number):
    sys.path[:0]=[str(snapshot/REL),str(snapshot/REL/'tests')]
    from run_tests import child
    plan=json.loads((OUTPUT/'plan.json').read_text(encoding='utf-8'))
    assigned=set(plan['groups'][number])
    discover=unittest.defaultTestLoader.discover
    def selected(*args,**kwargs):
        unittest.defaultTestLoader.discover=discover
        tests=[test for test in flat(discover(*args,**kwargs)) if test.id() in assigned]
        return unittest.TestSuite(tests)
    unittest.defaultTestLoader.discover=selected
    return child(ENGINE,'test_*.py',OUTPUT/f'worker-{number}.json',
                 plan['head'],plan['run_ids'][number],1)

def main():
    global OUTPUT,ENGINE
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=int);parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--engine',choices=['sqlite','duckdb'],required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--plan-only',action='store_true')
    args=parser.parse_args()
    OUTPUT=args.output_dir.resolve();ENGINE=args.engine
    if args.worker is not None:return worker(args.snapshot,args.worker)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    assert not (OUTPUT/'plan.json').exists(), 'Existing CI evidence must not be overwritten'
    sys.path.insert(0,str(PACKAGE/REL))
    from run_tests import source_fingerprint,validate_child_report
    before=source_fingerprint()
    os.environ['TEKLIF_TEST_SQLITE']='1'
    suite=unittest.defaultTestLoader.discover(str(PACKAGE/REL/'tests'),pattern='test_*.py')
    expected=sorted(test.id() for test in flat(suite))
    assert len(expected)==len(set(expected))==669
    evidence={'head':subprocess.check_output(['git','-C',str(PACKAGE),'rev-parse','HEAD'],text=True).strip(),'pass_ids':expected}
    groups=[sorted(evidence['pass_ids'])[number::8] for number in range(8)]
    sizes=[len(group) for group in groups]
    if args.plan_only:
        assert sorted(identifier for group in groups for identifier in group)==expected
        print(json.dumps({'status':'PLAN_PASS','tests':len(expected),'groups':sizes,'engine':ENGINE}),flush=True)
        return 0
    snapshot=Path(tempfile.mkdtemp(prefix='kilic-native-'))/'kilic-satinalma'
    shutil.copytree(PACKAGE,snapshot,ignore=shutil.ignore_patterns('__pycache__','test-results','.git'))
    assert source_fingerprint(snapshot)==before
    run_id=uuid.uuid4().hex
    plan={'run_id':run_id,'head':evidence['head'],'groups':groups,'expected_counts':sizes,
          'run_ids':[uuid.uuid4().hex for _ in groups],'snapshot':str(snapshot),
          'expected_ids':sorted(evidence['pass_ids']),'source_files':before}
    (OUTPUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    processes=[];streams=[]
    for number in range(len(groups)):
        stream=(OUTPUT/f'worker-{number}.log').open('w',encoding='utf-8');streams.append(stream)
        processes.append(subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),
            '--worker',str(number),'--snapshot',str(snapshot),'--engine',ENGINE,'--output-dir',str(OUTPUT)],stdout=stream,stderr=subprocess.STDOUT,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}))
    print(json.dumps({'status':'RUNNING','workers':8,'expected_counts':sizes,'run_id':run_id}),flush=True)
    last=None;started=time.monotonic();last_progress=0.0
    while any(process.poll() is None for process in processes):
        state=[process.poll() for process in processes]
        if state!=last:print(json.dumps({'finished':sum(code is not None for code in state),'exit_codes':state}),flush=True);last=state
        if time.monotonic()-last_progress>=30:
            tails={}
            for number in range(len(groups)):
                lines=(OUTPUT/f"worker-{number}.log").read_text(encoding="utf-8",errors="replace").splitlines()
                tails[str(number)]=lines[-1][:180] if lines else "starting"
            print(json.dumps({"elapsed_seconds":round(time.monotonic()-started),"progress":tails}),flush=True)
            last_progress=time.monotonic()
        if time.monotonic()-started>3600:
            for process in processes:
                if process.poll() is None:process.kill()
            raise TimeoutError('Parallel native acceptance exceeded 3600 seconds')
        time.sleep(5)
    for stream in streams:stream.close()
    reports=[]
    for number,process in enumerate(processes):
        path=OUTPUT/f'worker-{number}.json'
        if validate_child_report(path,ENGINE,plan['run_ids'][number],process.returncode,expected_source=before):
            raise ValueError('Incomplete/failed worker '+str(number))
        report=json.loads(path.read_text(encoding='utf-8'))
        if report['executed']!=sizes[number]:raise ValueError('Unexpected discovery coverage')
        reports.append(report)
    ids=[identifier for report in reports for identifier in report['pass_ids']]
    assert len(ids)==len(set(ids))==669 and sorted(ids)==plan['expected_ids']
    assert source_fingerprint()==source_fingerprint(snapshot)==before
    report={'requested_engine':ENGINE,'run_id':run_id,'status':'PASS','execution_mode':'8 isolated processes; unchanged test cases',
            'head':evidence['head'],'discovered':len(ids),'executed':len(ids),'passed':len(ids),
            'failed':0,'errors':0,'skipped':0,'expected_failures':0,'unexpected_successes':0,
            'pass_ids':sorted(ids),'source_files':before,'source_unchanged_during_run':True,
            'source_sha256':hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),
            'source_fingerprint_scope':'kilic-satinalma plugin runtime and instructions',
            'observed_connections':{('sqlite:sqlite3.Connection' if ENGINE=='sqlite' else 'duckdb:_duckdb.DuckDBPyConnection'):sum(sum(r['observed_connections'].values()) for r in reports)},
            'workers':[{'path':f'worker-{i}.json','run_id':r['run_id'],'passed':r['passed']} for i,r in enumerate(reports)],
            'seconds':round(time.monotonic()-started,2)}
    (OUTPUT/(ENGINE+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert validate_child_report(OUTPUT/(ENGINE+'.json'),ENGINE,run_id,0,expected_source=before)==0
    print(json.dumps({key:value for key,value in report.items() if key not in ('source_files','pass_ids')},ensure_ascii=False,indent=2),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
