from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time
from contextlib import contextmanager
from uuid import UUID, uuid4

from .errors import CoreError


def uuid_text(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CoreError("GECERSIZ_KIMLIK", "Geçerli UUID gerekli") from exc


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def hash_value(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def hash_file(path):
    with open_verified_source(path) as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _windows_source_handle(path):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(native_path(path)), 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        # Only a sharing/lock violation means another writer; a moved or denied
        # source is access loss and must not tell the user to close a file.
        if error in (32, 33):
            raise CoreError("KAYNAK_MESGUL", "Kaynak başka bir uygulamada yazma/silme için açık; dosyayı kapatıp yeniden dene")
        if error in (2, 3, 53, 67):
            raise CoreError("ERISIM_YOK", "Kaynak dosya bulunamadı veya yolu erişilemiyor; taşındıysa yeni yolu yeni sürüm olarak al")
        if error == 5:
            raise CoreError("ERISIM_YOK", "Kaynak dosyaya Windows erişimi reddedildi")
        raise CoreError("ERISIM_YOK", f"Kaynak sabit salt-okunur nesne olarak açılamadı (Windows hata {error})")
    return kernel, handle


def _validate_windows_source(kernel, handle, path):
    import ctypes
    from ctypes import wintypes
    class Information(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("created", wintypes.FILETIME),
                    ("accessed", wintypes.FILETIME), ("written", wintypes.FILETIME),
                    ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD), ("size_low", wintypes.DWORD),
                    ("links", wintypes.DWORD), ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(Information)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.GetLongPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel.GetLongPathNameW.restype = wintypes.DWORD
    info, buffer = Information(), ctypes.create_unicode_buffer(32768)
    size = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
    if (not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)) or not 0 < size < len(buffer)
            or info.attributes & (0x400 | 0x10) or info.links != 1):
        raise CoreError("ERISIM_YOK", "Kaynak nesnesi reparse/dizin/çoklu link veya doğrulanamayan nesne")
    expanded = ctypes.create_unicode_buffer(32768)
    expanded_size = kernel.GetLongPathNameW(str(native_path(path)), expanded, len(expanded))
    if not 0 < expanded_size < len(expanded):
        raise CoreError("ERISIM_YOK", "Windows uzun kaynak adı doğrulanamadı")
    expected = os.path.normcase(os.path.abspath(ordinary_path(expanded.value)))
    observed = os.path.normcase(os.path.abspath(ordinary_path(buffer.value)))
    if expected != observed:
        raise CoreError("ERISIM_YOK", "Açılan kaynak nesnesi istenen yolla eşleşmiyor")


@contextmanager
def open_verified_source(path):
    """Bind a read to one ordinary file; deny concurrent write/delete on Windows."""
    # This local parent check does not grant a root; callers still pass their own
    # authorized roots. It rejects reparse ancestors even for direct helper use.
    confined(path, [Path(path).absolute().parent])
    if os.name != "nt":
        with native_path(path).open("rb") as stream:
            if os.fstat(stream.fileno()).st_nlink != 1:
                raise CoreError("ERISIM_YOK", "Çoklu link kaynak olarak kullanılamaz")
            yield stream
        return
    import msvcrt
    kernel, handle = _windows_source_handle(path)
    transferred = False
    try:
        _validate_windows_source(kernel, handle, path)
        fd = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_BINARY)
        transferred = True
        with os.fdopen(fd, "rb") as stream:
            yield stream
            _validate_windows_source(kernel, handle, path)
    finally:
        if not transferred:
            kernel.CloseHandle(handle)


def read_verified_bytes(path, limit=100 * 1024 * 1024):
    with open_verified_source(path) as stream:
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise CoreError("BOYUT_SINIRI", "Kaynak nesnesi okuma bütçesini aştı")
        return data


def ordinary_path(path):
    value = os.fspath(path)
    if os.name == "nt" and value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif os.name == "nt" and value.startswith("\\\\?\\"):
        value = value[4:]
    return Path(value)


def native_path(path):
    """Extended Windows namespace for I/O only; containment uses ordinary paths."""
    path = ordinary_path(path).absolute()
    if os.name != "nt":
        return path
    value = str(path)
    return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)


def confined(path, roots):
    """No symlink/junction anywhere in the authorized path; no containment by prefix."""
    path = Path(os.path.abspath(ordinary_path(path)))
    if not any(path.is_relative_to(Path(os.path.abspath(ordinary_path(root)))) for root in roots):
        raise CoreError("ERISIM_YOK", "Yol izinli kökün dışında")
    for part in (*reversed(path.parents), path):
        probe = native_path(part)
        if probe.exists() or probe.is_symlink():
            info = probe.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise CoreError("ERISIM_YOK", "Symlink/junction kaynak veya hedef olarak kullanılamaz")
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise CoreError("ERISIM_YOK", "Çoklu hardlink kaynak veya hedef olarak kullanılamaz")
    resolved = ordinary_path(native_path(path).resolve())
    if not any(resolved.is_relative_to(ordinary_path(native_path(root).resolve())) for root in roots):
        raise CoreError("ERISIM_YOK", "Çözülmüş yol izinli kökün dışında")
    return path


REPLACE_RETRY_SECONDS = (0.05, 0.1, 0.2, 0.4, 0.8)


def replace_owned(source, target):
    """Move our own closed temp file into place.

    Windows scanners/indexers briefly open a just-closed file without delete
    sharing, which makes MoveFileEx report access denied. Only that error is
    retried, boundedly; every other failure surfaces at once.
    """
    for delay in REPLACE_RETRY_SECONDS + (None,):
        try:
            return os.replace(native_path(source), native_path(target))
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)


def rename_owned(source, target):
    """No-overwrite rename of our own just-built staging directory.

    Same transient scanner hold as replace_owned (e.g. a just-closed DuckDB file
    inside the folder). An existing target still fails at once.
    """
    for delay in REPLACE_RETRY_SECONDS + (None,):
        try:
            return os.rename(native_path(source), native_path(target))
        except FileExistsError:
            raise
        except PermissionError:
            if delay is None:
                raise
            time.sleep(delay)


def atomic_json(path, value):
    path = Path(path)
    content = canonical(value)
    temp = path.with_name(path.name + "." + str(uuid4()) + ".tmp")
    created = False
    try:
        with native_path(temp).open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        replace_owned(temp, path)
        created = False
    finally:
        if created:
            native_path(temp).unlink(missing_ok=True)


class FileLock:
    """Every repository read/write/migration/snapshot uses the same OS lock."""
    def __init__(self, path, timeout=5):
        self.path, self.timeout, self.file = Path(path), timeout, None

    def __enter__(self):
        if os.name != "nt":
            raise CoreError("KILIT_DESTEK_YOK", "Bu sürümde yalnız ölçülmüş Windows kilidi desteklenir")
        try:
            import msvcrt
        except ImportError as exc:
            raise CoreError("KILIT_DESTEK_YOK", "Windows kilit sağlayıcısı yok") from exc
        self.file = native_path(self.path).open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError as exc:
                if time.monotonic() >= deadline:
                    self.file.close()
                    self.file = None
                    raise CoreError("KILIT_MESGUL", "Başka oturum işlemi sürüyor; kilitsiz devam edilmedi") from exc
                time.sleep(0.025)

    def __exit__(self, *_):
        import msvcrt
        try:
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.file.close()
            self.file = None
