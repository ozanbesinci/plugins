"""Shared P4 gates. Issuance/execution are restricted to isolated synthetic test runtimes.

Email sending is removed. There is no production identity, permission issuer or writer.
The agent-facing Store/CLI can evaluate plans, but cannot mint or execute permissions.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import json
import os
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from .errors import CoreError
from .safety import canonical, confined, hash_file, hash_value, native_path, uuid_text
from .verification import reading_profile

VERSION = "p4-1.1"
ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "tests" / ".runtime"
MAX_OPERATIONS = 256
MAX_DECISIONS = 2048
MAX_ARTIFACT = 16 * 1024 * 1024
FORBIDDEN = {"SIGN_CONTRACT", "INITIATE_PAYMENT", "RELEASE_GUARANTEE", "ACCEPT_RISK", "APPROVE_AS_LEGAL", "OVERWRITE_SOURCE", "SEND_EMAIL"}


@lru_cache
def validator(name):
    schema = json.loads((ROOT / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def checked(name, value):
    if not validator(name).is_valid(value):
        raise CoreError("SEMA_HATASI", "P4 şema sınırı ihlal edildi")
    return value


def action_request(request):
    if isinstance(request, dict) and isinstance(request.get("plan"), dict) and request["plan"].get("action_type") == "SEND_EMAIL":
        raise CoreError("EPOSTA_GONDERIM_KALDIRILDI", "E-posta gönderimi kullanıcı kararıyla kapsamdan kaldırıldı")
    checked("p4_action_request", request)
    if len(canonical(request).encode("utf-8")) > 65536:
        raise CoreError("BOYUT_SINIRI", "P4 istek sınırı 64 KiB")
    request = json.loads(canonical(request))  # Freeze caller objects; no lossy text normalization.
    plan = request["plan"]
    for field in ("case_id", "operation_id"):
        plan[field] = uuid_text(plan[field])
    versions = plan["source_versions"]
    for version in versions:
        version["version_id"] = uuid_text(version["version_id"])
    if len(versions) > 64 or len({x["version_id"] for x in versions}) != len(versions):
        raise CoreError("SEMA_HATASI", "Kaynak sürümü sayısı/tekrarı uygun değil")
    parameters, payload = plan["parameters"], request["payload"]
    path = parameters["target_relative_path"]
    parts = path.split("/")
    if (len(parts) < 2 or parts[0] != "ciktilar" or any(x in {"", ".", ".."} for x in parts)
            or "\\" in path or ":" in path or any(ord(char) < 32 for char in path)
            or any(x.endswith((".", " ")) or os.path.isreserved(x) for x in parts)):
        raise CoreError("HEDEF_KAPSAMI", "Yeni çıktı hedefi uygun değil")
    if Path(path).suffix.lower() != "." + parameters["output_format"].lower():
        raise CoreError("DOSYA_TURU", "Çıktı uzantısı ve biçimi farklı")
    if parameters["content_plan_sha256"] != hash_value(payload["content_plan"]):
        raise CoreError("PAYLOAD_HASH_FARKLI", "İçerik planı hash'i farklı")
    for change in payload["changes"]:
        for key in ("version_id", "reading_id"):
            change[key] = uuid_text(change[key])
    expected = hash_value(payload["changes"]) if payload["changes"] else None
    if parameters["change_plan_sha256"] != expected:
        raise CoreError("PAYLOAD_HASH_FARKLI", "Değişiklik planı hash'i farklı")
    if plan["action_type"] == "APPLY_TRACK_CHANGES" and not payload["changes"]:
        raise CoreError("HEDEFLI_KANIT_GEREKLI", "Revizyon hedefi ve beklenen eski metin gerekli")
    if plan["action_type"] != "APPLY_TRACK_CHANGES" and payload["changes"]:
        raise CoreError("SEMA_HATASI", "Bu işlem revizyon hedefi kabul etmez")
    content=payload["content_plan"]
    if content.get("comments") and plan["action_type"]!="APPLY_TRACK_CHANGES":
        raise CoreError("SEMA_HATASI", "Yeni yorumlar yalnız hedefli revizyon planıyla uygulanır")
    if "clean_copy" in content and plan["action_type"]!="CREATE_CLEAN_COPY":
        raise CoreError("SEMA_HATASI", "Nüsha seçim planı yalnız CREATE_CLEAN_COPY içindir")
    return request


def payload_digest(request):
    return hash_value(action_request(request))


@dataclass(frozen=True)
class TestIdentity:
    actor_id: str
    identity_epoch: str
    policy_version: str
    company_scope_id: str
    case_ids: frozenset
    allowed_actions: frozenset
    explicit_request_digest: str | None
    authenticated: bool = True
    corporate_authorized: bool = False
    quality_ready: bool = False


@dataclass(frozen=True)
class TestQA:
    passed: bool
    digest: str


class GuardMixin:
    def evaluate_action(self, *, request):
        return SyntheticGuardRuntime(self).evaluate(request=request)

    def action_status(self, case_id, operation_id):
        case, operation = uuid_text(case_id), uuid_text(operation_id)
        with self._db() as db:
            self._case(db, case)
            row, _ = SyntheticGuardRuntime(self)._operation(db, case, operation)
            return {"case_id": case, "operation_id": operation, "state": row[2], "artifact_sha256": row[3],
                    "retry_safety": "NO_REPLAY" if row[2] in {"SIMULATION_COMMITTED", "SIMULATED_PROVIDER_ACCEPTED", "FAILED"} else "RECONCILE_REQUIRED",
                    "execution_scope": "SYNTHETIC_TEST_ONLY", "production_ready": False}


class SyntheticGuardRuntime:
    """Internal host/test interface. Never exposed as an agent-facing permission JSON tool."""
    def __init__(self, store, *, identity_provider=None, backend=None, signing_key=None, clock=None):
        self.store, self.identity_provider, self.backend = store, identity_provider, backend
        self.key = signing_key
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self):
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise CoreError("GUARD_CLOCK_ERROR", "UTC saat gerekli")
        return now

    def _identity(self):
        if self.identity_provider is None or self.backend is None or not isinstance(self.key, bytes) or len(self.key) < 32:
            raise CoreError("CONFIG_REQUIRED", "Üretim kimlik/izin/writer adaptörü yapılandırılmadı")
        if not getattr(self.backend, "synthetic_only", False) or not isinstance(getattr(self.backend, "version", None), str):
            raise CoreError("TEST_SCOPE_REQUIRED", "Yalnız sentetik backend kabul edilir")
        # Both sources and outputs must stay in this project's isolated fixture area.
        confined(self.store.root, [TEST_ROOT])
        for source in self.store.source_roots:
            confined(source, [TEST_ROOT])
        identity = self.identity_provider()
        if (type(identity) is not TestIdentity or not identity.actor_id or not identity.identity_epoch or not identity.policy_version
                or type(identity.authenticated) is not bool or type(identity.corporate_authorized) is not bool or type(identity.quality_ready) is not bool
                or not isinstance(identity.case_ids, frozenset) or not isinstance(identity.allowed_actions, frozenset)):
            raise CoreError("IDENTITY_ADAPTER_ERROR", "Sentetik kimlik adaptörü uygun değil")
        self._now()
        return identity

    def _bind(self, db, request, identity, *, allow_published_target=False):
        plan, payload = request["plan"], request["payload"]
        case = plan["case_id"]
        revision = self.store._case(db, case)
        sources, snapshots, profiles = [], {}, {}
        for source in plan["source_versions"]:
            version = source["version_id"]
            data, sha, document, _ = self.store._verification_source(db, case, version, current=True)
            if source["sha256"] != sha:
                raise CoreError("KAYNAK_HASH_FARKLI", "İşlem kaynak hash'i farklı")
            if self.store._invalid(db, case, [version]) or db.execute("SELECT 1 FROM surum_ebeveynleri WHERE case_id=? AND parent_id=? LIMIT 1", [case, version]).fetchone():
                raise CoreError("YENIDEN_INCELE", "İşlem kaynağı eski/geçersiz")
            sources.append({"version_id": version, "document_id": document, "sha256": sha})
            snapshots[version] = data
        target = None
        target = confined(self.store.root / plan["parameters"]["target_relative_path"], [self.store.root])
        if native_path(target).exists() and not allow_published_target:
            raise CoreError("HEDEF_MEVCUT", "Yeni çıktı hedefi zaten var; üzerine yazılmadı")
        ranges = {}
        for change in payload["changes"]:
            version, reading_id = change["version_id"], change["reading_id"]
            if version not in snapshots or change["target"]["format"] != "DOCX":
                raise CoreError("KAYNAK_KAPSAMI", "Revizyon hedefi izinli DOCX kaynağına ait değil")
            reading, profile = self.store._verification_reading(db, case, version, reading_id, snapshots[version])
            if profile != reading_profile("DOCX", "1")[1] or self.store._invalid(db, case, [reading_id]):
                raise CoreError("YENIDEN_INCELE", "Revizyon okuma profili değişti")
            _, excerpt = self.store._target(reading, change["target"])
            if excerpt != change["target"]["expected_text"]:
                raise CoreError("KAYNAK_ALINTISI", "Revizyon öncesi hedef metin farklı")
            group = (version, change["target"]["unit_id"], change["target"]["view"])
            start, end = change["target"]["start"], change["target"]["end"]
            if any(start < old_end and old_start < end for old_start, old_end in ranges.get(group, [])):
                raise CoreError("HEDEF_BELIRSIZ", "Revizyon hedefleri örtüşüyor")
            ranges.setdefault(group, []).append((start, end))
            profiles[reading_id] = profile
        identity_digest = hash_value({"actor": identity.actor_id, "epoch": identity.identity_epoch,
                                      "company": identity.company_scope_id, "authenticated": identity.authenticated,
                                      "corporate_authorized": identity.corporate_authorized, "quality_ready": identity.quality_ready})
        binding = {"request": request, "workspace": str(self.store.root), "semantic_version": revision,
                   "source_documents": sources, "reading_profiles": profiles, "identity_digest": identity_digest,
                   "policy_version": identity.policy_version, "backend_version": self.backend.version, "guard_version": VERSION}
        return binding, snapshots, target

    @staticmethod
    def _policy(request, identity):
        plan = request["plan"]
        if not identity.authenticated:
            return "BLOCK", ["TEST_IDENTITY_NOT_AUTHENTICATED"]
        if plan["case_id"] not in identity.case_ids or request["payload"]["company_scope_id"] != identity.company_scope_id:
            return "BLOCK", ["ACTOR_CASE_SCOPE_MISMATCH"]
        if plan["action_type"] not in identity.allowed_actions:
            return "BLOCK", ["TECHNICAL_CAPABILITY_UNAVAILABLE"]
        if plan["source_versions"] and not identity.quality_ready:
            return "BLOCK", ["SOURCE_QUALITY_UNVERIFIED"]
        if identity.explicit_request_digest != hash_value(request):
            return "REQUIRE_CONFIRMATION", ["EXPLICIT_SCOPED_REQUEST_REQUIRED"]
        if plan["purpose"] == "APPROVED_OUTPUT" and not identity.corporate_authorized:
            return "ESCALATE", ["CORPORATE_AUTHORITY_NOT_CONFIGURED"]
        return "ALLOW", ["SYNTHETIC_TEST_SCOPE_ONLY"]

    def _emit(self, db, request, decision, reasons, *, fingerprint=None, stage="PRE_ACTION", enabled=False):
        plan = request["plan"]
        case, operation = plan["case_id"], plan["operation_id"]
        if db.execute("SELECT count(*) FROM eylem_kararlari WHERE case_id=?", [case]).fetchone()[0] >= MAX_DECISIONS:
            raise CoreError("GUARD_AUDIT_LIMIT", "Muhafız kayıt sınırı")
        rid = self.store._record(db, case, "PROCESSING")
        report = {"schema_version": VERSION, "case_id": case, "operation_id": operation, "decision_id": rid,
                  "stage": stage, "decision": decision, "reasons": reasons, "fingerprint": fingerprint,
                  "execution_scope": "SYNTHETIC_TEST_ONLY" if enabled else "DISABLED", "production_ready": False,
                  "authority": "NOT_VERIFIED_FOR_PRODUCTION", "audit_persisted": True}
        checked("p4_guard_decision", report)
        db.execute("INSERT INTO eylem_kararlari VALUES(?,?,?,?,?,?)", [case, rid, operation, stage, decision, canonical(report)])
        self.store._event(db, case, "ACTION_GUARD_" + stage, {"operation_id": operation, "decision": decision, "reasons": reasons})
        return report

    def _blocked(self, request, code, *, stage="PRE_ACTION"):
        try:
            plan = request["plan"]
            minimal = {"plan": {"case_id": uuid_text(plan["case_id"]), "operation_id": uuid_text(plan["operation_id"])}}
            with self.store._db() as db:
                self.store._case(db, minimal["plan"]["case_id"])
                return self._emit(db, minimal, "BLOCK", [code], stage=stage)
        except Exception:
            return {"schema_version": VERSION, "case_id": None, "operation_id": None, "decision_id": None,
                    "stage": stage, "decision": "BLOCK", "reasons": [code, "AUDIT_UNAVAILABLE"], "fingerprint": None,
                    "execution_scope": "DISABLED", "production_ready": False, "authority": "NOT_VERIFIED_FOR_PRODUCTION", "audit_persisted": False}

    def evaluate(self, *, request):
        try:
            if isinstance(request, dict) and request.get("plan", {}).get("action_type") in FORBIDDEN:
                return self._blocked(request, "ABSOLUTE_PROHIBITION")
            frozen = action_request(request)
            identity = self._identity()
            with self.store._db() as db:
                binding, _, _ = self._bind(db, frozen, identity)
                decision, reasons = self._policy(frozen, identity)
                return self._emit(db, frozen, decision, reasons, fingerprint=hash_value(binding), enabled=True)
        except Exception as exc:
            return self._blocked(request, exc.code if isinstance(exc, CoreError) else "GUARD_TECHNICAL_ERROR")

    def _sign(self, body):
        return hmac.new(self.key, b"P4_SYNTHETIC_PERMISSION\0" + canonical(body).encode("utf-8"), hashlib.sha256).hexdigest()

    def _permission(self, db, case, permission_id):
        row = db.execute("SELECT operation_id,fingerprint,state,payload,signature FROM islem_izinleri WHERE case_id=? AND record_id=?", [case, permission_id]).fetchone()
        if not row:
            raise CoreError("IZIN_YOK", "İzin bu case içinde değil")
        body = checked("p4_permission", json.loads(row[3]))
        if (body["case_id"] != case or body["permission_id"] != permission_id or body["operation_id"] != str(row[0])
                or body["fingerprint"] != row[1] or body["state"] != row[2] or not hmac.compare_digest(self._sign(body), row[4])):
            raise CoreError("IZIN_BOZUK", "İzin zarfı/imzası farklı")
        issued, expires = datetime.fromisoformat(body["issued_at"]), datetime.fromisoformat(body["expires_at"])
        if (expires <= issued or expires - issued > timedelta(minutes=15)
                or (body["state"] == "CONSUMED" and body["consumed_by"] != body["operation_id"])
                or (body["state"] != "CONSUMED" and body["consumed_by"] is not None)):
            raise CoreError("IZIN_BOZUK", "İzin süre/tüketim kapsamı uygun değil")
        return body

    def _save_permission(self, db, body):
        checked("p4_permission", body)
        db.execute("UPDATE islem_izinleri SET state=?,payload=?,signature=? WHERE case_id=? AND record_id=?",
                   [body["state"], canonical(body), self._sign(body), body["case_id"], body["permission_id"]])
        self.store._event(db, body["case_id"], "PERMISSION_" + body["state"], {"operation_id": body["operation_id"], "permission_id": body["permission_id"], "proof_digest": hash_value(body)})

    def _operation(self, db, case, operation):
        row = db.execute("SELECT request_digest,payload,state,artifact_sha256,quarantine_key,output_key,provider_ref FROM islemler WHERE case_id=? AND record_id=?", [case, operation]).fetchone()
        if not row:
            raise CoreError("ISLEM_YOK", "İşlem bu case içinde değil")
        payload = json.loads(row[1])
        if (set(payload) != {"request", "binding", "fingerprint"} or hash_value(payload) != row[0]
                or hash_value(payload["binding"]) != payload["fingerprint"] or payload["binding"]["request"] != payload["request"]
                or action_request(payload["request"]) != payload["request"] or payload["request"]["plan"]["case_id"] != case
                or payload["request"]["plan"]["operation_id"] != operation):
            raise CoreError("ISLEM_BOZUK", "İşlem kapsamı kaydı farklı")
        return row, payload

    def issue_permission(self, *, request, expected_revision, ttl_seconds=300):
        """Trusted test host only. A request JSON/statement cannot call this via the CLI."""
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900:
            raise CoreError("IZIN_SURESI", "İzin 1–900 saniye ile sınırlı")
        frozen, identity = action_request(request), self._identity()
        plan = frozen["plan"]
        case, operation = plan["case_id"], plan["operation_id"]
        with self.store._db() as db:
            self.store._case(db, case, expected_revision)
            binding, _, _ = self._bind(db, frozen, identity)
            decision, reasons = self._policy(frozen, identity)
            proof = self._emit(db, frozen, decision, reasons, fingerprint=hash_value(binding), enabled=True)
            if decision != "ALLOW":
                return {"permission_id": None, "decision": proof, "reused": False}
            old = db.execute("SELECT record_id FROM islemler WHERE case_id=? AND record_id=?", [case, operation]).fetchone()
            payload = {"request": frozen, "binding": binding, "fingerprint": hash_value(binding)}
            if old:
                row, previous = self._operation(db, case, operation)
                if previous != payload or row[2] != "AUTHORIZED":
                    raise CoreError("ISLEM_TEKRARI", "Değişmiş/başlamış işlem için yeni operation_id gerekli")
                existing = db.execute("SELECT record_id FROM islem_izinleri WHERE case_id=? AND operation_id=?", [case, operation]).fetchall()
                if len(existing) != 1:
                    raise CoreError("IZIN_BOZUK", "Tek işlem için tek izin gerekli")
                body = self._permission(db, case, str(existing[0][0]))
                if body["state"] != "ISSUED" or datetime.fromisoformat(body["expires_at"]) <= self._now():
                    raise CoreError("YENI_ISLEM_GEREKLI", "İptal/süre sonrası otomatik yeni izin yok")
                return {"permission_id": body["permission_id"], "decision": proof, "reused": True}
            if db.execute("SELECT count(*) FROM islemler WHERE case_id=?", [case]).fetchone()[0] >= MAX_OPERATIONS:
                raise CoreError("GUARD_OPERATION_LIMIT", "İşlem kayıt sınırı")
            self.store._record(db, case, "PROCESSING", record_id=operation)
            db.execute("INSERT INTO islemler VALUES(?,?,?,?,'AUTHORIZED',NULL,NULL,NULL,NULL)", [case, operation, hash_value(payload), canonical(payload)])
            for source in plan["source_versions"]:
                db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)", [case, operation, source["version_id"], canonical({"action": True})])
            permission = self.store._record(db, case, "PROCESSING")
            now = self._now()
            body = {"schema_version": VERSION, "permission_id": permission, "case_id": case, "operation_id": operation,
                    "fingerprint": payload["fingerprint"], "actor_id": identity.actor_id, "identity_digest": binding["identity_digest"],
                    "policy_version": identity.policy_version, "issued_at": now.isoformat(), "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(),
                    "state": "ISSUED", "execution_scope": "SYNTHETIC_TEST_ONLY", "consumed_by": None}
            checked("p4_permission", body)
            db.execute("INSERT INTO islem_izinleri VALUES(?,?,?,?,?,?,?)", [case, permission, operation, body["fingerprint"], "ISSUED", canonical(body), self._sign(body)])
            self.store._event(db, case, "PERMISSION_ISSUED", {"operation_id": operation, "permission_id": permission, "proof_digest": hash_value(body)})
            return {"permission_id": permission, "decision": proof, "reused": False}

    def revoke_permission(self, case_id, permission_id):
        self._identity()
        case, permission = uuid_text(case_id), uuid_text(permission_id)
        with self.store._db() as db:
            body = self._permission(db, case, permission)
            if body["state"] != "ISSUED":
                raise CoreError("IZIN_TUKETILMIS", "Yalnız kullanılmamış izin iptal edilebilir")
            self._save_permission(db, dict(body, state="REVOKED"))

    def _fresh(self, db, request, previous, *, allow_published_target=False, require_live_window=True):
        identity = self._identity()
        binding, sources, target = self._bind(db, request, identity, allow_published_target=allow_published_target)
        decision, reasons = self._policy(request, identity)
        if decision != "ALLOW":
            raise CoreError("GUARD_" + decision, ",".join(reasons))
        if hash_value(binding) != previous["fingerprint"]:
            raise CoreError("IZIN_KAPSAMI_DEGISTI", "Kaynak/kimlik/politika/plan/host kapsamı değişti")
        plan = request["plan"]
        permissions = db.execute("SELECT record_id FROM islem_izinleri WHERE case_id=? AND operation_id=?", [plan["case_id"], plan["operation_id"]]).fetchall()
        if len(permissions) != 1:
            raise CoreError("IZIN_BOZUK", "İşlem izin sayısı farklı")
        body = self._permission(db, plan["case_id"], str(permissions[0][0]))
        if (body["fingerprint"] != previous["fingerprint"] or body["actor_id"] != identity.actor_id
                or body["identity_digest"] != binding["identity_digest"] or body["policy_version"] != identity.policy_version):
            raise CoreError("IZIN_KAPSAMI_DEGISTI", "İzin ve canlı kapsam farklı")
        if self.store._invalid(db, plan["case_id"], [plan["operation_id"], body["permission_id"]]):
            raise CoreError("YENIDEN_INCELE", "İşlem/izin bağımlılığı geçersiz")
        if (body["state"] not in {"ISSUED", "CONSUMED"}
                or datetime.fromisoformat(body["issued_at"]) > self._now()
                or (require_live_window and datetime.fromisoformat(body["expires_at"]) <= self._now())):
            raise CoreError("IZIN_SURESI", "Yürütme/commit öncesi izin iptal/süre kontrolü geçmedi")
        return identity, sources, target

    def _stage(self, db, case, operation, expected, state, **values):
        row, _ = self._operation(db, case, operation)
        if row[2] not in expected:
            raise CoreError("ISLEM_DURUMU", "İşlem durumu değişmiş; kör tekrar yok")
        permitted = {"artifact_sha256", "quarantine_key", "output_key", "provider_ref"}
        if not set(values) <= permitted:
            raise CoreError("ISLEM_DURUMU", "İç durum alanı uygun değil")
        assignments = ["state=?"] + [key + "=?" for key in values]
        db.execute("UPDATE islemler SET " + ",".join(assignments) + " WHERE case_id=? AND record_id=?", [state, *values.values(), case, operation])
        self.store._event(db, case, "ACTION_" + state, {"operation_id": operation, **values})

    def execute(self, *, request, permission_id):
        """Reserve/consume before a backend effect. No production adapters accepted."""
        reserved, published = False, False
        stage = "PRE_ACTION"
        try:
            frozen, identity = action_request(request), self._identity()
            case, operation = frozen["plan"]["case_id"], frozen["plan"]["operation_id"]
            permission = uuid_text(permission_id)
            with self.store._db() as db:
                row, previous = self._operation(db, case, operation)
                if row[2] != "AUTHORIZED" or previous["request"] != frozen:
                    raise CoreError("ISLEM_TEKRARI", "Eski/değişmiş/başlamış işlem yeniden yürütülemez")
                body = self._permission(db, case, permission)
                if body["operation_id"] != operation or body["state"] != "ISSUED":
                    raise CoreError("IZIN_TUKETILMIS", "İzin farklı işlemin veya kullanılmış")
                if datetime.fromisoformat(body["expires_at"]) <= self._now() or datetime.fromisoformat(body["issued_at"]) > self._now():
                    raise CoreError("IZIN_SURESI", "İzin süresi geçerli değil")
                identity, sources, target = self._fresh(db, frozen, previous)
                if body["fingerprint"] != previous["fingerprint"] or body["actor_id"] != identity.actor_id or body["identity_digest"] != previous["binding"]["identity_digest"]:
                    raise CoreError("IZIN_KAPSAMI_DEGISTI", "İzin aktör/kapsam bağı farklı")
                if self.store._invalid(db, case, [operation, permission]):
                    raise CoreError("YENIDEN_INCELE", "İşlem veya izin geçersizleştirilmiş")
                self._save_permission(db, dict(body, state="CONSUMED", consumed_by=operation))
                self._stage(db, case, operation, {"AUTHORIZED"}, "EXECUTING")
                self._emit(db, frozen, "ALLOW", ["SYNTHETIC_PERMISSION_CONSUMED"], fingerprint=body["fingerprint"], enabled=True)
            reserved = True
            stage = "POST_ACTION"
            data = self.backend.prepare_document(frozen, sources)
            if not isinstance(data, bytes) or not data or len(data) > MAX_ARTIFACT:
                raise CoreError("QA_FAILED", "Çıktı baytları sınır dışında")
            digest = hashlib.sha256(data).hexdigest()
            quarantine = confined(self.store.system / "eylem-karantina" / operation / "artifact.bin", [self.store.root])
            native_path(quarantine.parent).mkdir(parents=True, exist_ok=True)
            with native_path(quarantine).open("xb") as writer:
                writer.write(data)
                writer.flush()
                os.fsync(writer.fileno())
            key = quarantine.relative_to(self.store.system).as_posix()
            with self.store._db() as db:
                self._stage(db, case, operation, {"EXECUTING"}, "QUARANTINED", artifact_sha256=digest, quarantine_key=key)
            qa = self.backend.verify_document(frozen, data)
            if type(qa) is not TestQA or qa.passed is not True or qa.digest != digest or hash_file(quarantine) != digest:
                raise CoreError("QA_FAILED", "Çıktı QA/hash doğrulaması geçmedi")
            with self.store._db() as db:
                self._fresh(db, frozen, previous)
                self._stage(db, case, operation, {"QUARANTINED"}, "QA_PASSED")
                self._emit(db, frozen, "ALLOW", ["SYNTHETIC_OUTPUT_QA_ONLY"], stage=stage, fingerprint=previous["fingerprint"], enabled=True)
            stage = "COMPLETION"
            with self.store._db() as db:
                _, _, target = self._fresh(db, frozen, previous)
                confined(quarantine, [self.store.root])
                if hash_file(quarantine) != digest:
                    raise CoreError("QA_FAILED", "QA sonrası karantina değişmiş")
                native_path(target.parent).mkdir(parents=True, exist_ok=True)
                # Atomic exclusive publication on this same NTFS workspace; never replace().
                os.link(native_path(quarantine), native_path(target))
                published = True
                if hash_file(target) != digest:
                    raise CoreError("QA_FAILED", "Final çıktı hash'i farklı")
                self._fresh(db, frozen, previous, allow_published_target=True)
                persister = getattr(self.backend, "persist_document", None)
                if persister is not None:
                    persister(db, self.store, frozen, data, target)
                self._stage(db, case, operation, {"QA_PASSED"}, "SIMULATION_COMMITTED", output_key=target.relative_to(self.store.root).as_posix())
                proof = self._emit(db, frozen, "ALLOW", ["SIMULATION_COMPLETED_NOT_PRODUCTION_ACCEPTANCE"], stage=stage, fingerprint=previous["fingerprint"], enabled=True)
            return {"state": "SIMULATION_COMMITTED", "decision": proof, "output_path": str(target), "artifact_sha256": digest, "production_ready": False}
        except Exception as exc:
            code = exc.code if isinstance(exc, CoreError) else "GUARD_TECHNICAL_ERROR"
            if reserved:
                state = "RECONCILE_REQUIRED" if published else "FAILED"
                try:
                    with self.store._db() as db:
                        self._stage(db, case, operation, {"EXECUTING", "QUARANTINED", "QA_PASSED"}, state)
                except Exception:
                    state = "RECONCILE_REQUIRED"
                proof = self._blocked(request, code, stage=stage)
                return {"state": state, "decision": proof, "delivery_confirmed": False, "production_ready": False}
            return {"state": "BLOCKED", "decision": self._blocked(request, code), "delivery_confirmed": False, "production_ready": False}

    def completion_gate(self, case_id, operation_id):
        case, operation = uuid_text(case_id), uuid_text(operation_id)
        request = {"plan": {"case_id": case, "operation_id": operation}}
        try:
            self._identity()
            with self.store._db() as db:
                row, previous = self._operation(db, case, operation)
                request = previous["request"]
                permissions = db.execute("SELECT record_id FROM islem_izinleri WHERE case_id=? AND operation_id=?", [case, operation]).fetchall()
                if len(permissions) != 1 or self._permission(db, case, str(permissions[0][0]))["state"] != "CONSUMED":
                    raise CoreError("IZIN_BOZUK", "Tamamlanma tüketilmiş izin gerektirir")
                if row[2] != "SIMULATION_COMMITTED":
                    return self._emit(db, request, "BLOCK", ["NO_DOCUMENT_COMPLETION", row[2], "PROVIDER_ACCEPTANCE_IS_NOT_DELIVERY"], stage="COMPLETION", enabled=True)
                target = confined(self.store.root / row[5], [self.store.root])
                quarantine = confined(self.store.system / row[4], [self.store.root])
                if not native_path(target).is_file() or hash_file(target) != row[3] or hash_file(quarantine) != row[3]:
                    raise CoreError("QA_FAILED", "Teslim kaydı dosya/hash ile eşleşmiyor")
                # A completed effect can outlive its issuance window, but must still
                # match live access/policy/source scope. This cannot start a new effect.
                self._fresh(db, request, previous, allow_published_target=True, require_live_window=False)
                verifier = getattr(self.backend, "verify_completion", None)
                if verifier is not None:
                    verifier(db, self.store, request)
                return self._emit(db, request, "ALLOW", ["SIMULATION_COMPLETED_NOT_PRODUCTION_ACCEPTANCE"], stage="COMPLETION", fingerprint=previous["fingerprint"], enabled=True)
        except Exception as exc:
            return self._blocked(request, exc.code if isinstance(exc, CoreError) else "GUARD_TECHNICAL_ERROR", stage="COMPLETION")
