from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

from common import (
    PARSER_VERSION,
    SCHEMA_VERSION,
    clean_text,
    dump_json,
    iter_source_files,
    json_text,
    sha256_bytes,
    sha256_file,
    stable_id,
    utc_now,
)
from db import connect, init_db, set_state
from adapters import csv_adapter, docx_adapter, eml_adapter, image_adapter, pdf_adapter, text_adapter, xlsx_adapter
from adapters import archive_adapter, msg_adapter, office_legacy_adapter
from adapters.base import ParseResult, Unit, unsupported

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff"}
TEXT_EXTS = {".txt", ".md", ".rtf"}
CSV_EXTS = {".csv", ".tsv"}
ARCHIVE_EXTS = {".zip"}

ROLE_SIGNALS = {
    "specification": ["teknik sartname", "technical specification", "spesifikasyon", "technical spec"],
    "offer": ["fiyat teklifi", "teklif mektubu", "quotation", "offer no", "quote no", "birim fiyat", "unit price"],
    "boq": ["poz no", "metraj", "boq", "kesif", "bill of quantities"],
    "correspondence": ["subject:", "from:", "message-id:"],
    "support": ["certificate", "sertifika", "iso 9001", "ce declaration", "kapasite raporu"],
}


def _ascii_fold(text: str) -> str:
    table = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"})
    return text.translate(table).casefold()


def normalize_supplier_name(display: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _ascii_fold(display)).strip()


def detect_format(path: Path) -> tuple[str, str | None]:
    ext = path.suffix.lower()
    try:
        head = path.read_bytes()[:32]
    except Exception:
        head = b""
    mime = mimetypes.guess_type(path.name)[0]
    if head.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "image", "image/tiff"
    if head.startswith(b"\xd0\xcf\x11\xe0"):
        if ext == ".xls":
            return "xls", "application/vnd.ms-excel"
        if ext == ".doc":
            return "doc", "application/msword"
        if ext == ".msg":
            return "msg", "application/vnd.ms-outlook"
        return "ole", mime
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            if any(n.startswith("xl/") for n in names):
                return "xlsx", mime or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if any(n.startswith("word/") for n in names):
                return "docx", mime or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            return "zip", "application/zip"
        except Exception:
            return "zip", "application/zip"
    if ext in IMAGE_EXTS:
        return "image", mime
    if ext in CSV_EXTS:
        return "csv", mime or "text/csv"
    if ext == ".eml":
        return "eml", mime or "message/rfc822"
    if ext == ".msg":
        return "msg", mime or "application/vnd.ms-outlook"
    if ext in TEXT_EXTS:
        return "text", mime or "text/plain"
    if ext in {".xlsx", ".xlsm"}:
        return "xlsx", mime
    if ext == ".xls":
        return "xls", mime
    if ext == ".docx":
        return "docx", mime
    if ext == ".doc":
        return "doc", mime
    if ext == ".pdf":
        return "pdf", mime
    if ext in ARCHIVE_EXTS:
        return "zip", mime or "application/zip"
    return ext.lstrip(".") or "unknown", mime


def parse_by_format(path: Path, fmt: str) -> ParseResult:
    if fmt == "pdf":
        return pdf_adapter.parse(path)
    if fmt == "xlsx":
        return xlsx_adapter.parse(path)
    if fmt == "xls":
        return office_legacy_adapter.parse_xls(path)
    if fmt == "csv":
        return csv_adapter.parse(path)
    if fmt == "docx":
        return docx_adapter.parse(path)
    if fmt == "doc":
        return office_legacy_adapter.parse_doc(path)
    if fmt == "image":
        return image_adapter.parse(path)
    if fmt == "eml":
        return eml_adapter.parse(path)
    if fmt == "msg":
        return msg_adapter.parse(path)
    if fmt == "text":
        return text_adapter.parse(path)
    if fmt == "zip":
        return ParseResult("zipfile", "partial", [], ["Archive container; members are extracted safely and routed separately."])
    return unsupported(path, f"Unsupported format: {fmt}")


# A filename word is a weak but real signal; it breaks ties against incidental
# body text (an offer that mentions its certificates must stay an offer).
FILENAME_ROLE_SIGNALS = {
    "offer": ["teklif", "quotation", "quote", "offer", "proposal"],
    "specification": ["sartname", "specification"],
}


def role_candidate(text: str, filename: str) -> tuple[str, float]:
    sample = _ascii_fold(f"{filename}\n{text[:8000]}")
    name = re.sub(r"[^a-z0-9]+", " ", _ascii_fold(Path(filename).stem))
    scores: dict[str, int] = {}
    for role, signals in ROLE_SIGNALS.items():
        scores[role] = sum(1 for s in signals if _ascii_fold(s) in sample)
    for role, words in FILENAME_ROLE_SIGNALS.items():
        if any(re.search(rf"\b{w}\b", name) for w in words):
            scores[role] = scores.get(role, 0) + 2
    best = max(scores, key=scores.get)
    score = scores[best]
    if score == 0:
        return "unknown", 0.0
    return best, min(1.0, 0.45 + score * 0.2)


def revision_candidate(filename: str, text: str) -> str | None:
    sample = _ascii_fold(f"{filename} {text[:2500]}")
    # ASCII-only revision code after rev/revizyon/revision (also "_rev01"). Without
    # re.ASCII, case-insensitive matching let "REVİZE" (revised) yield the label "İZE".
    m = re.search(r"(?<![A-Za-z])(?:rev(?:izyon|ize)?|revision)[\s._:-]*(?:no[.:]?\s*)?([A-Za-z]?\d{1,3})(?![A-Za-z0-9])", sample, re.IGNORECASE | re.ASCII)
    return m.group(1) if m else None


def supplier_candidate(filename: str, text: str) -> tuple[str, str, float]:
    # Anchored supplier labels require source line boundaries; collapse spaces within each line only.
    sample = "\n".join(clean_text(line) for line in text[:4000].splitlines())
    patterns = [
        r"(?im)^\s*([A-Z0-9][A-Za-z0-9 .&'\-]{2,80}\b(?:A\.?S\.?|AS|LTD\.?\s*STI\.?|LIMITED|INC\.?|LLC))\b",
        r"(?im)^\s*(?:firma|company|supplier|vendor)\s*[:\-]\s*([^\n]{2,100})",
    ]
    for pat in patterns:
        m = re.search(pat, sample)
        if m:
            display = clean_text(m.group(1))
            normalized = re.sub(r"[^a-z0-9]+", " ", _ascii_fold(display)).strip()
            return display, normalized, 0.9
    stem = Path(filename).stem
    cleaned = re.sub(r"(?i)\b(teklif|quotation|quote|offer|rev(?:izyon)?|revision|fiyat|proposal)\b", " ", stem)
    cleaned = re.sub(r"[_\-.]+", " ", cleaned)
    cleaned = re.sub(r"\b20\d{2}[01]\d[0-3]\d\b|\b\d{4}-\d{2}-\d{2}\b", " ", cleaned)
    cleaned = clean_text(cleaned)
    if len(cleaned) >= 2:
        normalized = re.sub(r"[^a-z0-9]+", " ", _ascii_fold(cleaned)).strip()
        return cleaned, normalized, 0.45
    fallback = stem or "unknown supplier"
    normalized = re.sub(r"[^a-z0-9]+", " ", _ascii_fold(fallback)).strip()
    return fallback, normalized, 0.2


def _cache_key(source_sha: str, fmt: str) -> str:
    return stable_id("cache", source_sha, fmt, PARSER_VERSION, SCHEMA_VERSION)


def _parse_from_cache(run_root: Path, source_sha: str, fmt: str) -> ParseResult | None:
    con = connect(run_root)
    try:
        row = con.execute("SELECT result_json FROM cache_index WHERE cache_key=?", [_cache_key(source_sha, fmt)]).fetchone()
        if not row:
            return None
        obj = json.loads(row[0])
        # Environment failures are retried after dependencies recover. Their
        # old cache record remains audit evidence but is not a successful parse.
        if obj.get("status") == "unreadable":
            return None
        units = [Unit(x["unit_type"], x["unit_index"], x["locator"], x.get("text", ""), x.get("structured", {})) for x in obj.get("units", [])]
        return ParseResult(obj["parser_name"], obj["status"], units, obj.get("notes", []), obj.get("metadata", {}))
    finally:
        con.close()


def ingest_file(
    path: Path,
    source_root: Path,
    run_root: Path,
    parent_document_id: str | None = None,
    rel_override: str | None = None,
    use_cache: bool = True,
    folder_mappings: dict[str, str] | None = None,
) -> dict[str, Any]:
    fmt, mime = detect_format(path)
    source_sha = sha256_file(path)
    archive_dir = run_root / "source_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived = archive_dir / f"{source_sha}{path.suffix.lower()}"
    if not archived.exists():
        shutil.copyfile(path, archived)
    if sha256_file(archived) != source_sha:
        raise ValueError(f"Archived source hash mismatch for {path}")
    if rel_override is not None:
        rel = rel_override
    else:
        try:
            rel = str(path.resolve().relative_to(source_root.resolve())) if source_root.is_dir() else path.name
        except Exception:
            rel = path.name
    document_id = stable_id("doc", rel, source_sha)
    parsed = _parse_from_cache(run_root, source_sha, fmt) if use_cache else None
    cache_hit = parsed is not None
    if parsed is None:
        parsed = parse_by_format(path, fmt)
    sample_text = "\n".join(u.text for u in parsed.units[:8])
    role, role_confidence = role_candidate(sample_text, path.name)
    if fmt == "zip":
        # The archive is provenance for its separately ingested members, never
        # an additional commercial offer to price or rank.
        role, role_confidence = "support", 1.0
    revision = revision_candidate(path.name, sample_text)
    supplier_name, supplier_norm, supplier_conf = supplier_candidate(path.name, sample_text)
    declared_supplier = None
    if role == "offer" and folder_mappings:
        normalized_rel = rel.replace("\\", "/")
        matches = [folder for folder in folder_mappings
                   if normalized_rel.startswith(folder.strip("/") + "/")]
        if matches:
            declared_supplier = folder_mappings[max(matches, key=lambda folder: len(folder.strip("/")))]
            supplier_name = declared_supplier
            supplier_norm = normalize_supplier_name(declared_supplier)
            supplier_conf = 0.8
    supplier_id = None
    offer_id = None
    if role in {"offer", "support", "correspondence", "unknown"} and supplier_conf >= 0.2:
        supplier_id = stable_id("sup", supplier_norm or supplier_name, length=16)
        if role == "offer":
            # Separate formal sources until package/revision authority is explicitly resolved.
            offer_id = stable_id("off", document_id, length=18)
    record = {
        "document_id": document_id,
        "parent_document_id": parent_document_id,
        "relative_path": rel,
        "source_path": str(path.resolve()),
        "filename": path.name,
        "extension": path.suffix.lower(),
        "mime_type": mime,
        "format_family": fmt,
        "document_role": role,
        "role_confidence": role_confidence,
        "supplier_id": supplier_id,
        "supplier_name": supplier_name if supplier_id else None,
        "supplier_confidence": supplier_conf,
        "_supplier_user_declared": bool(declared_supplier),
        "offer_id": offer_id,
        "revision_label": revision,
        "revision_status": "unknown" if revision else None,
        "sha256": source_sha,
        "size_bytes": path.stat().st_size,
        "parser_name": parsed.parser_name,
        "parser_version": PARSER_VERSION,
        "parse_status": parsed.status,
        "parse_notes": "; ".join(parsed.notes),
        "source_mtime": path.stat().st_mtime,
        "units": parsed.units,
        "_parser_metadata": parsed.metadata,
        "metadata": {**parsed.metadata, "cache_hit": cache_hit, "archived_source_path": str(archived.relative_to(run_root))},
    }
    return record


def write_to_db(run_root: Path, record: dict[str, Any]) -> None:
    con = connect(run_root)
    try:
        con.execute(
            """
            INSERT OR REPLACE INTO documents(
              document_id,parent_document_id,relative_path,source_path,filename,extension,mime_type,format_family,
              document_role,role_confidence,supplier_id,offer_id,revision_label,revision_status,sha256,size_bytes,
              parser_name,parser_version,parse_status,parse_notes,source_mtime,metadata_json,active
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                record["document_id"], record.get("parent_document_id"), record["relative_path"], record.get("source_path"),
                record["filename"], record["extension"], record["mime_type"], record["format_family"],
                record["document_role"], record.get("role_confidence"), record.get("supplier_id"), record.get("offer_id"),
                record.get("revision_label"), record.get("revision_status"), record["sha256"], record["size_bytes"],
                record["parser_name"], record["parser_version"], record["parse_status"], record["parse_notes"],
                record["source_mtime"], json_text(record.get("metadata", {})), record.get("active", True),
            ],
        )
        if record.get("supplier_id") and record.get("active", True):
            con.execute(
                "INSERT OR IGNORE INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES (?,?,?,?)",
                [record["supplier_id"], record.get("supplier_name") or record["supplier_id"], normalize_supplier_name(record.get("supplier_name") or ""), "user_declared" if record.get("_supplier_user_declared") else ("confirmed" if (record.get("supplier_confidence") or 0) >= 0.8 else "provisional")],
            )
        if record.get("offer_id") and record.get("active", True):
            con.execute(
                "INSERT OR IGNORE INTO offers(offer_id,supplier_id,display_name,revision_label,status,source_document_ids_json) VALUES (?,?,?,?,?,?)",
                [record["offer_id"], record["supplier_id"], record.get("supplier_name"), record.get("revision_label"), "active", json_text([record["document_id"]])],
            )
            row = con.execute("SELECT source_document_ids_json FROM offers WHERE offer_id=?", [record["offer_id"]]).fetchone()
            try:
                ids = json.loads(row[0]) if row and row[0] else []
            except Exception:
                ids = []
            if record["document_id"] not in ids:
                ids.append(record["document_id"])
                con.execute("UPDATE offers SET source_document_ids_json=? WHERE offer_id=?", [json_text(ids), record["offer_id"]])
        con.execute("DELETE FROM document_units WHERE document_id=?", [record["document_id"]])
        for unit in record["units"]:
            payload = unit.as_dict()
            content_hash = sha256_bytes((payload["text"] + json_text(payload["structured"])).encode("utf-8"))
            unit_id = stable_id("unit", record["document_id"], str(payload["unit_type"]), str(payload["unit_index"]), content_hash)
            con.execute(
                "INSERT INTO document_units(unit_id,document_id,unit_type,unit_index,locator_json,text_content,structured_json,content_sha256) VALUES (?,?,?,?,?,?,?,?)",
                [unit_id, record["document_id"], payload["unit_type"], payload["unit_index"], json_text(payload["locator"]), payload["text"], json_text(payload["structured"]), content_hash],
            )
        cache_key = _cache_key(record["sha256"], record["format_family"])
        cache_payload = {
            "parser_name": record["parser_name"],
            "status": record["parse_status"],
            "notes": record["parse_notes"].split("; ") if record["parse_notes"] else [],
            "metadata": record.get("_parser_metadata", {}),
            "units": [u.as_dict() for u in record["units"]],
        }
        con.execute(
            "INSERT OR REPLACE INTO cache_index(cache_key,source_sha256,parser_name,parser_version,schema_version,result_json,created_at) VALUES (?,?,?,?,?,?,?)",
            [cache_key, record["sha256"], record["parser_name"], PARSER_VERSION, SCHEMA_VERSION, json_text(cache_payload), utc_now()],
        )
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()


def _inventory_row(rec: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in rec.items() if k not in {"units", "_parser_metadata", "_supplier_user_declared"}}


def _mark_duplicate_child(child: dict[str, Any], known_sha: dict[str, str]) -> None:
    previous = known_sha.get(child["sha256"])
    if previous:
        child["active"] = False
        child["offer_id"] = None
        child["metadata"]["duplicate_of_relative_path"] = previous
    else:
        known_sha[child["sha256"]] = child["relative_path"]


def _ingest_archive_members(rec: dict[str, Any], path: Path, source_root: Path, run_root: Path,
                            known_sha: dict[str, str], folder_mappings: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if rec["format_family"] != "zip":
        return []
    target = run_root / "extracted" / rec["document_id"]
    members = archive_adapter.extract_zip(path, target)
    out: list[dict[str, Any]] = []
    for member in members:
        rel = f"{rec['relative_path']}::{member.resolve().relative_to(target.resolve())}"
        child = ingest_file(member, target, run_root, parent_document_id=rec["document_id"], rel_override=rel,
                            folder_mappings=folder_mappings)
        _mark_duplicate_child(child, known_sha)
        write_to_db(run_root, child)
        out.append(child)
    return out


def _ingest_email_attachments(rec: dict[str, Any], path: Path, run_root: Path,
                              known_sha: dict[str, str], folder_mappings: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if rec["format_family"] != "eml":
        return []
    target = run_root / "extracted" / rec["document_id"]
    out: list[dict[str, Any]] = []
    for member, original_name, part_no in eml_adapter.extract_attachments(path, target):
        rel = f"{rec['relative_path']}::attachment-{part_no:03d}/{member.name}"
        child = ingest_file(member, target, run_root, parent_document_id=rec["document_id"], rel_override=rel,
                            folder_mappings=folder_mappings)
        child["metadata"]["email_attachment_name"] = original_name
        child["metadata"]["email_part_number"] = part_no
        _mark_duplicate_child(child, known_sha)
        write_to_db(run_root, child)
        out.append(child)
    return out


def ingest_source(source: Path, run_root: Path, inventory_only: bool = False,
                  folder_mappings: dict[str, str] | None = None) -> list[dict[str, Any]]:
    source = source.resolve()
    files = sorted(iter_source_files(source, run_root), key=lambda p: str(p).casefold())
    known_sha = {sha256_file(p): str(p.relative_to(source)) if source.is_dir() else p.name for p in files}
    inventory: list[dict[str, Any]] = []
    if not inventory_only:
        init_db(run_root)
    for p in files:
        try:
            rec = ingest_file(p, source if source.is_dir() else p.parent, run_root, folder_mappings=folder_mappings)
        except Exception as exc:
            source_sha = sha256_file(p)
            rec = {
                "document_id": stable_id("doc", str(p), source_sha),
                "parent_document_id": None,
                "relative_path": p.name,
                "source_path": str(p.resolve()),
                "filename": p.name,
                "format_family": "unknown",
                "document_role": "unknown",
                "role_confidence": 0.0,
                "revision_label": None,
                "revision_status": None,
                "sha256": source_sha,
                "size_bytes": p.stat().st_size,
                "parser_name": "error",
                "parser_version": PARSER_VERSION,
                "parse_status": "unreadable",
                "parse_notes": str(exc),
                "units": [],
                "metadata": {},
                "extension": p.suffix.lower(),
                "mime_type": mimetypes.guess_type(p.name)[0],
                "supplier_id": None,
                "supplier_name": None,
                "supplier_confidence": 0.0,
                "offer_id": None,
                "source_mtime": p.stat().st_mtime,
            }
        if not inventory_only:
            write_to_db(run_root, rec)
        inventory.append(_inventory_row(rec))
        if not inventory_only and rec["format_family"] == "zip" and rec["parse_status"] != "unreadable":
            try:
                for child in _ingest_archive_members(rec, p, source, run_root, known_sha, folder_mappings):
                    inventory.append(_inventory_row(child))
            except Exception as exc:
                raise RuntimeError(f"Archive extraction failed for {rec['relative_path']}: {exc}") from exc
        if not inventory_only and rec["format_family"] == "eml" and rec["parse_status"] != "unreadable":
            try:
                for child in _ingest_email_attachments(rec, p, run_root, known_sha, folder_mappings):
                    inventory.append(_inventory_row(child))
            except Exception as exc:
                raise RuntimeError(f"Email attachment extraction failed for {rec['relative_path']}: {exc}") from exc
    dump_json(run_root / "inventory.json", inventory)
    if not inventory_only:
        unreadable = sum(1 for x in inventory if x["parse_status"] == "unreadable")
        partial = sum(1 for x in inventory if x["parse_status"] == "partial")
        set_state(run_root, "INGEST", "PARTIAL" if unreadable or partial else "PASS", {"documents": len(inventory), "unreadable": unreadable, "partial": partial})
    return inventory


def main() -> None:
    ap = argparse.ArgumentParser(description="Multi-format deterministic ingest")
    ap.add_argument("--source", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--inventory-only", action="store_true")
    args = ap.parse_args()
    inv = ingest_source(Path(args.source), Path(args.run), inventory_only=args.inventory_only)
    print(json.dumps(inv, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
