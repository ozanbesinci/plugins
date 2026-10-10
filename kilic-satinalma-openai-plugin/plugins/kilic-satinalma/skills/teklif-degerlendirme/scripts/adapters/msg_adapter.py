from __future__ import annotations

from pathlib import Path

from adapters.base import ParseResult, Unit


def parse(path: Path) -> ParseResult:
    try:
        import extract_msg  # type: ignore
    except Exception:
        return ParseResult("extract-msg", "unreadable", [], ["MSG adapter requires the optional extract-msg package."])
    try:
        msg = extract_msg.Message(str(path))
        headers = {
            "subject": msg.subject or "",
            "sender": msg.sender or "",
            "to": msg.to or "",
            "date": str(msg.date or ""),
        }
        units = [Unit("msg_headers", 1, {"part": "headers"}, "\n".join(f"{k}: {v}" for k, v in headers.items()), headers)]
        if msg.body:
            units.append(Unit("msg_body", 2, {"part": "body"}, msg.body))
        attachments = []
        for idx, att in enumerate(msg.attachments, start=1):
            attachments.append({"index": idx, "filename": getattr(att, "longFilename", None) or getattr(att, "shortFilename", None)})
        return ParseResult("extract-msg", "read", units, [], {"attachments": attachments})
    except Exception as exc:
        return ParseResult("extract-msg", "unreadable", [], [str(exc)])
