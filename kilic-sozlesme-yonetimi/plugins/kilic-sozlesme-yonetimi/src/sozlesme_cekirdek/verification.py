"""Scoped append-only verification. Text match/render/user observation never grants authority."""
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from .errors import CoreError
from .safety import canonical, confined, hash_file, hash_value, native_path, uuid_text, read_verified_bytes

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0"
MAX_CONTROLS = 256
MAX_OBSERVATIONS = 3


@lru_cache
def validator(name):
    schema = json.loads((ROOT / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_control(report):
    if not validator("p2_verification").is_valid(report):
        raise CoreError("SEMA_HATASI", "Kapsamlı P2 kontrol kaydı şemaya uymuyor")
    scope = report["scope"]
    if hashlib.sha256(scope["expected_text"].encode("utf-8")).hexdigest() != scope["text_sha256"]:
        raise CoreError("KONTROL_BOZUK", "Kontrol alıntı hash'i değişmiş")
    if scope["start"] > scope["end"]:
        raise CoreError("KONTROL_BOZUK", "Kontrol aralığı ters")
    if report["method"] != "PDF_PAGE_RENDER":
        match = report["observed_text"] == scope["expected_text"]
        expected = "PASS" if report["method"] == "EXTRACTED_TEXT_MATCH" else "PARTIAL"
        if not scope["expected_text"] or report["comparison_match"] != match or report["outcome"] != (expected if match else "FAIL"):
            raise CoreError("KONTROL_BOZUK", "Kontrol sonucu metin karşılaştırmasıyla tutarsız")
    return report


def validate_policy(policy):
    if not isinstance(policy, str) or not 1 <= len(policy) <= 100:
        raise CoreError("GECERSIZ_GIRDI", "Doğrulama politika sürümü gerekli")


def reading_profile(kind, policy):
    from .readers import dependency_profile
    from .runtime_identity import reader_build_identity
    validate_policy(policy)
    settings = {"format": kind, "dependencies": dependency_profile(kind), "reader_build_digest": reader_build_identity(kind=kind),
                "reader_version": "1.0", "worker_timeout_seconds": 30,
                "read_only": True, "ocr": "NEVER_IMPLICIT"}
    return settings, hash_value({"tool": "p2-" + kind.lower(), "tool_version": "1.0",
                                 "settings": settings, "validation_version": "p2-1.0",
                                 "policy_version": policy, "result_schema": "P2"})


def renderer_profile():
    return canonical({name: importlib.metadata.version(name) for name in ("pypdfium2", "Pillow")})


def control_digest(method, request, reading_id, reading_digest, reader_profile, policy,
                   artifact, parent, observation, actual, version=VERSION):
    return hash_value({"method": method, "verifier_version": version, "request": request,
                       "reading_id": reading_id, "reading_digest": reading_digest,
                       "reader_profile": reader_profile, "policy": policy,
                       "renderer_profile": artifact["renderer_profile"] if artifact else None,
                       "parent_control_id": parent, "observation": observation, "observed_text": actual})


def png_info(png):
    from PIL import Image
    if not isinstance(png, bytes) or not 0 < len(png) <= 16 * 1024 * 1024 or not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise CoreError("RENDER_HATASI", "PNG biçimi veya çıktı boyutu uygun değil")
    try:
        with Image.open(io.BytesIO(png)) as im:
            if im.format != "PNG" or not all(0 < n <= 2000 for n in im.size):
                raise CoreError("RENDER_HATASI", "PNG boyut sınırı")
            size = im.size
            im.verify()
        return size
    except CoreError:
        raise
    except Exception as exc:
        raise CoreError("RENDER_HATASI", "PNG bütünlük denetimi başarısız") from exc


def bounded_render(data, page):
    from .readers.process_budget import run_bounded_worker
    if not isinstance(data, bytes) or len(data) > 16 * 1024 * 1024:
        raise CoreError("BELGE_SINIRI", "PDF render kaynak sınırı")
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    try:
        completed = run_bounded_worker([sys.executable, "-m", "sozlesme_cekirdek.verification_worker", str(page)],
                                       data, environment, stdout_limit=16 * 1024 * 1024)
    except CoreError as exc:
        if exc.code == "OKUMA_ZAMAN_SINIRI":
            raise CoreError("RENDER_ZAMAN_SINIRI", "Hedefli render süre bütçesinde sonlandırıldı") from exc
        raise
    if completed.returncode:
        raise CoreError("RENDER_HATASI", "Hedefli PDF render başarısız")
    png_info(completed.stdout)
    return completed.stdout


class VerificationMixin:
    def _verification_source(self, db, case_id, version_id, *, current=False):
        self._source(db, case_id, version_id, {"VERSION"})
        self._check_version_access(db, case_id, version_id)
        sha, key, original, document = db.execute(
            "SELECT sha256,storage_key,original_path,document_id FROM belge_surumu WHERE case_id=? AND record_id=?",
            [case_id, version_id]).fetchone()
        data = read_verified_bytes(confined(self.system / key, [self.output_root]))
        if hashlib.sha256(data).hexdigest() != sha:
            raise CoreError("KAYNAK_BOZUK", "Kontrol kaynağı snapshot hash'i farklı")
        source_current = hash_file(confined(original, self.source_roots)) == sha
        if current and not source_current:
            raise CoreError("KAYNAK_GUNCEL_DEGIL", "Kaynak dosya değişmiş; yeni sürümü al ve yeniden doğrula")
        return data, sha, str(document), source_current

    def _verification_reading(self, db, case_id, version_id, processing_id, data):
        from .readers import validate_reading
        row = db.execute("SELECT result,profile_digest,tool FROM isleme_calismalari WHERE case_id=? AND record_id=? AND document_version_id=?",
                         [case_id, processing_id, version_id]).fetchone()
        if not row or row[2] not in {"p2-docx", "p2-pdf", "p2-xlsx", "p2-eml"}:
            raise CoreError("KAYNAK_KAPSAMI", "P2 okuma kaydı gerekli")
        report = validate_reading(json.loads(row[0]), data)
        if row[2] != "p2-" + report["format"].lower():
            raise CoreError("KONTROL_BOZUK", "Okuma aracı/format farklı")
        return report, row[1]

    @staticmethod
    def _target(reading, request, *, allow_empty=False):
        if not validator("p2_verification_request").is_valid(request):
            raise CoreError("SEMA_HATASI", "P2 hedef kontrol isteği şemaya uymuyor")
        if reading["format"] != request["format"]:
            raise CoreError("DOSYA_TURU", "İstek ve okuma biçimi farklı")
        unit = next((x for x in reading["units"] if x["unit_id"] == request["unit_id"]), None)
        if unit is None or unit["views"][request["view"]] is None:
            raise CoreError("KAYNAK_KONUMU", "Kontrol birimi/görünümü kaynakta yok")
        text = unit["views"][request["view"]]
        start, end = request["start"], request["end"]
        if not 0 <= start <= end <= len(text) or end - start > 20000:
            raise CoreError("KAYNAK_KONUMU", "Kontrol aralığı görünüm dışında")
        if not allow_empty and (start == end or not request["expected_text"]):
            raise CoreError("KAYNAK_KONUMU", "Metin kontrolünde boş alıntı yok")
        return unit, text[start:end]

    @staticmethod
    def _invalid(db, case_id, ids):
        return any(db.execute("SELECT 1 FROM gecersizlestirmeler WHERE case_id=? AND target_id=? LIMIT 1", [case_id, rid]).fetchone() for rid in ids)

    def _load_control(self, db, case_id, version_id, control_id, data, source_current, policy, _seen=None):
        seen = set() if _seen is None else set(_seen)
        if control_id in seen or len(seen) >= 2:
            raise CoreError("KONTROL_BOZUK", "Render gözlem bağımlılığı döngülü/çok derin")
        seen.add(control_id)
        row = db.execute("SELECT payload,artifact,artifact_sha256,request_digest,method,outcome,reading_id,parent_control_id,CAST(checked_at AS VARCHAR) FROM dogrulamalar WHERE case_id=? AND document_version_id=? AND record_id=?",
                         [case_id, version_id, control_id]).fetchone()
        if not row:
            raise CoreError("KAYNAK_KAPSAMI", "Kontrol bu case ve belge sürümünde değil")
        report = validate_control(json.loads(row[0]))
        document = str(db.execute("SELECT document_id FROM belge_surumu WHERE case_id=? AND record_id=?", [case_id, version_id]).fetchone()[0])
        if (report["verification_id"] != control_id or report["case_id"] != case_id or report["version_id"] != version_id
                or report["request_digest"] != row[3] or report["method"] != row[4] or report["outcome"] != row[5]
                or report["processing_id"] != str(row[6]) or report["parent_control_id"] != (str(row[7]) if row[7] else None)
                or report["document_id"] != document or datetime.fromisoformat(report["checked_at"]) != datetime.fromisoformat(row[8])):
            raise CoreError("KONTROL_BOZUK", "Kontrol zarfı ve kayıt sütunları farklı")
        own = db.execute("SELECT result,profile_digest,status FROM isleme_calismalari WHERE case_id=? AND record_id=? AND document_version_id=?",
                         [case_id, control_id, version_id]).fetchone()
        if not own or json.loads(own[0]) != report or own[1] != report["request_digest"] or own[2] != "PARTIAL":
            raise CoreError("KONTROL_BOZUK", "Kontrol işleme kaydı farklı")
        reading, stored_profile = self._verification_reading(db, case_id, version_id, report["processing_id"], data)
        if hash_value(reading) != report["reading_digest"] or stored_profile != report["reader_profile_digest"]:
            raise CoreError("KONTROL_BOZUK", "Kontrolün okuma bağımlılığı değişmiş")
        request = {key: report["scope"][key] for key in ("unit_id", "view", "start", "end", "expected_text", "field_kind")}
        request["format"] = report["format"]
        unit, extracted = self._target(reading, request, allow_empty=report["method"] != "EXTRACTED_TEXT_MATCH")
        if report["method"] == "EXTRACTED_TEXT_MATCH" and extracted != report["observed_text"]:
            raise CoreError("KONTROL_BOZUK", "Kaydedilen karşılaştırma kaynak aralığına uymuyor")
        if report["issues"] != reading["issues"]:
            raise CoreError("KONTROL_BOZUK", "Okuma sorunları kontrol kaydından düşürülmüş")
        digest = control_digest(report["method"], request, report["processing_id"], report["reading_digest"],
                                stored_profile, report["policy_version"], report["artifact"], report["parent_control_id"],
                                report["observation"], report["observed_text"], report["method_version"])
        if digest != report["request_digest"]:
            raise CoreError("KONTROL_BOZUK", "Kontrol kapsamı/parmakizi farklı")
        dependencies = [{"record_id": version_id, "digest": reading["sha256"], "purpose": "SOURCE"},
                        {"record_id": report["processing_id"], "digest": hash_value(reading), "purpose": "READING"}]
        if report["parent_control_id"]:
            dependencies.append({"record_id": report["parent_control_id"], "digest": report["artifact"]["sha256"], "purpose": "RENDER"})
        if dependencies != report["dependencies"]:
            raise CoreError("KONTROL_BOZUK", "Kontrol kaynak bağımlılıkları farklı")
        if report["scope"]["locator"] != unit["locator"] or report["source_sha256"] != reading["sha256"]:
            raise CoreError("KONTROL_BOZUK", "Kaynak konumu/hash'i farklı")
        if report["artifact"] and report["artifact"]["page"] != unit["locator"]["page"]:
            raise CoreError("KONTROL_BOZUK", "Render sayfası kaynak birimiyle farklı")
        if row[1] is not None:
            png = bytes(row[1])
            width, height = png_info(png)
            artifact = report["artifact"]
            if (hashlib.sha256(png).hexdigest() != row[2] or artifact["sha256"] != row[2]
                    or artifact["size_bytes"] != len(png) or (artifact["width"], artifact["height"]) != (width, height)):
                raise CoreError("KONTROL_BOZUK", "Render görüntüsü bütünlüğü farklı")
        reasons = []
        if not source_current:
            reasons.append("SOURCE_FILE_CHANGED")
        if policy != report["policy_version"]:
            reasons.append("POLICY_VERSION_CHANGED")
        if reading_profile(report["format"], policy)[1] != stored_profile:
            reasons.append("READING_PROFILE_CHANGED")
        if report["method_version"] != VERSION:
            reasons.append("VERIFIER_VERSION_CHANGED")
        if report["artifact"] and report["artifact"]["renderer_profile"] != renderer_profile():
            reasons.append("RENDERER_PROFILE_CHANGED")
        ids = [version_id, report["processing_id"], control_id]
        if report["parent_control_id"]:
            parent, _, parent_reasons, _ = self._load_control(db, case_id, version_id, report["parent_control_id"], data, source_current, policy, seen)
            if (parent["method"] != "PDF_PAGE_RENDER" or parent["artifact"] != report["artifact"]
                    or any(parent["scope"][key] != report["scope"][key] for key in ("unit_id", "locator", "view", "start", "end", "expected_text", "field_kind"))):
                raise CoreError("KONTROL_BOZUK", "Gözlem render bağımlılığı farklı")
            reasons.extend(parent_reasons)
        if self._invalid(db, case_id, ids):
            reasons.append("DEPENDENCY_INVALIDATED")
        return report, "NEEDS_REVIEW" if reasons else "CURRENT_SCOPE_ONLY", sorted(set(reasons)), bytes(row[1]) if row[1] is not None else None

    def _write_control(self, db, case_id, version_id, processed, reading, profile, document, unit,
                       request, policy, method, *, actual=None, artifact=None, png=None, parent=None, observation=None):
        digest = control_digest(method, request, processed, hash_value(reading), profile, policy, artifact, parent, observation, actual)
        existing = db.execute("SELECT record_id FROM dogrulamalar WHERE case_id=? AND document_version_id=? AND request_digest=?", [case_id, version_id, digest]).fetchone()
        if existing:
            data, _, _, current = self._verification_source(db, case_id, version_id, current=True)
            saved, state, reasons, _ = self._load_control(db, case_id, version_id, str(existing[0]), data, current, policy)
            if reasons:
                raise CoreError("YENIDEN_INCELE", "Eski kontrol bağımlılığı geçerli değil")
            return {"verification_id": saved["verification_id"], "result": saved, "reused": True, "state": state}
        count = db.execute("SELECT count(*) FROM dogrulamalar WHERE case_id=? AND document_version_id=?", [case_id, version_id]).fetchone()[0]
        if count >= MAX_CONTROLS:
            raise CoreError("DOGRULAMA_BUTCESI", "Sürüm kontrol bütçesi doldu; otomatik deneme durdu")
        if parent:
            count = db.execute("SELECT count(*) FROM dogrulamalar WHERE case_id=? AND parent_control_id=?", [case_id, parent]).fetchone()[0]
            if count >= MAX_OBSERVATIONS:
                raise CoreError("DOGRULAMA_BUTCESI", "Hedef render için üç gözlem sınırı doldu; yeniden deneme durdu")
        match = actual == request["expected_text"] if actual is not None else None
        outcome = ("PASS" if match else "FAIL") if method == "EXTRACTED_TEXT_MATCH" else "NOT_RUN" if method == "PDF_PAGE_RENDER" else "PARTIAL" if match else "FAIL"
        scope_kind = {"EXTRACTED_TEXT_MATCH": "EXTRACTED_RANGE_ONLY", "PDF_PAGE_RENDER": "TARGET_PAGE_IMAGE_ONLY", "LOCAL_VISUAL_OBSERVATION": "LOCAL_REVIEW_OBSERVATION_ONLY"}[method]
        limitations = ["DOCUMENT_WIDE_FIDELITY_NOT_VERIFIED", "SEMANTIC_LEGAL_AND_AUTHORITY_NOT_VERIFIED", "FIELD_CLASSIFICATION_NOT_VERIFIED"]
        limitations.append("TEXT_MATCH_IS_NOT_SOURCE_IMAGE_VERIFICATION" if method == "EXTRACTED_TEXT_MATCH" else "RENDER_CREATION_IS_NOT_VISUAL_REVIEW" if method == "PDF_PAGE_RENDER" else "REVIEWER_IDENTITY_AND_OBSERVATION_NOT_AUTHENTICATED")
        if reading["format"] == "XLSX":
            limitations.append("FORMULAS_NOT_RECALCULATED")
        if reading["format"] == "DOCX":
            limitations.append("PROJECTION_IS_NOT_REVISION_ACCEPTANCE")
        control_id = str(uuid4())
        dependencies = [{"record_id": version_id, "digest": reading["sha256"], "purpose": "SOURCE"},
                        {"record_id": processed, "digest": hash_value(reading), "purpose": "READING"}]
        if parent:
            dependencies.append({"record_id": parent, "digest": artifact["sha256"], "purpose": "RENDER"})
        scope = {key: request[key] for key in ("unit_id", "view", "start", "end", "expected_text", "field_kind")}
        scope.update(locator=unit["locator"], text_sha256=hashlib.sha256(request["expected_text"].encode("utf-8")).hexdigest(),
                     field_kind_trust="CALLER_CLASSIFICATION_UNVERIFIED", scope_kind=scope_kind)
        # Keep all inherited issues, including enclosing DOCX structures and other pages.
        # A scoped control must not erase the original reader's blocking limitations.
        issues = reading["issues"]
        now = datetime.now(timezone.utc)
        report = dict(schema_version="2.1", verification_id=control_id, case_id=case_id, document_id=document,
                      version_id=version_id, processing_id=processed, source_sha256=reading["sha256"],
                      reading_digest=hash_value(reading), reader_profile_digest=profile, policy_version=policy,
                      method=method, method_version=VERSION, request_digest=digest, checked_at=now.isoformat(),
                      format=reading["format"], scope=scope, outcome=outcome, comparison_match=match, observed_text=actual,
                      artifact=artifact, observation=observation, parent_control_id=parent, issues=issues,
                      unverified_aspects=limitations, dependencies=dependencies,
                      dimensions={"integrity": "PASS", "coverage": "PARTIAL", "source_fidelity": "PARTIAL", "semantic": "NOT_RUN", "visual": "PARTIAL" if observation else "NOT_RUN"},
                      critical_analysis_allowed=False, authority="NOT_VERIFIED", revision_acceptance=False,
                      stop_reason="SCOPE_FINISHED_NO_AUTOMATIC_FALLBACK" if method == "EXTRACTED_TEXT_MATCH" else "WAITING_FOR_SOURCE_IMAGE_REVIEW" if not observation else "LOCAL_OBSERVATION_RECORDED_IDENTITY_UNVERIFIED")
        validate_control(report)
        self._record(db, case_id, "PROCESSING", control_id)
        db.execute("INSERT INTO isleme_calismalari VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [case_id, control_id, version_id, digest, "p2-verifier", VERSION, hash_value(request), "p2-verifier-1.0", policy, canonical(report), "PARTIAL", now])
        db.execute("INSERT INTO dogrulamalar VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [case_id, control_id, version_id, processed, parent, digest, method, outcome, canonical(report), now, png, artifact["sha256"] if png is not None else None])
        for dep in dependencies:
            db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)", [case_id, control_id, dep["record_id"], canonical(scope)])
        self._event(db, case_id, "READ_VERIFICATION_SCOPED", {"verification_id": control_id, "method": method, "outcome": outcome})
        self._bump(db, case_id)
        return {"verification_id": control_id, "result": report, "reused": False, "state": "CURRENT_SCOPE_ONLY"}

    def _verify_target(self, case_id, version_id, *, request, expected_revision, policy_version, render):
        if not validator("p2_verification_request").is_valid(request):
            raise CoreError("SEMA_HATASI", "Kontrol isteği şemaya uymuyor")
        case_id, version_id = map(uuid_text, (case_id, version_id))
        if render and request["format"] != "PDF":
            raise CoreError("DOSYA_TURU", "Bu dilimde yalnız PDF hedefli render destekleniyor")
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            self._verification_source(db, case_id, version_id, current=True)
        processed = self.read_document(case_id, version_id, format=request["format"], policy_version=policy_version)
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            data, sha, document, _ = self._verification_source(db, case_id, version_id, current=True)
            reading, profile = self._verification_reading(db, case_id, version_id, processed["processing_id"], data)
            if profile != reading_profile(request["format"], policy_version)[1] or self._invalid(db, case_id, [version_id, processed["processing_id"]]):
                raise CoreError("YENIDEN_INCELE", "Okuma profili/bağımlılığı güncel değil")
            unit, actual = self._target(reading, request, allow_empty=render)
            if not render:
                return self._write_control(db, case_id, version_id, processed["processing_id"], reading, profile, document, unit, request, policy_version, "EXTRACTED_TEXT_MATCH", actual=actual)
            # Find a matching render before invoking the native worker again.
            existing = db.execute("SELECT record_id FROM dogrulamalar WHERE case_id=? AND document_version_id=? AND method='PDF_PAGE_RENDER'", [case_id, version_id]).fetchall()
            for rid, in existing:
                saved, state, reasons, _ = self._load_control(db, case_id, version_id, str(rid), data, True, policy_version)
                if not reasons and saved["processing_id"] == processed["processing_id"] and all(saved["scope"][k] == request[k] for k in ("unit_id", "view", "start", "end", "expected_text", "field_kind")):
                    return {"verification_id": str(rid), "result": saved, "reused": True, "state": state}
            if unit["kind"] != "PDF_PAGE" or not unit["locator"]["page"]:
                raise CoreError("KAYNAK_KONUMU", "PDF kaynak sayfası gerekli")
            if db.execute("SELECT count(*) FROM dogrulamalar WHERE case_id=? AND document_version_id=?", [case_id, version_id]).fetchone()[0] >= MAX_CONTROLS:
                raise CoreError("DOGRULAMA_BUTCESI", "Render başlamadan sürüm kontrol bütçesi doldu")
            png = bounded_render(data, unit["locator"]["page"])
            width, height = png_info(png)
            artifact = {"sha256": hashlib.sha256(png).hexdigest(), "size_bytes": len(png), "page": unit["locator"]["page"], "width": width, "height": height, "mime_type": "image/png", "renderer_profile": renderer_profile()}
            # Recheck source after the native worker, before any control is published.
            self._verification_source(db, case_id, version_id, current=True)
            return self._write_control(db, case_id, version_id, processed["processing_id"], reading, profile, document, unit, request, policy_version, "PDF_PAGE_RENDER", artifact=artifact, png=png)

    def verify_excerpt(self, case_id, version_id, *, request, expected_revision, policy_version="1"):
        return self._verify_target(case_id, version_id, request=request, expected_revision=expected_revision, policy_version=policy_version, render=False)

    def prepare_pdf_review(self, case_id, version_id, *, request, expected_revision, policy_version="1"):
        return self._verify_target(case_id, version_id, request=request, expected_revision=expected_revision, policy_version=policy_version, render=True)

    def record_review_observation(self, case_id, version_id, *, observation, expected_revision, policy_version="1"):
        if not validator("p2_review_observation").is_valid(observation):
            raise CoreError("SEMA_HATASI", "Yerel inceleme gözlemi şemaya uymuyor")
        case_id, version_id = map(uuid_text, (case_id, version_id))
        parent_id = uuid_text(observation["render_control_id"])
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            data, _, document, current = self._verification_source(db, case_id, version_id, current=True)
            parent, _, reasons, _ = self._load_control(db, case_id, version_id, parent_id, data, current, policy_version)
            if reasons:
                raise CoreError("YENIDEN_INCELE", "Render kaydı bağımlılığı yeniden doğrulanmalı")
            if parent["method"] != "PDF_PAGE_RENDER" or parent["artifact"]["sha256"] != observation["artifact_sha256"]:
                raise CoreError("KONTROL_BOZUK", "Gözlem doğru render görüntüsüne bağlı değil")
            if not parent["scope"]["expected_text"]:
                raise CoreError("HEDEFLI_KANIT_GEREKLI", "Boş metinli/taranmış sayfanın görüntüsü saklanır; bu dilimde metin sadakati gözlemi için hedefli kanıt gerekli")
            reading, profile = self._verification_reading(db, case_id, version_id, parent["processing_id"], data)
            request = {k: parent["scope"][k] for k in ("unit_id", "view", "start", "end", "expected_text", "field_kind")}
            request["format"] = "PDF"
            unit, _ = self._target(reading, request, allow_empty=True)
            review = {"reviewer_label": observation["reviewer_label"], "identity_status": "UNVERIFIED_LOCAL_LABEL", "note": observation["note"], "trust": "UNVERIFIED_LOCAL_OBSERVATION"}
            return self._write_control(db, case_id, version_id, parent["processing_id"], reading, profile, document, unit, request, policy_version, "LOCAL_VISUAL_OBSERVATION", actual=observation["observed_text"], artifact=parent["artifact"], parent=parent_id, observation=review)

    def verification_history(self, case_id, version_id, *, policy_version="1"):
        case_id, version_id = map(uuid_text, (case_id, version_id))
        validate_policy(policy_version)
        with self._db() as db:
            self._case(db, case_id)
            data, _, _, current = self._verification_source(db, case_id, version_id)
            ids = db.execute("SELECT record_id FROM dogrulamalar WHERE case_id=? AND document_version_id=? ORDER BY checked_at,record_id", [case_id, version_id]).fetchall()
            controls = []
            for rid, in ids:
                report, state, reasons, _ = self._load_control(db, case_id, version_id, str(rid), data, current, policy_version)
                controls.append({"result": report, "state": state, "review_reasons": reasons})
            return {"case_id": case_id, "version_id": version_id, "controls": controls, "verification_status": "PARTIAL", "critical_analysis_allowed": False, "authority": "NOT_VERIFIED"}

    def review_image(self, case_id, version_id, control_id, *, expected_sha256, policy_version="1"):
        case_id, version_id, control_id = map(uuid_text, (case_id, version_id, control_id))
        with self._db() as db:
            self._case(db, case_id)
            data, _, _, current = self._verification_source(db, case_id, version_id, current=True)
            report, _, reasons, png = self._load_control(db, case_id, version_id, control_id, data, current, policy_version)
            if reasons:
                raise CoreError("YENIDEN_INCELE", "Render güncel değil; yeniden doğrula")
            if not png or report["artifact"]["sha256"] != expected_sha256:
                raise CoreError("KONTROL_BOZUK", "Görüntü kimliği/hash'i farklı")
            return png
