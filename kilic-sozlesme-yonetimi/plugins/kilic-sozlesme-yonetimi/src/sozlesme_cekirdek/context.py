"""Source-bound, registered dependency closure. No semantic/authority approval."""
from functools import lru_cache
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

from .errors import CoreError
from .safety import canonical, hash_value, uuid_text
from .schemas import validate
from .verification import reading_profile, validate_policy

VERSION = "p3-1.0"
MAX_NODES = 512
MAX_RELATIONS = 2048
MAX_PACKS = 512
TRUST = "UNTRUSTED_SOURCE_DATA_NOT_INSTRUCTIONS"
LIMITATIONS = [
    "Kapanım yalnız kayıtlı bağlantılar içindir; otomatik anlamsal bağlantı keşfi ve yeterlilik onayı uygulanmadı.",
    "Belge sadakati PARTIAL; beyan kimliği, aday bilgi, sınıflandırma ve bağlantı anlamı UNVERIFIED.",
    "Yetkili şirket kararı ve kritik inceleme izni bu paketle verilmez.",
    "Bütçe yalnız context alanının UTF-8 baytlarıdır; host token tüketimi ölçülmez.",
]


@lru_cache
def validator(name):
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas" / (name + ".schema.json")).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def checked(name, value):
    if not validator(name).is_valid(value):
        raise CoreError("SEMA_HATASI", "P3 kayıt/istek şemaya uymuyor")
    return value


def context_bytes(value):
    return len(canonical(value).encode("utf-8")) if value is not None else 0


def validate_pack(report):
    checked("p3_context_pack", report)
    budget = report["budget"]
    if context_bytes(report["context"]) != budget["used_bytes"] or budget["used_bytes"] > budget["max_context_bytes"]:
        raise CoreError("BAGLAM_BOZUK", "Bağlam bayt bütçesi farklı")
    complete = report["status"] == "COMPLETE_REGISTERED_SCOPE"
    if complete != (report["context"] is not None) or complete != report["registered_closure_complete"]:
        raise CoreError("BAGLAM_BOZUK", "Eksik bağlam tamamlanmış sayılamaz")
    if report["context"] is not None:
        entries = report["context"]["entries"]
        ids = [x["node_id"] for x in entries]
        if len(ids) != len(set(ids)) or ids != report["included"] or any(x["state"] != "CURRENT_REGISTERED_SCOPE" for x in entries):
            raise CoreError("BAGLAM_BOZUK", "Seçilmiş bağlam kayıtları farklı/eski")
        if (not set(report["required_nodes"]) <= set(ids) or not set(report["request"]["root_ids"]) <= set(report["required_nodes"])
                or report["missing_dependencies"] or report["stale_dependencies"]
                or report["context"]["case_id"] != report["case_id"]
                or report["context"]["semantic_version"] != report["semantic_version"]
                or report["context"]["purpose"] != report["request"]["purpose"]):
            raise CoreError("BAGLAM_BOZUK", "Tamamlanan kapanımın kapsamı farklı/eksik")
    elif report["included"]:
        raise CoreError("BAGLAM_BOZUK", "Eksik pakette kullanılabilir içerik yok")
    if budget["max_context_bytes"] != report["request"]["max_context_bytes"]:
        raise CoreError("BAGLAM_BOZUK", "İstek bütçesi farklı")
    return report


class ContextMixin:
    def _context_version(self, db, case, version, policy):
        data, sha, document, current = self._verification_source(db, case, version)
        reasons = [] if current else ["SOURCE_FILE_CHANGED"]
        if db.execute("SELECT 1 FROM surum_ebeveynleri WHERE case_id=? AND parent_id=? LIMIT 1", [case, version]).fetchone():
            reasons.append("SOURCE_VERSION_HAS_CHILD")
        if self._invalid(db, case, [version]):
            reasons.append("DEPENDENCY_INVALIDATED")
        return data, sha, document, reasons

    def _context_basis(self, db, case, spec, policy):
        kind = spec["node_kind"]
        deps, reasons = [], []
        if kind == "SOURCE_UNIT":
            version, reading_id = spec["version_id"], spec["reading_id"]
            data, sha, document, reasons = self._context_version(db, case, version, policy)
            reading, profile = self._verification_reading(db, case, version, reading_id, data)
            unit, text = self._target(reading, spec["target"])
            if text != spec["target"]["expected_text"]:
                raise CoreError("KAYNAK_ALINTISI", "Bağlam metni tam kaynak aralığına eşleşmiyor")
            if profile != reading_profile(reading["format"], policy)[1]:
                reasons.append("READING_PROFILE_CHANGED")
            deps = [version, reading_id]
            basis = {"content": {"excerpt": text, "attributes": unit["attributes"], "issues": reading["issues"]},
                     "provenance": {"version_id": version, "document_id": document, "source_sha256": sha,
                                    "reading_id": reading_id, "reading_digest": hash_value(reading),
                                    "reader_profile_digest": profile, "locator": unit["locator"], "target": spec["target"]},
                     "knowledge_status": "EXTRACTED_TEXT_PARTIAL"}
        elif kind == "USER_STATEMENT":
            ref = spec["record_id"]
            self._source(db, case, ref, {"STATEMENT"})
            row = db.execute("SELECT excerpt,session_ref,message_ref,identity_status FROM beyanlar WHERE case_id=? AND record_id=?", [case, ref]).fetchone()
            basis = {"content": {"statement": row[0]}, "provenance": {"record_id": ref, "session_ref": row[1], "message_ref": row[2]},
                     "knowledge_status": row[3]}
            deps = [ref]
        elif kind == "CANDIDATE":
            ref = spec["record_id"]
            self._source(db, case, ref, {"CANDIDATE"})
            row = db.execute("SELECT source_id,payload FROM bilgiler WHERE case_id=? AND record_id=?", [case, ref]).fetchone()
            payload = validate("aday_bilgi", json.loads(row[1]))
            if payload["case_id"] != case or payload["source_record_id"] != str(row[0]):
                raise CoreError("BAGLAM_BOZUK", "Aday kaynak zarfı farklı")
            source = str(row[0])
            source_kind = self._source(db, case, source, {"VERSION", "STATEMENT"})
            if source_kind == "VERSION":
                _, _, _, reasons = self._context_version(db, case, source, policy)
            if (payload["knowledge_kind"] == "USER_STATEMENT") != (source_kind == "STATEMENT"):
                raise CoreError("BAGLAM_BOZUK", "Aday bilgi/beyan türü farklı")
            basis = {"content": {"candidate": payload}, "provenance": {"record_id": ref, "source_id": source}, "knowledge_status": "UNVERIFIED"}
            deps = [ref, source]
        else:
            ref = spec["record_id"]
            row = db.execute("SELECT document_version_id FROM dogrulamalar WHERE case_id=? AND record_id=?", [case, ref]).fetchone()
            if not row:
                raise CoreError("KAYNAK_KAPSAMI", "P2 kontrol kaydı bu case içinde değil")
            version = str(row[0])
            data, _, _, reasons = self._context_version(db, case, version, policy)
            report, _, extra, _ = self._load_control(db, case, version, ref, data, "SOURCE_FILE_CHANGED" not in reasons, policy)
            reasons.extend(extra)
            # PNG bytes and potentially large entire reading are never inserted into a context.
            content = {key: report[key] for key in ("method", "outcome", "scope", "observed_text", "dimensions", "artifact", "issues", "authority", "critical_analysis_allowed")}
            basis = {"content": {"control": content}, "provenance": {"record_id": ref, "version_id": version, "reading_id": report["processing_id"], "control_digest": report["request_digest"]},
                     "knowledge_status": "SCOPED_CONTROL_NOT_AUTHORITY"}
            deps = [ref, version, report["processing_id"]]
        if self._invalid(db, case, deps):
            reasons.append("DEPENDENCY_INVALIDATED")
        return basis, deps, sorted(set(reasons))

    def register_context_node(self, case_id, *, spec, expected_revision, policy_version="1"):
        case = uuid_text(case_id)
        checked("p3_context_node", spec)
        spec = {key: uuid_text(value) if key in {"record_id", "version_id", "reading_id"} else value for key, value in spec.items()}
        validate_policy(policy_version)
        with self._db() as db:
            self._case(db, case, expected_revision)
            basis, deps, reasons = self._context_basis(db, case, spec, policy_version)
            if reasons:
                raise CoreError("YENIDEN_INCELE", "Bağlam kaynağı güncel değil: " + ", ".join(reasons))
            payload = {"spec": spec, "basis": basis, "dependencies": deps}
            if context_bytes(payload) > 65536:
                raise CoreError("BAGLAM_SINIRI", "Tek kayıt 64 KiB sınırını aşıyor; hedef aralığı küçült")
            digest = hash_value(payload)
            old = db.execute("SELECT record_id FROM icerik_birimleri WHERE case_id=? AND node_digest=?", [case, digest]).fetchone()
            if old:
                return {"node_id": str(old[0]), "reused": True}
            if db.execute("SELECT count(*) FROM icerik_birimleri WHERE case_id=?", [case]).fetchone()[0] >= MAX_NODES:
                raise CoreError("BAGLAM_SINIRI", "Case bağlam kayıt sınırı")
            rid = self._record(db, case, "PROCESSING")
            db.execute("INSERT INTO icerik_birimleri VALUES(?,?,?,?,?)", [case, rid, spec["node_kind"], digest, canonical(payload)])
            for source in deps:
                db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)", [case, rid, source, canonical({"context_node": True})])
            self._event(db, case, "CONTEXT_NODE_REGISTERED_UNVERIFIED", {"node_id": rid})
            self._bump(db, case)
            return {"node_id": rid, "reused": False}

    def _context_node(self, db, case, rid, policy):
        row = db.execute("SELECT node_kind,node_digest,payload FROM icerik_birimleri WHERE case_id=? AND record_id=?", [case, rid]).fetchone()
        if not row:
            raise CoreError("KAYNAK_KAPSAMI", "Bağlam düğümü bu case içinde değil")
        payload = json.loads(row[2])
        if set(payload) != {"spec", "basis", "dependencies"} or hash_value(payload) != row[1]:
            raise CoreError("BAGLAM_BOZUK", "Bağlam kayıt hash'i farklı")
        spec = checked("p3_context_node", payload["spec"])
        if row[0] != spec["node_kind"]:
            raise CoreError("BAGLAM_BOZUK", "Bağlam kayıt türü farklı")
        basis, deps, reasons = self._context_basis(db, case, spec, policy)
        if basis != payload["basis"] or deps != payload["dependencies"]:
            raise CoreError("BAGLAM_BOZUK", "Bağlam kaynağı/kanıt kaydı değişmiş")
        if self._invalid(db, case, [rid]):
            reasons.append("DEPENDENCY_INVALIDATED")
        return {"node_id": rid, "node_kind": spec["node_kind"], "role": spec.get("role", spec["node_kind"]),
                "title": spec["title"], "classification_status": "UNVERIFIED", "trust": TRUST, **basis,
                "state": "NEEDS_REVIEW" if reasons else "CURRENT_REGISTERED_SCOPE", "reasons": sorted(set(reasons))}

    def register_context_relation(self, case_id, *, spec, expected_revision):
        case = uuid_text(case_id)
        checked("p3_context_relation", spec)
        spec = {key: uuid_text(value) if key in {"from_id", "to_id", "supersedes_relation_id"} else value for key, value in spec.items()}
        with self._db() as db:
            self._case(db, case, expected_revision)
            for rid in [spec["from_id"]] + ([spec["to_id"]] if "to_id" in spec else []):
                if not db.execute("SELECT 1 FROM icerik_birimleri WHERE case_id=? AND record_id=?", [case, rid]).fetchone():
                    raise CoreError("KAYNAK_KAPSAMI", "Bağlantı bu case düğümlerine ait olmalı")
            digest = hash_value(spec)
            old = db.execute("SELECT record_id FROM iliskiler WHERE case_id=? AND relation_digest=?", [case, digest]).fetchone()
            if old:
                return {"relation_id": str(old[0]), "reused": True}
            prior = spec.get("supersedes_relation_id")
            if prior:
                previous = db.execute("SELECT from_id,relation FROM iliskiler WHERE case_id=? AND record_id=?", [case, prior]).fetchone()
                if not previous or str(previous[0]) != spec["from_id"] or previous[1] != spec["relation"]:
                    raise CoreError("KAYNAK_KAPSAMI", "Yerine geçen bağlantı aynı case, başlangıç ve türde olmalı")
                if db.execute("SELECT 1 FROM kayitlar WHERE case_id=? AND supersedes_id=? LIMIT 1", [case, prior]).fetchone():
                    raise CoreError("YENIDEN_INCELE", "Bağlantı zaten yeni kayıtla değiştirilmiş")
            if db.execute("SELECT count(*) FROM iliskiler WHERE case_id=?", [case]).fetchone()[0] >= MAX_RELATIONS:
                raise CoreError("BAGLAM_SINIRI", "Case bağlam bağlantı sınırı")
            rid = self._record(db, case, "PROCESSING", supersedes=prior)
            db.execute("INSERT INTO iliskiler VALUES(?,?,?,?,?,?,?,?)", [case, rid, spec["from_id"], spec.get("to_id"), spec["relation"], spec.get("unresolved_reference"), digest, canonical(spec)])
            if prior:
                self._invalidate(db, case, prior, rid, "RELATION_SUPERSEDED")
            self._event(db, case, "CONTEXT_RELATION_REGISTERED_UNVERIFIED", {"relation_id": rid})
            self._bump(db, case)
            return {"relation_id": rid, "reused": False}

    def _context_graph(self, db, case):
        graph = {}
        rows = db.execute("SELECT r.record_id,r.from_id,r.to_id,r.relation,r.unresolved_reference,r.relation_digest,r.payload FROM iliskiler r WHERE r.case_id=? AND NOT EXISTS (SELECT 1 FROM kayitlar k WHERE k.case_id=r.case_id AND k.supersedes_id=r.record_id) ORDER BY r.record_id", [case]).fetchall()
        if len(rows) > MAX_RELATIONS:
            raise CoreError("BAGLAM_SINIRI", "Bağlantı sınırı aşılmış")
        for rid, source, target, relation, missing, digest, raw in rows:
            spec = checked("p3_context_relation", json.loads(raw))
            if (hash_value(spec) != digest or spec["from_id"] != str(source) or spec.get("to_id") != (str(target) if target else None)
                    or spec["relation"] != relation or spec.get("unresolved_reference") != missing):
                raise CoreError("BAGLAM_BOZUK", "Bağlantı zarfı farklı")
            graph.setdefault(str(source), []).append({"relation_id": str(rid), **spec, "status": "UNVERIFIED",
                                                     "invalidated": self._invalid(db, case, [str(rid)])})
        return graph

    @staticmethod
    def _closure(roots, graph):
        pending, nodes, edges, missing = list(sorted(roots)), set(), {}, []
        while pending:
            rid = pending.pop(0)
            if rid in nodes:
                continue
            nodes.add(rid)
            if len(nodes) > MAX_NODES:
                raise CoreError("BAGLAM_SINIRI", "Kapanım düğüm sınırını aşıyor")
            for edge in graph.get(rid, []):
                if edge["relation"] == "RELATED":
                    continue
                edges[edge["relation_id"]] = edge
                if edge["invalidated"] or "to_id" not in edge:
                    missing.append({"relation_id": edge["relation_id"], "from_id": rid, "reference": edge.get("unresolved_reference", edge.get("to_id")),
                                    "reason": "DEPENDENCY_INVALIDATED" if edge["invalidated"] else "UNRESOLVED_REQUIRED_REFERENCE"})
                else:
                    pending.append(edge["to_id"])
        return nodes, edges, missing

    def context_pack(self, case_id, *, request):
        case = uuid_text(case_id)
        checked("p3_context_request", request)
        root_ids = [uuid_text(rid) for rid in request["root_ids"]]
        if len(set(root_ids)) != len(root_ids):
            raise CoreError("SEMA_HATASI", "Kök UUID'ler tekrarlanamaz")
        request = dict(request, root_ids=sorted(root_ids))
        policy = request["policy_version"]
        with self._db() as db:
            revision = self._case(db, case)
            graph = self._context_graph(db, case)
            required, edges, missing = self._closure(request["root_ids"], graph)
            loaded = {}
            def load(ids):
                for rid in sorted(ids):
                    if rid not in loaded:
                        loaded[rid] = self._context_node(db, case, rid, policy)
            load(required)
            stale = [{"node_id": rid, "reasons": loaded[rid]["reasons"]} for rid in sorted(required) if loaded[rid]["state"] == "NEEDS_REVIEW"]
            def payload(ids, links):
                return {"case_id": case, "purpose": request["purpose"], "semantic_version": revision,
                        "entries": [loaded[rid] for rid in sorted(ids)], "relations": [links[rid] for rid in sorted(links)],
                        "trust": TRUST, "limitations": LIMITATIONS}
            needed = context_bytes(payload(required, edges))
            maximum = request["max_context_bytes"]
            selected, links, omitted = set(required), dict(edges), []
            status = "INCOMPLETE_DEPENDENCIES" if missing else "NEEDS_REVIEW" if stale else "BUDGET_EXCEEDED" if needed > maximum else "COMPLETE_REGISTERED_SCOPE"
            if status != "COMPLETE_REGISTERED_SCOPE":
                selected.clear()
                links.clear()
                omitted = [{"node_id": rid, "reason": status, "required": True} for rid in sorted(required)]
            elif request["include_related"]:
                # Each optional neighbour includes its entire required closure as one atomic group.
                related = sorted([edge for rid in required for edge in graph.get(rid, []) if edge["relation"] == "RELATED"], key=lambda e: e["relation_id"])
                for edge in related:
                    if "to_id" not in edge or edge["invalidated"]:
                        omitted.append({"node_id": edge.get("to_id"), "reason": "OPTIONAL_REFERENCE_UNAVAILABLE", "required": False})
                        continue
                    group, group_edges, absent = self._closure([edge["to_id"]], graph)
                    load(group)
                    bad = any(loaded[rid]["state"] == "NEEDS_REVIEW" for rid in group)
                    proposed = dict(links, **group_edges)
                    proposed[edge["relation_id"]] = edge
                    reason = "OPTIONAL_DEPENDENCY_UNAVAILABLE" if absent or bad else "OPTIONAL_BUDGET_EXCEEDED" if context_bytes(payload(selected | group, proposed)) > maximum else None
                    if reason:
                        omitted.extend({"node_id": rid, "reason": reason, "required": False} for rid in sorted(group - selected))
                    else:
                        selected |= group
                        links = proposed
            included = sorted(selected)
            context = payload(selected, links) if status == "COMPLETE_REGISTERED_SCOPE" else None
            dependency_digest = hash_value({"nodes": loaded, "graph": graph, "missing": missing, "stale": stale})
            cache = hash_value({"case_id": case, "request": request, "revision": revision, "dependency_digest": dependency_digest, "version": VERSION})
            old = db.execute("SELECT record_id,payload_digest,payload FROM baglam_paketleri WHERE case_id=? AND cache_digest=?", [case, cache]).fetchone()
            report = {"schema_version": VERSION, "case_id": case, "semantic_version": revision, "request": request,
                      "status": status, "context": context, "included": included, "required_nodes": sorted(required), "omitted": omitted,
                      "missing_dependencies": missing, "stale_dependencies": stale, "dependency_digest": dependency_digest,
                      "registered_closure_complete": status == "COMPLETE_REGISTERED_SCOPE", "semantic_completeness": "UNVERIFIED",
                      "critical_analysis_allowed": False, "authority": "NOT_VERIFIED", "limitations": LIMITATIONS,
                      "budget": {"method": "CANONICAL_JSON_UTF8_BYTES", "scope": "CONTEXT_FIELD_ONLY", "max_context_bytes": maximum,
                                 "used_bytes": context_bytes(context), "required_bytes": needed, "host_token_count": None}}
            validate_pack(report)
            if selected:
                placeholders = ",".join("?" for _ in selected)
                versions = db.execute("SELECT DISTINCT k.source_id FROM kanit_baglari k JOIN belge_surumu v ON k.case_id=v.case_id AND k.source_id=v.record_id WHERE k.case_id=? AND k.target_id IN (" + placeholders + ")", [case, *sorted(selected)]).fetchall()
                for version, in versions:
                    # Recheck after assembly, including candidate version dependencies.
                    self._verification_source(db, case, str(version), current=True)
            if old:
                stored = validate_pack(json.loads(old[2]))
                if hash_value(stored) != old[1] or stored != report or self._invalid(db, case, [str(old[0])]):
                    raise CoreError("BAGLAM_BOZUK", "Cache bağlam kaydı farklı/geçersiz")
                return {"pack_id": str(old[0]), "reused": True, "result": stored}
            if db.execute("SELECT count(*) FROM baglam_paketleri WHERE case_id=?", [case]).fetchone()[0] >= MAX_PACKS:
                raise CoreError("BAGLAM_SINIRI", "Case bağlam paket sınırı")
            rid = self._record(db, case, "PROCESSING")
            db.execute("INSERT INTO baglam_paketleri VALUES(?,?,?,?,?,?)", [case, rid, revision, cache, hash_value(report), canonical(report)])
            for source in sorted(set(loaded) | {edge["relation_id"] for values in graph.values() for edge in values}):
                db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)", [case, rid, source, canonical({"context_pack": True})])
            self._event(db, case, "CONTEXT_PACK_CREATED", {"pack_id": rid, "status": status})
            # Pack/cache telemetry does not change semantic_version or cause a cache feedback loop.
            return {"pack_id": rid, "reused": False, "result": report}

    def context_pack_history(self, case_id):
        """Metadata only. Historical content is never offered as current context."""
        case = uuid_text(case_id)
        with self._db() as db:
            revision = self._case(db, case)
            rows = db.execute("SELECT record_id,semantic_version,payload_digest,payload FROM baglam_paketleri WHERE case_id=? ORDER BY record_id", [case]).fetchall()
            result = []
            for rid, original_revision, digest, raw in rows:
                report = validate_pack(json.loads(raw))
                if hash_value(report) != digest or report["case_id"] != case or report["semantic_version"] != original_revision:
                    raise CoreError("BAGLAM_BOZUK", "Geçmiş bağlam kaydı farklı")
                result.append({"pack_id": str(rid), "semantic_version": original_revision, "original_status": report["status"],
                               "state": "NEEDS_REVIEW" if original_revision != revision or self._invalid(db, case, [str(rid)]) else "RECHECK_REQUIRED",
                               "request": report["request"]})
            return {"case_id": case, "semantic_version": revision, "packs": result}

    def context_source_map(self, case_id, *, policy_version="1"):
        """All already-read source units, including notes/tables/annex documents. No parsing side effect."""
        case = uuid_text(case_id)
        validate_policy(policy_version)
        with self._db() as db:
            revision = self._case(db, case)
            versions = db.execute("SELECT record_id FROM belge_surumu WHERE case_id=? ORDER BY record_id", [case]).fetchall()
            if len(versions) > 128:
                raise CoreError("BAGLAM_SINIRI", "Kaynak haritası sürüm sınırı")
            nodes = db.execute("SELECT record_id,payload FROM icerik_birimleri WHERE case_id=? AND node_kind='SOURCE_UNIT'", [case]).fetchall()
            registered = {}
            for rid, raw in nodes:
                self._context_node(db, case, str(rid), policy_version)
                spec = json.loads(raw)["spec"]
                registered.setdefault((spec["version_id"], spec["reading_id"], spec["target"]["unit_id"]), []).append(str(rid))
            result, count = [], 0
            for version, in versions:
                version = str(version)
                data, sha, document, reasons = self._context_version(db, case, version, policy_version)
                rows = db.execute("SELECT record_id FROM isleme_calismalari WHERE case_id=? AND document_version_id=? AND tool IN ('p2-docx','p2-pdf','p2-xlsx','p2-eml') ORDER BY record_id", [case, version]).fetchall()
                readings = []
                for reading_id, in rows:
                    reading_id = str(reading_id)
                    reading, profile = self._verification_reading(db, case, version, reading_id, data)
                    if profile != reading_profile(reading["format"], policy_version)[1]:
                        continue
                    units = []
                    for unit in reading["units"]:
                        count += 1
                        if count > 4096:
                            raise CoreError("BAGLAM_SINIRI", "Kaynak haritası birim sınırı; sessiz kesilmedi")
                        units.append({"unit_id": unit["unit_id"], "kind": unit["kind"], "locator": unit["locator"],
                                      "attributes": unit["attributes"],
                                      "view_characters": {key: len(text) for key, text in unit["views"].items() if text is not None},
                                      "registered_node_ids": sorted(registered.get((version, reading_id, unit["unit_id"]), []))})
                    readings.append({"reading_id": reading_id, "format": reading["format"], "units": units, "issues": reading["issues"]})
                result.append({"version_id": version, "document_id": document, "source_sha256": sha, "reasons": reasons,
                               "reading_status": "PARTIAL" if readings else "NOT_READ_FOR_CURRENT_PROFILE", "readings": readings})
            return {"case_id": case, "semantic_version": revision, "versions": result, "unit_count": count,
                    "scope": "ALL_REGISTERED_VERSIONS_AND_EXISTING_CURRENT_PROFILE_READINGS", "semantic_mapping": "UNVERIFIED",
                    "critical_analysis_allowed": False, "limitations": LIMITATIONS}
