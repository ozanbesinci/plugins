"""Fresh per-user runtime smoke checks; no registration on partial success."""
import argparse
import hashlib
import os
import importlib.metadata
import json
from pathlib import Path
import platform
import struct
import sys
import tempfile

def verify(profile, native=None):
    if platform.system()!='Windows' or struct.calcsize('P')!=8 or not platform.python_version().startswith(profile['python_series']+'.'):
        raise ValueError('Windows cp314/64-bit Python required')
    for name,version in profile['packages'].items():
        if importlib.metadata.version(name)!=version: raise ValueError('Locked package mismatch: '+name)
    if native:
        bootstrap=Path(sys.prefix)/'Lib/site-packages/kilic_native_runtime.pth'
        if hashlib.sha256(bootstrap.read_bytes()).hexdigest()!=native['bootstrap_sha256']:
            raise ValueError('Microsoft yerel DLL yükleme girişi değişmiş.')
        bootstrap=Path(sys.prefix)/'Lib/site-packages/kilic_native_runtime.pth'
        if hashlib.sha256(bootstrap.read_bytes()).hexdigest()!=native['bootstrap_sha256']:
            raise ValueError('Microsoft yerel DLL yükleme girişi değişmiş.')
        for name,wanted in native['dlls'].items():
            path=Path(sys.prefix)/'Scripts'/name
            if hashlib.sha256(path.read_bytes()).hexdigest()!=wanted:
                raise ValueError('Microsoft yerel DLL kilidi uyuşmuyor: '+name)
    import duckdb,openpyxl,pypdf,pdfplumber,pypdfium2,docx,PIL,jsonschema,reportlab,fitz,win32com.client
    with tempfile.TemporaryDirectory(prefix='kilic-runtime-check-') as directory:
        root=Path(directory)
        with duckdb.connect(':memory:') as connection:
            if connection.execute('SELECT 41+1').fetchone()[0]!=42: raise ValueError('DuckDB smoke failed')
        book=openpyxl.Workbook();book.active['A1']=42;book.save(root/'check.xlsx');book.close()
        book=openpyxl.load_workbook(root/'check.xlsx');assert book.active['A1'].value==42;book.close()
        document=docx.Document();document.add_paragraph('Runtime 42');document.save(root/'check.docx')
        assert docx.Document(root/'check.docx').paragraphs[0].text=='Runtime 42'
        from reportlab.pdfgen.canvas import Canvas
        canvas=Canvas(str(root/'check.pdf'));canvas.drawString(30,700,'Runtime 42');canvas.save()
        assert 'Runtime 42' in pypdf.PdfReader(root/'check.pdf').pages[0].extract_text()
        with fitz.open(root/'check.pdf') as document: assert 'Runtime 42' in document[0].get_text()
    return {'schema':'kilic-offer-runtime/v1','profile_id':profile['id'],'lock_sha256':profile['lock_sha256'],
            'machine_id':hashlib.sha256((platform.node()+'\0'+os.environ.get('USERNAME','')).encode()).hexdigest(),
            'python':str(Path(sys.executable).resolve()),'environment_root':str(Path(sys.prefix).resolve()),
            'smoke':'PASS','native_excel_recalculation':'NOT_TESTED','duckdb_pdf_extension':'OPTIONAL_NOT_INSTALLED'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True);parser.add_argument('--runtime-id',required=True);parser.add_argument('--output',required=True);parser.add_argument('--native-runtime')
    args=parser.parse_args();profile=json.loads(Path(args.profile).read_text(encoding='utf-8'))
    native=json.loads(Path(args.native_runtime).read_text(encoding='utf-8')) if args.native_runtime else None
    result=verify(profile,native);result['runtime_id']=args.runtime_id
    if native:result['native_windows_runtime']={'version':native['version'],'package_sha256':native['sha256'],'dlls':native['dlls']}
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
