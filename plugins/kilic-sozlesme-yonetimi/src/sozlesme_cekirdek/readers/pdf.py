"""PDF text/page inventory with bounded render requests; no implicit OCR."""
import io
import re
import zlib
from pypdf import PdfReader
from pypdf.generic import ArrayObject, EncodedStreamObject
import pypdfium2 as pdfium
from ..errors import CoreError
from .common import feature, issue, locator, result_base, unit

MAX_PDF = 16 * 1024 * 1024
MAX_STREAM = 8 * 1024 * 1024


def safe_content(page):
    content = page.get("/Contents")
    content = content.get_object() if content is not None else None
    streams = content if isinstance(content, ArrayObject) else [] if content is None else [content]
    total = 0
    for ref in streams:
        stream = ref.get_object()
        raw = getattr(stream, "_data", b"")
        filters = stream.get("/Filter")
        if isinstance(stream, EncodedStreamObject) and filters:
            if str(filters) != "/FlateDecode":
                return False
            decoder = zlib.decompressobj()
            try:
                decoded = decoder.decompress(raw, MAX_STREAM + 1)
            except zlib.error:
                return False
            if len(decoded) > MAX_STREAM or decoder.unconsumed_tail or not decoder.eof:
                raise CoreError("BELGE_SINIRI", "PDF içerik stream açılım sınırı aşıldı")
            total += len(decoded)
        else:
            total += len(raw)
        if total > MAX_STREAM:
            raise CoreError("BELGE_SINIRI", "PDF sayfa içerik sınırı aşıldı")
    return True


def read_pdf(data):
    if len(data) > MAX_PDF or not data.startswith(b"%PDF-"):
        raise CoreError("DOSYA_TURU", "PDF türü/boyut sınırı uygun değil")
    report = result_base(data, "PDF", "pdf-text-inventory", ["pypdf", "pypdfium2"])
    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise CoreError("SIFRELI_BELGE", "Şifreli PDF desteklenmiyor; parola kırma yapılmadı")
        if len(reader.pages) > 100:
            raise CoreError("BELGE_SINIRI", "P2 PDF sayfa sınırı 100")
        feature(report, "pages", len(reader.pages), "TESTED")
        fields = reader.get_fields() or {}
        feature(report, "form_fields", len(fields), "PARTIAL")
        signatures = sum(str(v.get("/FT")) == "/Sig" for v in fields.values())
        feature(report, "signature_fields", signatures, "PARTIAL", "Kriptografik güven/yetki doğrulaması NOT_RUN")
        secondary = pdfium.PdfDocument(data)
        try:
            for index, page in enumerate(reader.pages):
                location = locator(page=index + 1, path="page:" + str(index + 1))
                if not safe_content(page):
                    text = ""
                    issue(report, "UNSUPPORTED_PDF_FILTER", "İçerik filtresi desteklenmiyor; metin çıkarmaya zorlanmadı",
                          location, "BLOCKING")
                else:
                    text = page.extract_text() or ""
                unit(report, "PDF_PAGE", location, text, display=text)
                pdf_page = secondary[index]
                text_page = None
                try:
                    text_page = pdf_page.get_textpage()
                    secondary_text = text_page.get_text_range()
                    normalize = lambda s: re.sub(r"\s+", "", s)
                    if normalize(text) != normalize(secondary_text):
                        issue(report, "SECONDARY_READER_DISAGREEMENT", "Aynı text layer'daki okuyucu çıktıları farklı",
                              location, "BLOCKING")
                finally:
                    if text_page is not None:
                        text_page.close()
                    pdf_page.close()
                feature(report, "annotations:page:" + str(index + 1), len(page.get("/Annots", [])), "PARTIAL")
                dereference = lambda value: value.get_object() if hasattr(value, "get_object") else value
                resources = dereference(page.get("/Resources", {}))
                xobjects = dereference(resources.get("/XObject", {}))
                images = sum(str(ref.get_object().get("/Subtype")) == "/Image" for ref in xobjects.values())
                feature(report, "direct_images:page:" + str(index + 1), images, "PARTIAL",
                        "Form XObject içindeki resimler ayrıca doğrulanmalı")
                if len(text.strip()) < 20:
                    issue(report, "LOW_TEXT_OR_SCAN", "Düşük metin/tarama adayı; render ve gerekirse OCR gerekli",
                          location, "BLOCKING")
                if re.search(r"%|₺|\b(?:TL|EUR|USD)\b|\d+[.,]\d+|\d{2}[./]\d{2}[./]\d{4}", text):
                    issue(report, "CRITICAL_VALUE_RENDER_REQUIRED", "Tutar/oran/tarih adayı kaynak görüntüsünde doğrulanmalı",
                          location, "BLOCKING")
            root = reader.trailer["/Root"]
            names = dereference(root.get("/Names", {}))
            if "/OpenAction" in root or "/AA" in root or "/JavaScript" in names:
                issue(report, "PDF_ACTIVE_ACTION", "PDF eylemleri çalıştırılmadı", severity="BLOCKING")
            if "/EmbeddedFiles" in names:
                issue(report, "PDF_ATTACHMENTS", "Ekler tespit edildi; içerikleri ayrıca okunmalı", severity="BLOCKING")
        finally:
            secondary.close()
    except CoreError:
        raise
    except Exception as exc:
        raise CoreError("BELGE_BOZUK", "PDF okuma başarısız: " + type(exc).__name__) from exc
    report["verification"]["methods"] = ["SOURCE_HASH", "PYPDF_PAGE_TEXT", "PDFIUM_SAME_TEXT_LAYER_CROSS_CHECK"]
    report["fallback"]["performed"].append("SECONDARY_SAME_TEXT_LAYER")
    report["fallback"]["next"] = ["TARGETED_PAGE_RENDER", "VISUAL_SOURCE_CHECK", "OCR_ONLY_IF_NEEDED"]
    return report


def render_pdf_page(data, page_number):
    if (not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1
            or len(data) > MAX_PDF or not data.startswith(b"%PDF-")):
        raise CoreError("GECERSIZ_GIRDI", "PDF sayfa/boyut parametresi uygun değil")
    doc = pdfium.PdfDocument(data)
    page = bitmap = None
    try:
        if page_number > len(doc) or len(doc) > 100:
            raise CoreError("GECERSIZ_GIRDI", "PDF sayfa numarası kapsam dışında")
        page = doc[page_number - 1]
        width, height = page.get_size()
        if width <= 0 or height <= 0:
            raise CoreError("BELGE_BOZUK", "PDF sayfa boyutu uygun değil")
        scale = min(1.5, 2000 / max(width, height))
        bitmap = page.render(scale=scale)
        output = io.BytesIO()
        bitmap.to_pil().save(output, format="PNG")
        return output.getvalue()
    finally:
        if bitmap is not None:
            bitmap.close()
        if page is not None:
            page.close()
        doc.close()
