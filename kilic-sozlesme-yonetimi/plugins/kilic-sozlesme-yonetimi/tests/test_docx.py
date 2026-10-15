"""Engineering tests; fake Word evidence below is distinct from the real native probe."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import duckdb
from lxml import etree
from sozlesme_cekirdek import Store,CoreError
from sozlesme_cekirdek.docx_revisions import (AUTHOR_PREFIX,RevisionArtifact,SyntheticDocxBackend,TestWordEvidence,
                                            prepare_revisions,project_ai,structural_qa,normalized)
from sozlesme_cekirdek.guard import SyntheticGuardRuntime
from sozlesme_cekirdek.readers.common import Package
from sozlesme_cekirdek.readers.docx import NS,q,read_docx,text_of
from sozlesme_cekirdek.safety import canonical,hash_file,hash_value
from guard_fixtures import Clock,Host,KEY,request
from reader_fixtures import docx_bytes,docx_parts,package_bytes

ROOT=Path(__file__).resolve().parents[1]
WHEN="2026-10-04T19:30:00Z"


def edit_request(data,*,case=None,version=None,reading=None,edits=None):
    case,version,reading=case or str(uuid4()),version or str(uuid4()),reading or str(uuid4())
    req=request(case,version,hashlib.sha256(data).hexdigest())
    req["plan"]["action_type"]="APPLY_TRACK_CHANGES"
    units=read_docx(data)["units"]
    changes=[]
    for snippet,old,new in edits or [("Avans oranı","20","15"),("100.000 TL","100.000","120.000")]:
        unit=next(x for x in units if snippet in x["views"]["AFTER"])
        start=unit["views"]["AFTER"].index(old)
        changes.append({"version_id":version,"reading_id":reading,"target":{"format":"DOCX","unit_id":unit["unit_id"],"view":"AFTER","start":start,"end":start+len(old),"expected_text":old,"field_kind":"OBLIGATION"},"new_text":new})
    req["payload"]["changes"]=changes
    req["plan"]["parameters"]["change_plan_sha256"]=hash_value(changes)
    return req


def synthetic_evidence(req,artifact):
    return TestWordEvidence(req["plan"]["operation_id"],hash_value(req),artifact.manifest["source_sha256"],artifact.manifest["artifact_sha256"],True,True,"1"*64)


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.data=docx_bytes()
        self.req=edit_request(self.data)
    def prepare(self,req=None,data=None):
        return prepare_revisions(data or self.data,req or self.req,when=WHEN)
    def error(self,code,fn):
        with self.assertRaises(CoreError) as caught: fn()
        self.assertEqual(code,caught.exception.code)
    def altered(self,artifact,mutator):
        parts=dict(Package(artifact.data).parts)
        mutator(parts)
        data=package_bytes(parts)
        manifest=copy.deepcopy(artifact.manifest)
        manifest["artifact_sha256"]=hashlib.sha256(data).hexdigest()
        return RevisionArtifact(data,manifest)

    def test_real_revision_markup_metadata_and_noncolliding_ids(self):
        artifact=self.prepare()
        root=Package(artifact.data).roots["word/document.xml"]
        revs=list(root.iter(q("ins")))+list(root.iter(q("del")))
        new=[x for x in revs if x.get(q("author"))==artifact.manifest["author"]]
        self.assertEqual(4,len(new))
        self.assertEqual(6,len(revs))
        self.assertEqual(4,len({x.get(q("id")) for x in new}))
        self.assertFalse({"10","11"}&{x.get(q("id")) for x in new})
        self.assertEqual(AUTHOR_PREFIX+self.req["plan"]["operation_id"],artifact.manifest["author"])
        self.assertTrue(all(x.get(q("date"))==WHEN for x in new))
        self.assertTrue(all(not x.findall(".//w:t",NS) and x.findall(".//w:delText",NS) for x in new if x.tag==q("del")))

    def test_ai_reject_returns_previous_structure_and_old_revisions(self):
        artifact=self.prepare()
        rejected=Package(project_ai(artifact.data,artifact.manifest,accept=False))
        original=Package(self.data)
        self.assertEqual(normalized(original.roots["word/document.xml"]),normalized(rejected.roots["word/document.xml"]))
        self.assertEqual("PASS",structural_qa(self.data,artifact)["status"])
        self.assertEqual("NOT_RUN",structural_qa(self.data,artifact)["word_qa"])

    def test_ai_accept_returns_planned_text_without_accepting_old_changes(self):
        artifact=self.prepare()
        accepted=read_docx(project_ai(artifact.data,artifact.manifest,accept=True))
        texts=[x["views"]["AFTER"] for x in accepted["units"]]
        self.assertIn("Avans oranı %15.",texts)
        self.assertIn("120.000 TL",texts)
        self.assertIn("Garanti süresi 36 aydır.",texts)
        self.assertEqual(2,len(accepted["revisions"]))
        self.assertEqual({"Sentetik Tedarikçi","Sentetik Hukuk"},{x["author"] for x in accepted["revisions"]})

    def test_comments_notes_headers_footers_styles_tables_are_preserved(self):
        artifact=self.prepare()
        before,after=Package(self.data),Package(artifact.data)
        for name in ["word/comments.xml","word/footnotes.xml","word/endnotes.xml","word/header1.xml","word/footer1.xml","word/styles.xml"]:
            self.assertEqual(before.parts[name],after.parts[name])
        root1,root2=before.roots["word/document.xml"],after.roots["word/document.xml"]
        for tag in ["tblPr","tblGrid","tcPr","sectPr","commentRangeStart","commentRangeEnd","commentReference","footnoteReference","endnoteReference"]:
            self.assertEqual([normalized(x) for x in root1.iter(q(tag))],[normalized(x) for x in root2.iter(q(tag))],tag)

    def test_multi_run_replacement_preserves_deleted_run_format_and_surroundings(self):
        parts=docx_parts()
        parts["word/document.xml"]=parts["word/document.xml"].replace('<w:r><w:t>Avans oranı %20.</w:t></w:r>', '<w:r><w:rPr><w:b/></w:rPr><w:t>Avans oranı %2</w:t></w:r><w:r><w:rPr><w:i/></w:rPr><w:t>0.</w:t></w:r>')
        data=package_bytes(parts)
        req=edit_request(data,edits=[("Avans oranı","20","15")])
        artifact=self.prepare(req,data)
        self.assertEqual("PASS",structural_qa(data,artifact)["status"])
        root=Package(artifact.data).roots["word/document.xml"]
        deletion=next(x for x in root.iter(q("del")) if x.get(q("author"))==artifact.manifest["author"])
        self.assertEqual(["2","0"],[x.text for x in deletion.iter(q("delText"))])
        self.assertEqual(1,len(deletion.findall(".//w:b",NS)))
        self.assertEqual(1,len(deletion.findall(".//w:i",NS)))

    def test_two_source_relative_ranges_in_one_paragraph_are_applied_descending(self):
        req=edit_request(self.data,edits=[("Avans oranı","Avans","Ödeme avansı"),("Avans oranı","20","15")])
        artifact=self.prepare(req)
        accepted=read_docx(project_ai(artifact.data,artifact.manifest,accept=True))
        self.assertIn("Ödeme avansı oranı %15.",[x["views"]["AFTER"] for x in accepted["units"]])
        self.assertEqual("PASS",structural_qa(self.data,artifact)["status"])

    def test_duplicate_text_uses_exact_unit_location_and_not_search_replace(self):
        parts=docx_parts()
        parts["word/document.xml"]=parts["word/document.xml"].replace('<w:sectPr>','<w:p><w:r><w:t>Avans oranı %20.</w:t></w:r></w:p><w:sectPr>')
        data=package_bytes(parts)
        artifact=self.prepare(edit_request(data,edits=[("Avans oranı","20","15")]),data)
        texts=[x["views"]["AFTER"] for x in read_docx(project_ai(artifact.data,artifact.manifest,accept=True))["units"]]
        self.assertEqual(1,texts.count("Avans oranı %15."))
        self.assertEqual(1,texts.count("Avans oranı %20."))

    def test_existing_revision_overlap_is_blocked_instead_of_flattened(self):
        req=edit_request(self.data,edits=[("Garanti süresi","36","48")])
        self.error("P5_UNSUPPORTED_TARGET",lambda:self.prepare(req))
        req=edit_request(self.data,edits=[("Garanti süresi","Garanti süresi 36","Garanti süresi 48")])
        self.error("P5_UNSUPPORTED_TARGET",lambda:self.prepare(req))

    def test_header_note_and_before_view_targets_are_not_written(self):
        for snippet,old in [("Sentetik üstbilgi","Sentetik"),("Dipnot kapsam","Dipnot")]:
            req=edit_request(self.data,edits=[(snippet,old,"Yeni")])
            self.error("P5_UNSUPPORTED_TARGET",lambda:self.prepare(req))
        req=copy.deepcopy(self.req)
        req["payload"]["changes"][0]["target"]["view"]="BEFORE"
        req["plan"]["parameters"]["change_plan_sha256"]=hash_value(req["payload"]["changes"])
        self.error("P5_UNSUPPORTED_TARGET",lambda:self.prepare(req))

    def test_source_hash_wrong_old_text_and_overlapping_ranges_are_rejected(self):
        req=copy.deepcopy(self.req);req["plan"]["source_versions"][0]["sha256"]="0"*64
        self.error("P5_SOURCE_HASH",lambda:self.prepare(req))
        req=copy.deepcopy(self.req);req["payload"]["changes"][0]["target"]["expected_text"]="99"
        req["plan"]["parameters"]["change_plan_sha256"]=hash_value(req["payload"]["changes"])
        self.error("P5_OLD_TEXT_MISMATCH",lambda:self.prepare(req))
        req=copy.deepcopy(self.req);req["payload"]["changes"].append(copy.deepcopy(req["payload"]["changes"][0]))
        req["plan"]["parameters"]["change_plan_sha256"]=hash_value(req["payload"]["changes"])
        self.error("P5_AMBIGUOUS_TARGET",lambda:self.prepare(req))

    def test_pure_deletion_is_one_real_revision_with_roundtrip(self):
        req=edit_request(self.data,edits=[("Avans oranı","20","")])
        artifact=self.prepare(req)
        self.assertEqual(1,len(artifact.manifest["changes"][0]["revision_ids"]))
        self.assertEqual("PASS",structural_qa(self.data,artifact)["status"])

    def test_noop_multiline_and_unsupported_action_are_explicit(self):
        for new,code in [("20","P5_NO_CHANGE"),("15\nYeni hüküm","P5_UNSUPPORTED_TEXT")]:
            req=edit_request(self.data,edits=[("Avans oranı","20",new)])
            self.error(code,lambda:self.prepare(req))
        req=request(str(uuid4()),str(uuid4()),hashlib.sha256(self.data).hexdigest())
        self.error("P5_UNSUPPORTED_ACTION",lambda:self.prepare(req))

    def test_external_links_signatures_and_fields_stop_before_word(self):
        for kind in ("external","signature","field","header_field"):
            parts=docx_parts()
            if kind=="external":
                parts["word/_rels/document.xml.rels"]=parts["word/_rels/document.xml.rels"].replace('</Relationships>','<Relationship Id="external1" Type="hyperlink" Target="https://example.invalid" TargetMode="External"/></Relationships>')
            elif kind=="signature": parts["_xmlsignatures/sig1.xml"]='<signature/>'
            elif kind=="field": parts["word/document.xml"]=parts["word/document.xml"].replace('<w:sectPr>','<w:p><w:r><w:instrText>DDE</w:instrText></w:r></w:p><w:sectPr>')
            else: parts["word/header1.xml"]=parts["word/header1.xml"].replace('</w:hdr>','<w:p><w:r><w:instrText>DDE</w:instrText></w:r></w:p></w:hdr>')
            data=package_bytes(parts)
            req=edit_request(data)
            self.error("P5_UNSUPPORTED_PACKAGE",lambda:self.prepare(req,data))

    def test_settings_creation_and_existing_protection_are_explicit(self):
        artifact=self.prepare()
        package=Package(artifact.data)
        self.assertEqual("true",package.roots["word/p5-settings.xml"].find(q("trackRevisions")).get(q("val")))
        parts=dict(package.parts)
        root=package.roots["word/p5-settings.xml"]
        etree.SubElement(root,q("documentProtection"))
        parts["word/p5-settings.xml"]=etree.tostring(root)
        data=package_bytes(parts)
        req=edit_request(data,edits=[("Bu belge","Bu belge","Bu kaynak")])
        self.error("P5_PROTECTED_DOCUMENT",lambda:self.prepare(req,data))

    def test_id_overflow_and_xml_control_characters_are_rejected(self):
        parts=docx_parts()
        parts["word/document.xml"]=parts["word/document.xml"].replace('<w:sectPr>','<w:p><w:bookmarkStart w:id="2147483647" w:name="overflow"/><w:bookmarkEnd w:id="2147483647"/></w:p><w:sectPr>')
        data=package_bytes(parts)
        self.error("P5_REVISION_ID",lambda:self.prepare(edit_request(data),data))
        req=edit_request(self.data,edits=[("Avans oranı","20","15\x00")])
        self.error("P5_UNSUPPORTED_TEXT",lambda:self.prepare(req))

    def test_modified_protected_parts_and_forged_allowlist_fail_structural_qa(self):
        artifact=self.prepare()
        changed=self.altered(artifact,lambda parts:parts.update({"word/comments.xml":parts["word/comments.xml"].replace(b'Oran',b'Changed')}))
        self.error("P5_QA_FAILED",lambda:structural_qa(self.data,changed))
        changed.manifest["allowed_modified_parts"].append("word/comments.xml")
        self.error("P5_QA_FAILED",lambda:structural_qa(self.data,changed))

    def test_unplanned_main_story_change_fails_even_with_updated_artifact_hash(self):
        artifact=self.prepare()
        changed=self.altered(artifact,lambda parts:parts.update({"word/document.xml":parts["word/document.xml"].replace(b'Garanti',b'Changed')}))
        self.error("P5_QA_FAILED",lambda:structural_qa(self.data,changed))

    def test_ai_metadata_and_manifest_extra_approval_are_rejected(self):
        artifact=self.prepare()
        changed=self.altered(artifact,lambda parts:parts.update({"word/document.xml":parts["word/document.xml"].replace(artifact.manifest["author"].encode(),b'Fake Legal')}))
        self.error("P5_MANIFEST",lambda:project_ai(changed.data,changed.manifest,accept=True))
        artifact.manifest["approved"]=True
        self.error("SEMA_HATASI",lambda:structural_qa(self.data,artifact))

    def test_same_source_plan_time_is_deterministic_and_source_not_mutated(self):
        first=self.prepare();second=self.prepare()
        self.assertEqual(first,second)
        self.assertEqual(hashlib.sha256(docx_bytes()).hexdigest(),hashlib.sha256(self.data).hexdigest())
        self.assertNotEqual(first.manifest["artifact_version_id"],first.manifest["source_version_id"])

    def test_source_cannot_impersonate_current_ai_operation_author(self):
        parts=docx_parts()
        author=AUTHOR_PREFIX+self.req["plan"]["operation_id"]
        parts["word/document.xml"]=parts["word/document.xml"].replace('Sentetik Tedarikçi',author)
        data=package_bytes(parts)
        req=edit_request(data)
        req["plan"]["operation_id"]=self.req["plan"]["operation_id"]
        self.error("P5_AUTHOR_COLLISION",lambda:self.prepare(req,data))

    def test_invalid_or_non_utc_revision_clock_stops_before_output(self):
        for when in (None,"invalid","2026-10-04T19:30:00","2026-10-04T22:30:00+03:00"):
            self.error("P5_TIME",lambda:prepare_revisions(self.data,self.req,when=when))


class DocxStoreTests(unittest.TestCase):
    def setUp(self):
        runtime=ROOT/"tests/.runtime";runtime.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix="p5-İı-",dir=runtime)
        self.addCleanup(self.temp.cleanup)
        self.area=Path(self.temp.name);self.sources=self.area/"sources";self.sources.mkdir()
        self.path=self.sources/"Sentetik.docx";self.path.write_bytes(docx_bytes())
        self.store=Store(self.area/"work",source_roots=[self.sources],output_root=self.area)
        self.case=self.store.create_case("Sentetik DOCX")
        self.doc=self.store.create_document(self.case,"DOCX",expected_revision=0)
        self.version=self.store.ingest(self.case,self.doc,self.path,expected_revision=self.rev())["version_id"]
        reading=self.store.read_document(self.case,self.version,format="DOCX")
        self.req=edit_request(self.path.read_bytes(),case=self.case,version=self.version,reading=reading["processing_id"])
        self.host,self.clock=Host(self.case),Clock()
        self.backend=SyntheticDocxBackend(when=WHEN,evidence_provider=synthetic_evidence)
        self.runtime=SyntheticGuardRuntime(self.store,identity_provider=self.host,backend=self.backend,signing_key=KEY,clock=self.clock)
    def rev(self): return self.store.case_revision(self.case)
    def issue(self):
        self.host.authorize(self.req)
        return self.runtime.issue_permission(request=self.req,expected_revision=self.rev())["permission_id"]
    def execute(self,permission=None): return self.runtime.execute(request=self.req,permission_id=permission or self.issue())
    def output_count(self):
        with self.store._db() as db: return db.execute("SELECT count(*) FROM docx_turevleri").fetchone()[0]

    def test_real_writer_integrates_guard_and_immutable_derived_version(self):
        before=self.rev()
        result=self.execute()
        self.assertEqual("SIMULATION_COMMITTED",result["state"])
        self.assertEqual(before,self.rev())
        self.assertEqual(1,self.output_count())
        history=self.store.docx_output_history(self.case)["outputs"]
        self.assertEqual("COMMITTED_AND_PRESENT",history[0]["state"])
        self.assertEqual(self.version,history[0]["source_version_id"])
        self.assertNotEqual(self.version,history[0]["artifact_version_id"])
        self.assertEqual("ALLOW",self.runtime.completion_gate(self.case,self.req["plan"]["operation_id"])["decision"])
        self.assertEqual(hashlib.sha256(docx_bytes()).hexdigest(),hash_file(self.path))
        self.assertEqual(6,len(read_docx(Path(result["output_path"]).read_bytes())["revisions"]))

    def test_missing_independent_word_or_visual_evidence_blocks_final_output(self):
        for provider in [None,lambda req,artifact:replace(synthetic_evidence(req,artifact),visual_reviewed=False)]:
            self.backend.evidence_provider=provider
            result=self.execute()
            self.assertEqual("FAILED",result["state"])
            self.assertEqual(0,self.output_count())
            self.assertFalse((self.store.root/self.req["plan"]["parameters"]["target_relative_path"]).exists())
            # Fresh operation after an intentionally failed one, without reusing its permit.
            self.req["plan"]["operation_id"]=str(uuid4())

    def test_evidence_is_bound_to_operation_source_artifact_and_full_request(self):
        for field,value in [("operation_id",str(uuid4())),("source_sha256","0"*64),("artifact_sha256","0"*64),("request_digest","0"*64)]:
            self.backend.evidence_provider=lambda req,artifact,field=field,value=value:replace(synthetic_evidence(req,artifact),**{field:value})
            self.assertEqual("FAILED",self.execute()["state"])
            self.assertEqual(0,self.output_count())
            self.req["plan"]["operation_id"]=str(uuid4())

    def test_derived_db_corruption_blocks_history_and_completion(self):
        self.execute()
        with self.store._db() as db: db.execute("UPDATE docx_turevleri SET artifact=?",[b"corrupt"])
        with self.assertRaises(CoreError):self.store.docx_output_history(self.case)
        self.assertEqual("BLOCK",self.runtime.completion_gate(self.case,self.req["plan"]["operation_id"])["decision"])

    def test_publication_commit_failure_rolls_back_derived_record(self):
        permission=self.issue()
        original=self.runtime._stage
        def failed(db,case,operation,expected,state,**values):
            if state=="SIMULATION_COMMITTED":raise RuntimeError("synthetic commit failure")
            return original(db,case,operation,expected,state,**values)
        with patch.object(self.runtime,"_stage",side_effect=failed):result=self.execute(permission)
        self.assertEqual("RECONCILE_REQUIRED",result["state"])
        self.assertEqual(0,self.output_count())
        self.assertTrue((self.store.root/self.req["plan"]["parameters"]["target_relative_path"]).is_file())

    def test_snapshot_keeps_derived_blob_and_lineage_without_false_file_completion(self):
        self.execute()
        snapshot=self.area/"snapshot";self.store.snapshot(snapshot)
        restored=Store.restore(snapshot,self.area/"restored",source_roots=[self.sources],output_root=self.area)
        history=restored.docx_output_history(self.case)["outputs"]
        self.assertEqual("FINAL_UNAVAILABLE",history[0]["state"])
        with restored._db() as db:
            blob,sha=db.execute("SELECT artifact,artifact_sha256 FROM docx_turevleri").fetchone()
            self.assertEqual(hashlib.sha256(bytes(blob)).hexdigest(),sha)

    def test_source_revocation_and_changed_source_do_not_return_current_output(self):
        self.execute()
        denied=Store(self.area/"work",source_roots=[self.area/"other"],output_root=self.area)
        with self.assertRaises(CoreError) as error:denied.docx_output_history(self.case)
        self.assertEqual("ERISIM_YOK",error.exception.code)
        self.path.write_bytes(b"changed")
        self.assertEqual("NEEDS_REVIEW",self.store.docx_output_history(self.case)["outputs"][0]["state"])

    def test_completion_rechecks_independent_evidence_without_rewriting_history(self):
        self.execute()
        self.backend.evidence_provider=lambda req,artifact:replace(synthetic_evidence(req,artifact),passed=False)
        self.assertEqual("BLOCK",self.runtime.completion_gate(self.case,self.req["plan"]["operation_id"])["decision"])
        self.assertEqual("COMMITTED_AND_PRESENT",self.store.docx_output_history(self.case)["outputs"][0]["state"])

    def test_real_cli_exposes_read_only_derived_history_only(self):
        self.execute()
        cmd=[sys.executable,"-m","sozlesme_cekirdek","--workspace",str(self.store.root),"--output-root",str(self.area),"--source-root",str(self.sources),"docx-output-history","--case-id",self.case]
        result=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",timeout=30)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(1,len(json.loads(result.stdout)["result"]["outputs"]))
        self.assertNotIn("old_text",result.stdout)

    def test_real_004_to_005_migration_and_digest_drift(self):
        from sozlesme_cekirdek.store import MIGRATION,MIGRATION_VERIFIER,MIGRATION_CONTEXT,MIGRATION_GUARD,NOW
        system=self.area/"older/.sistem";system.mkdir(parents=True)
        with duckdb.connect(str(system/"sozlesme.duckdb")) as db:
            for i,path in enumerate([MIGRATION,MIGRATION_VERIFIER,MIGRATION_CONTEXT,MIGRATION_GUARD],1):
                script=path.read_text(encoding="utf-8");db.execute(script)
                db.execute("INSERT INTO sema_gecmisi VALUES(?,?,?,?)",[i,"old",hashlib.sha256(script.encode()).hexdigest(),NOW()])
            db.execute("INSERT INTO dosyalar VALUES(?,?,0,'NEW',?)",[self.case,"Existing",NOW()])
        upgraded=Store(self.area/"older",source_roots=[self.sources],output_root=self.area)
        with upgraded._db() as db:
            self.assertEqual([1,2,3,4,5,6],[x[0] for x in db.execute("SELECT migration_no FROM sema_gecmisi ORDER BY migration_no").fetchall()])
            self.assertEqual(23,db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='main'").fetchone()[0])
        path=self.area/"drift.sql";path.write_text("-- drift",encoding="utf-8")
        with patch("sozlesme_cekirdek.store.MIGRATION_DOCX",path):
            with self.assertRaises(CoreError) as error:Store(self.store.root,source_roots=[self.sources],output_root=self.area)
        self.assertEqual("SEMA_DRIFT",error.exception.code)


if __name__=="__main__":unittest.main()
