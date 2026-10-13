"""Best-effort local error metadata; never log documents, messages or arguments.

No remote transport/dependency. Separate process/session files, bounded writes,
no deletion/rotation. Logging failures must not change the caller's result.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import re
import threading
import traceback
import uuid

MAX_EVENTS = 100
MAX_BYTES = 1024 * 1024
_SESSION = uuid.uuid4().hex[:12]
_LOCK = threading.Lock()
_COUNT = 0
ERROR_STATUSES = frozenset({'FAIL','FAILED','ERROR','BLOCKED','BLOCKED_ENVIRONMENT','TEKNIK_ENGEL','DEPENDENCIES_REQUIRED','MANUAL_REVIEW_REQUIRED','BUDGET_EXCEEDED','BUDGET_EXHAUSTED'})


def _token(value, fallback='UNKNOWN'):
    # Only code-owned short tokens are eligible; never coerce objects/paths.
    return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',value) else fallback


def _versions():
    skill = Path(__file__).resolve().parent.parent
    version = 'UNKNOWN'
    plugin = 'UNKNOWN'
    try:
        version = _token((skill/'VERSION').read_text(encoding='utf-8').strip())
    except Exception:
        pass
    try:
        plugin = _token(json.loads((skill.parent.parent/'.codex-plugin'/'plugin.json').read_text(encoding='utf-8')).get('version'))
    except Exception:
        pass
    return version,plugin


def log_error(operation: str, *, status: str | None = None, exception: Exception | None = None) -> bool:
    """Return whether an event was written. Never expose exception text/locals."""
    global _COUNT
    acquired = False
    try:
        root = os.environ.get('LOCALAPPDATA')
        if not root or not _LOCK.acquire(blocking=False):
            return False
        acquired = True
        if _COUNT >= MAX_EVENTS:
            return False
        now = datetime.now(timezone.utc)
        version,plugin = _versions()
        event = {'schema':'kilic-satinalma-error/v1','timestamp_utc':now.isoformat(),
                 'component':'teklif-degerlendirme','component_version':version,
                 'plugin_version':plugin,'operation':_token(operation),
                 'status':_token(status),'pid':os.getpid(),'session':_SESSION}
        if exception is not None:
            event['exception_type'] = _token(type(exception).__name__)
            event['frames'] = [{'module':_token(Path(frame.filename).name),
                                'function':_token(frame.name),'line':frame.lineno}
                               for frame in traceback.extract_tb(exception.__traceback__)[-5:]]
        directory = Path(root)/'KilicSatinalma'/'logs'
        directory.mkdir(parents=True,exist_ok=True)
        path = directory/f'errors_{now:%Y%m%d}_{os.getpid()}_{_SESSION}.jsonl'
        data = (json.dumps(event,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')
        size = path.stat().st_size if path.exists() else 0
        if size + len(data) > MAX_BYTES:
            return False
        with path.open('ab') as stream:
            stream.write(data)
        _COUNT += 1
        return True
    except Exception:
        return False
    finally:
        if acquired:
            _LOCK.release()


def log_failures(operation: str, statuses=ERROR_STATUSES):
    """Cover Python boundaries; keep returned objects and original exceptions."""
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            try:
                result = fn(*args,**kwargs)
            except Exception as exc:
                if type(exc).__name__ == 'UserAnswerRequired':
                    raise
                log_error(operation,status='ERROR',exception=exc)
                raise
            if isinstance(result,dict) and isinstance(result.get('status'),str) and result['status'] in statuses:
                log_error(operation,status=result['status'])
            return result
        return wrapped
    return decorate
