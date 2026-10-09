from __future__ import annotations

from email import policy
from email.parser import BytesParser
from pathlib import Path
import re

from adapters.base import ParseResult, Unit

MAX_ATTACHMENTS = 200
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024


def extract_attachments(path: Path, target_root: Path) -> list[tuple[Path, str, int]]:
    """Copy MIME attachment bytes into the run area, never into the source tree."""
    msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    parts = [(index, part) for index, part in enumerate(msg.walk(), start=1)
             if part.get_content_disposition() == "attachment"]
    if len(parts) > MAX_ATTACHMENTS:
        raise ValueError(f"Too many email attachments: {len(parts)}")
    prepared = []
    total = 0
    for index, part in parts:
        data = part.get_payload(decode=True)
        if data is None:
            raise ValueError(f"Email attachment {index} has no decodable bytes")
        if len(data) > MAX_ATTACHMENT_BYTES:
            raise ValueError(f"Email attachment {index} exceeds size limit")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Email attachments exceed total size limit")
        original = part.get_filename() or f"unnamed-{index}"
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", original).strip(" .")
        if not safe:
            safe = f"unnamed-{index}"
        prepared.append((index, safe, original, data))
    target_root.mkdir(parents=True, exist_ok=True)
    out = []
    for index, safe, original, data in prepared:
        target = target_root / f"{index:03d}-{safe}"
        target.write_bytes(data)
        out.append((target, original, index))
    return out


def parse(path: Path) -> ParseResult:
    try:
        msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    except Exception as exc:
        return ParseResult("stdlib-email", "unreadable", [], [str(exc)])
    units: list[Unit] = []
    idx = 1
    headers = {k: str(msg.get(k, "")) for k in ["Subject", "From", "To", "Date", "Message-ID"]}
    units.append(Unit("eml_headers", idx, {"part": "headers"}, "\n".join(f"{k}: {v}" for k, v in headers.items()), headers)); idx += 1
    attachments = []
    if msg.is_multipart():
        for pno, part in enumerate(msg.walk(), start=1):
            ctype = part.get_content_type()
            disp = part.get_content_disposition()
            if disp == "attachment":
                attachments.append({"part": pno, "filename": part.get_filename(), "content_type": ctype})
                continue
            if ctype == "text/plain":
                try:
                    body = part.get_content()
                except Exception:
                    body = ""
                if body:
                    units.append(Unit("eml_body", idx, {"part": pno}, str(body))); idx += 1
    else:
        try:
            body = msg.get_content()
        except Exception:
            body = ""
        if body:
            units.append(Unit("eml_body", idx, {"part": 1}, str(body))); idx += 1
    return ParseResult("stdlib-email", "read", units, [], {"headers": headers, "attachments": attachments})
