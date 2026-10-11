"""Regression checks against the isolated numeric/report patch."""
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))

from claim_registry import _numeric_tokens
from report_export import export_report
from openpyxl import load_workbook


class NumericReportRegression(unittest.TestCase):
    def test_distinct_literals_and_real_grouping(self):
        self.assertEqual(_numeric_tokens("%100 60 gün; 24 ay"), {"1E+2", "6E+1", "24"})
        self.assertEqual(_numeric_tokens("100 000 ve 1.000.000"), {"1E+5", "1E+6"})
        values = _numeric_tokens("1.234,56 EUR; 1,234.56 USD; 12,5 TL; 12.5 USD")
        self.assertEqual({Decimal(x) for x in values}, {Decimal("1234.56"), Decimal("12.5")})
        self.assertNotIn("10060", _numeric_tokens("%100 60 gün"))

    def test_recommendation_cell_and_provenance_binding(self):
        snapshot = {
            "status": "READY",
            "meta": {"profile": "standart", "decision_status": "SUFFICIENT",
                     "decision_recommendation": json.dumps({"type": "select_supplier", "supplier_id": "sup-a",
                                                            "text": "Satın alma onayına sunulsun."})},
            "suppliers": [{"supplier_id": "sup-a", "display_name": "Alpha Ltd."}],
            "offers": [{"offer_id": "off-a", "supplier_id": "sup-a", "status": "active"}],
            "claims": [{"claim_id": "claim-rec", "claim_type": "recommendation", "claim_text": "Satın alma onayına sunulsun."}],
        }

        from test_engine_support import ReportFixtureConnection
        class Connection(ReportFixtureConnection):
            def __init__(self): super().__init__("sha")

        bindings = []
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("reviewed_snapshot.load_latest", return_value=(snapshot, {"sha256": "sha", "relative_path": "snapshot.json"})), \
                 mock.patch("report_export.connect", return_value=Connection()), \
                 mock.patch("report_export._artifact", return_value="artifact"), \
                 mock.patch("report_export._insert_bindings", side_effect=lambda con, aid, sha, rows: bindings.extend(rows)), \
                 mock.patch("report_export._recalc_with_excel", return_value={"available": False}):
                output = export_report(Path(tmp))
            workbook = load_workbook(output["xlsx"], data_only=True)
            try:
                self.assertEqual(workbook["Ozet"]["B6"].value, "Alpha Ltd.: Satın alma onayına sunulsun.")
            finally:
                workbook.close()
            self.assertTrue(any(row["component_id"] == "xlsx:Ozet:B6" and
                                row["claim_ids"] == ["claim-rec"] for row in bindings))


if __name__ == "__main__":
    unittest.main()
