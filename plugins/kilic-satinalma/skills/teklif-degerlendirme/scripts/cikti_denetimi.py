"""Mechanical artifact checks, not a substitute for recalculation or visual review."""
from pathlib import Path, PurePosixPath
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal, InvalidOperation

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def validate_xlsx(path):
    path = Path(path)
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Çalışma kitabı .xlsx olmalı.")
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or len(names) > 5000 or sum(i.file_size for i in z.infolist()) > 128 * 1024 * 1024:
                raise ValueError("XLSX arşiv sınırı/yinelenmiş dosya hatası.")
            for name in names:
                if "\\" in name or name.startswith("/") or ".." in PurePosixPath(name).parts:
                    raise ValueError("XLSX arşivinde güvensiz yol.")
            if any(i.flag_bits & 1 for i in z.infolist()):
                raise ValueError("Şifreli XLSX desteklenmez.")
            required = {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
            if not required.issubset(names) or any(n.startswith("xl/externalLinks/") for n in names):
                raise ValueError("XLSX çekirdek yapısı eksik veya harici veri bağı var.")
            for name in required:
                ET.fromstring(z.read(name))
            package_rels = ET.fromstring(z.read("_rels/.rels"))
            if not any(r.get("Type", "").endswith("/officeDocument") and r.get("Target", "").lstrip("/") == "xl/workbook.xml"
                       and r.get("TargetMode") != "External" for r in package_rels):
                raise ValueError("XLSX paket/workbook ilişkisi yok.")
            workbook = ET.fromstring(z.read("xl/workbook.xml"))
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            mapping = {r.get("Id"): r for r in rels.findall(f"{{{PKG_NS}}}Relationship")}
            sheets = workbook.findall(f"{{{MAIN_NS}}}sheets/{{{MAIN_NS}}}sheet")
            if not sheets:
                raise ValueError("XLSX çalışma sayfası yok.")
            formula_count = 0
            for sheet in sheets:
                rel = mapping.get(sheet.get(f"{{{REL_NS}}}id"))
                if rel is None or rel.get("TargetMode") == "External":
                    raise ValueError("Çalışma sayfası ilişkisi eksik/harici.")
                target = rel.get("Target", "")
                normalized = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
                if not normalized.startswith("xl/worksheets/") or ".." in PurePosixPath(normalized).parts:
                    raise ValueError("Güvensiz çalışma sayfası yolu.")
                worksheet = ET.fromstring(z.read(normalized))
                if worksheet.tag != f"{{{MAIN_NS}}}worksheet" or worksheet.find(f"{{{MAIN_NS}}}sheetData") is None:
                    raise ValueError("Geçerli worksheet/sheetData yok.")
                for cell in worksheet.iter(f"{{{MAIN_NS}}}c"):
                    if cell.get("t") == "e":
                        raise ValueError(f"Excel hata hücresi: {sheet.get('name')}!{cell.get('r')}")
                    if cell.find(f"{{{MAIN_NS}}}f") is not None:
                        formula_count += 1
                        v = cell.find(f"{{{MAIN_NS}}}v")
                        if v is None:
                            raise ValueError("Formül önbelleği yok; yeniden hesaplama gerekli.")
                        if cell.get("t") == "str":
                            continue  # Excel's legitimate IF(..., "") result; real COM receipt still required.
                        if v.text is None or not v.text.strip():
                            raise ValueError("Sayısal formül önbelleği boş.")
                        try:
                            numeric = Decimal(v.text)
                            if not numeric.is_finite():
                                raise ValueError("Formül önbelleği sonlu değil.")
                        except InvalidOperation as exc:
                            raise ValueError("Sayısal formül önbelleği sayı değil.") from exc
            if formula_count == 0:
                raise ValueError("Karar kitabında hesap formülü yok.")
            return {"sheets": len(sheets), "formulas": formula_count, "scope": "structure_and_cache_only"}
    except (zipfile.BadZipFile, ET.ParseError, KeyError, RuntimeError) as exc:
        raise ValueError("Bozuk veya eksik XLSX yapısı.") from exc


def validate_pdf(path):
    path = Path(path)
    data = path.read_bytes()
    if path.suffix.lower() != ".pdf" or not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise ValueError("PDF başlığı/sonlandırması geçersiz veya dosya kesik.")
    # A parser is required for actual page/content checks; no signature-only PASS.
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF içerik kontrolü için pypdf yok; kontrol doğrulanamadı.") from exc
    try:
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted or not reader.pages:
            raise ValueError("PDF şifreli veya sayfasız.")
        texts = [(p.extract_text() or "") for p in reader.pages]
        if not any("Sonuç" in t and "Öneri" in t for t in texts):
            raise ValueError("PDF Sonuç ve Öneri bölümü metinden doğrulanamadı.")
        return {"pages": len(reader.pages), "scope": "parser_and_text_only"}
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("PDF içerik çözümlemesi başarısız.") from exc
