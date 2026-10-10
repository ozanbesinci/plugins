"""A revision question leaves unrelated offer reading available, not its decision."""
import json
import tempfile
import unittest
from pathlib import Path

from db import connect, init_db
from workflow import _independent_early_extraction


class IndependentEarlyExtractionTests(unittest.TestCase):
    def test_only_controlling_source_tasks_are_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            init_db(run)
            con = connect(run)
            try:
                for did, status in (("revision-7", "needs_input"),
                                    ("revision-8", "needs_input"),
                                    ("separate-item", "controlling")):
                    con.execute("""INSERT INTO source_authority(document_id,authority_scope,authority_class,
                                   authority_status,precedence_rank,rationale,assessed_by,assessed_at)
                                   VALUES (?, 'supplier_commitment', 'supplier_offer', ?, 70, 'fixture', 'test', '2026-10-08')""",
                                [did, status])
                con.commit()
            finally:
                con.close()
            pending = [{"task_id": did, "task_kind": "offer_semantic_fields", "document_id": None,
                        "payload_json": json.dumps({"document_ids": [did]}), "phase": "EXTRACT"}
                       for did in ("revision-7", "revision-8", "separate-item")]
            pending.append({"task_id": "mixed-offer", "task_kind": "offer_semantic_fields", "document_id": None,
                            "payload_json": json.dumps({"document_ids": ["revision-7", "separate-item"]}),
                            "phase": "EXTRACT"})
            safe = _independent_early_extraction(run, pending)
            self.assertEqual([task["task_id"] for task in safe], ["separate-item"])


if __name__ == "__main__":
    unittest.main()
