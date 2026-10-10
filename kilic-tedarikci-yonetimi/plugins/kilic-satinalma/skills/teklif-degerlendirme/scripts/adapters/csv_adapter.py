from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import ParseResult, Unit

ENCODINGS = ["utf-8-sig", "utf-8", "cp1254", "iso-8859-9"]


def _decode(path: Path):
    raw = path.read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


def parse(path: Path, chunk_rows: int = 100) -> ParseResult:
    text, encoding = _decode(path)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except Exception:
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    units: list[Unit] = []
    for idx in range(0, len(rows), chunk_rows):
        chunk = rows[idx: idx + chunk_rows]
        lines = [delimiter.join(str(x) for x in r) for r in chunk]
        units.append(Unit(
            "csv_chunk",
            idx // chunk_rows + 1,
            {"start_row": idx + 1, "end_row": idx + len(chunk), "delimiter": delimiter},
            "\n".join(lines),
            {"rows": chunk},
        ))
    return ParseResult("python-csv", "read", units, [], {"encoding": encoding, "delimiter": delimiter, "row_count": len(rows)})
