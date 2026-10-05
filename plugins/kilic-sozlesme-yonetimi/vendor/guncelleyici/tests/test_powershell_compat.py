"""Static guardrails for Windows PowerShell 5.1 source compatibility.

Native Parser::ParseFile remains the acceptance authority on Windows. These tests
prevent two recurring source-level failures before packaging: typographic quotes,
which PowerShell treats as string delimiters, and missing UTF-8 BOM on PS1 files.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PowerShellSourceCompatibilityTests(unittest.TestCase):
    def test_no_typographic_quotes_in_powershell_source(self):
        forbidden = {"\u2018", "\u2019", "\u201c", "\u201d"}
        failures = []
        for path in sorted(ROOT.rglob("*.ps1")):
            text = path.read_text(encoding="utf-8-sig")
            for line_number, line in enumerate(text.splitlines(), 1):
                chars = sorted(forbidden.intersection(line))
                if chars:
                    failures.append(f"{path.relative_to(ROOT)}:{line_number}: {chars}")
        self.assertEqual(failures, [], "Typographic quotes can terminate PowerShell strings: " + "; ".join(failures))

    def test_ps1_files_have_utf8_bom_for_windows_powershell_51(self):
        missing = []
        for path in sorted(ROOT.rglob("*.ps1")):
            if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
                missing.append(str(path.relative_to(ROOT)))
        self.assertEqual(missing, [], "Windows PowerShell 5.1 requires BOM-safe Unicode script files: " + ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
