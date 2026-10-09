from __future__ import annotations

import platform
import tempfile
from pathlib import Path

from adapters.base import ParseResult, Unit


def parse_xls(path: Path) -> ParseResult:
    if platform.system() != "Windows":
        return ParseResult("excel-com", "unreadable", [], ["Legacy XLS requires Windows Excel COM or an approved converter."])
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        return ParseResult("excel-com", "unreadable", [], [f"Excel COM unavailable: {exc}"])
    temp_dir = Path(tempfile.mkdtemp(prefix="teklif-xls-"))
    out = temp_dir / (path.stem + ".xlsx")
    excel = None
    wb = None
    prior_security = None
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.EnableEvents = False
        prior_security = excel.AutomationSecurity
        # msoAutomationSecurityForceDisable = 3. ReadOnly does not disable
        # VBA/XLM execution by itself.
        excel.AutomationSecurity = 3
        wb = excel.Workbooks.Open(
            str(path.resolve()), UpdateLinks=0, ReadOnly=True,
            IgnoreReadOnlyRecommended=True, AddToMru=False,
        )
        # Legacy Excel 4 macro sheets are not safe to treat as ordinary data.
        try:
            if int(wb.Excel4MacroSheets.Count) > 0:
                return ParseResult("excel-com", "unreadable", [], ["Legacy XLS contains Excel 4 macro sheets; blocked by policy."])
        except Exception:
            pass
        wb.SaveAs(str(out), FileFormat=51)
        wb.Close(False)
        wb = None
        from adapters.xlsx_adapter import parse as parse_xlsx
        result = parse_xlsx(out)
        result.parser_name = "excel-com->openpyxl"
        result.notes.append("Legacy XLS converted to a temporary XLSX working copy; original remained read-only.")
        return result
    except Exception as exc:
        return ParseResult("excel-com", "unreadable", [], [str(exc)])
    finally:
        try:
            if wb is not None:
                wb.Close(False)
        except Exception:
            pass
        try:
            if excel is not None and prior_security is not None:
                excel.AutomationSecurity = prior_security
        except Exception:
            pass
        try:
            if excel is not None:
                excel.Quit()
        except Exception:
            pass


def parse_doc(path: Path) -> ParseResult:
    if platform.system() != "Windows":
        return ParseResult("word-com", "unreadable", [], ["Legacy DOC requires Windows Word COM or an approved converter."])
    try:
        import win32com.client  # type: ignore
    except Exception as exc:
        return ParseResult("word-com", "unreadable", [], [f"Word COM unavailable: {exc}"])
    word = None
    doc = None
    prior_security = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        prior_security = word.AutomationSecurity
        word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        doc = word.Documents.Open(
            str(path.resolve()), ConfirmConversions=False, ReadOnly=True,
            AddToRecentFiles=False, NoEncodingDialog=True,
        )
        text = doc.Content.Text or ""
        units = [Unit("doc_text", 1, {"part": "body"}, text)]
        return ParseResult("word-com", "read", units, [], {"converted": False})
    except Exception as exc:
        return ParseResult("word-com", "unreadable", [], [str(exc)])
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None and prior_security is not None:
                word.AutomationSecurity = prior_security
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
