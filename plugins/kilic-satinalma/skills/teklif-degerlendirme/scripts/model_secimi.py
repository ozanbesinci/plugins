"""Resolve real offered models; no provider calls or invented fallback names."""
from __future__ import annotations
import datetime as dt

PROFILES = {
    "hizli": {"max_input_tokens": 8_000_000, "max_wall_seconds": 1500, "max_revisions": 1},
    "standart": {"max_input_tokens": 25_000_000, "max_wall_seconds": 3600, "max_revisions": 1},
    "yuksek_guvence": {"max_input_tokens": 50_000_000, "max_wall_seconds": 7200, "max_revisions": 2},
}
REQUIRED_MODEL = "gpt-6.1-sol"
REQUIRED_EFFORT = "high"
ROLES = {role: ("sol", REQUIRED_EFFORT) for role in (
    "extraction", "extraction_difficult", "requirements", "targeted_review",
    "blind_review", "adjudicator", "decision_summary", "technical", "financial", "contracts",
)}


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Katalog zamanı saat dilimi içermeli.")
    return result


def resolve(catalog, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not catalog.get("source") or not isinstance(catalog.get("models"), list):
        raise ValueError("Güncel araç/hesap kataloğu ve kaynağı gerekli.")
    age = (now - timestamp(catalog["observed_at"])).total_seconds()
    if not -60 <= age <= 300:
        raise ValueError("Model kataloğu taze değil; başlangıçta yeniden okuyun.")
    selected, seen = None, set()
    for row in catalog["models"]:
        identity = row["id"]
        if identity in seen:
            raise ValueError("Katalogda yinelenmiş model kimliği.")
        seen.add(identity)
        if identity != REQUIRED_MODEL:
            continue
        if not isinstance(row.get("efforts"), list) or not row["efforts"]:
            raise ValueError("Katalogda desteklenen eforlar eksik.")
        selected = row
    if selected is None:
        raise ValueError(f"Erişilebilir {REQUIRED_MODEL} yok; başka modele geçilmez.")
    if REQUIRED_EFFORT not in selected["efforts"]:
        raise ValueError(f"{REQUIRED_MODEL} High desteklemiyor; başka efora geçilmez.")
    return {role: {"family": family, "model": selected["id"], "reasoning_effort": effort}
            for role, (family, effort) in ROLES.items()}


def recommend(*, has_spec, purchase_type, imported, has_tco, max_amount=None, fast_limit=None):
    if any(type(value) is not bool for value in (has_spec,imported,has_tco)):
        raise ValueError('Şartname/ithalat/TCO alanları boolean olmalı.')
    if not isinstance(purchase_type,str) or not purchase_type.strip():
        raise ValueError('Alım türü gerekli.')
    for value in (max_amount,fast_limit):
        if value is not None and (type(value) not in (int,float) or value<0 or value!=value or value==float('inf')):
            raise ValueError('Tutar/eşik negatif olmayan sonlu sayı veya null olmalı.')
    if imported and has_tco:
        return "yuksek_guvence"
    if not has_spec and purchase_type == "genel_mal_hizmet" and not imported:
        if fast_limit is None or (max_amount is not None and max_amount <= fast_limit):
            return "hizli"
    return "standart"


def allowed_role(profile, role):
    if role not in ROLES or profile not in PROFILES:
        return False
    if role == "blind_review":
        return profile != "hizli"
    if role == "targeted_review":
        return profile == "hizli"
    if role in {"technical", "financial", "contracts"}:
        return profile == "yuksek_guvence"
    return True
