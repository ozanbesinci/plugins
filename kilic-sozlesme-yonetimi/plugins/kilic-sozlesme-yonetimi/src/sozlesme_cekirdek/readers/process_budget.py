"""Windows process budgets, not a filesystem/network security sandbox.

No document bytes are fed until the child belongs to a constrained Job Object.
Both pipes are drained with bounded buffers; closing the job kills its members.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from ..errors import CoreError


class WindowsJob:
    def __init__(self, process, memory_limit):
        self.handle = None
        if os.name != "nt":
            raise CoreError("PLATFORM_BUTCE", "Okuyucu Windows süreç bütçesi gerektirir")
        kernel = self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL

        class BasicLimits(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IOCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", IOCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000 | 0x100 | 0x8
        limits.BasicLimitInformation.ActiveProcessLimit = 1
        limits.ProcessMemoryLimit = memory_limit
        self.handle = kernel.CreateJobObjectW(None, None)
        if (not self.handle or not kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                or not kernel.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle)))):
            self.close()
            raise CoreError("PLATFORM_BUTCE", "Okuyucu süreç bütçesi kurulamadı; kaynak beslenmedi")

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def run_bounded_worker(command, data, environment, *, timeout=30,
                       stdout_limit=32 * 1024 * 1024, stderr_limit=64 * 1024,
                       memory_limit=512 * 1024 * 1024):
    started = time.monotonic()
    command = list(command)
    environment = dict(environment)
    environment.pop("__PYVENV_LAUNCHER__", None)
    # CPython's Windows venv redirector creates another process. Launch the
    # trusted base executable with the same launcher binding so exactly one
    # process enters the Job while the active venv/site-packages are retained.
    if (os.name == "nt" and sys.prefix != sys.base_prefix and command
            and Path(command[0]).absolute() == Path(sys.executable).absolute()):
        base = Path(getattr(sys, "_base_executable", ""))
        if (not base.is_absolute() or not base.is_file()
                or not base.resolve().is_relative_to(Path(sys.base_prefix).resolve())
                or base.resolve() == Path(sys.executable).resolve()
                or not (Path(sys.prefix) / "pyvenv.cfg").is_file()):
            raise CoreError("PLATFORM_BUTCE", "Tek süreç venv Python başlatıcısı doğrulanamadı")
        command[0] = str(base)
        environment["__PYVENV_LAUNCHER__"] = sys.executable
    # Optional numerical libraries must not fan out threads before reading input.
    # XLSX extraction needs no parallel BLAS; inherited host settings are bounded.
    environment = dict(environment, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=environment, bufsize=0,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    job = None
    threads = []
    exceeded = threading.Event()
    failed = threading.Event()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}

    def drain(name, pipe, limit):
        try:
            while True:
                chunk = pipe.read(4096)
                if not chunk:
                    break
                if len(buffers[name]) + len(chunk) > limit:
                    exceeded.set()
                    break
                buffers[name].extend(chunk)
        except (OSError, ValueError):
            failed.set()

    def feed():
        try:
            view = memoryview(data)
            while view:
                written = process.stdin.write(view[:65536])
                if not written:
                    break
                view = view[written:]
        except (BrokenPipeError, OSError, ValueError):
            pass  # The child's structured failure is read from stdout.
        finally:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    try:
        job = WindowsJob(process, memory_limit)
        threads = [threading.Thread(target=drain, args=(name, getattr(process, name), limit), daemon=True)
                   for name, limit in (("stdout", stdout_limit), ("stderr", stderr_limit))]
        threads.append(threading.Thread(target=feed, daemon=True))
        for thread in threads:
            thread.start()
        while process.poll() is None:
            if exceeded.is_set() or failed.is_set():
                break
            if time.monotonic() - started > timeout:
                raise CoreError("OKUMA_ZAMAN_SINIRI", "Okuyucu süre bütçesinde sonlandırıldı")
            time.sleep(0.01)
        if exceeded.is_set() or failed.is_set():
            raise CoreError("BELGE_SINIRI", "Okuyucu stdout/stderr sınırı veya boru hatası")
        for thread in threads:
            thread.join(max(0, timeout - (time.monotonic() - started)))
        if any(thread.is_alive() for thread in threads):
            raise CoreError("OKUMA_ZAMAN_SINIRI", "Okuyucu boruları süre bütçesinde kapanmadı")
        if exceeded.is_set() or failed.is_set():
            raise CoreError("BELGE_SINIRI", "Okuyucu stdout/stderr sınırı veya boru hatası")
        return subprocess.CompletedProcess(command, process.returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"]))
    finally:
        if job:
            job.close()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        for thread in threads:
            thread.join(1)
        for pipe in (process.stdin, process.stdout, process.stderr):
            pipe.close()
