"""Abrupt termination for disposable test workers; never imported by production."""
import os
from typing import NoReturn


def abrupt_exit(status: int) -> NoReturn:
    """Kill this process without Python or DLL shutdown callbacks on Windows.

    CRT _exit after DuckDB activity can fault during Windows teardown. Calling
    TerminateProcess on our own pseudo-handle models the intended hard crash.
    No PID, foreign handle, recovery, cleanup, or production capability is exposed.
    """
    if type(status) is not int or not 0 <= status <= 255:
        raise ValueError("Synthetic crash exit code must be an integer in 0..255")
    if os.name != "nt":
        os._exit(status)
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    if not kernel32.TerminateProcess(kernel32.GetCurrentProcess(), status):
        raise ctypes.WinError(ctypes.get_last_error())
    raise RuntimeError("Successful self-termination must not return")
