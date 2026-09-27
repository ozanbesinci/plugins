"""Resolve real offered models; no provider calls or invented fallback names."""
from __future__ import annotations
import datetime as dt
import re

PROFILES = {
    "hizli": {"max_input_tokens": 8_000_000, "max_wall_seconds": 1500, "max_revisions": 1},
    "standart": {"max_input_tokens": 25_000_000, "max_wall_seconds": 3600, "max_revisions": 1},
    "yuksek_guvence": {"max_input_tokens": 50_000_000, "max_wall_seconds": 7200, "max_revisions": 2},
}
ROLES = {
    "extraction": ("terra", "medium"), "extraction_difficult": ("terra", "high"),
    "requirements": ("terra", "high"), "targeted_review": ("terra", "high"),
    "blind_review": ("sol", "high"), "adjudicator": ("sol", "high"), "decision_summary": ("sol", "high"),
    "technical": ("terra", "high"), "financial": ("terra", "high"), "contracts": ("terra", "high"),
}
MODEL_ID = re.compile(r"^gpt-(\d+(?:\.\d+)*)-(sol|terra)$")


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
    selected, seen = {}, set()
    for row in catalog["models"]:
        identity = row["id"]
        if identity in seen:
            raise ValueError("Katalogda yinelenmiş model kimliği.")
        seen.add(identity)
        match = MODEL_ID.fullmatch(identity)
        if not match:  # Luna/Astra and unnamed future families cannot enter role selection.
            continue
        version = tuple(int(part) for part in match[1].split("."))
        family = match[2]
        if not isinstance(row.get("efforts"), list) or not row["efforts"]:
            raise ValueError("Katalogda desteklenen eforlar eksik.")
        if family not in selected or version > selected[family][0]:
            selected[family] = (version, row)
    result = {}
    for role, (family, effort) in ROLES.items():
        if family not in selected:
            raise ValueError(f"Erişilebilir {family} yok; başka aileye geçilmez.")
        row = selected[family][1]
        if effort not in row["efforts"]:
            raise ValueError(f"En yeni {family} {effort} desteklemiyor; eski sürüme dönülmez.")
        result[role] = {"family": family, "model": row["id"], "reasoning_effort": effort}
    return result


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
