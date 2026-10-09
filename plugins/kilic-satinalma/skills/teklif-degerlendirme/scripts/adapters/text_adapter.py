from __future__ import annotations

from pathlib import Path

from adapters.base import ParseResult, Unit
from adapters.csv_adapter import _decode


def parse(path: Path) -> ParseResult:
    text, enc = _decode(path)
    unit = Unit("text", 1, {"line_start": 1, "line_end": text.count("\n") + 1}, text)
    return ParseResult("text", "read", [unit], [], {"encoding": enc})
