"""Explicit scoped resolution creates draft copies; never business/legal approval."""
from copy import deepcopy
from datetime import datetime
import hashlib
import re
from uuid import UUID,uuid5
from lxml import etree
from .errors import CoreError
from .guard import action_request,checked
from .readers.common import Package
from .readers.docx import q,read_docx
from .safety import hash_value
from .docx_comments import MAIN,R,classic_comments,serialize,strip_comment_anchors

VERSION="p5-copy-1.0"
TAGS={q("ins"):"INSERTION",q("del"):"DELETION"}


def revision_inventory(package):
    result=[];ids=set()
    for name,root in package.roots.items():
        for node in root.iter():
            local=etree.QName(node).localname if isinstance(node.tag,str) else ""
            if local.endswith("Change") or local in {"moveFrom","moveTo","moveFromRangeStart","moveToRangeStart","cellIns","cellDel","cellMerge"}:
                raise CoreError("P5_COPY_UNSUPPORTED","Biçim/yapı/taşıma revizyonu çözümlenemez")
            if node.tag not in TAGS: continue
            rid=node.get(q("id"))
            if name!=MAIN or node.getparent().tag!=q("p") or not rid or not rid.isdigit() or rid in ids:
                raise CoreError("P5_COPY_UNSUPPORTED","Tekil ana paragraf revizyonu gerekli")
            expected=q("t") if node.tag==q("ins") else q("delText")
            if not len(node) or any(r.tag!=q("r") or len(r.findall(expected))!=1 or any(x.tag not in {q("rPr"),expected} for x in r) for r in node):
                raise CoreError("P5_COPY_UNSUPPORTED","Yalnız normal metin revizyonu çözümlenir")
            author,date=node.get(q("author")),node.get(q("date"))
            if not author or not date: raise CoreError("P5_COPY_UNSUPPORTED","Kaynak revision yazar/tarihi eksik")
            ids.add(rid);result.append({"revision_id":rid,"kind":TAGS[node.tag],"expected_author":author,"expected_date":date})
    return result


def copy_parts(source,plan):
    from .docx_revisions import enable_tracking
    package=Package(source)
    if package.main("DOCX")!=MAIN or any(x["external"] for x in package.relationships) or any(x.startswith("_xmlsignatures/") for x in package.parts):
        raise CoreError("P5_COPY_UNSUPPORTED","Özel/imzalı/dış bağlı paket temiz nüsha olamaz")
    report=read_docx(source)
    if any(x["severity"]=="BLOCKING" for x in report["issues"]): raise CoreError("P5_COPY_UNSUPPORTED","Kaynak yapısı doğrulanamadı")
    for root in package.roots.values():
        if any(x.tag in {q("fldChar"),q("fldSimple"),q("instrText"),q("delInstrText"),q("vanish"),q("webHidden"),q("sdt"),q("txbxContent"),q("altChunk"),q("object")} for x in root.iter()):
            raise CoreError("P5_COPY_UNSUPPORTED","Alan/gizli/özel içerik bu temiz nüsha diliminde kapalı")
    comments=classic_comments(package)
    if plan["mode"]=="EXTERNAL_CLEAN_DRAFT":
        # Unknown metadata/custom parts cannot be advertised as confidential-data free.
        safe={"[Content_Types].xml","_rels/.rels",MAIN,"word/_rels/document.xml.rels","word/styles.xml","word/numbering.xml","word/settings.xml","word/p5-settings.xml","word/comments.xml","word/footnotes.xml","word/endnotes.xml"}
        if any(n not in safe and not re.fullmatch(r"word/(header|footer)[0-9]+\.xml",n) for n in package.parts):
            raise CoreError("P5_COPY_UNSUPPORTED","Dış nüsha için bilinmeyen metadata/ek parça incelemesi gerekli")
        if plan["comment_policy"]!="DROP_ALL": raise CoreError("P5_INTERNAL_COMMENT","Dış temiz nüsha tüm yorumları açıkça kaldırmalı")
    inventory=revision_inventory(package)
    choices=plan["revision_decisions"]
    if len(choices)!=len(inventory) or len({x["revision_id"] for x in choices})!=len(choices):
        raise CoreError("P5_REVISION_SELECTION","Her mevcut revision için bir açık seçim gerekli")
    selected={x["revision_id"]:x for x in choices}
    for revision in inventory:
        choice=selected.get(revision["revision_id"])
        if choice is None or any(choice[k]!=v for k,v in revision.items()):
            raise CoreError("P5_REVISION_SELECTION","Revizyon ID/tür/yazar/tarih seçimi kaynakla farklı")
    root=deepcopy(package.roots[MAIN])
    for node in list(root.iter()):
        if node.tag not in TAGS: continue
        choice=selected[node.get(q("id"))]
        keep=(node.tag==q("ins"))==(choice["decision"]=="ACCEPT")
        parent,index=node.getparent(),node.getparent().index(node)
        if keep:
            for offset,child in enumerate(list(node)):
                for text in child.iter(q("delText")): text.tag=q("t")
                parent.insert(index+offset,child)
        parent.remove(node)
    parts=dict(package.parts)
    allowed=[MAIN,*enable_tracking(package,MAIN,parts)]
    settings_name=allowed[1]
    from .readers.common import xml
    settings=xml(parts[settings_name]);settings.find(q("trackRevisions")).set(q("val"),"false")
    parts[settings_name]=serialize(settings)
    removed=[]
    if plan["comment_policy"]=="DROP_ALL":
        ids={x.get(q("id")) for x in root.iter() if x.tag in {q("commentRangeStart"),q("commentRangeEnd"),q("commentReference")}}
        strip_comment_anchors(root,ids)
        if comments:
            removed.append(comments);del parts[comments]
            relname="word/_rels/document.xml.rels"
            rels=xml(parts[relname])
            for item in list(rels):
                if item.get("Type")==R+"/comments": rels.remove(item)
            parts[relname]=serialize(rels);allowed.append(relname)
            types=xml(parts["[Content_Types].xml"])
            for item in list(types):
                if item.get("PartName")=="/"+comments: types.remove(item)
            parts["[Content_Types].xml"]=serialize(types);allowed.append("[Content_Types].xml")
    parts[MAIN]=serialize(root)
    return parts,list(dict.fromkeys(allowed)),removed,inventory


def validate_copy_manifest(manifest):
    checked("p5_copy_manifest",manifest)
    if manifest["author"]!="AI Kılıç Sözleşme Yönetimi / "+manifest["operation_id"]:
        raise CoreError("P5_MANIFEST","Türev işlem yazarı farklı")
    return manifest


def prepare_copy(data,request,*,when):
    from .docx_revisions import packed,RevisionArtifact
    request=action_request(request)
    plan=request["plan"];copy=request["payload"]["content_plan"].get("clean_copy")
    if plan["action_type"]!="CREATE_CLEAN_COPY" or plan["parameters"]["output_format"]!="DOCX" or len(plan["source_versions"])!=1 or copy is None:
        raise CoreError("P5_COPY_PLAN_REQUIRED","Tek DOCX kaynak ve açık nüsha planı gerekli")
    if plan["purpose"]=="APPROVED_OUTPUT": raise CoreError("P5_BUSINESS_APPROVAL_REQUIRED","Temiz nüsha üretimi iş kararı onayı yaratamaz")
    purpose="INTERNAL_DRAFT" if copy["mode"]=="INTERNAL_RESOLVED_DRAFT" else "EXTERNAL_DRAFT"
    if plan["purpose"]!=purpose: raise CoreError("P5_COPY_SCOPE","Nüsha türü ve iç/dış amaç farklı")
    if request["payload"]["content_plan"].get("comments"): raise CoreError("P5_COPY_SCOPE","Temiz nüshada yeni yorum planı kabul edilmez")
    sha=hashlib.sha256(data).hexdigest()
    if plan["source_versions"][0]["sha256"]!=sha: raise CoreError("P5_SOURCE_HASH","Nüsha kaynağı hash'i farklı")
    try: instant=datetime.fromisoformat(when)
    except (TypeError,ValueError) as exc: raise CoreError("P5_TIME","UTC ISO zamanı gerekli") from exc
    if instant.tzinfo is None or instant.utcoffset().total_seconds()!=0: raise CoreError("P5_TIME","UTC zamanı gerekli")
    parts,allowed,removed,_=copy_parts(data,copy)
    output=packed(parts);original=Package(data)
    operation=plan["operation_id"]
    manifest={"schema_version":VERSION,"case_id":plan["case_id"],"operation_id":operation,
              "artifact_version_id":str(uuid5(UUID(operation),"P5_DERIVED_COPY")),"source_version_id":plan["source_versions"][0]["version_id"],
              "source_sha256":sha,"artifact_sha256":hashlib.sha256(output).hexdigest(),"request_digest":hash_value(request),
              "author":"AI Kılıç Sözleşme Yönetimi / "+operation,"created_at":instant.isoformat().replace("+00:00","Z"),
              "copy_plan":copy,"allowed_modified_parts":allowed,"removed_parts":removed,
              "protected_parts":{n:hashlib.sha256(b).hexdigest() for n,b in original.parts.items() if n not in set(allowed+removed)},
              "business_approval":"NOT_GRANTED","word_qa":"NOT_RUN","visual_qa":"NOT_RUN","production_ready":False}
    validate_copy_manifest(manifest)
    return RevisionArtifact(output,manifest)


def copy_qa(source,artifact):
    manifest=validate_copy_manifest(artifact.manifest)
    if hashlib.sha256(source).hexdigest()!=manifest["source_sha256"] or hashlib.sha256(artifact.data).hexdigest()!=manifest["artifact_sha256"]:
        raise CoreError("P5_QA_FAILED","Nüsha kaynak/çıktı hash'i farklı")
    expected,allowed,removed,_=copy_parts(source,manifest["copy_plan"])
    original,result=Package(source),Package(artifact.data)
    if result.parts!=expected or manifest["allowed_modified_parts"]!=allowed or manifest["removed_parts"]!=removed:
        raise CoreError("P5_QA_FAILED","Nüsha açık seçim/parça planına uymuyor")
    protected={n:hashlib.sha256(b).hexdigest() for n,b in original.parts.items() if n not in set(allowed+removed)}
    if manifest["protected_parts"]!=protected or revision_inventory(result): raise CoreError("P5_QA_FAILED","Nüsha koruma/revision kontrolü farklı")
    return {"status":"PASS","method":"EXPLICIT_SCOPED_REVISION_RESOLUTION_AND_COMMENT_POLICY","source_sha256":manifest["source_sha256"],
            "artifact_sha256":manifest["artifact_sha256"],"word_qa":"NOT_RUN","visual_qa":"NOT_RUN","production_ready":False,"business_approval":"NOT_GRANTED"}
