import json
from pathlib import Path
import tempfile
import unittest
from ortam_ve_belge import extract, render_pages
from kayit_temeli import inventory, sha


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)

    def test_unknown_format_is_preserved_and_not_silently_read(self):
        source=self.root/'proposal.unknown'; source.write_bytes(b'Not parsed')
        self.assertEqual(len(inventory(self.root)['entries']),1)
        result=extract(source,self.root/'parsed')
        self.assertEqual(result['status'],'UNVERIFIED'); self.assertEqual(result['source_sha256'],sha(source))

    def test_hidden_sheet_row_column_and_formula_are_included(self):
        from openpyxl import Workbook
        source=self.root/'test.xlsx'; w=Workbook(); s=w.create_sheet('Hidden evidence'); s.sheet_state='hidden'
        s['A1']='=1+2'; s.row_dimensions[1].hidden=True; s.column_dimensions['A'].hidden=True; w.save(source); w.close()
        result=extract(source,self.root/'parsed'); evidence=result['parts'][1]
        self.assertEqual(evidence['state'],'hidden'); self.assertEqual(evidence['hidden_rows'],[1]); self.assertEqual(evidence['hidden_columns'],['A'])
        self.assertIn('=1+2',(self.root/'parsed'/evidence['text_file']).read_text())

    def test_mail_attachment_cannot_be_silently_ignored(self):
        from email.message import EmailMessage
        m=EmailMessage(); m['Subject']='Synthetic'; m.set_content('Offer attached'); m.add_attachment(b'fake pdf',maintype='application',subtype='pdf',filename='quote.pdf')
        source=self.root/'test.eml'; source.write_bytes(m.as_bytes()); result=extract(source,self.root/'parsed')
        self.assertEqual(result['status'],'PARTIAL'); self.assertTrue(result['parts'][0]['attachments'][0]['needs_read'])

    def test_pdf_original_page_image_has_source_and_image_hash(self):
        from pypdf import PdfWriter
        source=self.root/'test.pdf'; w=PdfWriter(); w.add_blank_page(width=200,height=200)
        with source.open('wb') as out: w.write(out)
        before=sha(source); report=render_pages(source,self.root/'images',[1])
        self.assertEqual(report['source_sha256'],before); self.assertEqual(sha(source),before)
        self.assertEqual(report['images'][0]['image_sha256'],sha(report['images'][0]['image_path']))


if __name__=='__main__': unittest.main()
