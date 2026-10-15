"""Bounded real OOXML revisions, with untouched source bytes and explicit operation IDs.

Only plain, unambiguous main-story run ranges are writable. Existing revisions are
never silently accepted or rewritten. Native Word/visual QA is a separate gate.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import zipfile
from uuid import UUID, uuid5

from lxml import etree
from .errors import CoreError
from .guard import TestQA, action_request
from .readers.common import Package, REL
from .readers.docx import NS, W, q, read_docx, text_of, path_of
from .safety import canonical, hash_value, uuid_text

VERSION = "p5-docx-1.0"
AUTHOR_PREFIX = "AI Kılıç Sözleşme Yönetimi / "
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
SPACE = "{http://www.w3.org/XML/1998/namespace}space"
MAX_DATA = 16 * 1024 * 1024


def serialized(root):
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def packed(parts):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            entry = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    data = stream.getvalue()
    if len(data) > MAX_DATA:
        raise CoreError("P5_OUTPUT_LIMIT", "DOCX türevi 16 MiB sınırını aşıyor")
    return data


def normalized(node):
    """Structural equality modulo XML indentation and adjacent identical plain runs."""
    root = deepcopy(node)
    for current in root.iter():
        if current.tag not in {q("t"), q("delText"), q("instrText"), q("delInstrText")}:
            if current.text is not None and not current.text.strip(): current.text = None
        if current.tail is not None and not current.tail.strip(): current.tail = None
    for parent in root.iter():
        previous = None
        for child in list(parent):
            simple = child.tag == q("r") and all(x.tag in {q("rPr"), q("t")} for x in child) and len(child.findall(q("t"))) == 1
            if simple and previous is not None and dict(previous.attrib) == dict(child.attrib):
                a, b = previous.find(q("rPr")), child.find(q("rPr"))
                if (None if a is None else etree.tostring(a)) == (None if b is None else etree.tostring(b)):
                    previous.find(q("t")).text = (previous.find(q("t")).text or "") + (child.find(q("t")).text or "")
                    previous.find(q("t")).set(SPACE, "preserve")
                    parent.remove(child)
                    continue
            previous = child if simple else None
    # xml:space presence is a lexical distinction only when whitespace is involved.
    for text in root.iter(q("t")):
        text.set(SPACE, "preserve")
    return etree.tostring(root, method="c14n")


def safe_run(run):
    return run.tag == q("r") and len(run.findall(q("t"))) == 1 and all(x.tag in {q("rPr"), q("t")} for x in run)


def run_piece(run, text, *, deleted=False):
    result = etree.Element(q("r"), attrib=dict(run.attrib))
    props = run.find(q("rPr"))
    if props is not None: result.append(deepcopy(props))
    value = etree.SubElement(result, q("delText") if deleted else q("t"))
    value.set(SPACE, "preserve")
    value.text = text
    return result


def spans(paragraph, start, end):
    cursor, selected = 0, []
    for index, child in enumerate(paragraph):
        text = text_of(child, "AFTER", paragraph=True)
        next_cursor = cursor + len(text)
        overlaps = cursor < end and start < next_cursor
        interior_marker = not text and start < cursor < end and child.tag != q("pPr")
        if overlaps or interior_marker:
            if not safe_run(child):
                raise CoreError("P5_UNSUPPORTED_TARGET", "Hedef eski revizyon/alan/denetim işaretine dokunuyor")
            if child.findall(".//w:rPrChange", NS) or child.findall(".//w:vanish", NS):
                raise CoreError("P5_UNSUPPORTED_TARGET", "Gizli/biçim revizyonlu run hedefi desteklenmiyor")
            selected.append((index, child, max(start-cursor, 0), min(end-cursor, len(text))))
        cursor = next_cursor
    if not selected or sum(b-a for _, _, a, b in selected) != end-start:
        raise CoreError("P5_AMBIGUOUS_TARGET", "Hedef tekil normal run aralığına bağlanamadı")
    if any(b[0] != a[0]+1 for a,b in zip(selected, selected[1:])):
        raise CoreError("P5_UNSUPPORTED_TARGET", "Hedef arasındaki mevcut işaretler korunmalı")
    return selected


def replace_range(paragraph, target, new, *, author=None, when=None, ids=None):
    selected = spans(paragraph, target["start"], target["end"])
    old = "".join((run.find(q("t")).text or "")[a:b] for _,run,a,b in selected)
    if old != target["expected_text"]:
        raise CoreError("P5_OLD_TEXT_MISMATCH", "Beklenen eski metin gerçek run içeriğiyle farklı")
    first, last = selected[0], selected[-1]
    first_text = first[1].find(q("t")).text or ""
    last_text = last[1].find(q("t")).text or ""
    replacements = []
    if first[2]: replacements.append(run_piece(first[1], first_text[:first[2]]))
    if ids is not None:
        deletion = etree.Element(q("del"), attrib={q("id"): ids[0], q("author"): author, q("date"): when})
        for _,run,a,b in selected: deletion.append(run_piece(run, (run.find(q("t")).text or "")[a:b], deleted=True))
        replacements.append(deletion)
        if new:
            insertion = etree.Element(q("ins"), attrib={q("id"): ids[1], q("author"): author, q("date"): when})
            insertion.append(run_piece(first[1], new))
            replacements.append(insertion)
    elif new:
        replacements.append(run_piece(first[1], new))
    if last[3] < len(last_text): replacements.append(run_piece(last[1], last_text[last[3]:]))
    offset = first[0]
    for _,run,_,_ in selected: paragraph.remove(run)
    for index, replacement in enumerate(replacements): paragraph.insert(offset+index, replacement)


def enable_tracking(package, main, parts):
    relation = [x for x in package.relationships if x["source"]==main and x["type"]==R+"/settings"]
    if len(relation)>1: raise CoreError("P5_SETTINGS_AMBIGUOUS", "Birden çok ayar ilişkisi")
    changed=[]
    if relation:
        name=relation[0]["resolved_part"]
        root=deepcopy(package.roots[name])
        if root.tag!=q("settings"): raise CoreError("P5_SETTINGS_AMBIGUOUS", "Ayar parçası türü farklı")
    else:
        name="word/p5-settings.xml"
        if name in parts: raise CoreError("P5_SETTINGS_AMBIGUOUS", "Yeni ayar parçası adı mevcut")
        root=etree.Element(q("settings"),nsmap={"w":W})
        relname=main.rsplit("/",1)[0]+"/_rels/"+main.rsplit("/",1)[1]+".rels"
        rels=deepcopy(package.roots[relname]) if relname in package.roots else etree.Element("{"+REL+"}Relationships",nsmap={None:REL})
        rid="p5TrackSettings"
        if any(x.get("Id")==rid for x in rels): raise CoreError("P5_SETTINGS_AMBIGUOUS", "Ayar ilişki kimliği mevcut")
        etree.SubElement(rels,"{"+REL+"}Relationship",Id=rid,Type=R+"/settings",Target="p5-settings.xml")
        parts[relname]=serialized(rels)
        content=deepcopy(package.roots["[Content_Types].xml"])
        etree.SubElement(content,"{"+CT+"}Override",PartName="/"+name,ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml")
        parts["[Content_Types].xml"]=serialized(content)
        changed.extend([relname,"[Content_Types].xml"])
    if root.findall(q("documentProtection")) or len(root.findall(q("trackRevisions")))>1:
        raise CoreError("P5_PROTECTED_DOCUMENT", "Koruma/ayar belirsizliği desteklenmiyor")
    track=root.find(q("trackRevisions"))
    if track is None: track=etree.SubElement(root,q("trackRevisions"))
    track.set(q("val"),"true")
    parts[name]=serialized(root)
    return [name,*changed]


@dataclass(frozen=True)
class RevisionArtifact:
    data: bytes
    manifest: dict


def prepare_revisions(data, request, *, when):
    request=action_request(request)
    plan=request["plan"]
    changes=request["payload"].get("changes",[])
    if plan["action_type"]!="APPLY_TRACK_CHANGES" or plan["parameters"]["output_format"]!="DOCX":
        raise CoreError("P5_UNSUPPORTED_ACTION", "İlk P5 dilimi yalnız hedefli DOCX revizyonu üretir")
    versions={x["version_id"] for x in changes}
    if len(versions)!=1: raise CoreError("P5_ONE_SOURCE_REQUIRED", "Tek kaynak DOCX üzerinde revizyon gerekli")
    source_version=next(iter(versions))
    sha=hashlib.sha256(data).hexdigest()
    if next((x["sha256"] for x in plan["source_versions"] if x["version_id"]==source_version),None)!=sha:
        raise CoreError("P5_SOURCE_HASH", "Yazma kaynağı tam izin hash'iyle farklı")
    try:
        instant=datetime.fromisoformat(when)
    except (TypeError,ValueError) as exc:
        raise CoreError("P5_TIME", "Revizyon zamanı geçerli UTC ISO zamanı olmalı") from exc
    if instant.tzinfo is None or instant.utcoffset().total_seconds()!=0:
        raise CoreError("P5_TIME", "Revizyon zamanı UTC olmalı")
    when=instant.isoformat().replace("+00:00","Z")
    operation=plan["operation_id"]
    author=AUTHOR_PREFIX+operation
    package=Package(data)
    main=package.main("DOCX")
    if main!="word/document.xml" or any(x["external"] for x in package.relationships) or any(x.startswith("_xmlsignatures/") for x in package.parts):
        raise CoreError("P5_UNSUPPORTED_PACKAGE", "Özel ana parça/dış ilişki/imzalı paket bu yazma diliminde kapalı")
    report=read_docx(data)
    if any(x["severity"]=="BLOCKING" for x in report["issues"]):
        raise CoreError("P5_SOURCE_UNVERIFIED", "Kaynağın çözülmemiş yapısal okuma sorunu var")
    root=deepcopy(package.roots[main])
    if any(x.tag in {q("fldChar"),q("fldSimple"),q("instrText"),q("delInstrText")} for part in package.roots.values() for x in part.iter()):
        raise CoreError("P5_UNSUPPORTED_PACKAGE", "Alan kodlu belge bu Word test diliminde kapalı")
    if any(x.get(q("author"))==author for part in package.roots.values() for x in part.iter()):
        raise CoreError("P5_AUTHOR_COLLISION", "Yeni işlem yazarı kaynakta zaten mevcut; eski ve yeni revizyon ayrımı belirsiz")
    paragraphs={path_of(p):p for p in root.iter(q("p"))}
    units={x["unit_id"]:x for x in report["units"]}
    used=[]
    for part in package.roots.values():
        for node in part.iter():
            value=node.get(q("id"))
            if value is not None:
                if not value.isdigit() and value not in {"-1","-2"}: raise CoreError("P5_REVISION_ID", "Paket ID alanı geçersiz")
                if value.isdigit(): used.append(int(value))
    next_id=max(used,default=0)+1
    if next_id+2*len(changes)>2147483647: raise CoreError("P5_REVISION_ID", "Revizyon kimliği aralığı dolu")
    resolved,manifest_changes=[],[]
    ranges={}
    for change in changes:
        target=change["target"]
        unit=units.get(target["unit_id"])
        if (unit is None or unit["kind"]!="PARAGRAPH" or unit["locator"]["part"]!=main
                or target["format"]!="DOCX" or target["view"]!="AFTER"):
            raise CoreError("P5_UNSUPPORTED_TARGET", "İlk yazma dilimi yalnız ana belge AFTER paragrafına yazar")
        paragraph=paragraphs[unit["locator"]["path"]]
        if any(x.tag in {q("ins"),q("del"),q("sdt"),q("txbxContent"),q("moveFrom"),q("moveTo")} for x in paragraph.iterancestors()):
            raise CoreError("P5_UNSUPPORTED_TARGET", "Revizyon/denetim kutusu içindeki paragraf yazılamaz")
        start,end=target["start"],target["end"]
        if start>=end or unit["views"]["AFTER"][start:end]!=target["expected_text"]:
            raise CoreError("P5_OLD_TEXT_MISMATCH", "Kaynak hedef alıntısı/aralığı farklı")
        if change["new_text"]==target["expected_text"]:
            raise CoreError("P5_NO_CHANGE", "Aynı metin yeni revizyon olarak kaydedilmez")
        if any(ord(c)<32 or 0xD800<=ord(c)<=0xDFFF for c in change["new_text"]):
            raise CoreError("P5_UNSUPPORTED_TEXT", "Çok paragraf/tab/denetim karakteri revizyonu bu dilimde kapalı")
        path=unit["locator"]["path"]
        if any(start<b and a<end for a,b in ranges.get(path,[])):
            raise CoreError("P5_AMBIGUOUS_TARGET", "Revizyon aralıkları örtüşüyor")
        ranges.setdefault(path,[]).append((start,end))
        spans(paragraph,start,end)  # Validate every range before changing any XML.
        ids=[str(next_id)] + ([str(next_id+1)] if change["new_text"] else [])
        next_id+=len(ids)
        details={"source_version_id":source_version,"reading_id":change["reading_id"],"unit_id":target["unit_id"],
                 "part":main,"path":path,"start":start,"end":end,"old_text":target["expected_text"],"new_text":change["new_text"],"revision_ids":ids}
        manifest_changes.append(details)
        resolved.append((paragraph,deepcopy(target),change["new_text"],ids))
    # Descending offsets keep all source-relative ranges valid within each paragraph.
    for paragraph,target,new,ids in sorted(resolved,key=lambda row:row[1]["start"],reverse=True):
        replace_range(paragraph,target,new,author=author,when=when,ids=ids)
    parts=dict(package.parts)
    parts[main]=serialized(root)
    allowed=[main,*enable_tracking(package,main,parts)]
    from .docx_comments import comment_details,add_comment_parts
    comments=comment_details(package,request,manifest_changes,next_id=next_id)
    if comments:
        allowed+=add_comment_parts(parts,comments,author=author,when=when,main_root=root)
        parts[main]=serialized(root)
        allowed=list(dict.fromkeys(allowed))
    output=packed(parts)
    manifest={"schema_version":VERSION,"case_id":plan["case_id"],"operation_id":operation,
              "artifact_version_id":str(uuid5(UUID(operation),"P5_DERIVED_DOCX")),"source_version_id":source_version,
              "source_sha256":sha,"artifact_sha256":hashlib.sha256(output).hexdigest(),"request_digest":hash_value(request),
              "author":author,"created_at":when,"changes":manifest_changes,"allowed_modified_parts":allowed,
              "protected_parts":{n:hashlib.sha256(b).hexdigest() for n,b in package.parts.items() if n not in allowed},
              "word_qa":"NOT_RUN","visual_qa":"NOT_RUN","production_ready":False}
    if comments: manifest["comments"]=comments
    validate_manifest(manifest)
    return RevisionArtifact(output,manifest)


def validate_manifest(manifest):
    if manifest.get("schema_version")=="p5-copy-1.0":
        from .docx_copies import validate_copy_manifest
        return validate_copy_manifest(manifest)
    from .guard import checked
    checked("p5_revision_manifest",manifest)
    if manifest["author"]!=AUTHOR_PREFIX+manifest["operation_id"]:
        raise CoreError("P5_MANIFEST", "AI işlem yazarı farklı")
    ids=[rid for change in manifest["changes"] for rid in change["revision_ids"]]
    if len(ids)!=len(set(ids)): raise CoreError("P5_MANIFEST", "Yeni revizyon kimlikleri yineleniyor")
    seen_indices=set(); seen_comments=set()
    for comment in manifest.get("comments",[]):
        index=comment["change_index"]
        if index>=len(manifest["changes"]) or index in seen_indices:
            raise CoreError("P5_MANIFEST", "Yorum değişiklik kapsamı farklı")
        change=manifest["changes"][index]
        if (not change["new_text"] or comment["anchor_revision_id"]!=change["revision_ids"][-1]
                or comment["comment_id"] in seen_comments or comment["comment_id"] in ids):
            raise CoreError("P5_MANIFEST", "Yorum kimliği veya hedef revizyonu farklı")
        seen_indices.add(index); seen_comments.add(comment["comment_id"])
    return manifest


def project_ai(data, manifest, *, accept):
    """Internal QA projection only; never accepts/rejects existing third-party changes."""
    validate_manifest(manifest)
    if type(accept) is not bool or hashlib.sha256(data).hexdigest()!=manifest["artifact_sha256"]:
        raise CoreError("P5_MANIFEST", "AI görünüm türevi tam çıktı hash'i gerektirir")
    package=Package(data)
    main=package.main("DOCX")
    root=deepcopy(package.roots[main])
    ids={rid for change in manifest["changes"] for rid in change["revision_ids"]}
    matched=set()
    for node in list(root.iter()):
        if node.tag not in {q("ins"),q("del")} or node.get(q("id")) not in ids: continue
        if node.get(q("author"))!=manifest["author"] or node.get(q("date"))!=manifest["created_at"] or node.get(q("id")) in matched:
            raise CoreError("P5_MANIFEST", "Yeni revizyon metadata'sı/tekilliği farklı")
        matched.add(node.get(q("id")))
        parent,index=node.getparent(),node.getparent().index(node)
        keep=(node.tag==q("ins"))==accept
        if keep:
            for offset,child in enumerate(list(node)):
                for text in child.iter(q("delText")): text.tag=q("t")
                parent.insert(index+offset,child)
        parent.remove(node)
    if matched!=ids: raise CoreError("P5_MANIFEST", "Yeni revizyonların tamamı bulunamadı")
    parts=dict(package.parts)
    if not accept and manifest.get("comments"):
        from .docx_comments import strip_comment_anchors
        strip_comment_anchors(root,{x["comment_id"] for x in manifest["comments"]})
    parts[main]=serialized(root)
    return packed(parts)


def structural_qa(source, artifact):
    if artifact.manifest.get("schema_version")=="p5-copy-1.0":
        from .docx_copies import copy_qa
        return copy_qa(source,artifact)
    manifest=validate_manifest(artifact.manifest)
    if hashlib.sha256(source).hexdigest()!=manifest["source_sha256"] or hashlib.sha256(artifact.data).hexdigest()!=manifest["artifact_sha256"]:
        raise CoreError("P5_QA_FAILED", "Kaynak/çıktı hash'i farklı")
    original,result=Package(source),Package(artifact.data)
    main=original.main("DOCX")
    expected_parts=dict(original.parts)
    allowed_list=[main,*enable_tracking(original,main,expected_parts)]
    comments=manifest.get("comments",[])
    if comments:
        from .docx_comments import add_comment_parts,strip_comment_anchors
        allowed_list+=add_comment_parts(expected_parts,comments,author=manifest["author"],when=manifest["created_at"])
        allowed_list=list(dict.fromkeys(allowed_list))
    if manifest["allowed_modified_parts"]!=allowed_list or any(result.parts.get(n)!=b for n,b in expected_parts.items() if n!=main):
        raise CoreError("P5_QA_FAILED", "Ayar/ilişki/parça izin listesi kaynağa uymuyor")
    allowed=set(allowed_list)
    if set(result.parts)!=set(original.parts)|set(allowed) or any(result.parts.get(n)!=b for n,b in original.parts.items() if n not in allowed):
        raise CoreError("P5_QA_FAILED", "İzin dışı paket parçası değişimi")
    if manifest["protected_parts"]!={n:hashlib.sha256(b).hexdigest() for n,b in original.parts.items() if n not in allowed}:
        raise CoreError("P5_QA_FAILED", "Korunan parça envanteri farklı")
    rejected=Package(project_ai(artifact.data,manifest,accept=False))
    if normalized(rejected.roots[main])!=normalized(original.roots[main]):
        raise CoreError("P5_QA_FAILED", "Yalnız AI reddi önceki çalışma yapısını vermedi")
    expected=deepcopy(original.roots[main])
    paragraphs={path_of(p):p for p in expected.iter(q("p"))}
    for change in sorted(manifest["changes"],key=lambda row:row["start"],reverse=True):
        target={"start":change["start"],"end":change["end"],"expected_text":change["old_text"]}
        replace_range(paragraphs[change["path"]],target,change["new_text"])
    accepted=Package(project_ai(artifact.data,manifest,accept=True))
    if comments: strip_comment_anchors(accepted.roots[main],{x["comment_id"] for x in comments})
    if normalized(accepted.roots[main])!=normalized(expected):
        raise CoreError("P5_QA_FAILED", "Yalnız AI kabulü planlanan çalışma yapısını vermedi")
    # Regeneration bounds the allowed relationship/settings changes as well.
    old_revs=[normalized(x) for x in original.roots[main].iter() if x.tag in {q("ins"),q("del")}]
    old_after=[normalized(x) for x in accepted.roots[main].iter() if x.tag in {q("ins"),q("del")}]
    if old_revs!=old_after: raise CoreError("P5_QA_FAILED", "Önceki revizyonlar korunmadı")
    return {"status":"PASS","method":"SCOPED_OOXML_AI_ACCEPT_REJECT_AND_PROTECTED_PARTS",
            "word_qa":"NOT_RUN","visual_qa":"NOT_RUN","production_ready":False,
            "source_sha256":manifest["source_sha256"],"artifact_sha256":manifest["artifact_sha256"]}


@dataclass(frozen=True)
class TestWordEvidence:
    operation_id: str
    request_digest: str
    source_sha256: str
    artifact_sha256: str
    passed: bool
    visual_reviewed: bool
    evidence_digest: str


class SyntheticDocxBackend:
    """P4 integration confined by its runtime. Evidence adapter is trusted test code only."""
    synthetic_only=True
    version="p5-writer-2.0"
    def __init__(self, *, when, evidence_provider=None):
        self.when,self.evidence_provider=when,evidence_provider
        self.prepared={}
        self.proofs={}
    def prepare_document(self, request, snapshots):
        is_copy=request["plan"]["action_type"]=="CREATE_CLEAN_COPY"
        versions={x["version_id"] for x in (request["plan"]["source_versions"] if is_copy else request["payload"].get("changes",[]))}
        if len(versions)!=1: raise CoreError("P5_ONE_SOURCE_REQUIRED", "Tek kaynak gerekli")
        source=snapshots[next(iter(versions))]
        if is_copy:
            from .docx_copies import prepare_copy
            artifact=prepare_copy(source,request,when=self.when)
        else: artifact=prepare_revisions(source,request,when=self.when)
        self.prepared[request["plan"]["operation_id"]]=(source,artifact,hash_value(request))
        return artifact.data
    def verify_document(self, request, data):
        operation=request["plan"]["operation_id"]
        source,artifact,digest=self.prepared[operation]
        if hash_value(request)!=digest or data!=artifact.data:
            raise CoreError("P5_QA_FAILED", "QA kapsamı değişmiş")
        proof=structural_qa(source,artifact)
        if self.evidence_provider is None: return TestQA(False,artifact.manifest["artifact_sha256"])
        evidence=self.evidence_provider(request,artifact)
        if (type(evidence) is not TestWordEvidence or evidence.operation_id!=operation or evidence.request_digest!=digest
                or evidence.source_sha256!=artifact.manifest["source_sha256"] or evidence.artifact_sha256!=artifact.manifest["artifact_sha256"]
                or evidence.passed is not True or evidence.visual_reviewed is not True
                or not isinstance(evidence.evidence_digest,str) or len(evidence.evidence_digest)!=64
                or any(c not in "0123456789abcdef" for c in evidence.evidence_digest)):
            return TestQA(False,artifact.manifest["artifact_sha256"])
        self.proofs[operation]={**proof,"word_qa":"PASS_WITH_TEST_SCOPE","visual_qa":"PASS_WITH_TEST_SCOPE","evidence_digest":evidence.evidence_digest}
        return TestQA(True,artifact.manifest["artifact_sha256"])
    def export_recovery_payload(self,request,data):
        operation=request["plan"]["operation_id"]
        _,artifact,digest=self.prepared[operation]
        if data!=artifact.data or digest!=hash_value(request):
            raise CoreError("P5_QA_FAILED","Recovery capsule için hazırlama bağı farklı")
        return {"schema_version":"p5-recovery-1.0","manifest":artifact.manifest}
    def restore_recovery_payload(self,request,snapshots,data,payload):
        if not isinstance(payload,dict) or set(payload)!={"schema_version","manifest"} or payload["schema_version"]!="p5-recovery-1.0":
            raise CoreError("P5_OUTPUT_CORRUPT","Recovery backend manifesti geçersiz")
        manifest=validate_manifest(payload["manifest"])
        operation=request["plan"]["operation_id"]
        if (manifest["case_id"]!=request["plan"]["case_id"] or manifest["operation_id"]!=operation
                or manifest["request_digest"]!=hash_value(request)
                or manifest["artifact_sha256"]!=hashlib.sha256(data).hexdigest()
                or manifest["source_version_id"] not in snapshots):
            raise CoreError("P5_OUTPUT_CORRUPT","Recovery artefakt/istek/kaynak bağı farklı")
        source=snapshots[manifest["source_version_id"]]
        artifact=RevisionArtifact(data,manifest)
        structural_qa(source,artifact)
        self.prepared[operation]=(source,artifact,hash_value(request))
    def persist_document(self, db, store, request, data, target):
        from .outputs import persist_docx
        operation=request["plan"]["operation_id"]
        _,artifact,digest=self.prepared[operation]
        if data!=artifact.data or hash_value(request)!=digest or operation not in self.proofs:
            raise CoreError("P5_QA_FAILED", "Türev kayıt için aynı QA gerekli")
        persist_docx(db,store,request,artifact,target,self.proofs[operation])
    def verify_completion(self, db, store, request):
        operation,case=request["plan"]["operation_id"],request["plan"]["case_id"]
        row=db.execute("SELECT metadata,metadata_digest,artifact,artifact_sha256,record_id,source_version_id FROM docx_turevleri WHERE case_id=? AND operation_id=?",[case,operation]).fetchone()
        if not row: raise CoreError("P5_OUTPUT_CORRUPT","Tamamlanma için türev kayıt gerekli")
        metadata=json.loads(row[0])
        artifact=RevisionArtifact(bytes(row[2]),metadata["manifest"])
        manifest=validate_manifest(artifact.manifest)
        if (hash_value(metadata)!=row[1] or manifest["case_id"]!=case or manifest["operation_id"]!=operation
                or manifest["artifact_version_id"]!=str(row[4]) or manifest["source_version_id"]!=str(row[5])
                or manifest["artifact_sha256"]!=row[3] or manifest["request_digest"]!=hash_value(request)
                or metadata["qa"].get("word_qa")!="PASS_WITH_TEST_SCOPE" or metadata["qa"].get("visual_qa")!="PASS_WITH_TEST_SCOPE"):
            raise CoreError("P5_OUTPUT_CORRUPT","Türev kapsam/QA/bütünlük farklı")
        source,_,_,_=store._verification_source(db,case,manifest["source_version_id"],current=True)
        structural_qa(source,artifact)
        if store._invalid(db,case,[str(row[4])]): raise CoreError("YENIDEN_INCELE","Türev geçersizleştirilmiş")
        current=self.evidence_provider(request,artifact) if self.evidence_provider else None
        if (type(current) is not TestWordEvidence or current.operation_id!=operation or current.request_digest!=hash_value(request) or current.source_sha256!=manifest["source_sha256"]
                or current.artifact_sha256!=manifest["artifact_sha256"] or current.passed is not True or current.visual_reviewed is not True
                or current.evidence_digest!=metadata["qa"].get("evidence_digest")):
            raise CoreError("P5_QA_FAILED","Türevün bağımsız test QA kanıtı güncel değil")
