"""Bound one owned Windows process tree; no name-based process termination."""
from pathlib import Path
import subprocess
import time

def run_owned(command, *, cwd, timeout_seconds=75, environment=None):
    if (isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float))
            or not 0 < timeout_seconds <= 180):
        raise ValueError('Calculation deadline must be greater than zero and at most 180 seconds')
    import pywintypes,win32api,win32con,win32event,win32file,win32job,win32process
    job=win32job.CreateJobObject(None,'')
    process=thread=stdin=stdout=None
    owned_handles=[]
    start=time.monotonic()
    try:
        limits=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags']=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,limits)
        # Assign before the first instruction: child processes cannot escape a
        # race between launch and assignment. Each attempt has a fresh profile.
        startup=win32process.STARTUPINFO()
        attributes=pywintypes.SECURITY_ATTRIBUTES();attributes.bInheritHandle=True
        stdin=win32file.CreateFile('NUL',win32con.GENERIC_READ,win32con.FILE_SHARE_READ|win32con.FILE_SHARE_WRITE,
                                   attributes,win32con.OPEN_EXISTING,win32con.FILE_ATTRIBUTE_NORMAL,None)
        stdout=win32file.CreateFile(str(Path(cwd)/'engine-console.log'),win32con.GENERIC_WRITE,win32con.FILE_SHARE_READ|win32con.FILE_SHARE_DELETE,
                                    attributes,win32con.CREATE_NEW,win32con.FILE_ATTRIBUTE_NORMAL,None)
        startup.dwFlags|=win32con.STARTF_USESTDHANDLES
        startup.hStdInput=stdin;startup.hStdOutput=stdout;startup.hStdError=stdout
        process,thread,pid,tid=win32process.CreateProcess(
            str(command[0]),subprocess.list2cmdline([str(x) for x in command]),
            None,None,True,win32con.CREATE_SUSPENDED|win32con.CREATE_NO_WINDOW,
            environment,str(Path(cwd).resolve()),startup)
        try:win32job.AssignProcessToJobObject(job,process)
        except BaseException:
            win32process.TerminateProcess(process,3)
            win32event.WaitForSingleObject(process,5000)
            raise
        win32process.ResumeThread(thread)
        result=win32event.WaitForSingleObject(process,int(timeout_seconds*1000))
        timed_out=result==win32event.WAIT_TIMEOUT
        if not timed_out and result!=win32event.WAIT_OBJECT_0:raise OSError('Calculation wait failed')
        # Capture handles before termination: the active-count can reach zero
        # before process teardown signals handles and releases file locks.
        for owned_pid in win32job.QueryInformationJobObject(job,win32job.JobObjectBasicProcessIdList):
            if owned_pid==pid:continue
            try:owned_handles.append(win32api.OpenProcess(win32con.SYNCHRONIZE,False,owned_pid))
            except pywintypes.error as exc:
                if exc.winerror!=87:raise  # an already-exited PID needs no wait
        # Kill-on-close also closes a child that remains after its parent exits.
        win32job.TerminateJobObject(job,3)
        deadline=time.monotonic()+5
        for handle in [process,*owned_handles]:
            remaining=max(0,int((deadline-time.monotonic())*1000))
            if win32event.WaitForSingleObject(handle,remaining)!=win32event.WAIT_OBJECT_0:
                raise OSError('Owned calculation process teardown did not finish')
        while win32job.QueryInformationJobObject(job,win32job.JobObjectBasicAccountingInformation)['ActiveProcesses']:
            if time.monotonic()>=deadline:raise OSError('Owned calculation processes did not exit')
            time.sleep(.02)
        code=win32process.GetExitCodeProcess(process)
        return {'exit_code':code,'timed_out':timed_out,'seconds':round(time.monotonic()-start,3),
                'owned_process_cleanup':'JOB_EMPTY','pid':pid}
    except pywintypes.error as exc:
        raise OSError('Owned calculation process could not run: '+str(exc)) from exc
    finally:
        # Closing the job still kills its own children on parent exceptions.
        job.Close()
        for handle in owned_handles:handle.Close()
        if thread is not None:thread.Close()
        if process is not None:process.Close()
        if stdin is not None:stdin.Close()
        if stdout is not None:stdout.Close()
