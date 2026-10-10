from functools import lru_cache
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from .errors import CoreError

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def validator(name):
    if name not in {"aday_bilgi", "islem_plani", "kontrol_sonucu"}:
        raise CoreError("SEMA_YOK", "Tanımlı şema adı gerekli")
    schema = json.loads((ROOT / "spec" / "semalar" / (name + ".schema.json")).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate(name, value):
    errors = sorted(validator(name).iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise CoreError("SEMA_HATASI", "; ".join(str(list(e.path)) + ": " + e.validator for e in errors))
    return value
