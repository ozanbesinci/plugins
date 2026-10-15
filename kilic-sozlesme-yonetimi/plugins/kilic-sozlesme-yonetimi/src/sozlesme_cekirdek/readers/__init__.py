"""Fixed reader registry; document bytes never select code or grant permission."""
from functools import lru_cache
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from jsonschema import Draft202012Validator
from ..errors import CoreError
from .process_budget import run_bounded_worker

ROOT = Path(__file__).resolve().parents[3]
DEPENDENCIES = {"DOCX": ["lxml"], "PDF": ["pypdf", "pypdfium2"], "XLSX": ["lxml", "openpyxl"], "EML": []}


def dependency_profile(kind):
    if kind not in DEPENDENCIES:
        raise CoreError("DOSYA_TURU", "Yalnız DOCX/PDF/XLSX/EML destekleniyor")
    return {name: importlib.metadata.version(name) for name in DEPENDENCIES[kind]}


@lru_cache
def reading_validator():
    schema = json.loads((ROOT / "schemas" / "p2_reading.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_reading(report, data):
    if not reading_validator().is_valid(report):
        raise CoreError("SEMA_HATASI", "P2 okuma sonucu şemaya uymuyor")
    sha = hashlib.sha256(data).hexdigest()
    if report["sha256"] != sha or report["size_bytes"] != len(data):
        raise CoreError("KAYNAK_BOZUK", "Okuma sonucu kaynakla eşleşmiyor")
    seen = set()
    for row in report["units"]:
        expected = hashlib.sha256(sha.encode("ascii") + repr(sorted(row["locator"].items())).encode("utf-8")).hexdigest()
        if row["unit_id"] != expected or expected in seen:
            raise CoreError("KAYNAK_BOZUK", "Okuma birimi kimliği/konumu geçersiz")
        seen.add(expected)
    return report


def read_document(data, kind):
    dependency_profile(kind)
    if not isinstance(data, bytes) or len(data) > 64 * 1024 * 1024:
        raise CoreError("BELGE_SINIRI", "P2 kaynak bayt sınırı 64 MiB")
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"),
                       PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    completed = run_bounded_worker([sys.executable, "-m", "sozlesme_cekirdek.readers.worker", kind],
                                  data, environment)
    try:
        report = json.loads(completed.stdout.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise CoreError("OKUYUCU_HATASI", "Okuyucu geçerli yapılandırılmış çıktı üretmedi") from exc
    if completed.returncode:
        raise CoreError(report.get("error", "OKUYUCU_HATASI"), report.get("message", "Okuyucu başarısız"))
    if report.get("format") != kind:
        raise CoreError("DOSYA_TURU", "Okuma biçimi istenen türle eşleşmiyor")
    return validate_reading(report, data)


def excerpt(report, unit_id, view, start, end, expected_text):
    if view not in {"RAW", "BEFORE", "AFTER", "DISPLAY"}:
        raise CoreError("GORUNUM_GEREKLI", "Kaynak görünümü açıkça seçilmeli")
    row = next((x for x in report["units"] if x["unit_id"] == unit_id), None)
    text = None if row is None else row["views"][view]
    if text is None:
        raise CoreError("KAYNAK_KONUMU", "Birimin seçilen görünümü yok")
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
            or not isinstance(expected_text, str) or text[start:end] != expected_text):
        raise CoreError("ALINTI_UYUSMAZLIGI", "Alıntı/range seçilen kaynak metniyle birebir eşleşmiyor")
    return {"source_sha256": report["sha256"], "unit_id": unit_id, "locator": row["locator"],
            "view": view, "start": start, "end": end, "text": expected_text,
            "text_sha256": hashlib.sha256(expected_text.encode("utf-8")).hexdigest(),
            "verification_scope": "EXACT_EXTRACTED_TEXT_MATCH_ONLY",
            "critical_analysis_allowed": False, "authority": "NOT_VERIFIED"}
