"""Run only offline Python tests. Writes an evidence JSON to an explicit external path."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import platform
import sys
import unittest

class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.records=[]
    def addSuccess(self,test):super().addSuccess(test);self.records.append({'test':test.id(),'status':'PASS'})
    def addFailure(self,test,err):super().addFailure(test,err);self.records.append({'test':test.id(),'status':'FAIL'})
    def addError(self,test,err):super().addError(test,err);self.records.append({'test':test.id(),'status':'ERROR'})
    def addSkip(self,test,reason):super().addSkip(test,reason);self.records.append({'test':test.id(),'status':'NOT_RUN','reason':reason})

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    skill=Path(__file__).resolve().parents[1]
    if a.output.resolve().is_relative_to(skill):
        raise SystemExit('Test evidence output must be outside the installed skill tree.')
    syntax=[]
    for file in skill.rglob('*.py'):
        compile(file.read_text(encoding='utf-8-sig'),str(file),'exec')
        syntax.append(str(file.relative_to(skill)))
    suite=unittest.defaultTestLoader.discover(str(skill/'tests'),pattern='test_*.py')
    result=unittest.TextTestRunner(verbosity=2,resultclass=RecordedResult).run(suite)
    categories={'source_contract_assertions':0,'pro_audit_contracts':0,'python_fixture_tests':0}
    for record in result.records:
        if '.SourceContractTests.' in record['test']:
            key='source_contract_assertions'
        elif record['test'].startswith('test_pro_audit.'):
            key='pro_audit_contracts'
        else:
            key='python_fixture_tests'
        categories[key]+=1
    report={'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'platform':platform.platform(),
            'python':platform.python_version(),'status':'PASS' if result.wasSuccessful() else 'FAIL',
            'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
            'categories':categories,'python_syntax_checked':syntax,'results':result.records,
            'windows_powershell_parser':'NOT_RUN','windows_orchestration_harness':'NOT_RUN',
            'live_installers':'NOT_RUN','native_pdf_extension':'NOT_RUN','excel_com':'NOT_RUN',
            'production_approved':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if result.wasSuccessful() else 2
if __name__=='__main__':raise SystemExit(main())