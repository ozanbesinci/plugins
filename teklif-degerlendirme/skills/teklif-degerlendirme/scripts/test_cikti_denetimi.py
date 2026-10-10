import tempfile
from pathlib import Path
import unittest
import zipfile

from cikti_denetimi import validate_xlsx, validate_pdf


def workbook_fixture(path, cache="2", error=False, string=False):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        z.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Kontrol" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        attr = ' t="e"' if error else ' t="str"' if string else ''
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"{attr}><f>1+1</f><v>{cache}</v></c></row></sheetData></worksheet>')


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="teklif-artifact-test-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "test.xlsx"

    def test_structural_workbook_and_cache(self):
        workbook_fixture(self.path)
        self.assertEqual(validate_xlsx(self.path)["formulas"], 1)

    def test_zip_header_is_not_workbook(self):
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
        with self.assertRaises(ValueError): validate_xlsx(self.path)

    def test_missing_cached_value_blocks(self):
        workbook_fixture(self.path, cache="")
        with self.assertRaises(ValueError): validate_xlsx(self.path)

    def test_formula_error_blocks(self):
        workbook_fixture(self.path, cache="#DIV/0!", error=True)
        with self.assertRaises(ValueError): validate_xlsx(self.path)

    def test_excel_empty_string_cache_is_valid(self):
        workbook_fixture(self.path, cache='', string=True)
        self.assertEqual(validate_xlsx(self.path)['formulas'],1)

    def test_numeric_cache_must_be_finite_number(self):
        for value in ('NOT_A_NUMBER','NaN','Infinity'):
            workbook_fixture(self.path,cache=value)
            with self.assertRaises(ValueError): validate_xlsx(self.path)

    def test_truncated_pdf_blocks(self):
        p = self.path.with_suffix(".pdf"); p.write_bytes(b"%PDF-1.7 fake")
        with self.assertRaises(ValueError): validate_pdf(p)


if __name__ == "__main__": unittest.main()
