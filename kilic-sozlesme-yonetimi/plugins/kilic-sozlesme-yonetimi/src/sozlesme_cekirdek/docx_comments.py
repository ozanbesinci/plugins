"""Classic comments only. Audience is explicit plan data, never inferred legal authority."""
from copy import deepcopy
from lxml import etree
from .errors import CoreError
from .readers.common import Package,REL
from .readers.docx import W,q

R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT="http://schemas.openxmlformats.org/package/2006/content-types"
SPACE="{http://www.w3.org/XML/1998/namespace}space"
MAIN="word/document.xml"


def serialize(root):
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8",standalone=True)


def classic_comments(package):
    rels=[x for x in package.relationships if x["type"]==R+"/comments"]
    if len(rels)>1 or any(x["external"] or x["source"]!=MAIN for x in rels):
        raise CoreError("P5_COMMENT_SCOPE","Yorum ilişkisi belirsiz veya ana belge dışında")
    if any("comment" in n.casefold() and n not in {"word/comments.xml"} for n in package.parts):
        raise CoreError("P5_COMMENT_SCOPE","Modern/genişletilmiş yorum yapısı bu dilimde desteklenmiyor")
    name=rels[0]["resolved_part"] if rels else None
    if name and (name!="word/comments.xml" or package.roots[name].tag!=q("comments")):
        raise CoreError("P5_COMMENT_SCOPE","Klasik yorum parçası gerekli")
    if "word/comments.xml" in package.parts and name is None:
        raise CoreError("P5_COMMENT_SCOPE","Sahipsiz yorum parçası")
    for n,root in package.roots.items():
        if n not in {MAIN,name} and any(x.tag in {q("commentRangeStart"),q("commentRangeEnd"),q("commentReference")} for x in root.iter()):
            raise CoreError("P5_COMMENT_SCOPE","Yan parçada yorum işareti desteklenmiyor")
    return name


def add_comment_parts(parts,details,*,author,when,main_root=None):
    if not details: return []
    package=Package(parts_bytes(parts))
    name=classic_comments(package)
    changed=[]
    if name is None:
        name="word/comments.xml"
        root=etree.Element(q("comments"),nsmap={"w":W})
        relname="word/_rels/document.xml.rels"
        rels=deepcopy(package.roots[relname]) if relname in package.roots else etree.Element("{"+REL+"}Relationships",nsmap={None:REL})
        rid="p5Comments"
        if any(x.get("Id")==rid for x in rels): raise CoreError("P5_COMMENT_SCOPE","Yorum ilişki kimliği mevcut")
        etree.SubElement(rels,"{"+REL+"}Relationship",Id=rid,Type=R+"/comments",Target="comments.xml")
        parts[relname]=serialize(rels)
        types=deepcopy(package.roots["[Content_Types].xml"])
        etree.SubElement(types,"{"+CT+"}Override",PartName="/"+name,ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml")
        parts["[Content_Types].xml"]=serialize(types)
        changed.extend([relname,"[Content_Types].xml"])
    else: root=deepcopy(package.roots[name])
    existing={x.get(q("id")) for x in root}
    for entry in details:
        cid=entry["comment_id"]
        if cid in existing: raise CoreError("P5_COMMENT_SCOPE","Yeni yorum ID'si kaynakla çakışıyor")
        existing.add(cid)
        comment=etree.SubElement(root,q("comment"),attrib={q("id"):cid,q("author"):author,q("date"):when,q("initials"):"AI"})
        p=etree.SubElement(comment,q("p"));r=etree.SubElement(p,q("r"));t=etree.SubElement(r,q("t"))
        t.set(SPACE,"preserve");t.text=entry["text"]
        if main_root is not None:
            nodes=[x for x in main_root.iter(q("ins")) if x.get(q("id"))==entry["anchor_revision_id"]]
            if len(nodes)!=1: raise CoreError("P5_COMMENT_SCOPE","Yorum tek yeni ekleme revizyonuna bağlanmalı")
            node=nodes[0];parent=node.getparent();index=parent.index(node)
            parent.insert(index,etree.Element(q("commentRangeStart"),attrib={q("id"):cid}))
            parent.insert(index+2,etree.Element(q("commentRangeEnd"),attrib={q("id"):cid}))
            reference=etree.Element(q("r"))
            etree.SubElement(reference,q("commentReference"),attrib={q("id"):cid})
            parent.insert(index+3,reference)
    parts[name]=serialize(root)
    return [name,*changed]


def parts_bytes(parts):
    from .docx_revisions import packed
    return packed(parts)


def strip_comment_anchors(root,ids):
    for node in list(root.iter()):
        if node.tag in {q("commentRangeStart"),q("commentRangeEnd"),q("commentReference")} and node.get(q("id")) in ids:
            parent=node.getparent();parent.remove(node)
            if parent.tag==q("r") and all(x.tag==q("rPr") for x in parent): parent.getparent().remove(parent)


def comment_details(package,request,changes,*,next_id):
    entries=request["payload"]["content_plan"].get("comments",[])
    if not entries: return []
    classic_comments(package)
    if request["plan"]["purpose"]!="INTERNAL_DRAFT" and any(x["audience"]!="EXTERNAL" for x in entries):
        raise CoreError("P5_INTERNAL_COMMENT","İç yorum dış amaçlı revizyonlu nüshaya taşınamaz")
    result=[];indices=set()
    for entry in entries:
        index=entry["change_index"]
        if index>=len(changes) or index in indices or not changes[index]["new_text"]:
            raise CoreError("P5_COMMENT_SCOPE","Her yorum tek ve metin içeren yeni değişikliğe bağlanmalı")
        text=entry["text"]
        if not text.strip() or any(ord(c)<32 or 0xD800<=ord(c)<=0xDFFF for c in text):
            raise CoreError("P5_COMMENT_SCOPE","Yorum tek normal metin olmalı")
        if next_id>2147483647: raise CoreError("P5_REVISION_ID","Yorum ID aralığı dolu")
        result.append({**entry,"comment_id":str(next_id),"anchor_revision_id":changes[index]["revision_ids"][-1]})
        next_id+=1;indices.add(index)
    return result
