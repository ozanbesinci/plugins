"""Stdlib-only host entry: normalize startup/import/argument failures as one JSON.

No installer, credentials, host authority or production action is granted here.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
from uuid import uuid4


class OutputBudgetExceeded(Exception):
    pass


class BoundedOutput(io.StringIO):
    def __init__(self):
        super().__init__()
        self.used = 0

    def reconfigure(self, *, encoding=None, **options):
        # Core requests UTF-8 on its stdout; this buffer stores Unicode and its
        # growth budget is already counted in UTF-8 bytes.
        if encoding is not None and encoding.lower().replace('-', '') != 'utf8':
            raise ValueError('Only UTF-8 is supported')

    def write(self, value):
        self.used += len(value.encode('utf-8'))
        if self.used > 64 * 1024 * 1024:
            raise OutputBudgetExceeded()
        return super().write(value)


def blocked(code):
    return {'schema_version':'1.0','operation_id':str(uuid4()),'status':'BLOCKED',
            'technical_status':'BLOCKED','business_status':'NOT_RUN','business_acceptance':'NOT_GRANTED',
            'error_code':code,'result_refs':[],'evidence_refs':[],'warnings':[],
            'limitations':['Başlangıç işlemi çalışmadı; host/iş/uzman kabulü verilmedi.'],
            'retry_safety':'NO_BLIND_RETRY','tool_version':None,'components':None,
            'analysis_status':'NOT_RUN','authority':'NOT_VERIFIED'}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    sys.dont_write_bytecode = True
    if os.name != 'nt':
        print(json.dumps(blocked('PLATFORM_CONFIG_REQUIRED'),ensure_ascii=False))
        return 2
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    output = BoundedOutput()
    exit_code, failure = 0, None
    try:
        with contextlib.redirect_stdout(output):
            runpy.run_module('sozlesme_cekirdek',run_name='__main__')
    except SystemExit as exc:
        exit_code = exc.code if type(exc.code) is int else 2
    except ImportError:
        exit_code, failure = 2, 'CONFIG_REQUIRED'
    except OutputBudgetExceeded:
        exit_code, failure = 3, 'CLI_OUTPUT_LIMIT'
    except Exception:
        exit_code, failure = 3, 'CLI_STARTUP_ERROR'
    text = output.getvalue()
    if not failure:
        try:
            value = json.loads(text)
            if not isinstance(value,dict) or value.get('status') not in {'SUCCEEDED','BLOCKED'}:
                raise ValueError()
        except ValueError:
            if exit_code == 0 and any(flag in sys.argv[1:] for flag in ('--help','-h')):
                print(text,end='') # Explicit developer help, never a job outcome.
                return 0
            failure = 'CLI_ARGUMENT_ERROR' if exit_code else 'CLI_PROTOCOL_ERROR'
            exit_code = 2 if exit_code else 3
    if failure:
        value = blocked(failure)
    print(json.dumps(value,ensure_ascii=False))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
