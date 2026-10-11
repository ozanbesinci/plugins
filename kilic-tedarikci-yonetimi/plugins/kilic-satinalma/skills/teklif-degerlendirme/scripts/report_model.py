"""WP-047/048 conservative projection; never creates a reviewed decision snapshot."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from common import json_text, sha256_file
from db import connect, rows_as_dict

STATUS_MAP = {"compliant":"COMPLIANT", "noncompliant":"NONCOMPLIANT",
              "not_stated":"NOT_STATED", "requires_rfi":"REQUIRES_CONFIRMATION",
              "partial":"REQUIRES_CONFIRMATION", "conflict":"CONFLICTING",
              "not_applicable":"NOT_APPLICABLE", "uygunsuz":"NONCOMPLIANT",
              "fail":"NONCOMPLIANT", "failed":"NONCOMPLIANT"}
MATRIX_HEADERS = ["Firma", "Teklif", "Madde", "Beklenen", "Durum", "Önem",
                  "Karar etkisi", "Gerekçe", "Şartname kanıtı", "Teklif kanıtı"]

def decode(value, default=None):
    if isinstance(value, (dict,list)): return value
    try: return json.loads(value)
    except (ValueError, TypeError): return default

def matrix(snapshot):
    """Projection only; not_stated and provisional judgments cannot become exclusions."""
    docs = {x["document_id"]: x for x in snapshot.get("documents", [])}
    evidence = {x["evidence_id"]: x for x in snapshot.get("evidence", [])}
    suppliers = {x["supplier_id"]: x["display_name"] for x in snapshot.get("suppliers", [])}
    facts = {}
    for f in snapshot.get("facts", []):
        if f.get("requirement_id") and f.get("field_key") == "requirement_status":
            key = (f.get("offer_id"), f["requirement_id"])
            if key in facts: raise ValueError("Duplicate requirement assessment grain")
            facts[key] = f

    def binding(eid, offer=None):
        ev = evidence.get(eid)
        if not ev: return None
        doc = docs.get(ev.get("document_id"))
        if not doc or ev.get("source_sha256") != doc.get("sha256"):
            raise ValueError("Requirement evidence document/hash mismatch")
        if offer and (doc.get("offer_id") != offer["offer_id"] or
                      doc.get("supplier_id") != offer["supplier_id"]):
            raise ValueError("Requirement evidence belongs to another supplier/offer")
        return {"evidence_id":eid, "document_id":doc["document_id"], "sha256":doc["sha256"],
                "locator":decode(ev.get("locator_json"),{}), "quote":ev.get("quote"),
                "evidence_status":ev.get("evidence_status")}

    rows = []
    for offer in snapshot.get("offers", []):
        for req in snapshot.get("requirements", []):
            f = facts.get((offer["offer_id"], req["requirement_id"]), {})
            if f and f.get("supplier_id") != offer["supplier_id"]:
                raise ValueError("Requirement fact supplier/offer mismatch")
            spec = binding(req.get("evidence_id"))
            if spec and spec["document_id"] != req.get("source_document_id"):
                raise ValueError("Requirement evidence is not its specification document")
            proof = binding(f.get("evidence_id"), offer)
            status = STATUS_MAP.get(str(f.get("value_text") or "").casefold(), "NOT_STATED")
            certainty = f.get("evidence_status")
            if certainty == "unreadable": status = "UNREADABLE"
            elif certainty == "conflicting": status = "CONFLICTING"
            elif certainty in {"requires_confirmation","assumption"}: status = "REQUIRES_CONFIRMATION"
            elif status in {"COMPLIANT","NONCOMPLIANT","NOT_APPLICABLE"} and (
                    certainty != "verified" or not proof or not spec or
                    proof["evidence_status"] != "verified" or spec["evidence_status"] != "verified"):
                status = "REQUIRES_CONFIRMATION"
            critical = bool(req.get("critical"))
            exclusion = next((x for x in snapshot.get("exclusions", [])
                              if x.get("offer_id")==offer["offer_id"] and
                              x.get("requirement_id")==req["requirement_id"] and
                              x.get("status")=="confirmed" and x.get("decision")=="exclude"), None)
            effect = "EXCLUDE_OFFER" if exclusion and status=="NONCOMPLIANT" else (
                     "BLOCK_RECOMMENDATION" if critical and status not in
                     {"COMPLIANT","NOT_APPLICABLE"} else "WARNING" if status!="COMPLIANT" else "NONE")
            rows.append({"supplier_id":offer["supplier_id"],"supplier":suppliers.get(offer["supplier_id"],offer["supplier_id"]),
                         "offer_id":offer["offer_id"],"offer_status":offer.get("status"),
                         "requirement_id":req["requirement_id"],"expected":req.get("text"),
                         "status":status,"severity":"CRITICAL" if critical else "MEDIUM",
                         "decision_effect":effect,"reason":exclusion.get("reason") if exclusion else
                         "Kaynak hükmü; eksiklik ve uygunsuzluk ayrı gösterilir.",
                         "spec_evidence":spec,"offer_evidence":proof})
    return sorted(rows, key=lambda x: (0 if x["status"]=="NONCOMPLIANT" and x["severity"]=="CRITICAL"
                                      else 1 if x["severity"]=="CRITICAL" else 2,
                                      x["supplier_id"],x["offer_id"],x["requirement_id"]))

def matrix_values(row):
    return [row["supplier"],row["offer_id"],row["requirement_id"],row["expected"],
            row["status"],row["severity"],row["decision_effect"],row["reason"],
            json_text(row["spec_evidence"]),json_text(row["offer_evidence"])]

def current_excluded_offers(model):
    """Read current mandatory facts; retain only requirement-free explicit exclusions.

    Historical requirement exclusions are audit records, not current membership.
    Rendering must neither run the mutating engine nor rewrite those records.
    """
    mandatory = {r['requirement_id'] for r in model['requirements']
                 if r.get('category') == 'mandatory'}
    excluded = {f['offer_id'] for f in model['facts']
                if f.get('requirement_id') in mandatory
                and f.get('evidence_status') == 'verified'
                and (f.get('value_text') or '').casefold() in
                    {'noncompliant', 'uygunsuz', 'fail', 'failed'}}
    excluded.update(e['offer_id'] for e in model['exclusions']
                    if e.get('status') == 'confirmed' and e.get('decision') == 'exclude'
                    and not e.get('requirement_id'))
    return excluded


def build_preliminary(run_root: Path, reason: str):
    # Do not create a DB merely to emit a safety notice.
    model = {"schema":"teklif-report-model/v1","profile":"standart",
             "decision_assurance":"NO_DECISION","comparison_status":"BLOCKED",
             "content_status":"PRELIMINARY","recommendation":None,"ranking":[],
             "limitations":[reason,"Ön rapor satınalma onayı veya doğrulanmış öneri değildir."],
             "documents":[],"suppliers":[],"offers":[],"facts":[],"evidence":[],
             "requirements":[],"exclusions":[],"open_issues":[],"calculations":[],
             "integrity_findings":[],"buyer_declarations":[],"buyer_quantity_totals":[]}
    try:
        if not any((run_root / name).is_file() for name in ("analysis.test.sqlite","analysis.duckdb")):
            raise ValueError("Çalışma veri deposu bulunamadı")
        con = connect(run_root)
        try:
            con.execute("BEGIN TRANSACTION")
            meta = dict(con.execute("SELECT key,value FROM run_meta").fetchall())
            model["profile"] = meta.get("profile","standart")
            for table in ("documents","suppliers","offers","facts","evidence","requirements","exclusions","open_issues"):
                model[table] = rows_as_dict(con, f"SELECT * FROM {table}")
            from preliminary_buyer_values import project
            model['buyer_declarations'],model['buyer_quantity_totals']=project(con,model)
            # Do not promote calculation records or existing decision_summary into a reviewed result.
        finally:
            con.close()
        for doc in model["documents"]:
            metadata = decode(doc.get("metadata_json"),{}) or {}
            archive = run_root / str(metadata.get("archived_source_path") or
                                    f"source_archive/{doc['sha256']}{doc.get('extension') or ''}")
            if not archive.resolve().is_relative_to(run_root.resolve()):
                raise ValueError("Kaynak arşivi çalışma klasörü dışında")
            if not archive.is_file() or sha256_file(archive) != doc["sha256"]:
                raise ValueError("Kaynak arşivi hash uyuşmazlığı: "+doc["relative_path"])
        model["matrix"] = matrix(model)
        active = [o for o in model["offers"] if o.get("status")=="active"]
        excluded = current_excluded_offers(model)
        eligible = [o for o in active if o["offer_id"] not in excluded]
        suppliers = {o["supplier_id"] for o in eligible}
        model["comparison_status"] = ("NO_ELIGIBLE_OFFERS" if not eligible else
             "NOT_APPLICABLE_SINGLE_SUPPLIER" if len(suppliers)<=1 else "BLOCKED")
        if not model["requirements"]:
            model["limitations"].append("Şartname maddesi yok veya çıkarılamadı; teknik uygunluk değerlendirilmedi.")
        if not active: model["limitations"].append("Aktif teklif yok; maliyet hesaplanamadı.")
        model["source_digest"] = hashlib.sha256(json_text(sorted(
            [(d["document_id"],d["sha256"]) for d in model["documents"]])).encode()).hexdigest()
    except Exception as exc:
        model.update(decision_assurance="BLOCKED_INTEGRITY", content_status="SAFETY_NOTICE",
                     comparison_status="BLOCKED", documents=[],suppliers=[],offers=[],
                     facts=[],evidence=[],requirements=[],exclusions=[],matrix=[],open_issues=[],
                     buyer_declarations=[],buyer_quantity_totals=[])
        model["integrity_findings"].append(str(exc))
        model["limitations"].append("Bütünlük sorunu nedeniyle teklif değerleri yayımlanmadı.")
    return model
