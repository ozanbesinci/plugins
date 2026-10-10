from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.base import ParseResult, Unit
from common import clean_text


def parse(path: Path) -> ParseResult:
    notes: list[str] = []
    units: list[Unit] = []
    page_count = 0
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                text = ""
                notes.append(f"PDF s.{i} text extraction failed: {exc}")
            units.append(Unit("pdf_page", i, {"page": i}, text=text))
    except Exception as exc:
        return ParseResult("pypdf", "unreadable", [], [str(exc)])

    try:
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                tables: list[Any] = []
                try:
                    for table in page.extract_tables() or []:
                        tables.append(table)
                except Exception as exc:
                    notes.append(f"PDF s.{i} table extraction failed: {exc}")
                if tables and i <= len(units):
                    units[i - 1].structured["tables"] = tables
    except Exception as exc:
        notes.append(f"pdfplumber secondary parse unavailable: {exc}")

    blank_pages = [u.unit_index for u in units if not clean_text(u.text)]
    status = "partial" if blank_pages else "read"
    if blank_pages:
        notes.append(f"Text layer empty on pages: {blank_pages}; render/vision required.")
    return ParseResult(
        "pypdf+pdfplumber",
        status,
        units,
        notes,
        {"page_count": page_count, "blank_text_pages": blank_pages, "needs_visual_pages": blank_pages},
    )


def duckdb_pdf_secondary(path: Path) -> dict[str, Any]:
    """Optional secondary extraction. Never installs extensions automatically."""
    try:
        import duckdb  # type: ignore
    except ImportError:
        return {"available": False, "reason": "duckdb_python_missing"}
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute("SELECT extension_name, installed, loaded FROM duckdb_extensions() WHERE extension_name='pdf'").fetchall()
        if not rows or not rows[0][1]:
            return {"available": False, "reason": "duckdb_pdf_not_installed"}
        if not rows[0][2]:
            con.execute("LOAD pdf")
        data = con.execute("SELECT * FROM read_pdf(?)", [str(path)]).fetchall()
        cols = [c[0] for c in con.description]
        return {"available": True, "rows": [dict(zip(cols, r)) for r in data]}
    except Exception as exc:
        return {"available": False, "reason": f"duckdb_pdf_error:{exc}"}
    finally:
        con.close()
