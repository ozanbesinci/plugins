from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time
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
    with native_path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
    resolved = ordinary_path(native_path(path).resolve())
    if not any(resolved.is_relative_to(ordinary_path(native_path(root).resolve())) for root in roots):
        raise CoreError("ERISIM_YOK", "Çözülmüş yol izinli kökün dışında")
    return path


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + str(uuid4()) + ".tmp")
    with native_path(temp).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(native_path(temp), native_path(path))


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
