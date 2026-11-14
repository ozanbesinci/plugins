"""Static internal-draft OOXML and a bounded, owned-instance Word adapter.

This module does not grant publication, corporate approval or visual acceptance.
Only its own closed OOXML vocabulary is admitted to the native renderer.
"""
from __future__ import annotations

import hashlib
from contextlib import ExitStack
from importlib import metadata
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

from .errors import CoreError
from .safety import canonical, open_verified_source

MAX_TEXT = 65536
MAX_DOCX = 2 * 1024 * 1024
MAX_XML = 2 * 1024 * 1024
MAX_PAGES = 25
MAX_PDF = 32 * 1024 * 1024
MAX_PNG = 8 * 1024 * 1024
MAX_TOTAL_PNG = 128 * 1024 * 1024
MAX_PIXELS = 4_000_000
MAX_RENDER_SECONDS = 60
MAX_WORD_MEMORY = 1024 * 1024 * 1024
HEADER = "İÇ ÇALIŞMA TASLAĞI"
FOOTER = "İmza ve kurumsal onay için değildir."
PURPOSE = "Bu belge iç değerlendirme içindir. Taslak metin, kullanıcı beyanı ve kaynak alıntısı ayrı etiketlenmiştir."
SOURCE_FREE_NOTICE = "Bu taslak için kaynak belge kullanılmadı; metin değerlendirmeye sunulan bir öneridir."
PARTIAL_NOTICE = "Bu taslak yalnız mevcut kaynaklar üzerinden hazırlanmıştır. Aşağıdaki eksik kaynakların içeriği değerlendirilmedi."
LABELS = {
    "DRAFT_TEXT": "İç taslak | Taslak öneri",
    "USER_STATEMENT": "İç taslak | Kullanıcı beyanı",
    "SOURCE_EXCERPT": "İç taslak | Kaynak alıntısı",
}
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
ET.register_namespace("w", W)
ET.register_namespace("r", R)


def _error(message, code="TASLAK_QA"):
    raise CoreError(code, message)


def _text(value, *, limit=MAX_TEXT, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        _error("Taslak metin türü veya uzunluğu geçersiz")
    if any((ord(c) < 32 and c != "\n") or 0xD800 <= ord(c) <= 0xDFFF or
           ord(c) in (0xFFFE, 0xFFFF) for c in value):
        _error("Taslak metninde desteklenmeyen XML karakteri var")
    return value


def _xml(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def _paragraph(text, style="Normal"):
    p = ET.Element(f"{{{W}}}p")
    props = ET.SubElement(p, f"{{{W}}}pPr")
    ET.SubElement(props, f"{{{W}}}pStyle", {f"{{{W}}}val": style})
    run = ET.SubElement(p, f"{{{W}}}r")
    ET.SubElement(run, f"{{{W}}}t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = text
    return p


def _section():
    section = ET.Element(f"{{{W}}}sectPr")
    ET.SubElement(section, f"{{{W}}}headerReference", {f"{{{W}}}type": "default", f"{{{R}}}id": "rIdHeader"})
    ET.SubElement(section, f"{{{W}}}footerReference", {f"{{{W}}}type": "default", f"{{{R}}}id": "rIdFooter"})
    ET.SubElement(section, f"{{{W}}}pgSz", {f"{{{W}}}w": "11906", f"{{{W}}}h": "16838"})
    ET.SubElement(section, f"{{{W}}}pgMar", {f"{{{W}}}{key}": value for key, value in
                  {"top": "1134", "right": "1134", "bottom": "1134", "left": "1134",
                   "header": "567", "footer": "567", "gutter": "0"}.items()})
    return section


def _document(paragraphs):
    document = ET.Element(f"{{{W}}}document")
    body = ET.SubElement(document, f"{{{W}}}body")
    for style, text in paragraphs:
        body.append(_paragraph(text, style))
    body.append(_section())
    return _xml(document)


def _static_parts():
    relationships = "http://schemas.openxmlformats.org/package/2006/relationships"
    types = "http://schemas.openxmlformats.org/package/2006/content-types"
    root = ET.Element("Relationships", xmlns=relationships)
    ET.SubElement(root, "Relationship", Id="rIdDocument", Type=R + "/officeDocument", Target="word/document.xml")
    doc_rels = ET.Element("Relationships", xmlns=relationships)
    for identity, kind, target in (("rIdStyles", "styles", "styles.xml"), ("rIdSettings", "settings", "settings.xml"),
                                   ("rIdHeader", "header", "header1.xml"), ("rIdFooter", "footer", "footer1.xml")):
        ET.SubElement(doc_rels, "Relationship", Id=identity, Type=R + "/" + kind, Target=target)
    content_types = ET.Element("Types", xmlns=types)
    ET.SubElement(content_types, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    for part, kind in (("document", "document.main"), ("styles", "styles"), ("settings", "settings"),
                        ("header1", "header"), ("footer1", "footer")):
        ET.SubElement(content_types, "Override", PartName=f"/word/{part}.xml",
                      ContentType=f"application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml")
    styles = ET.Element(f"{{{W}}}styles")
    for identity, size, bold in (("Normal", 22, False), ("Title", 40, False), ("Heading1", 28, True),
                                 ("Label", 20, True), ("SourceExcerpt", 22, False), ("Stamp", 20, True)):
        attrs = {f"{{{W}}}type": "paragraph", f"{{{W}}}styleId": identity}
        if identity == "Normal":
            attrs[f"{{{W}}}default"] = "1"
        style = ET.SubElement(styles, f"{{{W}}}style", attrs)
        ET.SubElement(style, f"{{{W}}}name", {f"{{{W}}}val": {"Heading1": "heading 1"}.get(identity, identity)})
        if identity != "Normal":
            ET.SubElement(style, f"{{{W}}}basedOn", {f"{{{W}}}val": "Normal"})
        ppr = ET.SubElement(style, f"{{{W}}}pPr")
        if identity in ("Title", "Heading1", "Label"):
            ET.SubElement(ppr, f"{{{W}}}keepNext")
        ET.SubElement(ppr, f"{{{W}}}widowControl")
        ET.SubElement(ppr, f"{{{W}}}spacing", {f"{{{W}}}after": "120", f"{{{W}}}line": "276", f"{{{W}}}lineRule": "auto"})
        if identity == "SourceExcerpt":
            ET.SubElement(ppr, f"{{{W}}}ind", {f"{{{W}}}left": "284"})
        if identity == "Heading1":
            ET.SubElement(ppr, f"{{{W}}}outlineLvl", {f"{{{W}}}val": "0"})
        rpr = ET.SubElement(style, f"{{{W}}}rPr")
        ET.SubElement(rpr, f"{{{W}}}rFonts", {f"{{{W}}}{key}": "Aptos" for key in ("ascii", "hAnsi", "eastAsia", "cs")})
        if bold:
            ET.SubElement(rpr, f"{{{W}}}b")
        ET.SubElement(rpr, f"{{{W}}}color", {f"{{{W}}}val": "000000"})
        ET.SubElement(rpr, f"{{{W}}}sz", {f"{{{W}}}val": str(size)})
        ET.SubElement(rpr, f"{{{W}}}szCs", {f"{{{W}}}val": str(size)})
        ET.SubElement(rpr, f"{{{W}}}lang", {f"{{{W}}}val": "tr-TR"})
    settings = ET.Element(f"{{{W}}}settings")
    ET.SubElement(settings, f"{{{W}}}updateFields", {f"{{{W}}}val": "false"})
    header, footer = ET.Element(f"{{{W}}}hdr"), ET.Element(f"{{{W}}}ftr")
    header.append(_paragraph(HEADER, "Stamp"))
    footer.append(_paragraph(FOOTER, "Stamp"))
    return {"[Content_Types].xml": _xml(content_types), "_rels/.rels": _xml(root),
            "word/_rels/document.xml.rels": _xml(doc_rels), "word/styles.xml": _xml(styles),
            "word/settings.xml": _xml(settings), "word/header1.xml": _xml(header), "word/footer1.xml": _xml(footer)}


def build_docx(title, sections, provenance):
    """Build deterministic, macro/link/field-free OOXML; all input is plain text."""
    title = _text(title, limit=200)
    if "\n" in title or not isinstance(sections, list) or not 1 <= len(sections) <= 100:
        _error("Taslak başlığı veya bölüm sayısı geçersiz")
    if not isinstance(provenance, dict):
        _error("Taslak köken bilgisi gerekli")
    case_id = provenance.get("case_id")
    revision = provenance.get("context_version")
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", case_id):
        _error("Taslak vaka kimliği geçersiz")
    if not isinstance(revision, (str, int)) or isinstance(revision, bool) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", str(revision)):
        _error("Taslak bağlam sürümü geçersiz")
    limits = provenance.get("limitations", [])
    if not isinstance(limits, list) or len(limits) > 30:
        _error("Taslak kapsam sınırları geçersiz")
    # Technical provenance and general audit limitations remain in the manifest.
    # Only limitations that affect the reader's interpretation appear in the body.
    for limitation in limits:
        _text(limitation, limit=2000)
    paragraphs = [("Title", title), ("Normal", PURPOSE)]
    source_free = provenance.get("source_free", False)
    partial = provenance.get("partial_review")
    if type(source_free) is not bool or (source_free and partial is not None):
        _error("Taslak kaynak kapsamı çelişkili")
    if source_free:
        paragraphs.append(("Normal", SOURCE_FREE_NOTICE))
    elif partial is not None:
        if (not isinstance(partial, dict) or partial.get("scope") != "AVAILABLE_REGISTERED_EVIDENCE_ONLY"
                or partial.get("registered_closure_complete") is not False
                or not isinstance(partial.get("missing_dependencies"), list)
                or not 1 <= len(partial["missing_dependencies"]) <= 256):
            _error("Kısmi taslağın eksik kaynak kapsamı geçersiz")
        paragraphs.append(("Normal", PARTIAL_NOTICE))
        for missing in partial["missing_dependencies"]:
            if not isinstance(missing, dict):
                _error("Eksik kaynak adı geçersiz")
            reference = _text(missing.get("reference"), limit=2000)
            if "\n" in reference:
                _error("Eksik kaynak adı tek satır olmalı")
            paragraphs.append(("Normal", "Eksik kaynak: " + reference))
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"heading", "text", "kind", "node_ids"}:
            _error("Taslak bölümü kapalı şemaya uymuyor")
        kind = section["kind"]
        if not isinstance(kind, str) or kind not in LABELS or not isinstance(section["node_ids"], list) or any(not isinstance(n, str) for n in section["node_ids"]):
            _error("Taslak bölüm türü veya kaynak düğümleri geçersiz")
        if source_free and kind != "DRAFT_TEXT":
            _error("Kaynaksız taslak, kaynak alıntısı veya kayıtlı beyan içeremez")
        heading = _text(section["heading"], limit=200)
        text = _text(section["text"])
        if "\n" in heading:
            _error("Bölüm başlığı tek satır olmalı")
        paragraphs.extend((("Heading1", heading), ("Label", LABELS[kind])))
        paragraphs.extend(("SourceExcerpt" if kind == "SOURCE_EXCERPT" else "Normal", line)
                          for line in text.split("\n"))
    if sum(len(text) for _, text in paragraphs) > MAX_TEXT or len(paragraphs) > 1500:
        _error("Taslak toplam metin/paragraf sınırı aşıldı", "TASLAK_SINIRI")
    parts = _static_parts()
    parts["word/document.xml"] = _document(paragraphs)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            package.writestr(info, parts[name])
    result = output.getvalue()
    structural_qa(result)
    return result


def structural_qa(docxbytes):
    """Reject all non-template package/XML structure, including hidden content."""
    try:
        if not isinstance(docxbytes, bytes) or not 0 < len(docxbytes) <= MAX_DOCX:
            _error("DOCX boyutu uygun değil", "TASLAK_SINIRI")
        fixed = _static_parts()
        expected_names = set(fixed) | {"word/document.xml"}
        with zipfile.ZipFile(io.BytesIO(docxbytes)) as archive:
            infos = archive.infolist()
            if len(infos) != len(expected_names) or {p.filename for p in infos} != expected_names:
                _error("DOCX paket parçası izin listesiyle uyuşmuyor")
            if archive.comment or sum(p.file_size for p in infos) > MAX_XML or any(p.flag_bits & 1 for p in infos):
                _error("DOCX paket bütçesi veya şifreleme uygun değil")
            parts = {p.filename: archive.read(p) for p in infos}
        if any(parts[name] != data for name, data in fixed.items()):
            _error("Taslak şablonu, damga, stil veya ilişki değiştirilmiş")
        raw = parts["word/document.xml"]
        if b"<!" in raw:
            _error("XML bildirim/genişletme yapısı kabul edilmiyor")
        document = ET.fromstring(raw)
        if document.tag != f"{{{W}}}document" or document.attrib or len(document) != 1:
            _error("DOCX gövdesi geçersiz")
        body = document[0]
        if body.tag != f"{{{W}}}body" or body.attrib or len(body) > 1501 or not len(body):
            _error("DOCX gövde sınırı geçersiz")
        if ET.tostring(body[-1]) != ET.tostring(_section()):
            _error("Her sayfadaki damga veya sayfa geometrisi değişmiş")
        paragraphs = []
        for p in list(body)[:-1]:
            if p.tag != f"{{{W}}}p" or len(p) != 2 or p[0].tag != f"{{{W}}}pPr" or len(p[0]) != 1 or p[1].tag != f"{{{W}}}r" or len(p[1]) != 1:
                _error("DOCX statik paragraf yapısı dışına çıkıyor")
            style = p[0][0].get(f"{{{W}}}val")
            text = p[1][0].text or ""
            _text(text, empty=True)
            if ET.tostring(p) != ET.tostring(_paragraph(text, style)):
                _error("DOCX gizli/etkin içerik veya doğrudan biçim içeriyor")
            paragraphs.append((style, text))
        if raw != _document(paragraphs) or sum(len(t) for _, t in paragraphs) > MAX_TEXT:
            _error("DOCX kanonik yapı veya metin sınırı geçersiz")
        if len(paragraphs) < 5 or paragraphs[0][0] != "Title" or not paragraphs[0][1].strip() or paragraphs[1] != ("Normal", PURPOSE):
            _error("Taslak başlığı veya görünür amaç uyarısı yok")
        position, source_free = 2, False
        if paragraphs[position] == ("Normal", SOURCE_FREE_NOTICE):
            source_free = True
            position += 1
        elif paragraphs[position] == ("Normal", PARTIAL_NOTICE):
            position += 1
            first_missing = position
            while position < len(paragraphs) and paragraphs[position][0] == "Normal":
                if not paragraphs[position][1].startswith("Eksik kaynak: ") or not paragraphs[position][1][14:].strip():
                    _error("Kısmi taslakta eksik kaynak adı yok")
                position += 1
            if not 1 <= position - first_missing <= 256:
                _error("Kısmi taslağın eksik kaynak listesi yok veya sınırı aşıyor")
        count = 0
        while position < len(paragraphs):
            if paragraphs[position][0] != "Heading1" or not paragraphs[position][1].strip() or position + 2 >= len(paragraphs):
                _error("Taslak bölüm yapısı eksik")
            label = paragraphs[position + 1]
            if label[0] != "Label" or label[1] not in LABELS.values():
                _error("Taslak/kullanıcı/kaynak ayrımı eksik")
            if source_free and label[1] != LABELS["DRAFT_TEXT"]:
                _error("Kaynaksız taslakta kaynak/beyan etiketi olamaz")
            style = "SourceExcerpt" if label[1] == LABELS["SOURCE_EXCERPT"] else "Normal"
            position += 2
            first = position
            while position < len(paragraphs) and paragraphs[position][0] != "Heading1":
                if paragraphs[position][0] != style:
                    _error("Bölüm türü ve metin biçimi eşleşmiyor")
                position += 1
            if position == first:
                _error("Boş taslak bölümü")
            count += 1
        if not 1 <= count <= 100:
            _error("Taslak bölümü yok veya sınır aşıldı")
    except CoreError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise CoreError("TASLAK_QA", "DOCX yapısal doğrulaması tamamlanamadı") from exc
    return {"passed": True, "checks": ["closed_static_ooxml", "no_macros_external_links_or_fields", "draft_stamp_every_page",
                                       "black_title_and_heading_styles", "a4_2cm_margins", "visible_section_provenance", "text_and_package_limits"]}


def _read_json(path, limit=8192):
    with open_verified_source(path) as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        _error("Word makbuzu sınırı aşıldı")
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise CoreError("TASLAK_QA", "Word makbuzu JSON değil") from exc


def _adapter_paths():
    source = Path(__file__).resolve()
    return source, source.parents[2] / "scripts" / "render-internal-draft.ps1"


def adapter_fingerprint():
    """Bind this exact adapter source and installed PDF/PNG library versions."""
    try:
        source, script = _adapter_paths()
        profile = {}
        for key, path in (("draft_document_py_sha256", source), ("render_ps1_sha256", script)):
            with open_verified_source(path) as stream:
                profile[key] = hashlib.file_digest(stream, "sha256").hexdigest()
        for key, package in (("pypdfium2_version", "pypdfium2"), ("Pillow_version", "Pillow")):
            version = metadata.version(package)
            if not isinstance(version, str) or not version.strip() or len(version) > 128:
                _error("Görüntüleme kitaplığı sürümü doğrulanamadı")
            profile[key] = version
        return hashlib.sha256(canonical(profile).encode("utf-8")).hexdigest()
    except CoreError:
        raise
    except (OSError, metadata.PackageNotFoundError) as exc:
        raise CoreError("TASLAK_RENDER_YOK", "Adaptör dosya/sürüm kimliği ölçülemedi") from exc


def _validate_owner(receipt, token):
    keys = {"protocol", "token", "pid", "creation_filetime", "hwnd", "owned", "exe", "version"}
    if not isinstance(receipt, dict) or set(receipt) != keys or receipt["protocol"] != 1 or receipt["token"] != token or receipt["owned"] is not True:
        _error("Word işlem sahipliği makbuzu geçersiz")
    if any(type(receipt[key]) is not int or receipt[key] <= 0 for key in ("pid", "creation_filetime", "hwnd")):
        _error("Word işlem kimliği geçersiz")
    if not isinstance(receipt["version"], str) or not re.fullmatch(r"\d+\.\d+(?:\.\d+){0,2}", receipt["version"]):
        _error("Word sürümü doğrulanamadı")
    if not isinstance(receipt["exe"], str) or not Path(receipt["exe"]).is_absolute() or Path(receipt["exe"]).name.upper() != "WINWORD.EXE":
        _error("Word çalıştırılabilir dosyası doğrulanamadı")
    return receipt


def _word_failure(qa_dir, token):
    """A closed diagnostic vocabulary; no exception message/document data."""
    path = qa_dir / "word-error.json"
    if not path.is_file():
        return "Word açma/dışa aktarma doğrulaması tamamlanamadı (NO_DIAGNOSTIC)"
    receipt = _read_json(path, limit=2048)
    stages = {"INPUT", "NATIVE_API", "ACTIVATE", "BLANK", "WINDOW", "OWNERSHIP", "OWNER_RECEIPT", "CONFIGURE",
              "HANDSHAKE", "OPEN", "PAGINATE", "EXPORT", "HASH", "CLOSE", "RESTORE", "QUIT", "RELEASE"}
    if (not isinstance(receipt, dict) or set(receipt) != {"protocol", "token", "status", "stage", "exception_type", "hresult"}
            or type(receipt["protocol"]) is not int or receipt["protocol"] != 1 or receipt["token"] != token
            or receipt["status"] != "FAILED" or not isinstance(receipt["stage"], str) or receipt["stage"] not in stages
            or not isinstance(receipt["exception_type"], str) or not re.fullmatch(r"[A-Za-z0-9_.+`]{1,160}", receipt["exception_type"])
            or type(receipt["hresult"]) is not int or not -(2 ** 31) <= receipt["hresult"] < 2 ** 31):
        _error("Word hata makbuzu kapalı teşhis şemasına uymuyor")
    return (f"Word doğrulaması tamamlanamadı ({receipt['stage']}; "
            f"{receipt['exception_type']}; HRESULT {receipt['hresult']})")


class _OwnedWord:
    """Retain a process HANDLE so a reused PID can never become a cleanup target."""
    def __init__(self, receipt, started_filetime):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.handle = ctypes, None
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel = self.kernel
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = kernel.OpenProcess(0x1000 | 0x0001 | 0x00100000 | 0x0400 | 0x0010, False, receipt["pid"])
        if not handle:
            _error("Word işlem nesnesi açılamadı")
        try:
            created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
            buffer, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)) or not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                _error("Word işlem nesnesi doğrulanamadı")
            creation = (created.dwHighDateTime << 32) | created.dwLowDateTime
            if creation != receipt["creation_filetime"] or creation < started_filetime or os.path.normcase(buffer.value) != os.path.normcase(receipt["exe"]):
                _error("Word işlem sahipliği veya oluşturulma zamanı uyuşmuyor")
            self.exe_path = Path(buffer.value)
            self.handle = handle
        finally:
            if self.handle is None:
                kernel.CloseHandle(handle)

    def memory(self):
        from ctypes import wintypes
        ctypes = self.ctypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
                        ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                         "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        api = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        api.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not api(self.handle, ctypes.byref(counters), counters.cb):
            if self.kernel.WaitForSingleObject(self.handle, 0) == 0:
                return 0
            _error("Word bellek bütçesi ölçülemedi")
        return max(counters.WorkingSetSize, counters.PagefileUsage)

    def close(self):
        if self.handle is not None:
            # Only this retained, creation-time-verified object; never process-name kill.
            if self.kernel.WaitForSingleObject(self.handle, 0) == 258:
                self.kernel.TerminateProcess(self.handle, 1)
                self.kernel.WaitForSingleObject(self.handle, 2000)
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def _run_word(docx_path, qa_dir):
    if os.name != "nt":
        _error("Yerel Word doğrulaması yalnız Windows üzerinde kullanılabilir", "TASLAK_RENDER_YOK")
    script = Path(__file__).resolve().parents[2] / "scripts" / "render-internal-draft.ps1"
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    if not script.is_file() or not powershell.is_file():
        _error("Sabit Word doğrulama adaptörü bulunamadı", "TASLAK_RENDER_YOK")
    token = uuid.uuid4().hex
    owner_path, receipt_path = qa_dir / "word-owner.json", qa_dir / "word-render.json"
    go_path, pdf_path = qa_dir / "word-continue.json", qa_dir / "document.pdf"
    if any(p.exists() for p in (owner_path, receipt_path, go_path, pdf_path, qa_dir / "word-error.json")):
        _error("Word doğrulama hedefleri yeni ve boş olmalı")
    command = [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(script), "-DocxPath", str(docx_path), "-QaDirectory", str(qa_dir), "-Token", token]
    # UTC FILETIME, captured before COM activation. A pre-existing instance is never owned.
    started_filetime = (time.time_ns() // 100) + 116444736000000000
    started, owned = time.monotonic(), None
    held = ExitStack()
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        while True:
            if owned is None and owner_path.exists():
                receipt = _validate_owner(_read_json(owner_path), token)
                owned = _OwnedWord(receipt, started_filetime)
                # The path comes from the retained process object, not just child JSON.
                # Deny write/delete sharing until export and receipt validation finish.
                exe_stream = held.enter_context(open_verified_source(owned.exe_path))
                exe_before = hashlib.file_digest(exe_stream, "sha256").hexdigest()
                go_temp = go_path.with_suffix(".writing")
                with go_temp.open("x", encoding="ascii") as stream:
                    json.dump({"token": token}, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                go_temp.rename(go_path)
            if owned is not None and owned.memory() > MAX_WORD_MEMORY:
                _error("Word bellek bütçesi aşıldı", "TASLAK_SINIRI")
            if pdf_path.exists() and pdf_path.stat().st_size > MAX_PDF:
                _error("Word PDF boyut sınırı aşıldı", "TASLAK_SINIRI")
            returncode = process.poll()
            if returncode is not None:
                break
            if time.monotonic() - started > MAX_RENDER_SECONDS:
                _error("Word doğrulaması 60 saniye içinde tamamlanamadı", "TASLAK_RENDER_ZAMAN")
            time.sleep(0.05)
        if returncode != 0 or owned is None or not receipt_path.is_file():
            _error(_word_failure(qa_dir, token), "TASLAK_RENDER_YOK")
        result = _read_json(receipt_path)
        expected = {"protocol", "token", "status", "pid", "creation_filetime", "version", "page_count", "pdf_sha256", "exe_sha256", "options_restored"}
        if (not isinstance(result, dict) or set(result) != expected or result["protocol"] != 1 or result["token"] != token
                or result["status"] != "EXPORTED" or result["pid"] != receipt["pid"]
                or result["options_restored"] is not True
                or result["creation_filetime"] != receipt["creation_filetime"] or result["version"] != receipt["version"]
                or type(result["page_count"]) is not int or not 1 <= result["page_count"] <= MAX_PAGES
                or not isinstance(result["pdf_sha256"], str) or not re.fullmatch("[0-9a-f]{64}", result["pdf_sha256"])
                or not isinstance(result["exe_sha256"], str) or not re.fullmatch("[0-9a-f]{64}", result["exe_sha256"])):
            _error("Word dışa aktarma makbuzu geçersiz")
        exe_stream.seek(0)
        exe_after = hashlib.file_digest(exe_stream, "sha256").hexdigest()
        if result["exe_sha256"] != exe_before or exe_after != exe_before:
            _error("Word çalıştırılabilir dosyası makbuzla veya başlangıç kimliğiyle eşleşmiyor")
        return result
    finally:
        try:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        finally:
            try:
                if owned is not None:
                    owned.close()
            finally:
                held.close()


def _render_pdf(pdf_path, qa_dir, expected_count):
    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError as exc:
        raise CoreError("TASLAK_RENDER_YOK", "PDF sayfa doğrulama bağımlılıkları bulunamadı") from exc
    with open_verified_source(pdf_path) as stream:
        pdf_bytes = stream.read(MAX_PDF + 1)
    if not 0 < len(pdf_bytes) <= MAX_PDF or not pdf_bytes.startswith(b"%PDF-"):
        _error("PDF türü veya boyutu geçersiz", "TASLAK_SINIRI")
    pages, total = [], 0
    try:
        with pdfium.PdfDocument(pdf_bytes) as document:
            if not 1 <= len(document) <= MAX_PAGES or len(document) != expected_count:
                _error("Word ve PDF sayfa sayısı eşleşmiyor veya sınır aşıldı", "TASLAK_SINIRI")
            for index in range(len(document)):
                page = document[index]
                try:
                    width, height = page.get_size()
                    scale = 1.5  # 108 dpi: A4 is approximately 893 x 1263 pixels.
                    if not all(math.isfinite(v) and 0 < v <= 2000 for v in (width, height)) or math.ceil(width * scale) * math.ceil(height * scale) > MAX_PIXELS:
                        _error("PDF sayfa piksel sınırı aşıldı", "TASLAK_SINIRI")
                    bitmap = page.render(scale=scale)
                    try:
                        pil = bitmap.to_pil()
                        with io.BytesIO() as buffer:
                            pil.save(buffer, format="PNG")
                            data = buffer.getvalue()
                        pil.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                total += len(data)
                if len(data) > MAX_PNG or total > MAX_TOTAL_PNG:
                    _error("PNG görüntü bütçesi aşıldı", "TASLAK_SINIRI")
                # Validate the actual encoded image, not only the renderer's dimensions.
                with Image.open(io.BytesIO(data)) as check:
                    if check.format != "PNG" or check.width * check.height > MAX_PIXELS:
                        _error("PNG biçimi veya boyutu geçersiz")
                    check.verify()
                path = qa_dir / f"page-{index + 1:03d}.png"
                with path.open("xb") as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                pages.append({"page": index + 1, "path": str(path), "sha256": hashlib.sha256(data).hexdigest()})
    except CoreError:
        raise
    except Exception as exc:
        raise CoreError("TASLAK_QA", "PDF bütün sayfalarıyla görüntülenemedi") from exc
    return pages


def render_docx(docx_path, qa_dir):
    """Render only verified static DOCX; return evidence, never visual acceptance."""
    docx_path, qa_dir = Path(docx_path), Path(qa_dir)
    if not docx_path.is_absolute() or not qa_dir.is_absolute() or docx_path.suffix.lower() != ".docx":
        _error("Word doğrulaması mutlak DOCX/QA yolları gerektirir")
    qa_dir.mkdir(parents=True, exist_ok=True)
    if qa_dir.is_symlink() or not qa_dir.is_dir():
        _error("QA klasörü normal bir dizin olmalı")
    try:
        adapter_sha256 = adapter_fingerprint()
        # Keep write/delete sharing denied while Word opens read-only and exports.
        with open_verified_source(docx_path) as stream:
            data = stream.read(MAX_DOCX + 1)
            structural_qa(data)
            before = hashlib.sha256(data).hexdigest()
            receipt = _run_word(docx_path, qa_dir)
            stream.seek(0)
            if hashlib.sha256(stream.read(MAX_DOCX + 1)).hexdigest() != before:
                _error("Word doğrulama sırasında DOCX baytları değişti")
        pdf_path = qa_dir / "document.pdf"
        with open_verified_source(pdf_path) as stream:
            data = stream.read(MAX_PDF + 1)
        if not data or len(data) > MAX_PDF or hashlib.sha256(data).hexdigest() != receipt["pdf_sha256"]:
            _error("PDF baytları Word makbuzuyla eşleşmiyor")
        pages = _render_pdf(pdf_path, qa_dir, receipt["page_count"])
        if adapter_fingerprint() != adapter_sha256:
            _error("Doğrulama sırasında Word/PDF adaptör kimliği değişti")
        return {"renderer": {"name": "Microsoft Word COM", "version": receipt["version"],
                             "exe_sha256": receipt["exe_sha256"], "adapter_sha256": adapter_sha256},
                "pdf": {"path": str(pdf_path), "sha256": receipt["pdf_sha256"]}, "pages": pages}
    except CoreError:
        raise
    except Exception as exc:
        raise CoreError("TASLAK_RENDER_YOK", "Yerel Word doğrulaması güvenle tamamlanamadı") from exc
