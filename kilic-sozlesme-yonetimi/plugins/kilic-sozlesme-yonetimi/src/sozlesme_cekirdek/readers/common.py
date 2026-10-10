"""Bounded, read-only package inspection. This is not an OS security boundary."""
from __future__ import annotations
import hashlib
import io
import posixpath
from urllib.parse import unquote, urlsplit
import zipfile

from lxml import etree
from ..errors import CoreError

REL = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_BYTES = 64 * 1024 * 1024
MAX_PART = 8 * 1024 * 1024
MAX_NODES = 200_000


def locator(part="", path="", *, page=None, sheet=None, cell=None):
    return {"part": part, "path": path, "page": page, "sheet": sheet, "cell": cell}


def issue(report, code, message, location=None, severity="WARNING"):
    report["issues"].append({"code": code, "message": message, "locator": location,
                             "severity": severity})


def feature(report, name, count, status="PARTIAL", note=""):
    report["inventory"].append({"feature": name, "count": count, "status": status, "note": note})


def result_base(data, kind, name, dependencies):
    import importlib.metadata
    return {"schema_version": "2.0", "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data), "format": kind, "trust": "UNTRUSTED_DATA",
            "reader": {"name": name, "version": "1.0",
                       "dependencies": [{"name": p, "version": importlib.metadata.version(p)}
                                        for p in dependencies]},
            "units": [], "inventory": [], "parts": [], "relationships": [], "revisions": [],
            "issues": [], "verification": {
                "status": "PARTIAL", "integrity": "PASS", "coverage": "PARTIAL",
                "source_fidelity": "PARTIAL", "semantic": "NOT_RUN", "visual": "NOT_RUN",
                "critical_analysis_allowed": False, "revision_acceptance": False,
                "methods": [], "stop_reason": "ADDITIONAL_SOURCE_VERIFICATION_REQUIRED"},
            "fallback": {"performed": ["PRIMARY_DETERMINISTIC"], "next": [], "ocr_calls": 0}}


def unit(report, kind, location, raw, before=None, after=None, display=None, attributes=None):
    identity = repr(sorted(location.items())).encode("utf-8")
    uid = hashlib.sha256(report["sha256"].encode("ascii") + identity).hexdigest()
    row = {"unit_id": uid, "kind": kind, "locator": location,
           "views": {"RAW": raw, "BEFORE": before, "AFTER": after, "DISPLAY": display},
           "attributes": [{"key": str(k), "value": str(v)} for k, v in (attributes or {}).items()]}
    report["units"].append(row)
    return row


def xml(data):
    if len(data) > MAX_PART:
        raise CoreError("PAKET_SINIRI", "XML parçası boyut sınırını aştı")
    try:
        parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                                 huge_tree=False, recover=False)
        root = etree.fromstring(data, parser)
        if root.getroottree().docinfo.doctype or any(isinstance(x, etree._Entity) for x in root.iter()):
            raise CoreError("XML_DTD_YASAK", "DTD/entity içeren kaynak okunmadı")
        if sum(1 for _ in root.iter()) > MAX_NODES:
            raise CoreError("PAKET_SINIRI", "XML düğüm sınırı aşıldı")
        return root
    except etree.XMLSyntaxError as exc:
        raise CoreError("BELGE_BOZUK", "XML yapısı geçersiz") from exc


class Package:
    def __init__(self, data):
        if len(data) > MAX_BYTES:
            raise CoreError("PAKET_SINIRI", "P2 paket sınırı 64 MiB")
        self.parts = {}
        self.roots = {}
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 1024 or sum(x.file_size for x in entries) > MAX_BYTES:
                    raise CoreError("PAKET_SINIRI", "Paket parça/toplam boyut sınırı aşıldı")
                seen = set()
                for item in entries:
                    name = item.filename
                    if (not name or "\\" in name or ":" in name or name.startswith("/")
                            or any(x in {"", ".", ".."} for x in name.rstrip("/").split("/"))):
                        raise CoreError("PAKET_YOLU", "Geçersiz paket parçası yolu")
                    if name.casefold() in seen:
                        raise CoreError("PAKET_YINELENEN", "Yinelenen paket parçası")
                    seen.add(name.casefold())
                    if item.flag_bits & 1 or (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise CoreError("PAKET_YASAK", "Şifreli/symlink paket parçası")
                    if item.file_size > MAX_PART or item.file_size > max(item.compress_size, 1) * 200:
                        raise CoreError("PAKET_SINIRI", "Paket parçası açılım sınırı aşıldı")
                    if item.is_dir():
                        continue
                    self.parts[name] = archive.read(item)  # CRC checked, never extracted.
                    if name.lower().endswith((".xml", ".rels")):
                        self.roots[name] = xml(self.parts[name])
                    if name.lower().endswith(("vbaproject.bin", ".exe", ".dll")):
                        raise CoreError("AKTIF_ICERIK", "Aktif paket içeriği desteklenmiyor")
        except CoreError:
            raise
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
            raise CoreError("BELGE_BOZUK", "ZIP/CRC veya sıkıştırma biçimi geçersiz") from exc
        if "[Content_Types].xml" not in self.roots or "_rels/.rels" not in self.roots:
            raise CoreError("DOSYA_TURU", "Geçerli OOXML paket yapısı yok")
        self.relationships = []
        for name, root in self.roots.items():
            if not name.endswith(".rels"):
                continue
            if root.tag != "{" + REL + "}Relationships":
                raise CoreError("BELGE_BOZUK", "İlişki XML namespace geçersiz")
            source = "" if name == "_rels/.rels" else posixpath.join(
                posixpath.dirname(posixpath.dirname(name)), posixpath.basename(name)[:-5])
            ids = set()
            for rel in root:
                rid, target, typ = (rel.get(k) for k in ("Id", "Target", "Type"))
                if not rid or not target or not typ or rid in ids:
                    raise CoreError("BELGE_BOZUK", "İlişki kimliği/hedefi geçersiz")
                ids.add(rid)
                external = rel.get("TargetMode") == "External"
                resolved = None if external else self.resolve(source, target)
                if resolved is not None and resolved not in self.parts:
                    raise CoreError("ILISKI_EKSIK", "İlişki hedefi pakette yok")
                self.relationships.append({"source": source, "id": rid, "type": typ,
                                           "target": target, "external": external,
                                           "resolved_part": resolved})

    @staticmethod
    def resolve(source, target):
        value = unquote(target)
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or "\\" in value or ":" in value:
            raise CoreError("PAKET_YOLU", "İç ilişki paket dışına çıkamaz")
        path = posixpath.normpath(parsed.path[1:] if parsed.path.startswith("/") else
                                 posixpath.join(posixpath.dirname(source), parsed.path))
        if path.startswith(("../", "/")) or path in {"..", "."}:
            raise CoreError("PAKET_YOLU", "İç ilişki paket dışına çıkamaz")
        return path

    def main(self, family):
        roots = [r for r in self.relationships if r["source"] == ""
                 and r["type"].endswith("/officeDocument") and not r["external"]]
        if len(roots) != 1 or roots[0]["resolved_part"] not in self.roots:
            raise CoreError("DOSYA_TURU", "Tek ana belge ilişkisi gerekli")
        name = roots[0]["resolved_part"]
        overrides = self.roots["[Content_Types].xml"]
        content_type = next((x.get("ContentType", "") for x in overrides
                             if x.get("PartName") == "/" + name), "")
        expected = {"DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"}
        if content_type != expected[family]:
            raise CoreError("DOSYA_TURU", "Gerçek ana parça türü istenen belge türü değil")
        return name

    def describe(self, report):
        report["parts"] = [{"name": n, "sha256": hashlib.sha256(b).hexdigest(),
                            "size_bytes": len(b)} for n, b in sorted(self.parts.items())]
        report["relationships"] = self.relationships
        for rel in self.relationships:
            if rel["external"]:
                issue(report, "EXTERNAL_RELATIONSHIP", "Dış ilişki envanterlendi; hedef açılmadı",
                      locator(rel["source"], rel["id"]))
