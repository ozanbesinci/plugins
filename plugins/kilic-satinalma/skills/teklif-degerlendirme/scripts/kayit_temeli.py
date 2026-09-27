"""Local immutable hashes and guarded writes for one analysis directory."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, default=str)
            out.flush(); os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def contained(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Dosya koşu alanı dışında.")
    return path


def inventory(root, selected=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("Kaynak klasörü yok.")
    excluded = {"analiz", ".git", ".codex", ".agents", "__pycache__"}
    paths = []
    if selected is not None:
        if not isinstance(selected, list) or not selected or len(selected) != len(set(selected)):
            raise ValueError("Kaynak listesi benzersiz, boş olmayan yollar içermeli.")
        paths = [root/p for p in selected]
    else:
        for directory, folders, files in os.walk(root, followlinks=False):
            folders[:] = [f for f in folders if f.casefold() not in excluded and not f.startswith(".")
                          and not Path(directory,f).is_symlink() and not Path(directory,f).is_junction()]
            paths.extend(Path(directory,f) for f in files if not f.startswith((".", "~$")) and f.lower() != "desktop.ini")
    entries = []
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Kaynak dosya yok veya bağlantı.")
        path = contained(root, path)
        h = sha(path); rel = path.relative_to(root).as_posix()
        entries.append({"source_id": hashlib.sha256((rel+h).encode()).hexdigest()[:24],
                        "relative_path": rel, "sha256": h, "size_bytes": path.stat().st_size})
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    return {"root": str(root), "entries": entries, "dataset_sha256": digest}


@contextlib.contextmanager
def lock(root):
    path = Path(root)/".operation.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ValueError("İşlem kilidi var; sahibi doğrulanmadan kaldırılmaz.") from error
    os.close(fd)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)
