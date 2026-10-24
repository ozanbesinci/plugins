"""Real production reader chain, synthetic sources only; no business acceptance."""
from pathlib import Path
import io
import json
import os
import sys
import zipfile
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from runtime_registry import probe

def sample_docx():
    w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    parts={
      "[Content_Types].xml":'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
      "_rels/.rels":'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
      "word/document.xml":'<w:document xmlns:w="'+w+'"><w:body><w:p><w:r><w:t>Runtime 42</w:t></w:r></w:p></w:body></w:document>'}
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    return out.getvalue()

def smoke():
    observed=probe(ROOT)
    if observed["status"]!="READY":raise ValueError("Runtime profile not ready: "+json.dumps(observed))
    from sozlesme_cekirdek.readers import read_document
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    from openpyxl import Workbook
    writer=PdfWriter();page=writer.add_blank_page(400,300)
    font=DictionaryObject({NameObject("/Type"):NameObject("/Font"),NameObject("/Subtype"):NameObject("/Type1"),NameObject("/BaseFont"):NameObject("/Helvetica")})
    page[NameObject("/Resources")]=DictionaryObject({NameObject("/Font"):DictionaryObject({NameObject("/F1"):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b"BT /F1 12 Tf 30 250 Td (Runtime 42) Tj ET")
    page[NameObject("/Contents")]=writer._add_object(stream)
    pdf=io.BytesIO();writer.write(pdf);writer.close()
    workbook=Workbook();workbook.active.append(["Runtime 42"]);xlsx=io.BytesIO();workbook.save(xlsx);workbook.close()
    samples={"DOCX":sample_docx(),"PDF":pdf.getvalue(),"XLSX":xlsx.getvalue(),
             "EML":b"From: synthetic@example.invalid\r\nTo: test@example.invalid\r\nSubject: runtime\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nRuntime 42\r\n"}
    results={}
    for kind,data in samples.items():
        result=read_document(data,kind)
        if "Runtime 42" not in json.dumps(result,ensure_ascii=False):raise ValueError(kind+" marker missing")
        results[kind]={"status":"PASS","units":len(result["units"])}
    return {"status":"PASS","readers":results,"scope":"SYNTHETIC_PRODUCTION_READER_CHAIN","business_acceptance":"NOT_GRANTED"}

if __name__=="__main__":
    print(json.dumps(smoke(),ensure_ascii=False))
