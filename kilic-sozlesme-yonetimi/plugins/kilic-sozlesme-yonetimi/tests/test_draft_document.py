"""Focused internal draft tests. Native Office is never invoked by this module."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET
import zipfile

from sozlesme_cekirdek.errors import CoreError
from sozlesme_cekirdek import draft_document as draft


def sections():
    return [{"heading": "Ödeme koşulları", "kind": "DRAFT_TEXT", "text": "Bedel 100 TL & KDV <yüzde 20>.\nİkinci satır ıİşŞğĞüÜöÖçÇ.", "node_ids": []},
            {"heading": "Kullanıcının talebi", "kind": "USER_STATEMENT", "text": '"Vade 30 gün"', "node_ids": ["node-user"]},
            {"heading": "Belgedeki hüküm", "kind": "SOURCE_EXCERPT", "text": "Teslim süresi 10 gündür.", "node_ids": ["node-source"]}]


def provenance():
    return {"case_id": "case-123", "context_version": 2, "limitations": ["Hukuk incelemesi bekleniyor."],
            "company_identity": "BU KİMLİK BELGEYE TAŞINMAMALI", "source_versions": []}


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def package(parts):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return buffer.getvalue()


def owner_receipt(token):
    return {"protocol": 1, "token": token, "pid": 12345, "creation_filetime": 134000000000000000,
            "hwnd": 98765, "owned": True, "exe": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE", "version": "16.0"}


class DraftDocumentTests(unittest.TestCase):
    def setUp(self):
        self.document = draft.build_docx("Satınalma sözleşmesi iç çalışma taslağı", sections(), provenance())

    def error(self, call, code=None):
        with self.assertRaises(CoreError) as caught:
            call()
        if code is not None:
            self.assertEqual(code, caught.exception.code)

    def test_deterministic_plain_text_round_trip_and_visible_labels(self):
        self.assertEqual(self.document, draft.build_docx("Satınalma sözleşmesi iç çalışma taslağı", sections(), provenance()))
        parts = unpack(self.document)
        root = ET.fromstring(parts["word/document.xml"])
        text = "\n".join(n.text or "" for n in root.iter(f"{{{draft.W}}}t"))
        for section in sections():
            self.assertIn(section["text"], text)
            self.assertIn(draft.LABELS[section["kind"]], text)
        self.assertNotIn("Kapsam sınırı:", text)
        self.assertNotIn("Bağlam sürümü", text)
        self.assertNotIn("case-123", text)
        self.assertNotIn("BU KİMLİK", text)
        self.assertIn(b"&amp;", parts["word/document.xml"])
        self.assertIn(b"&lt;", parts["word/document.xml"])
        self.assertEqual({"passed", "checks"}, set(draft.structural_qa(self.document)))

    def test_static_header_footer_styles_and_geometry(self):
        parts = unpack(self.document)
        self.assertIn(draft.HEADER, parts["word/header1.xml"].decode())
        self.assertIn(draft.FOOTER, parts["word/footer1.xml"].decode())
        styles = ET.fromstring(parts["word/styles.xml"])
        for identity in ("Normal", "Title", "Heading1"):
            style = next(s for s in styles if s.get(f"{{{draft.W}}}styleId") == identity)
            self.assertEqual("000000", style.find(f"{{{draft.W}}}rPr/{{{draft.W}}}color").get(f"{{{draft.W}}}val"))
            self.assertEqual("Aptos", style.find(f"{{{draft.W}}}rPr/{{{draft.W}}}rFonts").get(f"{{{draft.W}}}ascii"))
        self.assertNotIn(b"titlePg", parts["word/document.xml"])
        self.assertNotIn(b"evenAndOddHeaders", parts["word/settings.xml"])

    def test_external_relationship_macro_and_duplicate_entries_fail_closed(self):
        for name, data in (("word/vbaProject.bin", b"macro"), ("word/embeddings/object.bin", b"object")):
            parts = unpack(self.document); parts[name] = data
            self.error(lambda: draft.structural_qa(package(parts)))
        parts = unpack(self.document)
        parts["word/_rels/document.xml.rels"] = parts["word/_rels/document.xml.rels"].replace(b"Target=", b'TargetMode="External" Target=', 1)
        self.error(lambda: draft.structural_qa(package(parts)))
        buffer = io.BytesIO(self.document)
        with zipfile.ZipFile(buffer, "a") as archive:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                archive.writestr("word/document.xml", parts["word/document.xml"])
        self.error(lambda: draft.structural_qa(buffer.getvalue()))

    def test_header_footer_labels_styles_and_field_tamper_rejected(self):
        mutations = [
            ("word/header1.xml", draft.HEADER.encode(), b"FINAL"),
            ("word/footer1.xml", draft.FOOTER.encode(), b"Approved"),
            ("word/styles.xml", b"000000", b"0000FF"),
            ("word/document.xml", draft.LABELS["USER_STATEMENT"].encode(), b"unlabelled"),
            ("word/document.xml", b"<w:r>", b'<w:r><w:instrText>INCLUDETEXT https://example.test/</w:instrText>'),
            ("word/document.xml", b"<w:r>", b'<w:r><w:rPr><w:vanish /></w:rPr>'),
            ("word/document.xml", b'<w:sectPr>', b'<w:sectPr><w:titlePg/>'),
        ]
        for part, old, new in mutations:
            with self.subTest(part=part, new=new):
                parts = unpack(self.document)
                self.assertIn(old, parts[part])
                parts[part] = parts[part].replace(old, new, 1)
                self.error(lambda: draft.structural_qa(package(parts)))

    def test_xml_entity_or_extra_non_template_structure_rejected(self):
        parts = unpack(self.document)
        parts["word/document.xml"] = parts["word/document.xml"].replace(b"<w:document", b'<!DOCTYPE x [<!ENTITY x "boom">]><w:document', 1)
        self.error(lambda: draft.structural_qa(package(parts)))
        self.error(lambda: draft.structural_qa(b"not a docx"))
        self.error(lambda: draft.structural_qa(bytearray(self.document)))

    def test_input_limits_and_closed_sections(self):
        for change in ({"kind": "SOURCE_QUOTE"}, {"kind": []}, {"html": "<b>hello</b>"}, {"text": "bad\x00xml"},
                       {"text": "x" * draft.MAX_TEXT}, {"heading": "line\nbreak"}, {"node_ids": [123]}):
            with self.subTest(change=list(change)):
                values = sections(); values[0].update(change)
                self.error(lambda: draft.build_docx("Test", values, provenance()))
        self.error(lambda: draft.build_docx("", sections(), provenance()))
        self.error(lambda: draft.build_docx("Test", [], provenance()))
        bad = provenance(); bad["context_version"] = True
        self.error(lambda: draft.build_docx("Test", sections(), bad))

    def test_visible_scope_shows_only_source_free_or_complete_missing_reference_list(self):
        context = provenance()
        context["source_free"] = True
        context["limitations"] = ["Model görsel incelemesi PDF PNG; teknik denetim kaydı."]
        data = draft.build_docx("Test", sections()[:1], context)
        text = unpack(data)["word/document.xml"].decode("utf-8")
        self.assertIn(draft.SOURCE_FREE_NOTICE, text)
        self.assertNotIn("teknik denetim", text)
        self.assertNotIn("Bağlam sürümü", text)
        self.error(lambda: draft.build_docx("Test", sections(), context))
        context["source_free"] = False
        context["partial_review"] = {"scope": "AVAILABLE_REGISTERED_EVIDENCE_ONLY", "registered_closure_complete": False,
                                     "missing_dependencies": [{"reference": "Ek 2 Teknik şartname"}, {"reference": "Ek 5 Ödeme tablosu"}]}
        data = draft.build_docx("Test", sections(), context)
        parts = unpack(data)
        text = parts["word/document.xml"].decode("utf-8")
        self.assertIn(draft.PARTIAL_NOTICE, text)
        self.assertIn("Eksik kaynak: Ek 2 Teknik şartname", text)
        self.assertIn("Eksik kaynak: Ek 5 Ödeme tablosu", text)
        self.assertNotIn("teknik denetim", text)
        parts["word/document.xml"] = parts["word/document.xml"].replace(draft.PARTIAL_NOTICE.encode(), b"Unlabelled scope")
        self.error(lambda: draft.structural_qa(package(parts)))
        context["partial_review"]["missing_dependencies"] *= 129
        self.error(lambda: draft.build_docx("Test", sections(), context))

    def test_owner_receipt_rejects_missing_fields_other_exe_false_identity_and_bad_token(self):
        token = "a" * 32
        valid = owner_receipt(token)
        draft._validate_owner(valid, token)
        for changed in ({"owned": False}, {"pid": True}, {"creation_filetime": 0}, {"exe": "WINWORD.EXE"},
                        {"exe": r"C:\Windows\notepad.exe"}, {"version": "unknown"}, {"token": "b" * 32}, {"unexpected": 1}):
            candidate = dict(valid, **changed)
            self.error(lambda: draft._validate_owner(candidate, token))
        missing = dict(valid); missing.pop("hwnd")
        self.error(lambda: draft._validate_owner(missing, token))

    def test_word_receipt_failure_limits_and_timeout_do_not_accept_output(self):
        for mode in ("bad_json", "bad_page_count", "extra_receipt", "failed", "memory", "timeout", "exe_mismatch"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                worker = Mock()
                worker.poll.return_value = None if mode == "timeout" else (1 if mode == "failed" else 0)
                process_owner = Mock(); process_owner.memory.return_value = draft.MAX_WORD_MEMORY + 1 if mode == "memory" else 1
                process_owner.exe_path = folder / "WINWORD.EXE"
                process_owner.exe_path.write_bytes(b"unit-test executable identity only")
                executable_hash = hashlib.sha256(process_owner.exe_path.read_bytes()).hexdigest()
                def launch(command, **kwargs):
                    token = command[-1]
                    (folder / "word-owner.json").write_text(json.dumps(owner_receipt(token)), encoding="utf-8")
                    result = {"protocol": 1, "token": token, "status": "EXPORTED", "pid": 12345,
                              "creation_filetime": 134000000000000000, "version": "16.0", "page_count": 26 if mode == "bad_page_count" else 1,
                              "pdf_sha256": "1" * 64, "exe_sha256": "2" * 64 if mode == "exe_mismatch" else executable_hash,
                              "options_restored": True}
                    if mode == "extra_receipt": result["accepted"] = True
                    (folder / "word-render.json").write_text("oops" if mode == "bad_json" else json.dumps(result), encoding="utf-8")
                    return worker
                with patch.object(draft.subprocess, "Popen", side_effect=launch), patch.object(draft, "_OwnedWord", return_value=process_owner), \
                     patch.object(draft.time, "monotonic", side_effect=[0, 61] if mode == "timeout" else None):
                    self.error(lambda: draft._run_word(folder / "input.docx", folder))
                process_owner.close.assert_called_once()
                if mode == "timeout": worker.kill.assert_called_once()

    def test_renderer_failure_does_not_return_passing_qa(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            docx = folder / "input.docx"; docx.write_bytes(self.document)
            with patch.object(draft, "_run_word", side_effect=CoreError("TASLAK_RENDER_YOK", "fake Office unavailable")):
                self.error(lambda: draft.render_docx(docx, folder / "qa"), "TASLAK_RENDER_YOK")
            damaged = unpack(self.document); damaged["word/vbaProject.bin"] = b"macro"
            docx.write_bytes(package(damaged))
            with patch.object(draft, "_run_word") as renderer:
                self.error(lambda: draft.render_docx(docx, folder / "qa"))
                renderer.assert_not_called()

    def test_pdf_all_pages_hashes_limits_and_malformed_bytes(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842); writer.add_blank_page(width=595, height=842)
            pdf = folder / "document.pdf"
            with pdf.open("wb") as output: writer.write(output)
            writer.close()
            pages = draft._render_pdf(pdf, folder, 2)
            self.assertEqual([1, 2], [p["page"] for p in pages])
            for page in pages:
                self.assertTrue(Path(page["path"]).is_absolute())
                self.assertEqual(hashlib.sha256(Path(page["path"]).read_bytes()).hexdigest(), page["sha256"])
            self.error(lambda: draft._render_pdf(pdf, folder, 3), "TASLAK_SINIRI")
            with patch.object(draft, "MAX_PDF", 1):
                self.error(lambda: draft._render_pdf(pdf, folder, 2), "TASLAK_SINIRI")
            with patch.object(draft, "MAX_PIXELS", 1):
                self.error(lambda: draft._render_pdf(pdf, folder, 2), "TASLAK_SINIRI")
            pdf.write_bytes(b"%PDF-malformed")
            self.error(lambda: draft._render_pdf(pdf, folder, 1))

    def test_render_contract_returns_only_real_file_hashes(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); docx = folder / "input.docx"; docx.write_bytes(self.document)
            def fake_office(path, qa):
                pdf = qa / "document.pdf"; writer = PdfWriter(); writer.add_blank_page(width=595, height=842)
                with pdf.open("wb") as output: writer.write(output)
                writer.close()
                return {"pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "version": "16.0", "page_count": 1,
                        "exe_sha256": "3" * 64}
            with patch.object(draft, "_run_word", side_effect=fake_office):
                report = draft.render_docx(docx, folder / "qa")
            self.assertEqual({"renderer", "pdf", "pages"}, set(report))
            self.assertEqual({"name", "version", "exe_sha256", "adapter_sha256"}, set(report["renderer"]))
            self.assertEqual("3" * 64, report["renderer"]["exe_sha256"])
            self.assertEqual(draft.adapter_fingerprint(), report["renderer"]["adapter_sha256"])
            self.assertEqual({"path", "sha256"}, set(report["pdf"]))
            self.assertEqual({"page", "path", "sha256"}, set(report["pages"][0]))

    def test_adapter_fingerprint_changes_with_either_source_or_library_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, script = folder / "adapter.py", folder / "adapter.ps1"
            source.write_bytes(b"python adapter v1"); script.write_bytes(b"powershell adapter v1")
            versions = {"pypdfium2": "5.0", "Pillow": "12.0"}
            with patch.object(draft, "_adapter_paths", return_value=(source, script)), \
                 patch.object(draft.metadata, "version", side_effect=lambda name: versions[name]):
                initial = draft.adapter_fingerprint()
                self.assertEqual(initial, draft.adapter_fingerprint())
                source.write_bytes(b"python adapter v2")
                python_changed = draft.adapter_fingerprint()
                script.write_bytes(b"powershell adapter v2")
                script_changed = draft.adapter_fingerprint()
                versions["pypdfium2"] = "5.1"
                pdfium_changed = draft.adapter_fingerprint()
                versions["Pillow"] = "12.1"
                pillow_changed = draft.adapter_fingerprint()
                self.assertEqual(5, len({initial, python_changed, script_changed, pdfium_changed, pillow_changed}))

    def test_renderer_rejects_profile_change_during_export(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); docx = folder / "input.docx"; docx.write_bytes(self.document)
            def fake_office(path, qa):
                pdf = qa / "document.pdf"; writer = PdfWriter(); writer.add_blank_page(width=595, height=842)
                with pdf.open("wb") as output: writer.write(output)
                writer.close()
                return {"pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "version": "16.0", "page_count": 1,
                        "exe_sha256": "3" * 64}
            with patch.object(draft, "_run_word", side_effect=fake_office), \
                 patch.object(draft, "adapter_fingerprint", side_effect=["a" * 64, "b" * 64]):
                self.error(lambda: draft.render_docx(docx, folder / "qa"), "TASLAK_QA")

    def test_word_receipt_executable_hash_matches_parent_held_object(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            worker = Mock(); worker.poll.return_value = 0
            process_owner = Mock(); process_owner.memory.return_value = 1
            process_owner.exe_path = folder / "WINWORD.EXE"
            process_owner.exe_path.write_bytes(b"unit-test executable identity only")
            executable_hash = hashlib.sha256(process_owner.exe_path.read_bytes()).hexdigest()
            def launch(command, **kwargs):
                token = command[-1]
                (folder / "word-owner.json").write_text(json.dumps(owner_receipt(token)), encoding="utf-8")
                result = {"protocol": 1, "token": token, "status": "EXPORTED", "pid": 12345,
                          "creation_filetime": 134000000000000000, "version": "16.0", "page_count": 1,
                          "pdf_sha256": "1" * 64, "exe_sha256": executable_hash, "options_restored": True}
                (folder / "word-render.json").write_text(json.dumps(result), encoding="utf-8")
                return worker
            with patch.object(draft.subprocess, "Popen", side_effect=launch), patch.object(draft, "_OwnedWord", return_value=process_owner):
                receipt = draft._run_word(folder / "input.docx", folder)
            self.assertEqual(executable_hash, receipt["exe_sha256"])
            process_owner.close.assert_called_once()

    def test_native_failure_diagnostic_is_bounded_typed_and_content_free(self):
        token = "a" * 32
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            valid = {"protocol": 1, "token": token, "status": "FAILED", "stage": "OPEN",
                     "exception_type": "System.Runtime.InteropServices.COMException", "hresult": -2147024809}
            path = folder / "word-error.json"
            path.write_text(json.dumps(valid), encoding="utf-8")
            diagnosis = draft._word_failure(folder, token)
            self.assertIn("OPEN", diagnosis)
            self.assertIn("-2147024809", diagnosis)
            for change in ({"message": "document secret"}, {"stage": "arbitrary private data"},
                           {"exception_type": "secret text\n"}, {"hresult": True}, {"token": "b" * 32}):
                path.write_text(json.dumps(dict(valid, **change)), encoding="utf-8")
                self.error(lambda: draft._word_failure(folder, token))
            path.write_text("x" * 2049, encoding="utf-8")
            self.error(lambda: draft._word_failure(folder, token))


if __name__ == "__main__":
    unittest.main()
