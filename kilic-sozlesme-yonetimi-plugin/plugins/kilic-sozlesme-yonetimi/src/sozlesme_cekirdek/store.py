from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone, date
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

import duckdb

from .errors import CoreError
from .safety import FileLock, confined, hash_file, hash_value, canonical, atomic_json, uuid_text, native_path, ordinary_path
from .schemas import validate
from .verification import VerificationMixin, reading_profile
from .context import ContextMixin
from .guard import GuardMixin
from .outputs import OutputMixin
from .business import BusinessMixin

NOW = lambda: datetime.now(timezone.utc)
MIGRATION = Path(__file__).parent / "migrations" / "001.sql"
MIGRATION_VERIFIER = Path(__file__).parent / "migrations" / "002.sql"
MIGRATION_CONTEXT = Path(__file__).parent / "migrations" / "003.sql"
MIGRATION_GUARD = Path(__file__).parent / "migrations" / "004.sql"
MIGRATION_DOCX = Path(__file__).parent / "migrations" / "005.sql"
MIGRATION_BUSINESS = Path(__file__).parent / "migrations" / "006.sql"


class Store(BusinessMixin, OutputMixin, GuardMixin, ContextMixin, VerificationMixin):
    """Short-lived sequential coordinator. Application boundary, NOT host sandbox/identity."""
    def __init__(self, workspace, *, source_roots, output_root, lock_timeout=5):
        self.output_root = Path(output_root).absolute()
        self.root = confined(workspace, [self.output_root])
        self.source_roots = tuple(Path(x).absolute() for x in source_roots)
        if not self.source_roots:
            raise CoreError("CONFIG_REQUIRED", "İzinli kaynak kökü gerekli")
        self.system = self.root / ".sistem"
        confined(self.system, [self.output_root])
        self.db_path = self.system / "sozlesme.duckdb"
        if os.name == "nt" and len(str(self.db_path).encode("utf-16-le")) // 2 > 240:
            raise CoreError("DB_YOL_SINIRI", "DuckDB dosya yolu bu Windows sürümünde en fazla 240 UTF-16 birimi olmalı; kısa çalışma klasörü gerekli")
        native_path(self.system).mkdir(parents=True, exist_ok=True)
        for name in ("kaynaklar", "gecici", "journal"):
            native_path(self.system / name).mkdir(exist_ok=True)
        self.lock_path = self.system / "access.lock"
        self.lock_timeout = lock_timeout
        with self._db() as db:
            exists = db.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='sema_gecmisi'").fetchone()[0]
            paths = [MIGRATION, MIGRATION_VERIFIER, MIGRATION_CONTEXT, MIGRATION_GUARD, MIGRATION_DOCX, MIGRATION_BUSINESS]
            scripts = [path.read_text(encoding="utf-8") for path in paths]
            expected = [(i + 1, hashlib.sha256(script.encode("utf-8")).hexdigest())
                        for i, script in enumerate(scripts)]
            rows = db.execute("SELECT migration_no,change_digest FROM sema_gecmisi ORDER BY migration_no").fetchall() if exists else []
            if rows != expected[:len(rows)] or len(rows) > len(expected):
                raise CoreError("SEMA_DRIFT", "Migration geçmişi bu kaynakla eşleşmiyor")
            for i in range(len(rows), len(scripts)):
                db.execute(scripts[i])
                db.execute("INSERT INTO sema_gecmisi VALUES(?,?,?,?)", [i + 1, ["1.0", "p2-verifier-1.0", "p3-context-1.0", "p4-guard-1.0", "p5-docx-1.0", "p6-business-1.0"][i], expected[i][1], NOW()])

    @contextmanager
    def _db(self):
        confined(self.db_path, [self.output_root])
        confined(self.lock_path, [self.output_root])
        with FileLock(self.lock_path, self.lock_timeout):
            db = duckdb.connect(str(native_path(self.db_path)), config={"enable_external_access": False, "threads": 1})
            try:
                db.execute("SET TimeZone='UTC'")
                db.execute("BEGIN TRANSACTION")
                yield db
                db.execute("COMMIT")
            except BaseException:
                try:
                    db.execute("ROLLBACK")
                finally:
                    db.close()
                raise
            else:
                db.close()

    @staticmethod
    def _record(db, case_id, kind, record_id=None, supersedes=None):
        record_id = record_id or str(uuid4())
        db.execute("INSERT INTO kayitlar VALUES(?,?,?,?,?)", [case_id, record_id, kind, NOW(), supersedes])
        return record_id

    @classmethod
    def _event(cls, db, case_id, event, details):
        rid = cls._record(db, case_id, "EVENT")
        db.execute("INSERT INTO islem_olaylari VALUES(?,?,?,?,?)", [case_id, rid, event, NOW(), canonical(details)])

    @staticmethod
    def _case(db, case_id, expected=None):
        row = db.execute("SELECT semantic_version FROM dosyalar WHERE case_id=?", [case_id]).fetchone()
        if not row:
            raise CoreError("KAYNAK_YOK", "Case bulunamadı")
        if expected is not None and row[0] != expected:
            raise CoreError("SURUM_CAKISMASI", "Case değişti; güncel bağlamı yeniden oku")
        return row[0]

    @staticmethod
    def _source(db, case_id, record_id, allowed=None):
        row = db.execute("SELECT record_type FROM kayitlar WHERE case_id=? AND record_id=?", [case_id, record_id]).fetchone()
        if not row or (allowed and row[0] not in allowed):
            raise CoreError("KAYNAK_KAPSAMI", "Kaynak bu case veya gerekli kayıt türü içinde değil")
        return row[0]

    @staticmethod
    def _bump(db, case_id):
        db.execute("UPDATE dosyalar SET semantic_version=semantic_version+1 WHERE case_id=?", [case_id])

    def _check_version_access(self, db, case_id, version_id):
        row = db.execute("SELECT original_path FROM belge_surumu WHERE case_id=? AND record_id=?", [case_id,version_id]).fetchone()
        if not row:
            raise CoreError("KAYNAK_KAPSAMI", "Kaynak sürümü bu case içinde değil")
        original = confined(row[0], self.source_roots)
        if not native_path(original).is_file():
            raise CoreError("ERISIM_YOK", "Kaynak erişimi yok; eski kayıt üzerinden okunmadı")

    def create_case(self, title):
        if not isinstance(title, str) or not title.strip():
            raise CoreError("GECERSIZ_GIRDI", "Case başlığı gerekli")
        case_id = str(uuid4())
        with self._db() as db:
            db.execute("INSERT INTO dosyalar VALUES(?,?,0,'NEW',?)", [case_id, title, NOW()])
            self._event(db, case_id, "CASE_CREATED", {})
        return case_id

    def case_revision(self, case_id):
        with self._db() as db:
            return self._case(db, uuid_text(case_id))

    def create_document(self, case_id, title, *, expected_revision, document_type="UNKNOWN"):
        case_id = uuid_text(case_id)
        if not title or not document_type:
            raise CoreError("GECERSIZ_GIRDI", "Belge başlığı/türü gerekli")
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            rid = self._record(db, case_id, "DOCUMENT")
            db.execute("INSERT INTO belgeler VALUES(?,?,?,?)", [case_id, rid, title, document_type])
            self._event(db, case_id, "DOCUMENT_CREATED", {"document_id": rid})
            self._bump(db, case_id)
        return rid

    def ingest(self, case_id, document_id, source, *, expected_revision, parent_version_id=None,
               business_status="UNKNOWN", _fault=None):
        case_id, document_id = uuid_text(case_id), uuid_text(document_id)
        if business_status not in {"UNKNOWN", "DRAFT", "SUPPLIER_PROPOSAL", "PURCHASING_PROPOSAL", "SIGNED"}:
            raise CoreError("GECERSIZ_DURUM", "Bilinmeyen belge iş durumu")
        path = confined(source, self.source_roots)
        if not native_path(path).is_file() or path.name.lower() in {"auth.json", "config.toml", "settings.local.json"} or path.name.startswith(".env"):
            raise CoreError("ERISIM_YOK", "Kaynak dosya uygun değil")
        if native_path(path).stat().st_size > 100 * 1024 * 1024:
            raise CoreError("BOYUT_SINIRI", "P1 kaynak sınırı 100 MiB")
        version_id = str(uuid4())
        journal = self.system / "journal" / (version_id + ".json")
        final = self.system / "kaynaklar" / case_id / document_id / (version_id + ".bin")
        confined(final, [self.output_root])
        staging = self.system / "gecici" / (version_id + ".part")
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            self._source(db, case_id, document_id, {"DOCUMENT"})
            before = native_path(path).stat()
            sha = hashlib.sha256()
            with native_path(path).open("rb") as reader, native_path(staging).open("xb") as writer:
                for block in iter(lambda: reader.read(1024 * 1024), b""):
                    sha.update(block)
                    writer.write(block)
                writer.flush()
                os.fsync(writer.fileno())
            after = native_path(path).stat()
            digest = sha.hexdigest()
            if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns or hash_file(path) != digest:
                native_path(staging).unlink()
                raise CoreError("KAYNAK_DEGISTI", "Alım sırasında kaynak değişti")
            row = db.execute("SELECT record_id,storage_key FROM belge_surumu WHERE case_id=? AND document_id=? AND sha256=?", [case_id, document_id, digest]).fetchone()
            if row:
                existing = confined(self.system / row[1], [self.output_root])
                if hash_file(existing) != digest:
                    raise CoreError("KAYNAK_BOZUK", "Önceki snapshot hash'i farklı")
                native_path(staging).unlink()
                return {"version_id": str(row[0]), "sha256": digest, "reused": True}
            has_prior = db.execute("SELECT count(*) FROM belge_surumu WHERE case_id=? AND document_id=?", [case_id,document_id]).fetchone()[0]
            if has_prior and not parent_version_id:
                native_path(staging).unlink()
                raise CoreError("SURUM_TEMELI_GEREKLI", "Değişen belgenin ebeveyn sürümünü açıkça seç; dosya adından son sürüm varsayılmadı")
            if parent_version_id:
                parent_version_id = uuid_text(parent_version_id)
                self._source(db, case_id, parent_version_id, {"VERSION"})
                parent_doc = db.execute("SELECT document_id FROM belge_surumu WHERE case_id=? AND record_id=?", [case_id, parent_version_id]).fetchone()[0]
                if str(parent_doc) != document_id:
                    raise CoreError("KAYNAK_KAPSAMI", "Ebeveyn aynı mantıksal belgeye ait olmalı")
            native_path(final.parent).mkdir(parents=True, exist_ok=True)
            record = {"version_id": version_id, "case_id": case_id, "document_id": document_id, "sha256": digest,
                      "storage_key": final.relative_to(self.system).as_posix(), "state": "PREPARED"}
            atomic_json(journal, record)
            os.replace(native_path(staging), native_path(final))
            os.chmod(native_path(final), 0o444)
            if _fault == "after_publish":
                raise CoreError("SENTETIK_KESINTI", "Yayın sonrası sentetik kayıt kesintisi")
            self._record(db, case_id, "VERSION", version_id)
            media = self._media_type(final, path.suffix)
            db.execute("INSERT INTO belge_surumu VALUES(?,?,?,?,?,?,?,?,?,?)", [case_id, version_id, document_id, digest,
                       native_path(final).stat().st_size, media, record["storage_key"], str(path), NOW(), business_status])
            if parent_version_id:
                db.execute("INSERT INTO surum_ebeveynleri VALUES(?,?,?,'REVISION')", [case_id, version_id, parent_version_id])
                self._invalidate(db, case_id, parent_version_id, version_id, "SOURCE_VERSION_CHANGED")
            self._event(db, case_id, "SOURCE_INGESTED", {"version_id": version_id, "sha256": digest})
            self._bump(db, case_id)
        record["state"] = "COMMITTED"
        atomic_json(journal, record)
        return {"version_id": version_id, "sha256": digest, "reused": False}

    @staticmethod
    def _media_type(path, suffix):
        with native_path(path).open("rb") as stream:
            start = stream.read(8)
        if start.startswith(b"%PDF-"):
            return "application/pdf"
        if start.startswith(b"PK"):
            return "application/zip;uninspected"
        if suffix.lower() == ".txt":
            try:
                native_path(path).read_text(encoding="utf-8-sig")
                return "text/plain;charset=utf-8"
            except UnicodeError:
                return "application/octet-stream"
        return "application/octet-stream"

    def read_version(self, case_id, version_id):
        case_id, version_id = uuid_text(case_id), uuid_text(version_id)
        with self._db() as db:
            self._source(db, case_id, version_id, {"VERSION"})
            self._check_version_access(db,case_id,version_id)
            sha, key = db.execute("SELECT sha256,storage_key FROM belge_surumu WHERE case_id=? AND record_id=?", [case_id, version_id]).fetchone()
            path = confined(self.system / key, [self.output_root])
            content = native_path(path).read_bytes()
            if hashlib.sha256(content).hexdigest() != sha:
                raise CoreError("KAYNAK_BOZUK", "Snapshot hash doğrulaması başarısız")
            return content

    def version_diff(self,case_id,old_version,new_version):
        """Deterministic byte delta; never labelled a clause/semantic comparison."""
        old=self.read_version(case_id,old_version)
        new=self.read_version(case_id,new_version)
        first=next((i for i,(a,b) in enumerate(zip(old,new)) if a!=b),min(len(old),len(new)) if old!=new else None)
        return {"case_id":uuid_text(case_id),"old_version_id":uuid_text(old_version),"new_version_id":uuid_text(new_version),
                "old_sha256":hashlib.sha256(old).hexdigest(),"new_sha256":hashlib.sha256(new).hexdigest(),
                "same_bytes":old==new,"old_size":len(old),"new_size":len(new),"first_changed_byte":first,
                "comparison_scope":"BYTES_ONLY","semantic_comparison":"NOT_RUN"}

    def add_parent(self, case_id, child, parent, *, expected_revision):
        case_id, child, parent = map(uuid_text, (case_id, child, parent))
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            for rid in (child, parent):
                self._source(db, case_id, rid, {"VERSION"})
            docs = db.execute("SELECT DISTINCT document_id FROM belge_surumu WHERE case_id=? AND record_id IN (?,?)", [case_id, child, parent]).fetchall()
            if len(docs) != 1:
                raise CoreError("KAYNAK_KAPSAMI", "Ebeveyn başka belgeye ait")
            edges = db.execute("SELECT child_id,parent_id FROM surum_ebeveynleri WHERE case_id=?", [case_id]).fetchall()
            graph = {}
            for a, b in edges:
                graph.setdefault(str(a), set()).add(str(b))
            todo, visited = [parent], set()
            while todo:
                node = todo.pop()
                if node == child:
                    raise CoreError("SURUM_DONGUSU", "Sürüm ebeveynleri döngü oluşturuyor")
                if node not in visited:
                    visited.add(node)
                    todo.extend(graph.get(node, ()))
            db.execute("INSERT INTO surum_ebeveynleri VALUES(?,?,?,'BRANCH')", [case_id, child, parent])
            self._event(db, case_id, "VERSION_LINKED", {"child": child, "parent": parent})
            self._bump(db, case_id)

    def add_statement(self, case_id, text, *, expected_revision, session_ref=None, message_ref=None):
        case_id = uuid_text(case_id)
        if not isinstance(text, str) or not text.strip():
            raise CoreError("GECERSIZ_GIRDI", "Beyan metni gerekli")
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            rid = self._record(db, case_id, "STATEMENT")
            db.execute("INSERT INTO beyanlar VALUES(?,?,?,?,?,?,'UNVERIFIED_LOCAL_STATEMENT')", [case_id, rid, text, NOW(), session_ref, message_ref])
            self._event(db, case_id, "STATEMENT_RECORDED", {"statement_id": rid})
            self._bump(db, case_id)
        return rid

    def add_candidate(self, payload, *, expected_revision, locator, supersedes=None):
        validate("aday_bilgi", payload)
        case_id, source = uuid_text(payload["case_id"]), uuid_text(payload["source_record_id"])
        canonical(locator)
        if not isinstance(locator, dict) or not locator:
            raise CoreError("KONUM_EKSIK", "Kaynak konumu gerekli")
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            return self._add_candidate_locked(db, case_id, source, payload, locator, supersedes)

    def _add_candidate_locked(self, db, case_id, source, payload, locator, supersedes=None):
        """Shared candidate transaction for source intake and anchored business facts."""
        validate("aday_bilgi", payload)
        value = payload["value"]
        columns = {"text": None, "decimal": None, "rate": None, "date": None, "boolean": None, "unknown": None}
        if value["type"] == "decimal":
            number = Decimal(value["value"])
            precision, scale = (18, 10) if payload["unit"] == "ratio" else (24, 6)
            with localcontext() as ctx:
                ctx.prec = max(50, len(value["value"]) + 20)
                if not number.is_finite() or abs(number) >= Decimal(10) ** (precision-scale) or number.quantize(Decimal(10) ** -scale) != number:
                    raise CoreError("ONDALIK_SINIRI", "Değer sessiz yuvarlanmadan saklanamıyor")
            columns["rate" if scale == 10 else "decimal"] = number
        elif value["type"] == "date":
            columns["date"] = date.fromisoformat(value["value"])
        elif value["type"] == "unknown":
            columns["unknown"] = value["reason"]
        else:
            columns[value["type"]] = value["value"]
        source_kind = self._source(db, case_id, source, {"VERSION", "STATEMENT"})
        if source_kind == "VERSION":
            self._check_version_access(db,case_id,source)
        if (payload["knowledge_kind"] == "USER_STATEMENT") != (source_kind == "STATEMENT"):
            raise CoreError("BILGI_TURU", "Beyan ve belge gerçeği kaynak türüyle karıştırılamaz")
        if supersedes:
            supersedes = uuid_text(supersedes)
            self._source(db, case_id, supersedes, {"CANDIDATE"})
            old_field = db.execute("SELECT field_code FROM bilgiler WHERE case_id=? AND record_id=?", [case_id,supersedes]).fetchone()[0]
            if old_field != payload["field"]:
                raise CoreError("BILGI_TURU", "Farklı bilgi alanı supersedes olarak kullanılamaz")
        rid = self._record(db, case_id, "CANDIDATE", supersedes=supersedes)
        db.execute("INSERT INTO bilgiler VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'UNVERIFIED',?)", [case_id, rid, source, payload["field"], value["type"], columns["text"], columns["decimal"], columns["rate"], columns["date"], columns["boolean"], columns["unknown"], payload["unit"], payload["currency"], payload["knowledge_kind"], payload["meaning_status"], canonical(payload)])
        db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)", [case_id, rid, source, canonical(locator)])
        if supersedes:
            db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPERSEDES',?)", [case_id, rid, supersedes, canonical(locator)])
            self._invalidate(db, case_id, supersedes, rid, "SUPERSEDED")
        self._event(db, case_id, "CANDIDATE_RECORDED", {"candidate_id": rid})
        self._bump(db, case_id)
        return rid

    @classmethod
    def _invalidate(cls, db, case_id, target, cause, reason):
        affected = {str(target)}
        edges = db.execute("SELECT target_id,source_id FROM kanit_baglari WHERE case_id=? AND relation='SUPPORTS'", [case_id]).fetchall()
        while True:
            extra = {str(a) for a,b in edges if str(b) in affected}
            if extra <= affected:
                break
            affected |= extra
        for item in affected:
            rid = cls._record(db, case_id, "INVALIDATION")
            db.execute("INSERT INTO gecersizlestirmeler VALUES(?,?,?,?,?,?,'NEEDS_REVIEW')", [case_id, rid, item, cause, reason, NOW()])

    def invalidate(self, case_id, target, cause, reason, *, expected_revision):
        case_id, target, cause = map(uuid_text, (case_id, target, cause))
        if not reason:
            raise CoreError("GECERSIZ_GIRDI", "Geçersizleştirme nedeni gerekli")
        with self._db() as db:
            self._case(db, case_id, expected_revision)
            self._source(db, case_id, target)
            self._source(db, case_id, cause)
            self._invalidate(db, case_id, target, cause, reason)
            self._event(db, case_id, "DEPENDENCY_INVALIDATED", {"target": target, "cause": cause, "reason": reason})
            self._bump(db, case_id)

    def process(self, case_id, version_id, *, tool, tool_version, settings, validation_version, policy_version, extractor):
        """Unverified structured cache; no caller can set VERIFIED through this API."""
        return self._process(case_id, version_id, tool=tool, tool_version=tool_version,
                             settings=settings, validation_version=validation_version,
                             policy_version=policy_version, extractor=extractor, result_schema="P1")

    def read_document(self, case_id, version_id, *, format, policy_version="1"):
        from .readers import read_document
        settings, _ = reading_profile(format, policy_version)
        return self._process(case_id, version_id, tool="p2-" + format.lower(),
                             tool_version="1.0", settings=settings, validation_version="p2-1.0",
                             policy_version=policy_version,
                             extractor=lambda data: read_document(data, format), result_schema="P2")

    def source_excerpt(self, case_id, version_id, *, format, unit_id, view, start, end, expected_text):
        from .readers import excerpt
        processed = self.read_document(case_id, version_id, format=format)
        proof = excerpt(processed["result"], unit_id, view, start, end, expected_text)
        return dict(proof, case_id=uuid_text(case_id), version_id=uuid_text(version_id),
                    processing_id=processed["processing_id"])

    def _process(self, case_id, version_id, *, tool, tool_version, settings, validation_version,
                 policy_version, extractor, result_schema):
        case_id, version_id = map(uuid_text, (case_id, version_id))
        profile = hash_value({"tool": tool, "tool_version": tool_version, "settings": settings,
                              "validation_version": validation_version, "policy_version": policy_version,
                              "result_schema": result_schema})
        with self._db() as db:
            self._source(db, case_id, version_id, {"VERSION"})
            row = db.execute("SELECT sha256,storage_key,original_path FROM belge_surumu WHERE case_id=? AND record_id=?", [case_id, version_id]).fetchone()
            original = confined(row[2], self.source_roots)
            if not native_path(original).is_file():
                raise CoreError("ERISIM_YOK", "Kaynak erişimi yok; cache üzerinden okunmadı")
            snapshot = confined(self.system / row[1], [self.output_root])
            data = native_path(snapshot).read_bytes()
            if hashlib.sha256(data).hexdigest() != row[0]:
                raise CoreError("KAYNAK_BOZUK", "Snapshot değişmiş")
            invalid = db.execute("SELECT count(*) FROM gecersizlestirmeler WHERE case_id=? AND target_id=?", [case_id, version_id]).fetchone()[0]
            old = db.execute("SELECT record_id,result FROM isleme_calismalari WHERE case_id=? AND document_version_id=? AND profile_digest=?", [case_id, version_id, profile]).fetchone()
            if old and not invalid:
                cached = json.loads(old[1])
                if result_schema == "P2":
                    from .readers import validate_reading
                    validate_reading(cached, data)
                return {"processing_id": str(old[0]), "result": cached, "reused": True,
                        "verification_status": "PARTIAL" if result_schema == "P2" else "UNVERIFIED"}
            if old:
                raise CoreError("YENIDEN_INCELE", "Bağımlılığı değişen profil yeniden değerlendirme gerektiriyor")
            result = extractor(data)
            if result_schema == "P2":
                from .readers import validate_reading
                validate_reading(result, data)
            else:
                from jsonschema import Draft202012Validator
                schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "p1_inventory.schema.json").read_text(encoding="utf-8"))
                if not Draft202012Validator(schema).is_valid(result):
                    raise CoreError("SEMA_HATASI", "P1 işleme çıktısı envanter şemasına uymuyor")
            if result["sha256"] != row[0] or result["size_bytes"] != len(data):
                raise CoreError("KAYNAK_BOZUK", "İşleme envanteri kaynak baytlarıyla eşleşmiyor")
            rid = self._record(db, case_id, "PROCESSING")
            status = "PARTIAL" if result_schema == "P2" else "STRUCTURED_UNVERIFIED"
            db.execute("INSERT INTO isleme_calismalari VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [case_id,rid,version_id,profile,tool,tool_version,hash_value(settings),validation_version,policy_version,canonical(result),status,NOW()])
            self._event(db, case_id, "SOURCE_READING_PARTIAL" if result_schema == "P2" else "SOURCE_STRUCTURED_UNVERIFIED", {"processing_id": rid})
            return {"processing_id": rid, "result": result, "reused": False,
                    "verification_status": "PARTIAL" if result_schema == "P2" else "UNVERIFIED"}

    def context(self, case_id):
        case_id = uuid_text(case_id)
        with self._db() as db:
            revision = self._case(db, case_id)
            versions = db.execute("SELECT record_id FROM belge_surumu WHERE case_id=?", [case_id]).fetchall()
            for version, in versions:
                self._check_version_access(db,case_id,str(version))
            rows = db.execute("SELECT record_id,payload FROM bilgiler WHERE case_id=? ORDER BY record_id", [case_id]).fetchall()
            stale = {str(x[0]) for x in db.execute("SELECT target_id FROM gecersizlestirmeler WHERE case_id=?", [case_id]).fetchall()}
            superseded = {str(x[0]) for x in db.execute("SELECT supersedes_id FROM kayitlar WHERE case_id=? AND supersedes_id IS NOT NULL", [case_id]).fetchall()}
            return {"schema_version": "1.0", "case_id": case_id, "semantic_version": revision,
                    "candidates": [{"record_id": str(rid), "payload": json.loads(payload), "verification_status": "UNVERIFIED",
                                    "state": "SUPERSEDED" if str(rid) in superseded else "NEEDS_REVIEW" if str(rid) in stale else "CANDIDATE"} for rid,payload in rows],
                    "limitations": ["P1: okuma sadakati, uzman değerlendirmesi ve yetkili karar bu kayıtla doğrulanmaz."],
                    "requested_output": "CHAT"}

    def reconcile(self):
        out = []
        with self._db() as db:
            for native in sorted(native_path(self.system / "journal").glob("*.json")):
                path = ordinary_path(native)
                confined(path, [self.output_root])
                item = json.loads(native_path(path).read_text(encoding="utf-8"))
                snapshot = confined(self.system / item["storage_key"], [self.output_root])
                if not native_path(snapshot).is_file() or hash_file(snapshot) != item["sha256"]:
                    state = "CORRUPT"
                else:
                    exists = db.execute("SELECT 1 FROM belge_surumu WHERE case_id=? AND record_id=? AND sha256=?", [item["case_id"],item["version_id"],item["sha256"]]).fetchone()
                    state = "COMMITTED" if exists else "QUARANTINED"
                item["state"] = state
                atomic_json(path, item)
                out.append({"version_id": item["version_id"], "state": state})
            for path in native_path(self.system / "gecici").glob("*.part"):
                out.append({"temporary_file": path.name, "state": "QUARANTINED"})
        return out

    def snapshot(self, destination):
        """Explicit project-local consistency snapshot; never copies arbitrary user directories."""
        target = confined(destination, [self.output_root])
        if native_path(target).exists() or target.is_relative_to(self.root):
            raise CoreError("HEDEF_VAR", "Snapshot yeni ve workspace dışında bir hedef gerektirir")
        stage = target.with_name(target.name + ".pending")
        confined(stage, [self.output_root])
        with FileLock(self.lock_path, self.lock_timeout):
            db = duckdb.connect(str(native_path(self.db_path)), config={"enable_external_access": False, "threads": 1})
            try:
                versions = db.execute("SELECT storage_key,sha256 FROM belge_surumu").fetchall()
                db.execute("CHECKPOINT")
            finally:
                db.close()
            native_path(stage).mkdir(parents=True, exist_ok=False)
            files = []
            for source, relative, expected in [(self.db_path,".sistem/sozlesme.duckdb",None)] + [(self.system / key,".sistem/" + key,sha) for key,sha in versions]:
                source = confined(source, [self.output_root])
                sha = hash_file(source)
                if expected and sha != expected:
                    raise CoreError("KAYNAK_BOZUK", "Tutarlı snapshot kaynak hash'i başarısız")
                dest = stage / relative
                native_path(dest.parent).mkdir(parents=True, exist_ok=True)
                shutil.copyfile(native_path(source),native_path(dest))
                files.append({"path": relative,"sha256": sha})
            atomic_json(stage / "snapshot.json", {"format": "kilic-local-snapshot-1", "created_at": NOW().isoformat(), "files": files})
            os.rename(native_path(stage),native_path(target))
        return target

    @classmethod
    def restore(cls, snapshot, destination, *, source_roots, output_root):
        snap = confined(snapshot, [output_root])
        target = confined(destination, [output_root])
        target_db = target / ".sistem" / "sozlesme.duckdb"
        stage_db = target.with_name(target.name + ".restore-pending") / ".sistem" / "sozlesme.duckdb"
        if os.name == "nt" and any(len(str(p).encode("utf-16-le")) // 2 > 240 for p in (target_db, stage_db)):
            raise CoreError("DB_YOL_SINIRI", "Restore hedefi ve staging DuckDB yolu en fazla 240 UTF-16 birimi olmalı")
        if native_path(target).exists():
            raise CoreError("HEDEF_VAR", "Mevcut workspace üzerine restore yok")
        manifest = json.loads(native_path(snap / "snapshot.json").read_text(encoding="utf-8"))
        if manifest.get("format") != "kilic-local-snapshot-1" or not isinstance(manifest.get("files"), list):
            raise CoreError("SNAPSHOT_BOZUK", "Snapshot biçimi geçersiz")
        paths = [x["path"] for x in manifest["files"]]
        if len(paths) != len(set(paths)) or paths.count(".sistem/sozlesme.duckdb") != 1:
            raise CoreError("SNAPSHOT_BOZUK", "Snapshot envanteri geçersiz")
        for item in manifest["files"]:
            rel = Path(item["path"])
            import re
            allowed = item["path"] == ".sistem/sozlesme.duckdb" or re.fullmatch(r"\.sistem/kaynaklar/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}\.bin",item["path"])
            if rel.is_absolute() or ".." in rel.parts or not allowed:
                raise CoreError("SNAPSHOT_BOZUK", "Snapshot izinli dosya listesinin dışına çıkıyor")
            source = confined(snap / rel,[snap])
            if not native_path(source).is_file() or hash_file(source) != item["sha256"]:
                raise CoreError("SNAPSHOT_BOZUK", "Snapshot hash kontrolü başarısız")
        stage = target.with_name(target.name + ".restore-pending")
        confined(stage,[output_root])
        native_path(stage).mkdir(parents=True,exist_ok=False)
        for item in manifest["files"]:
            dest = stage / item["path"]
            native_path(dest.parent).mkdir(parents=True,exist_ok=True)
            shutil.copyfile(native_path(snap / item["path"]),native_path(dest))
            if item["path"].startswith(".sistem/kaynaklar/"):
                os.chmod(native_path(dest),0o444)
        candidate = cls(stage,source_roots=source_roots,output_root=output_root)
        with candidate._db() as db:
            rows = db.execute("SELECT storage_key,sha256 FROM belge_surumu").fetchall()
            for key,sha in rows:
                if hash_file(confined(candidate.system / key,[output_root])) != sha:
                    raise CoreError("SNAPSHOT_BOZUK", "DB/kaynak snapshot ilişkisi başarısız")
        os.rename(native_path(stage),native_path(target))
        return cls(target,source_roots=source_roots,output_root=output_root)
