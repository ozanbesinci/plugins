"""Immutable P5 derivative lineage. Metadata/history never grants delivery authority."""
import hashlib
import json
from .errors import CoreError
from .safety import canonical, confined, hash_file, hash_value, native_path, uuid_text


def persist_docx(db,store,request,artifact,target,proof):
    from .docx_revisions import validate_manifest, structural_qa
    manifest=validate_manifest(artifact.manifest)
    case,operation=request["plan"]["case_id"],request["plan"]["operation_id"]
    rid=manifest["artifact_version_id"]
    row=db.execute("SELECT state FROM islemler WHERE case_id=? AND record_id=?",[case,operation]).fetchone()
    if not row or row[0]!="QA_PASSED" or manifest["case_id"]!=case or manifest["operation_id"]!=operation or manifest["request_digest"]!=hash_value(request):
        raise CoreError("P5_OUTPUT_STATE","Türev yalnız aynı QA_PASSED işlem içinde kaydedilir")
    source,_,_,_=store._verification_source(db,case,manifest["source_version_id"],current=True)
    structural_qa(source,artifact)
    if proof.get("artifact_sha256")!=manifest["artifact_sha256"] or proof.get("word_qa")!="PASS_WITH_TEST_SCOPE" or proof.get("visual_qa")!="PASS_WITH_TEST_SCOPE":
        raise CoreError("P5_QA_FAILED","Türev için Word/görsel test kanıtı gerekli")
    if hash_file(target)!=manifest["artifact_sha256"]:
        raise CoreError("P5_QA_FAILED","Final türev hash'i farklı")
    metadata={"manifest":manifest,"qa":proof,"output_key":target.relative_to(store.root).as_posix(),"version_kind":"DERIVED_ARTIFACT_NOT_INPUT_SOURCE","production_ready":False}
    store._record(db,case,"PROCESSING",record_id=rid)
    db.execute("INSERT INTO docx_turevleri VALUES(?,?,?,?,?,?,?,?)",[case,rid,operation,manifest["source_version_id"],manifest["artifact_sha256"],canonical(metadata),hash_value(metadata),artifact.data])
    db.execute("INSERT INTO kanit_baglari VALUES(?,?,?,'SUPPORTS',?)",[case,rid,manifest["source_version_id"],canonical({"derived_docx":True})])
    store._event(db,case,"DOCX_DERIVED_VERSION_REGISTERED",{"artifact_version_id":rid,"operation_id":operation,"source_version_id":manifest["source_version_id"],"sha256":manifest["artifact_sha256"]})


class OutputMixin:
    def docx_output_history(self,case_id):
        from .docx_revisions import validate_manifest
        case=uuid_text(case_id)
        history=[]
        with self._db() as db:
            self._case(db,case)
            rows=db.execute("SELECT record_id,operation_id,source_version_id,artifact_sha256,metadata,metadata_digest,artifact FROM docx_turevleri WHERE case_id=? ORDER BY record_id",[case]).fetchall()
            for rid,operation,source,sha,body,digest,data in rows:
                metadata=json.loads(body)
                manifest=validate_manifest(metadata["manifest"])
                if (set(metadata)!={"manifest","qa","output_key","version_kind","production_ready"} or hash_value(metadata)!=digest
                        or manifest["case_id"]!=case or manifest["artifact_version_id"]!=str(rid) or manifest["operation_id"]!=str(operation)
                        or manifest["source_version_id"]!=str(source) or manifest["artifact_sha256"]!=sha or hashlib.sha256(bytes(data)).hexdigest()!=sha):
                    raise CoreError("P5_OUTPUT_CORRUPT","Türev kayıt/manifest/bayt bütünlüğü farklı")
                # Do not return source text, revisions or internal comments in a history listing.
                state="RECHECK_REQUIRED"
                try:
                    self._verification_source(db,case,str(source),current=True)
                    target=confined(self.root/metadata["output_key"],[self.root])
                    row=db.execute("SELECT state FROM islemler WHERE case_id=? AND record_id=?",[case,operation]).fetchone()
                    if self._invalid(db,case,[str(rid),str(source),str(operation)]): state="NEEDS_REVIEW"
                    elif not row or row[0]!="SIMULATION_COMMITTED": state="RECONCILE_REQUIRED"
                    elif not native_path(target).is_file(): state="FINAL_UNAVAILABLE"
                    elif hash_file(target)!=sha: state="NEEDS_REVIEW"
                    else: state="COMMITTED_AND_PRESENT"
                except CoreError as exc:
                    if exc.code=="ERISIM_YOK": raise
                    state="NEEDS_REVIEW"
                history.append({"artifact_version_id":str(rid),"operation_id":str(operation),"source_version_id":str(source),"sha256":sha,
                                "state":state,"version_kind":metadata["version_kind"],"completion_check_required":True,"production_ready":False,
                                "copy_mode":manifest.get("copy_plan",{}).get("mode"),"business_approval":"NOT_GRANTED"})
        return {"case_id":case,"outputs":history,"production_ready":False}
