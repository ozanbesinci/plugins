from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault('TEKLIF_TEST_SQLITE', '1')
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from compare_reviews import compare
from db import connect, init_db, set_meta
from decision_gate import run_gate
from task_queue import _add_task
from procurement_engine import run_engine
from independent_recompute import run as independent_recompute
from common import json_text, utc_now


class SafetyAndDiffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='teklif-v5-test-'))
        init_db(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _offer(self, offer_id='O1', supplier_id='S1'):
        con = connect(self.tmp)
        try:
            con.execute("INSERT INTO suppliers(supplier_id,display_name,normalized_name,identification_status) VALUES (?,?,?,?)", [supplier_id, supplier_id, supplier_id, 'confirmed'])
            con.execute("INSERT INTO offers(offer_id,supplier_id,display_name,quote_date,validity_end,status,source_document_ids_json) VALUES (?,?,?,?,?,?,?)", [offer_id, supplier_id, supplier_id, '2026-09-20', '2026-12-31', 'active', '[]'])
            for field, text, num in [
                ('total', None, 1000), ('currency', 'TRY', None), ('payment', 'pesin', None),
                ('delivery', '10 gun', None), ('quote_date', None, None), ('validity', '31.12.2026', None),
            ]:
                con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_text,value_number,value_date,evidence_status,critical,extraction_path,normalized_json,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            [f'{offer_id}/field/{field}', offer_id, supplier_id, field, text, num, '2026-09-20' if field=='quote_date' else None, 'verified', True, 'deterministic', '{}', utc_now()])
            con.commit()
        finally:
            con.close()

    def test_diff_only_compares_review_scope(self):
        self._offer()
        con = connect(self.tmp)
        try:
            _add_task(con, 'REVIEW', 'difficult_semantics', 'independent_fact_review', {'offer_id':'O1','fact_ids':['O1/field/total']}, offer_id='O1')
            task = con.execute("SELECT task_id FROM task_queue LIMIT 1").fetchone()[0]
            con.execute("INSERT INTO review_facts(review_id,fact_id,value_number,evidence_status,review_path) VALUES (?,?,?,?,?)", [task, 'O1/field/total', 1000, 'verified', 'independent_llm'])
            con.commit()
        finally:
            con.close()
        out = compare(self.tmp, task)
        self.assertEqual(out['matched'], 1)
        self.assertEqual(out['differences'], 0)

    def test_payment_difference_requires_currency_rate(self):
        self._offer('O1','S1')
        self._offer('O2','S2')
        con = connect(self.tmp)
        try:
            con.execute("UPDATE facts SET value_text=?,normalized_json=? WHERE fact_id='O1/field/payment'", ['%30 pesin %70 teslim', json_text({'payment_schedule':[{'ratio':0.3,'days':0},{'ratio':0.7,'days':30}]})])
            con.execute("UPDATE facts SET value_text=?,normalized_json=? WHERE fact_id='O2/field/payment'", ['%20 pesin %80 teslim', json_text({'payment_schedule':[{'ratio':0.2,'days':0},{'ratio':0.8,'days':30}]})])
            con.commit()
        finally:
            con.close()
        run_engine(self.tmp)
        independent_recompute(self.tmp)
        out = run_gate(self.tmp, date(2026,10,3))
        self.assertEqual(out['status'], 'PRELIMINARY_ONLY')
        self.assertTrue(any(x['code']=='PAYMENT_COMPARABILITY_RATE_MISSING' for x in out['reasons']))
        set_meta(self.tmp, 'financial_parameters', {'discount_rates': {'TRY': 0.12}})
        con = connect(self.tmp)
        try:
            con.execute("DELETE FROM open_issues WHERE issue_type='payment_comparability'")
            con.commit()
        finally:
            con.close()
        run_engine(self.tmp)
        independent_recompute(self.tmp)
        out2 = run_gate(self.tmp, date(2026,10,3))
        self.assertEqual(out2['status'], 'SUFFICIENT')


if __name__ == '__main__':
    unittest.main()
