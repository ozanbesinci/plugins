"""WordprocessingML inventory and explicitly scoped revision projections."""
from lxml import etree
from ..errors import CoreError
from .common import Package, feature, issue, locator, result_base, unit

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
q = lambda name: "{" + W + "}" + name
REVISIONS = {"ins", "del", "moveFrom", "moveTo"}
CONTENT_ROOTS = {"document", "hdr", "ftr", "comments", "footnotes", "endnotes"}


def path_of(node):
    # Prefix-independent expanded-name XPath-like locator, not a generated clause number.
    elements = []
    for current in [*reversed(list(node.iterancestors())), node]:
        if not isinstance(current.tag, str):
            continue
        index = 1 + sum(x.tag == current.tag for x in current.itersiblings(preceding=True))
        elements.append(current.tag + "[" + str(index) + "]")
    return "/" + "/".join(elements)


def excluded(node, mode):
    for current in [node, *node.iterancestors()]:
        if current.tag in {q("ins"), q("moveTo")} and mode == "BEFORE":
            return True
        if current.tag in {q("del"), q("moveFrom")} and mode == "AFTER":
            return True
    return False


def text_of(node, mode="RAW", *, paragraph=False):
    if excluded(node, mode):
        return ""
    def walk(current):
        if excluded(current, mode):
            return ""
        if paragraph and current is not node and current.tag in {q("p"), q("txbxContent")}:
            return ""  # nested text box paragraphs have their own units.
        if current.tag in {q("t"), q("delText")}:
            return current.text or ""
        if current.tag in {q("instrText"), q("delInstrText")}:
            return (current.text or "") if mode == "RAW" else ""
        if current.tag == q("tab"):
            return "\t"
        if current.tag in {q("br"), q("cr")}:
            return "\n"
        return "".join(walk(child) for child in current)
    return walk(node)


def read_docx(data):
    report = result_base(data, "DOCX", "ooxml-docx", ["lxml"])
    package = Package(data)
    main = package.main("DOCX")
    if package.roots[main].tag != q("document"):
        raise CoreError("DOSYA_TURU", "Word namespace veya ana belge kökü desteklenmiyor")
    package.describe(report)
    counts = {}
    content_names = set()
    for part, root in package.roots.items():
        if root.tag == q("numbering"):
            feature(report, "numbering_definitions", len(root.findall(q("num"))), "PARTIAL",
                    "Tanımlar korundu; görünür liste numarası hesaplanmadı")
        if root.tag == q("styles"):
            feature(report, "style_definitions", len(root.findall(q("style"))), "PARTIAL")
            if root.findall(".//w:vanish", NS):
                issue(report, "STYLE_VISIBILITY", "Stil kaynaklı gizli metin görünürlüğü render gerektirir",
                      locator(part), "BLOCKING")
        if root.tag not in {q(x) for x in CONTENT_ROOTS}:
            continue
        content_names.add(part)
        root_kind = etree.QName(root).localname
        for node in root.iter():
            if not isinstance(node.tag, str) or not node.tag.startswith("{" + W + "}"):
                continue
            local = etree.QName(node).localname
            counts[local] = counts.get(local, 0) + 1
            location = locator(part, path_of(node))
            if local in REVISIONS:
                nested = any(x.tag in {q(r) for r in REVISIONS} for x in node.iterancestors())
                report["revisions"].append({
                    "kind": local, "id": node.get(q("id")), "author": node.get(q("author")),
                    "date": node.get(q("date")), "locator": location, "nested": nested,
                    "raw": text_of(node), "before": text_of(node, "BEFORE"),
                    "after": text_of(node, "AFTER")})
                if nested:
                    issue(report, "NESTED_REVISION", "İç içe revizyon; güvenilir çalışma görünümü kesinleşmedi",
                          location, "BLOCKING")
            if local != "p":
                continue
            ancestors = list(node.iterancestors())
            props = node.find(q("pPr"))
            attrs = {"revision_projection_scope": "TEXT_ONLY_NOT_ACCEPTANCE"}
            if props is not None:
                attrs["paragraph_properties_xml"] = etree.tostring(props, encoding="unicode")
            for container in ancestors:
                if container.tag in {q("comment"), q("footnote"), q("endnote")}:
                    for key in ("id", "author", "date", "type"):
                        if container.get(q(key)) is not None:
                            attrs["container_" + key] = container.get(q(key))
            attrs["table_depth"] = sum(x.tag == q("tbl") for x in ancestors)
            attrs["hidden_run_count"] = len(node.findall(".//w:vanish", NS))
            attrs["comment_ids"] = ",".join(x.get(q("id"), "") for x in
                                           node.findall(".//w:commentReference", NS))
            for note_kind in ("footnote", "endnote"):
                attrs[note_kind + "_ids"] = ",".join(x.get(q("id"), "") for x in
                                                     node.findall(".//w:" + note_kind + "Reference", NS))
            kind = {"hdr": "HEADER", "ftr": "FOOTER", "comments": "COMMENT",
                    "footnotes": "FOOTNOTE", "endnotes": "ENDNOTE"}.get(root_kind, "PARAGRAPH")
            if any(x.tag == q("txbxContent") for x in ancestors):
                kind = "TEXTBOX"
            unit(report, kind, location, text_of(node, paragraph=True),
                 text_of(node, "BEFORE", paragraph=True), text_of(node, "AFTER", paragraph=True),
                 attributes=attrs)
        if part != main and not any(r["resolved_part"] == part for r in package.relationships):
            issue(report, "ORPHAN_CONTENT_PART", "İlişkilendirilmemiş içerik parçası da envanterlendi",
                  locator(part), "BLOCKING")
    for name, count in sorted(counts.items()):
        feature(report, name, count, "TESTED" if name in {"p", "tbl", "ins", "del", "comment"} else "PARTIAL")
    feature(report, "content_parts", len(content_names), "TESTED")
    for name, explanation in {
        "altChunk": "Dış/alternatif içerik okunmadı",
        "object": "Gömülü nesne çalıştırılmadı/okunmadı",
        "fldChar": "Alan kodu ve cached görünüm envanterlendi; yeniden hesaplanmadı",
        "fldSimple": "Alan cached görünümü hesap doğrulaması değildir",
        "numPr": "Numaralandırma referansı korunuyor; görünür madde numarası hesaplanmadı",
        "pPrChange": "Paragraf biçim revizyonu metin izdüşümüyle doğrulanmaz",
        "rPrChange": "Biçim revizyonu ham envanterdedir; render gerekir",
        "tblPrChange": "Tablo biçim revizyonu render gerektirir",
        "vanish": "Gizli metin analitik metne dahildir; görünürlük render ile doğrulanmalı",
        "drawing": "Görsel içeriğin anlamı doğrulanmadı",
        "txbxContent": "Metin kutusu konumu/görünürlüğü render ile doğrulanmalı",
    }.items():
        if counts.get(name):
            issue(report, name.upper(), explanation, severity="BLOCKING" if name in {"altChunk", "object"} else "WARNING")
    for part, root in package.roots.items():
        if root.findall(".//w:pPr/w:rPr/w:del", NS) or root.findall(".//w:trPr/w:del", NS):
            issue(report, "STRUCTURAL_REVISION", "Paragraf işareti/satır revizyonu; metin birleşimi doğrulanmadı",
                  locator(part), "BLOCKING")
        if root.findall(".//{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent"):
            issue(report, "ALTERNATE_CONTENT", "Choice/Fallback görünüm seçimi doğrulanmadı",
                  locator(part), "BLOCKING")
    comment_ids = {x.get(q("id")) for root in package.roots.values() for x in root.iter(q("comment"))}
    for part, root in package.roots.items():
        for reference in root.iter(q("commentReference")):
            if reference.get(q("id")) not in comment_ids:
                issue(report, "MISSING_COMMENT", "Yorum referansı var; yorum içeriği yok",
                      locator(part, path_of(reference)), "BLOCKING")
    report["verification"]["methods"] = ["ZIP_CRC_AND_PART_HASHES", "SAFE_XML", "OOXML_TEXT_REVISION_PROJECTIONS"]
    report["fallback"]["next"] = ["TARGETED_WORD_RENDER", "VISUAL_SOURCE_CHECK"]
    return report
