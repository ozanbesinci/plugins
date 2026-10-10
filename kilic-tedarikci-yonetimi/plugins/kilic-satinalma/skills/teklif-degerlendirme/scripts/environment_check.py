from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path
from typing import Any

MIN_PYTHON = (3, 11)
PACKAGE_MODULES = {
    "duckdb": "duckdb",
    "openpyxl": "openpyxl",
    "pypdf": "pypdf",
    "pdfplumber": "pdfplumber",
    "pypdfium2": "pypdfium2",
    "python-docx": "docx",
    "pillow": "PIL",
    "pywin32": "win32com",
}


def _version_tuple(value: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", value or "")
    return tuple(int(x) for x in nums[:4]) or (0,)


def _cmp(installed: str, op: str, wanted: str) -> bool:
    left = _version_tuple(installed)
    right = _version_tuple(wanted)
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return {
        ">=": left >= right,
        "<=": left <= right,
        ">": left > right,
        "<": left < right,
        "==": left == right,
    }[op]


def _spec_ok(installed: str, spec: str) -> bool:
    if not spec:
        return True
    for clause in spec.split(","):
        clause = clause.strip()
        m = re.fullmatch(r"(>=|<=|==|>|<)\s*([0-9][0-9A-Za-z_.+-]*)", clause)
        if not m:
            return False
        if not _cmp(installed, m.group(1), m.group(2)):
            return False
    return True


def _platform_marker_applies(marker: str | None) -> bool:
    if not marker:
        return True
    marker = marker.strip()
    m = re.fullmatch(r'platform_system\s*==\s*["\']([^"\']+)["\']', marker)
    if m:
        return platform.system().casefold() == m.group(1).casefold()
    return True


def parse_requirements(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        req, sep, marker = line.partition(";")
        if not _platform_marker_applies(marker if sep else None):
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*((?:(?:>=|<=|==|>|<)[^,;\s]+\s*,?\s*)*)", req.strip())
        if not m:
            rows.append({"requirement": line, "parse_error": True, "applies": True})
            continue
        rows.append({
            "package": m.group(1),
            "spec": re.sub(r"\s+", "", m.group(2) or ""),
            "requirement": line,
            "applies": True,
        })
    return rows


def module_version(package: str, module: str) -> dict[str, Any]:
    try:
        imported = importlib.import_module(module)
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = getattr(imported, "__version__", None)
        return {"available": True, "version": version}
    except Exception as exc:
        return {"available": False, "error": str(exc), "version": None}


def check_requirements(requirements: Path) -> dict[str, Any]:
    items = []
    missing = []
    wrong_version = []
    parse_errors = []
    for req in parse_requirements(requirements):
        if req.get("parse_error"):
            parse_errors.append(req["requirement"])
            items.append({**req, "status": "parse_error"})
            continue
        package = str(req["package"])
        module = PACKAGE_MODULES.get(package.casefold(), package.replace("-", "_"))
        state = module_version(package, module)
        status = "ok"
        if not state["available"]:
            status = "missing"
            missing.append(req["requirement"])
        elif req.get("spec") and not _spec_ok(str(state.get("version") or "0"), str(req["spec"])):
            status = "version_mismatch"
            wrong_version.append({"requirement": req["requirement"], "installed": state.get("version")})
        items.append({**req, **state, "module": module, "status": status})
    return {
        "requirements_file": str(requirements),
        "items": items,
        "missing": missing,
        "version_mismatch": wrong_version,
        "parse_errors": parse_errors,
        "ok": not missing and not wrong_version and not parse_errors,
    }


def check_duckdb_pdf(require_pdf_extension: bool = True) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except Exception as exc:
        return {
            "duckdb": False,
            "pdf_extension": False,
            "required": require_pdf_extension,
            "error": str(exc),
        }
    result: dict[str, Any] = {
        "duckdb": True,
        "duckdb_version": getattr(duckdb, "__version__", None),
        "pdf_extension": False,
        "required": require_pdf_extension,
    }
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT extension_name, installed, loaded FROM duckdb_extensions() WHERE extension_name='pdf'"
        ).fetchall()
        result["extension_rows"] = rows
        installed = bool(rows and rows[0][1])
        loaded = bool(rows and rows[0][2])
        if installed and not loaded:
            con.execute("LOAD pdf")
            loaded = True
        expected = [
            "read_pdf", "read_pdf_lines", "read_pdf_words", "read_pdf_layout",
            "read_pdf_tables", "pdf_chunks", "pdf_info", "pdf_to_png",
        ]
        found: dict[str, bool] = {}
        if installed and loaded:
            for name in expected:
                try:
                    count = con.execute(
                        "SELECT count(*) FROM duckdb_functions() WHERE function_name=?", [name]
                    ).fetchone()[0]
                    found[name] = bool(count)
                except Exception:
                    found[name] = False
        result["pdf_functions"] = found
        result["pdf_extension"] = bool(found.get("read_pdf"))
        result["pdf_installed"] = installed
        result["pdf_loaded"] = loaded
    except Exception as exc:
        result["pdf_error"] = str(exc)
    finally:
        con.close()
    return result


from error_log import log_failures


@log_failures('environment_check.check')
def check(requirements: Path | None = None, require_pdf_extension: bool = True) -> dict[str, Any]:
    skill_root = Path(__file__).resolve().parents[1]
    requirements = requirements or (skill_root / "requirements.txt")
    req = check_requirements(requirements)
    duck = check_duckdb_pdf(require_pdf_extension=require_pdf_extension)
    python_ok = sys.version_info[:2] >= MIN_PYTHON
    duck_ok = bool(duck.get("duckdb"))
    pdf_ok = bool(duck.get("pdf_extension")) or not require_pdf_extension
    ready = python_ok and req["ok"] and duck_ok and pdf_ok
    missing_components = missing_component_list(python_ok, req, duck, require_pdf_extension)
    return {
        "status": "READY" if ready else "BLOCKED_ENVIRONMENT",
        "action": "CONTINUE" if ready else "STOP_ANALYSIS",
        "python": {
            "version": platform.python_version(),
            "minimum": ".".join(map(str, MIN_PYTHON)),
            "ok": python_ok,
            "executable": sys.executable,
        },
        "platform": platform.platform(),
        "requirements": req,
        "duckdb": duck,
        "missing_components": missing_components,
        "blocking_reasons": [x["reason"] for x in missing_components],
        "automatic_installation": False,
        "installation_performed": False,
        "user_message": None if ready else blocked_message(missing_components),
        "windows_excel_com_possible": platform.system() == "Windows",
    }


def missing_component_list(python_ok: bool, req: dict[str, Any], duck: dict[str, Any], require_pdf_extension: bool) -> list[dict[str, Any]]:
    """Concrete, user-facing list of what blocks analysis. Nothing is installed here."""
    out: list[dict[str, Any]] = []
    if not python_ok:
        out.append({"component": "Python", "required": f">={MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
                    "installed": platform.python_version(), "reason": "Python sürümü yetersiz"})
    for item in req.get("items", []):
        if item.get("status") == "missing":
            out.append({"component": item.get("package") or item.get("requirement"), "required": item.get("requirement"),
                        "installed": None, "reason": "Python paketi bulunamadı"})
        elif item.get("status") == "version_mismatch":
            out.append({"component": item.get("package"), "required": item.get("requirement"),
                        "installed": item.get("version"), "reason": "Python paketi sürümü aralık dışında"})
        elif item.get("status") == "parse_error":
            out.append({"component": "requirements.txt", "required": item.get("requirement"),
                        "installed": None, "reason": "Gereksinim satırı okunamadı"})
    listed = {str(x.get("component") or "").casefold() for x in out}
    if not duck.get("duckdb") and "duckdb" not in listed:
        out.append({"component": "duckdb", "required": "DuckDB Python paketi", "installed": None,
                    "reason": "DuckDB Python paketi yüklenemedi"})
    if require_pdf_extension and duck.get("duckdb") and not duck.get("pdf_extension"):
        out.append({"component": "DuckDB pdf eklentisi", "required": "read_pdf işlevi yüklenebilir olmalı",
                    "installed": "kurulu" if duck.get("pdf_installed") else None,
                    "reason": "DuckDB pdf eklentisi kurulu değil veya yüklenemiyor"})
    return out


def blocked_message(missing_components: list[dict[str, Any]]) -> str:
    lines = ["Çalışma ortamı hazır değil; teklif analizi başlatılmadı. Eksik veya uyumsuz bileşenler:"]
    for item in missing_components:
        installed = f" (kurulu: {item['installed']})" if item.get("installed") else ""
        lines.append(f"- {item['component']}: {item['required']}{installed} — {item['reason']}")
    lines.append("Bu skill otomatik kurulum yapmaz. Bileşenleri yetkili kişi kurduktan sonra ortam kontrolünü yeniden çalıştırın.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check v5 runtime dependencies before any procurement analysis")
    ap.add_argument("--output")
    ap.add_argument("--requirements", type=Path)
    ap.add_argument("--strict", action="store_true", help="Return non-zero when the environment blocks analysis")
    ap.add_argument("--pdf-extension-optional", action="store_true")
    args = ap.parse_args()
    result = check(args.requirements, require_pdf_extension=not args.pdf_extension_optional)
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)
    if result.get("user_message"):
        print(result["user_message"], file=sys.stderr)
    if args.strict and result["status"] != "READY":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
