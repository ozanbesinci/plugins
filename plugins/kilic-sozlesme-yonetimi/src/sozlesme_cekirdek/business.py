"""Source-anchored facts, comparisons and obligation candidates; no business approval.

Values are derived from exact spans. Classification/meaning and event authenticity remain
unverified. The source coordinator, schema checker and calculation engine are shared.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal, localcontext
import json
import re

from .calculations import calculate
from .context import checked
from .errors import CoreError
from .safety import canonical, hash_value, uuid_text
from .verification import validate_policy

VERSION = "p6-business-1.0"
TABLES = {"is_bilgisi_baglari", "yukumlulukler", "gerceklesmeler"}
UNITS = {
    "months": {"ay", "ays", "month", "months"},
    "days": {"gün", "gun", "day", "days"},
    "calendar_days": {"takvim günü", "takvim gunu", "calendar days"},
    "business_days": {"iş günü", "is gunu", "business days"},
    "ratio": {"%", "oran", "ratio"},
    "money": {"bedel", "tutar", "amount"},
    "quantity": {"adet", "birim", "quantity", "units"},
}
LIMITS = {"is_bilgisi_baglari": 512, "yukumlulukler": 256, "gerceklesmeler": 1024}


def span_text(excerpt, span):
    if span is None:
        return None
    if span["start"] >= span["end"] or span["end"] > len(excerpt) or excerpt[span["start"]:span["end"]] != span["text"]:
        raise CoreError("KAYNAK_ALINTISI", "İş bilgisi tam kaynak aralığına eşleşmiyor")
    return span["text"]


def normalize(spec, excerpt):
    raw = span_text(excerpt, spec["value_span"])
    unit_raw = span_text(excerpt, spec["unit_span"])
    currency_raw = span_text(excerpt, spec["currency_span"])
    if (spec["unit"] is None) != (unit_raw is None) or (spec["currency"] is None) != (currency_raw is None):
        raise CoreError("BIRIM_KAYNAGI", "Birim/para kodu ayrı kaynak aralığı gerektirir")
    if unit_raw is not None and unit_raw.casefold() not in UNITS[spec["unit"]]:
        raise CoreError("BIRIM_KAYNAGI", "Kaynak birimi seçilen normalleştirmeye uymuyor")
    if currency_raw is not None:
        aliases = {spec["currency"]}
        if spec["currency"] == "TRY":
            aliases |= {"TL", "₺"}
        if currency_raw not in aliases:
            raise CoreError("PARA_BIRIMI", "Para kodu kaynakta yok; kur dönüşümü yapılmadı")
    method = spec["normalization"]
    if method == "TEXT":
        return {"type": "text", "value": raw}
    if method == "DATE_ISO":
        if spec["unit"] is not None or spec["currency"] is not None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            raise CoreError("TARIH_KAYNAGI", "Tarih yalnız tam ISO kaynak ifadesinden alınır")
        try:
            return {"type": "date", "value": date.fromisoformat(raw).isoformat()}
        except ValueError as exc:
            raise CoreError("TARIH_KAYNAGI", "Kaynak tarihi geçersiz") from exc
    pattern = r"-?(0|[1-9][0-9]*)(\.[0-9]+)?"
    if method == "INTEGER":
        pattern = r"-?(0|[1-9][0-9]*)"
    elif method in {"DECIMAL_TR", "PERCENT_TR"}:
        pattern = r"-?(0|[1-9][0-9]*|[1-9][0-9]{0,2}(\.[0-9]{3})+)(,[0-9]+)?"
    if not re.fullmatch(pattern, raw):
        raise CoreError("SAYI_KAYNAGI", "Sayı biçimi açık normalleştirmeyle uyuşmuyor")
    canonical_number = raw.replace(".", "").replace(",", ".") if method in {"DECIMAL_TR", "PERCENT_TR"} else raw
    number = Decimal(canonical_number)
    if method == "PERCENT_TR":
        if spec["unit"] != "ratio" or unit_raw != "%":
            raise CoreError("BIRIM_KAYNAGI", "Yüzde dönüşümü kaynak yüzde işaretine bağlıdır")
        with localcontext() as ctx:
            ctx.prec = max(64, len(raw) + 10)
            number /= Decimal(100)
    elif spec["unit"] == "ratio" and unit_raw == "%":
        raise CoreError("BIRIM_KAYNAGI", "Yüzdeyi kesir oranıyla karıştırma; PERCENT_TR seç")
    return {"type": "decimal", "value": format(number, "f")}


class BusinessMixin:
    def _business_source(self, db, case, node_id, policy, *, require_current=True):
        node = self._context_node(db, case, uuid_text(node_id), policy)
        if node["node_kind"] not in {"SOURCE_UNIT", "USER_STATEMENT"}:
            raise CoreError("BILGI_TURU", "İş kaydı tam belge aralığına veya ayrı kullanıcı beyanına bağlanmalı")
        if require_current and node["state"] != "CURRENT_REGISTERED_SCOPE":
            raise CoreError("YENIDEN_INCELE", "İş kaydının kaynak düğümü güncel değil")
        return node

    @staticmethod
    def _excerpt(node):
        return node["content"]["excerpt" if node["node_kind"] == "SOURCE_UNIT" else "statement"]

    @staticmethod
    def _business_payload(db, table, case, record):
        if table not in TABLES:
            raise CoreError("GECERSIZ_GIRDI", "Tanımsız iş kayıt türü")
        row = db.execute(f"SELECT payload,payload_digest FROM {table} WHERE case_id=? AND record_id=?", [case, uuid_text(record)]).fetchone()
        if not row:
            raise CoreError("KAYNAK_KAPSAMI", "İş kaydı bu case içinde değil")
        payload = json.loads(row[0])
        if hash_value(payload) != row[1]:
            raise CoreError("IS_KAYDI_BOZUK", "İş kaydının kaynak parmakizi farklı")
        return payload

    def _business_freshness(self, db, case, record, node):
        if db.execute("SELECT 1 FROM kayitlar WHERE case_id=? AND supersedes_id=? LIMIT 1", [case, record]).fetchone():
            return "SUPERSEDED"
        return "NEEDS_REVIEW" if node["state"] != "CURRENT_REGISTERED_SCOPE" or self._invalid(db, case, [record]) else "CURRENT_CANDIDATE"

    @staticmethod
    def _business_limit(db, table, case):
        if db.execute(f"SELECT count(*) FROM {table} WHERE case_id=?", [case]).fetchone()[0] >= LIMITS[table]:
            raise CoreError("IS_KAYDI_SINIRI", "Case iş kayıt sınırı doldu")

    def _business_links(self, db, case, record, dependencies):
        for dependency in sorted(set(dependencies)):
            db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)", [case, record, dependency, canonical({"business_projection": True})])

    def register_business_fact(self, case_id, *, spec, expected_revision, policy_version="1"):
        case = uuid_text(case_id)
        checked("p6_business_fact", spec)
        validate_policy(policy_version)
        with self._db() as db:
            self._case(db, case, expected_revision)
            node = self._business_source(db, case, spec["source_node_id"], policy_version)
            statement = node["node_kind"] == "USER_STATEMENT"
            if statement != (spec["plane"] in {"USER_POSITION", "REPORTED_EVENT"}):
                raise CoreError("BILGI_DUZLEMI", "Beyan yazılı hüküm veya belgeli olay yerine geçemez")
            source = node["provenance"]["record_id" if statement else "version_id"]
            candidate = {"schema_version": "1.0", "case_id": case, "source_record_id": source,
                "field": spec["field"], "knowledge_kind": "USER_STATEMENT" if statement else "DOCUMENT_TEXT",
                "value": normalize(spec, self._excerpt(node)), "unit": spec["unit"], "currency": spec["currency"],
                "source_excerpt": self._excerpt(node), "meaning_status": "UNCERTAIN"}
            payload = {"spec": spec, "policy_version": policy_version, "candidate": candidate, "source": node}
            digest = hash_value(payload)
            old = db.execute("SELECT record_id FROM is_bilgisi_baglari WHERE case_id=? AND fact_digest=?", [case, digest]).fetchone()
            if old:
                if self._business_freshness(db, case, str(old[0]), node) != "CURRENT_CANDIDATE":
                    raise CoreError("YENIDEN_INCELE", "Aynı iş kaydı zaten değişmiş")
                return {"fact_id": str(old[0]), "reused": True}
            prior = spec.get("supersedes_id")
            if prior:
                prior_payload = self._business_payload(db, "is_bilgisi_baglari", case, prior)
                if any(prior_payload["spec"][key] != spec[key] for key in ("plane", "field", "scope_key")):
                    raise CoreError("BILGI_DUZLEMI", "Yerine geçen bilgi aynı kapsam/alan/düzlemde olmalı")
                if db.execute("SELECT 1 FROM kayitlar WHERE case_id=? AND supersedes_id=?", [case, prior]).fetchone():
                    raise CoreError("YENIDEN_INCELE", "İş bilgisi zaten değiştirilmiş")
            self._business_limit(db, "is_bilgisi_baglari", case)
            record = self._add_candidate_locked(db, case, source, candidate, {"source_node_id": spec["source_node_id"], "spans": spec}, prior)
            db.execute("INSERT INTO is_bilgisi_baglari VALUES(?,?,?,?,?,?,?,?)", [case, record, spec["source_node_id"], spec["scope_key"], spec["plane"], digest, canonical(payload), digest])
            self._business_links(db, case, record, [spec["source_node_id"]])
            self._business_source(db, case, spec["source_node_id"], policy_version)
            return {"fact_id": record, "reused": False}

    def _business_fact(self, db, case, record, policy):
        payload = self._business_payload(db, "is_bilgisi_baglari", case, record)
        spec = checked("p6_business_fact", payload["spec"])
        node = self._business_source(db, case, spec["source_node_id"], policy, require_current=False)
        row = db.execute("SELECT payload FROM bilgiler WHERE case_id=? AND record_id=?", [case, record]).fetchone()
        candidate = payload["candidate"]
        if json.loads(row[0]) != candidate or normalize(spec, self._excerpt(node)) != candidate["value"]:
            raise CoreError("IS_KAYDI_BOZUK", "Normalleştirilmiş değer kaynak veya aday kayıtla farklı")
        old_source = payload["source"]
        if any(old_source[key] != node[key] for key in ("content", "provenance", "node_kind")):
            raise CoreError("IS_KAYDI_BOZUK", "İş bilgisinin kaynak kaydı farklı")
        state = self._business_freshness(db, case, record, node)
        if payload["policy_version"] != policy:
            state = "NEEDS_REVIEW"
        return {"fact_id": record, "scope_key": spec["scope_key"], "plane": spec["plane"], "field": spec["field"],
            "value": candidate["value"], "unit": candidate["unit"], "currency": candidate["currency"], "state": state,
            "source_node_id": spec["source_node_id"], "source_excerpt": self._excerpt(node), "provenance": node["provenance"],
            "normalization": spec["normalization"], "value_span": spec["value_span"], "meaning_status": "UNVERIFIED",
            "classification_status": "UNVERIFIED", "source_verification": node["knowledge_status"], "business_approval": "NOT_GRANTED"}

    def _required_fact(self, db, case, record, scope, policy, *, plane=None, value_type=None):
        fact = self._business_fact(db, case, uuid_text(record), policy)
        if fact["state"] != "CURRENT_CANDIDATE":
            raise CoreError("YENIDEN_INCELE", "Bağlı iş bilgisi güncel değil")
        if fact["scope_key"] != scope or (plane is not None and fact["plane"] != plane) or (value_type and fact["value"]["type"] != value_type):
            raise CoreError("BILGI_DUZLEMI", "Bağlı bilgi aynı iş kapsamı ve gerekli düzlem/türde değil")
        return fact

    def register_obligation(self, case_id, *, spec, expected_revision, policy_version="1"):
        case = uuid_text(case_id)
        checked("p6_obligation", spec)
        validate_policy(policy_version)
        with self._db() as db:
            self._case(db, case, expected_revision)
            node = self._business_source(db, case, spec["source_node_id"], policy_version)
            if node["node_kind"] != "SOURCE_UNIT":
                raise CoreError("BILGI_DUZLEMI", "Yükümlülük adayı yazılı kaynak hükmüne bağlı olmalı")
            dependencies = [spec["source_node_id"]]
            if spec["due_fact_id"]:
                self._required_fact(db, case, spec["due_fact_id"], spec["scope_key"], policy_version, plane="WRITTEN", value_type="date")
                dependencies.append(spec["due_fact_id"])
            if spec["due_rule"]:
                rule = spec["due_rule"]
                count = self._required_fact(db, case, rule["count_fact_id"], spec["scope_key"], policy_version, plane="WRITTEN", value_type="decimal")
                if count["unit"] not in {"calendar_days", "business_days", "months", "days"}:
                    raise CoreError("TARIH_KURALI", "Süre bilgisi gün/ay birimine bağlı olmalı")
                dependencies.append(rule["count_fact_id"])
                if rule["start_fact_id"]:
                    start = self._required_fact(db, case, rule["start_fact_id"], spec["scope_key"], policy_version, value_type="date")
                    if start["plane"] not in {"DOCUMENTED_EVENT", "REPORTED_EVENT"}:
                        raise CoreError("BILGI_DUZLEMI", "Başlangıç olayı yazılı plan veya pozisyonla karıştırılamaz")
                    dependencies.append(rule["start_fact_id"])
            payload = {"spec": spec, "source": node, "dependencies": dependencies, "policy_version": policy_version}
            digest = hash_value(payload)
            old = db.execute("SELECT record_id FROM yukumlulukler WHERE case_id=? AND obligation_digest=?", [case, digest]).fetchone()
            if old:
                if self._business_freshness(db, case, str(old[0]), node) != "CURRENT_CANDIDATE":
                    raise CoreError("YENIDEN_INCELE", "Aynı yükümlülük kaydı zaten değişmiş")
                return {"obligation_id": str(old[0]), "reused": True}
            prior = spec.get("supersedes_id")
            if prior:
                previous = self._business_payload(db, "yukumlulukler", case, prior)
                if previous["spec"]["scope_key"] != spec["scope_key"] or db.execute("SELECT 1 FROM kayitlar WHERE case_id=? AND supersedes_id=?", [case, prior]).fetchone():
                    raise CoreError("YENIDEN_INCELE", "Yükümlülük değiştirme kapsamı farklı veya zaten değişmiş")
            self._business_limit(db, "yukumlulukler", case)
            record = self._record(db, case, "PROCESSING", supersedes=prior)
            db.execute("INSERT INTO yukumlulukler VALUES(?,?,?,?,?,?,?)", [case, record, spec["source_node_id"], spec["scope_key"], digest, canonical(payload), digest])
            self._business_links(db, case, record, dependencies)
            if prior:
                self._invalidate(db, case, prior, record, "OBLIGATION_SUPERSEDED")
            self._event(db, case, "OBLIGATION_CANDIDATE_RECORDED", {"obligation_id": record})
            self._bump(db, case)
            self._business_source(db, case, spec["source_node_id"], policy_version)
            return {"obligation_id": record, "reused": False}

    def register_business_event(self, case_id, *, spec, expected_revision, policy_version="1"):
        case = uuid_text(case_id)
        checked("p6_business_event", spec)
        validate_policy(policy_version)
        with self._db() as db:
            self._case(db, case, expected_revision)
            obligation = self._business_payload(db, "yukumlulukler", case, spec["obligation_id"])
            source = self._business_source(db, case, spec["source_node_id"], policy_version)
            basis = self._business_source(db, case, obligation["spec"]["source_node_id"], policy_version)
            if self._business_freshness(db, case, spec["obligation_id"], basis) != "CURRENT_CANDIDATE":
                raise CoreError("YENIDEN_INCELE", "Olay eski/değişmiş yükümlülüğe uygulanamaz")
            dependencies = [spec["obligation_id"], spec["source_node_id"]]
            if spec["event_date_fact_id"]:
                fact = self._required_fact(db, case, spec["event_date_fact_id"], obligation["spec"]["scope_key"], policy_version, value_type="date")
                expected_plane = "REPORTED_EVENT" if source["node_kind"] == "USER_STATEMENT" else "DOCUMENTED_EVENT"
                if fact["plane"] != expected_plane or fact["source_node_id"] != spec["source_node_id"]:
                    raise CoreError("BILGI_DUZLEMI", "Olay tarihi aynı olay kaynağına bağlı olmalı")
                dependencies.append(spec["event_date_fact_id"])
            payload = {"spec": spec, "source": source, "dependencies": dependencies, "policy_version": policy_version}
            digest = hash_value(payload)
            old = db.execute("SELECT record_id FROM gerceklesmeler WHERE case_id=? AND event_digest=?", [case, digest]).fetchone()
            if old:
                return {"event_id": str(old[0]), "reused": True}
            self._business_limit(db, "gerceklesmeler", case)
            record = self._record(db, case, "PROCESSING")
            db.execute("INSERT INTO gerceklesmeler VALUES(?,?,?,?,?,?,?)", [case, record, spec["obligation_id"], spec["source_node_id"], digest, canonical(payload), digest])
            self._business_links(db, case, record, dependencies)
            self._event(db, case, "EVENT_REPORT_RECORDED_NOT_VERIFIED", {"event_id": record})
            self._bump(db, case)
            self._business_source(db, case, spec["source_node_id"], policy_version)
            return {"event_id": record, "reused": False}

    @staticmethod
    def _compare(facts):
        groups = defaultdict(list)
        for fact in facts:
            if fact["state"] == "CURRENT_CANDIDATE":
                groups[(fact["scope_key"], fact["field"])].append(fact)
        comparisons = []
        for (scope, field), group in sorted(groups.items()):
            for index, left in enumerate(group):
                for right in group[index + 1:]:
                    a, b = left["value"], right["value"]
                    if a["type"] != b["type"] or left["unit"] != right["unit"]:
                        status = "INCOMPARABLE_TYPE_OR_UNIT"
                    elif left["currency"] != right["currency"]:
                        status = "CURRENCY_MISMATCH_NO_FX"
                    elif a["type"] == "decimal" and left["unit"] is None:
                        status = "UNIT_REQUIRED"
                    else:
                        equal = Decimal(a["value"]) == Decimal(b["value"]) if a["type"] == "decimal" else a == b
                        status = "VALUE_MATCH" if equal else "VALUE_MISMATCH"
                    comparisons.append({"scope_key": scope, "field": field, "left_fact_id": left["fact_id"],
                        "right_fact_id": right["fact_id"], "planes": [left["plane"], right["plane"]], "status": status,
                        "meaning_status": "UNVERIFIED", "contract_amended": False, "authorized_decision": False})
                    if len(comparisons) > 256:
                        raise CoreError("IS_KAYDI_SINIRI", "İş karşılaştırma sınırı; kapsamı küçült")
        return comparisons

    def business_overview(self, case_id, *, as_of, scope_keys, selected_versions, policy_version="1", expected_revision=None):
        case = uuid_text(case_id)
        validate_policy(policy_version)
        try:
            if not isinstance(as_of, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
                raise ValueError()
            today = date.fromisoformat(as_of)
        except ValueError as exc:
            raise CoreError("TARIH_KURALI", "İnceleme tarihi açık ISO tarih olmalı") from exc
        if not isinstance(scope_keys, list) or not scope_keys or len(scope_keys) > 64 or any(not isinstance(s, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", s) for s in scope_keys) or len(set(scope_keys)) != len(scope_keys):
            raise CoreError("GECERSIZ_GIRDI", "İş kapsamları açık, tekil ve sınırlı olmalı")
        if not isinstance(selected_versions, list) or len(selected_versions) > 64:
            raise CoreError("KAYNAK_KAPSAMI", "Kaynak sürümleri açık ve sınırlı olmalı")
        versions = {uuid_text(version) for version in selected_versions}
        with self._db() as db:
            revision = self._case(db, case, expected_revision)
            facts = []
            for record, scope in db.execute("SELECT record_id,scope_key FROM is_bilgisi_baglari WHERE case_id=? ORDER BY record_id", [case]).fetchall():
                if scope in scope_keys:
                    facts.append(self._business_fact(db, case, str(record), policy_version))
            by_id = {fact["fact_id"]: fact for fact in facts}
            obligations, events = [], []
            for record, scope in db.execute("SELECT record_id,scope_key FROM yukumlulukler WHERE case_id=? ORDER BY record_id", [case]).fetchall():
                if scope not in scope_keys:
                    continue
                rid = str(record)
                payload = self._business_payload(db, "yukumlulukler", case, rid)
                spec = checked("p6_obligation", payload["spec"])
                source = self._business_source(db, case, spec["source_node_id"], policy_version, require_current=False)
                state = self._business_freshness(db, case, rid, source)
                if payload["policy_version"] != policy_version:
                    state = "NEEDS_REVIEW"
                due, due_status, due_reason = None, "MISSING_RULE", spec["missing_due_reason"]
                start_plane = None
                if state == "CURRENT_CANDIDATE":
                    try:
                        if spec["due_fact_id"]:
                            fact = self._required_fact(db, case, spec["due_fact_id"], scope, policy_version, plane="WRITTEN", value_type="date")
                            due, due_status = fact["value"]["value"], "SOURCE_DATE_CANDIDATE"
                        elif spec["due_rule"]:
                            rule = spec["due_rule"]
                            count = self._required_fact(db, case, rule["count_fact_id"], scope, policy_version, plane="WRITTEN", value_type="decimal")
                            quantity = Decimal(count["value"]["value"])
                            if rule["start_fact_id"] is None:
                                due_reason = "Başlangıç olayı kaydı eksik: " + rule["anchor_event"]
                            elif count["unit"] == "days":
                                due_reason = "İş günü/takvim günü ayrımı kaynakta açıklanmamış"
                            elif quantity != quantity.to_integral_value() or not 1 <= quantity <= 3660:
                                due_reason = "Süre pozitif tam sayı/sınır içinde değil"
                            else:
                                start = self._required_fact(db, case, rule["start_fact_id"], scope, policy_version, value_type="date")
                                start_plane = start["plane"]
                                if start_plane not in {"DOCUMENTED_EVENT", "REPORTED_EVENT"}:
                                    raise CoreError("BILGI_DUZLEMI", "Başlangıç olayı düzlemi farklı")
                                if count["unit"] == "business_days" and not rule["calendar_version"]:
                                    due_reason = "Tatil takvimi sürümü eksik"
                                else:
                                    answer = calculate({"kind": "DATE", "start": start["value"]["value"], "count": int(quantity),
                                        "unit": "MONTHS" if count["unit"] == "months" else "DAYS",
                                        "day_type": "BUSINESS" if count["unit"] == "business_days" else "CALENDAR",
                                        "include_start": rule["include_start"], "month_end": rule["month_end"], "weekend": rule["weekend"],
                                        "holidays": rule["holidays"], "holiday_calendar_complete": rule["holiday_calendar_complete"]})
                                    due, due_status, due_reason = answer["date"], "CALCULATED_CANDIDATE", None
                    except CoreError as exc:
                        if exc.code in {"YENIDEN_INCELE", "KAYNAK_KAPSAMI", "BILGI_DUZLEMI", "IS_KAYDI_BOZUK"}:
                            raise
                        due_reason = exc.code + ": " + str(exc)
                obligation_events = []
                for event_record, in db.execute("SELECT record_id FROM gerceklesmeler WHERE case_id=? AND obligation_id=? ORDER BY record_id", [case, rid]).fetchall():
                    event_id = str(event_record)
                    event_payload = self._business_payload(db, "gerceklesmeler", case, event_id)
                    event_spec = checked("p6_business_event", event_payload["spec"])
                    event_source = self._business_source(db, case, event_spec["source_node_id"], policy_version, require_current=False)
                    event_state = self._business_freshness(db, case, event_id, event_source)
                    if state != "CURRENT_CANDIDATE" or event_payload["policy_version"] != policy_version:
                        event_state = "NEEDS_REVIEW"
                    event = {"event_id": event_id, "obligation_id": rid, "description": event_spec["description"],
                        "event_kind": "REPORTED_EVENT" if event_source["node_kind"] == "USER_STATEMENT" else "DOCUMENT_BACKED_REPORT",
                        "state": event_state, "reports_completion": event_spec["reports_completion"], "actual_completion_verified": False,
                        "meaning_status": "UNVERIFIED", "provenance": event_source["provenance"], "source_excerpt": self._excerpt(event_source)}
                    if event_spec["event_date_fact_id"]:
                        date_fact = by_id.get(event_spec["event_date_fact_id"])
                        if date_fact is None or date_fact["state"] != "CURRENT_CANDIDATE":
                            event["state"] = "NEEDS_REVIEW"
                        event["event_date"] = date_fact["value"]["value"] if date_fact else None
                    events.append(event)
                    obligation_events.append(event)
                claims = [event for event in obligation_events if event["state"] == "CURRENT_CANDIDATE" and event["reports_completion"]]
                obligations.append({"obligation_id": rid, "scope_key": scope, "description": spec["description"],
                    "completion_criterion": spec["completion_criterion"], "obligated_party": spec["obligated_party"], "state": state,
                    "due_date": due, "due_status": due_status, "missing_due_reason": due_reason, "start_plane": start_plane,
                    "date_position": "PAST_DUE_CANDIDATE" if due and date.fromisoformat(due) < today else "DUE_TODAY_CANDIDATE" if due == as_of else "UPCOMING_CANDIDATE" if due else "UNRESOLVED",
                    "completion_claim_ids": [event["event_id"] for event in claims], "closed": False, "close_allowed": False,
                    "meaning_status": "UNVERIFIED", "provenance": source["provenance"], "source_excerpt": self._excerpt(source)})
            history = []
            def selected(rows, key):
                visible = []
                for row in rows:
                    version = row["provenance"].get("version_id")
                    if version is not None and version not in versions:
                        if row["state"] == "CURRENT_CANDIDATE":
                            raise CoreError("KAYNAK_KAPSAMI", "Güncel iş kaydı kaynağı seçilen sürümler dışında")
                        history.append({"record_id": row[key], "state": row["state"], "source_version_id": version})
                    else:
                        visible.append(row)
                return visible
            facts = selected(facts, "fact_id")
            obligations = selected(obligations, "obligation_id")
            events = selected(events, "event_id")
            visible_obligations = {row["obligation_id"] for row in obligations}
            for event in events[:]:
                if event["obligation_id"] not in visible_obligations:
                    history.append({"record_id": event["event_id"], "state": "NEEDS_REVIEW", "source_version_id": event["provenance"].get("version_id")})
                    events.remove(event)
            sources_current = True
            for version in versions:
                _, _, _, current = self._verification_source(db, case, version)
                sources_current = sources_current and current
            return {"schema_version": VERSION, "case_id": case, "context_version": revision, "as_of": as_of,
                "facts": facts, "comparisons": self._compare(facts), "obligations": obligations, "events": events,
                "history": history, "all_selected_sources_current": sources_current,
                "business_approval": "NOT_GRANTED", "critical_analysis_allowed": False, "automated_monitoring": False,
                "limitations": ["Sayı/tarih dönüşümü kaynak aralığına bağlıdır; alan/düzlem/olay yorumu UNVERIFIED.",
                    "Tarih konumu hukuki ihlal kararı, olay kaydı tamamlanma kabulü değildir.",
                    "Sorumlu bilinmiyorsa null; bildirim, dış işlem ve otomatik takip kurulmadı."]}
