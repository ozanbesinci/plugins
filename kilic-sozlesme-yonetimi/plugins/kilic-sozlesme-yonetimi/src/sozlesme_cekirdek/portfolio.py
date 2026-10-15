"""K27 read-only measurement over an explicit case list, not a company-wide query.

Every case passes its own revision, access and source checks through the existing
single-case business overview. A case that cannot be read is excluded with its
reason and never counted. Sources stay inside their case; only counts are summed.
No arbitrary SQL, interpretation, approval or automated follow-up.
"""
from datetime import date
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from .errors import CoreError
from .safety import hash_value, uuid_text
from .verification import validate_policy

VERSION = "portfolio-1.0"
ROOT = Path(__file__).resolve().parents[2]
MAX_ATTENTION = 16
POSITIONS = {"PAST_DUE_CANDIDATE": "obligations_past_due_candidate", "DUE_TODAY_CANDIDATE": "obligations_due_today_candidate",
             "UPCOMING_CANDIDATE": "obligations_upcoming_candidate", "UNRESOLVED": "obligations_unresolved_due"}
INCOMPARABLE = {"INCOMPARABLE_TYPE_OR_UNIT", "CURRENCY_MISMATCH_NO_FX", "UNIT_REQUIRED"}
LIMITATIONS = [
    "Kapsam yalnız istekte açıkça listelenen ve okunabilen case'lerdir; şirket geneli veya örneklemden genelleme değildir.",
    "Erişilemeyen, değişen veya kapsam dışı kaynaklı case ölçüme dahil edilmedi; nedeni ayrı gösterildi.",
    "Sayımlar aday iş kayıtlarıdır; tarih konumu ihlal kararı, değer farkı sözleşme değişikliği değildir.",
    "Ortak sorun yorumu ve iyileştirme önerisi model/uzman değerlendirmesidir; bu ölçüm onay vermez.",
]
METRICS = [
    ("cases_with_value_mismatch", "En az bir yazılı-beyan değer farkı olan case", "Dahil edilen case"),
    ("cases_with_changed_sources", "Seçili kaynağı kayıttan sonra değişen case", "Dahil edilen case"),
    ("obligations_past_due_candidate", "Vadesi geçmiş aday güncel yükümlülük", "Güncel yükümlülük"),
    ("obligations_unresolved_due", "Vadesi çözülemeyen güncel yükümlülük", "Güncel yükümlülük"),
    ("obligations_unknown_party", "Sorumlusu kaynakta belirsiz güncel yükümlülük", "Güncel yükümlülük"),
    ("facts_needs_review", "Yeniden inceleme gereken iş bilgisi", "Bütün görünür iş bilgileri"),
]


@lru_cache
def validator(name):
    schema = json.loads((ROOT / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def checked(name, value):
    if not validator(name).is_valid(value):
        raise CoreError("SEMA_HATASI", "Portföy istek/sonuç şeması farklı")
    return value


def measures(overview):
    facts, obligations, comparisons = overview["facts"], overview["obligations"], overview["comparisons"]
    current = [row for row in obligations if row["state"] == "CURRENT_CANDIDATE"]
    result = {"facts": len(facts), "facts_current": sum(row["state"] == "CURRENT_CANDIDATE" for row in facts),
              "comparisons": len(comparisons), "value_mismatches": sum(row["status"] == "VALUE_MISMATCH" for row in comparisons),
              "incomparable_comparisons": sum(row["status"] in INCOMPARABLE for row in comparisons),
              "obligations": len(obligations), "obligations_current": len(current),
              "obligations_unknown_party": sum(row["obligated_party"] is None for row in current),
              "obligations_with_completion_claim": sum(bool(row["completion_claim_ids"]) for row in current),
              "events": len(overview["events"]), "all_selected_sources_current": overview["all_selected_sources_current"]}
    result["facts_needs_review"] = result["facts"] - result["facts_current"]
    for position, key in POSITIONS.items():
        result[key] = sum(row["date_position"] == position for row in current)
    return result


def attention(overview):
    rows = []
    for row in overview["obligations"]:
        version = row["provenance"].get("version_id")
        if row["state"] != "CURRENT_CANDIDATE":
            rows.append(("NEEDS_REVIEW", row["obligation_id"], row["description"], row["due_date"], version))
        elif row["date_position"] in {"PAST_DUE_CANDIDATE", "UNRESOLVED"}:
            kind = "PAST_DUE_CANDIDATE" if row["date_position"] == "PAST_DUE_CANDIDATE" else "UNRESOLVED_DUE"
            rows.append((kind, row["obligation_id"], row["description"], row["due_date"], version))
    for row in overview["comparisons"]:
        if row["status"] == "VALUE_MISMATCH":
            rows.append(("VALUE_MISMATCH", row["left_fact_id"] + "|" + row["right_fact_id"],
                         row["scope_key"] + "/" + row["field"], None, None))
    for row in overview["facts"]:
        if row["state"] != "CURRENT_CANDIDATE":
            rows.append(("NEEDS_REVIEW", row["fact_id"], row["scope_key"] + "/" + row["field"], None,
                         row["provenance"].get("version_id")))
    keys = ("kind", "record_id", "description", "due_date", "source_version_id")
    return [dict(zip(keys, row)) for row in rows[:MAX_ATTENTION]], max(0, len(rows) - MAX_ATTENTION)


def portfolio_overview(store, request):
    checked("portfolio_request", request)
    validate_policy(request["policy_version"])
    try:
        date.fromisoformat(request["as_of"])
    except ValueError as exc:
        raise CoreError("TARIH_KURALI", "İnceleme tarihi açık ISO tarih olmalı") from exc
    case_ids = [uuid_text(row["case_id"]) for row in request["cases"]]
    if len(set(case_ids)) != len(case_ids):
        raise CoreError("GECERSIZ_GIRDI", "Portföy case listesi tekrar içeremez")
    cases = []
    for case, row in zip(case_ids, request["cases"]):
        versions = [uuid_text(version) for version in row["selected_versions"]]
        entry = {"case_id": case, "status": "EXCLUDED", "context_version": None, "selected_versions": versions,
                 "error_code": None, "reason": None, "measures": None, "attention": [], "attention_truncated": 0}
        try:
            # The existing overview pins the expected revision and rechecks access/hash for every selected version.
            overview = store.business_overview(case, as_of=request["as_of"], scope_keys=request["scope_keys"],
                                               selected_versions=versions, policy_version=request["policy_version"],
                                               expected_revision=row["expected_revision"])
        except CoreError as exc:
            entry.update(error_code=exc.code, reason=str(exc))
        else:
            items, truncated = attention(overview)
            entry.update(status="INCLUDED", context_version=overview["context_version"], measures=measures(overview),
                         attention=items, attention_truncated=truncated)
        cases.append(entry)
    included = [row["measures"] for row in cases if row["status"] == "INCLUDED"]
    current_obligations = sum(row["obligations_current"] for row in included)
    totals = {"cases_with_value_mismatch": (sum(row["value_mismatches"] > 0 for row in included), len(included)),
              "cases_with_changed_sources": (sum(not row["all_selected_sources_current"] for row in included), len(included)),
              "facts_needs_review": (sum(row["facts_needs_review"] for row in included), sum(row["facts"] for row in included))}
    for key in ("obligations_past_due_candidate", "obligations_unresolved_due", "obligations_unknown_party"):
        totals[key] = (sum(row[key] for row in included), current_obligations)
    metrics = [{"id": key, "numerator": totals[key][0], "denominator": totals[key][1],
                "numerator_basis": numerator, "denominator_basis": denominator} for key, numerator, denominator in METRICS]
    status = ("NO_INCLUDED_CASE" if not included else "COMPLETE_LISTED_SCOPE" if len(included) == len(cases)
              else "PARTIAL_LISTED_SCOPE")
    result = {"schema_version": VERSION, "request_id": request["request_id"], "request_digest": hash_value(request),
              "purpose": request["purpose"], "as_of": request["as_of"], "scope_keys": request["scope_keys"], "status": status,
              "coverage": {"method": "EXPLICIT_CASE_LIST_ONLY", "requested_cases": len(cases), "included_cases": len(included),
                           "excluded_cases": len(cases) - len(included), "company_wide": False, "sampling_inference": "NOT_RUN"},
              "cases": cases, "metrics": metrics, "cross_case_source_mixing": False, "interpretation": "NOT_RUN",
              "business_acceptance": "NOT_GRANTED", "authority": "NOT_VERIFIED", "critical_analysis_allowed": False,
              "limitations": LIMITATIONS}
    return checked("portfolio_result", result)
