"""Bounded native Office work on disposable copies; preserve report inputs."""
import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

def windows_identity(pid):
    """Capture an identity from a handle, never from a process name alone."""
    if platform.system() != 'Windows': return None
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:return _identity_from_handle(kernel,handle)
    finally:kernel.CloseHandle(handle)

def _identity_from_handle(kernel,handle):
    from ctypes import wintypes
    created=wintypes.FILETIME();exit_time=wintypes.FILETIME();system=wintypes.FILETIME();user=wintypes.FILETIME()
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    if not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exit_time),ctypes.byref(system),ctypes.byref(user)):return None
    size=wintypes.DWORD(32768);name=ctypes.create_unicode_buffer(size.value)
    if not kernel.QueryFullProcessImageNameW(handle,0,name,ctypes.byref(size)):return None
    ticks=(created.dwHighDateTime<<32)|created.dwLowDateTime
    return {'created_100ns':ticks,'image':name.value}

def _stop_owned_excel(receipt,attempt,started_ns):
    """Only terminate the receipt-bound new Excel instance, using one handle."""
    try:record=json.loads(receipt.read_text(encoding='utf-8'))
    except (OSError,ValueError):return 'NOT_PROVEN_NO_RECEIPT'
    if record.get('attempt')!=attempt or not isinstance(record.get('pid'),int):return 'NOT_PROVEN_IDENTITY'
    identity=record.get('identity') or {}
    if not isinstance(identity.get('created_100ns'),int) or identity['created_100ns']<started_ns//100+116444736000000000:
        return 'NOT_PROVEN_PREEXISTING_PROCESS'
    if platform.system()!='Windows':return 'NOT_PROVEN_PLATFORM'
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    handle=kernel.OpenProcess(0x1000|0x0001,False,record['pid'])
    if not handle:return 'NOT_PROVEN_PROCESS_UNAVAILABLE'
    try:
        current=_identity_from_handle(kernel,handle)
        if current!=identity or Path(current['image']).name.casefold()!='excel.exe':return 'NOT_PROVEN_IDENTITY'
        return 'TERMINATED_OWNED_EXCEL' if kernel.TerminateProcess(handle,1) else 'OWNED_EXCEL_TERMINATION_FAILED'
    finally:kernel.CloseHandle(handle)

def execute_office(operation,path,pdf=None,*,timeout_seconds=45,_worker=None):
    if operation not in {'recalculate','pdf'}:raise ValueError('Unknown native Office operation')
    if not isinstance(timeout_seconds,(int,float)) or isinstance(timeout_seconds,bool) or not 0<timeout_seconds<=120:
        raise ValueError('Native Office deadline must be greater than zero and at most 120 seconds')
    if operation=='pdf' and pdf is None:raise ValueError('PDF target required')
    if platform.system()!='Windows':return {'available':False,'reason':'not_windows'}
    # This tree is never a published report revision. A hung native app can only
    # modify this copy, even if cleanup ownership cannot be proved.
    temp_root=Path(tempfile.gettempdir()).resolve()
    work=Path(tempfile.mkdtemp(prefix='kilic-office-',dir=temp_root))
    attempt=uuid.uuid4().hex;result_path=work/'result.json';receipt=work/'owner.json'
    output=work/'output.pdf';copied=work/'input.xlsx'
    started_ns=time.time_ns();proc=None;preserve_work=False
    try:
        shutil.copy2(path,copied)
        command=[sys.executable,'-X','utf8',str(_worker or Path(__file__).with_name('excel_worker.py')),
                 '--operation',operation,'--input',str(copied),'--output',str(output),
                 '--result',str(result_path),'--receipt',str(receipt),'--attempt',attempt]
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:stdout,stderr=proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill();proc.communicate(timeout=5)
            cleanup=_stop_owned_excel(receipt,attempt,started_ns)
            preserve_work=cleanup!='TERMINATED_OWNED_EXCEL'
            return {'available':False,'reason':'native_office_timeout','timeout_seconds':timeout_seconds,
                    'owned_process_cleanup':cleanup,'isolated_copy':str(work) if preserve_work else None}
        if proc.returncode!=0:
            return {'available':False,'reason':'native_office_worker_failed','worker_exit_code':proc.returncode}
        result=json.loads(result_path.read_text(encoding='utf-8'))
        if result.get('attempt')!=attempt or result.get('operation')!=operation:
            return {'available':False,'reason':'native_office_result_identity_mismatch'}
        if result.get('available') is not True:return result
        produced=copied if operation=='recalculate' else output
        if not produced.is_file() or produced.stat().st_size==0:
            return {'available':False,'reason':'native_office_output_missing'}
        destination=Path(path) if operation=='recalculate' else Path(pdf)
        # Same-directory atomic replacement, including a different temp volume.
        staged=destination.with_name('.'+destination.name+'.native-'+attempt)
        shutil.copy2(produced,staged);os.replace(staged,destination)
        return {**result,'path':str(destination),'timeout_seconds':timeout_seconds}
    except (OSError,ValueError) as exc:
        return {'available':False,'reason':'native_office_error:'+str(exc)}
    finally:
        # The exact disposable target is checked before recursive cleanup.
        if not preserve_work and work.resolve().parent==temp_root and work.name.startswith('kilic-office-'):
            try:shutil.rmtree(work)
            except OSError:pass
