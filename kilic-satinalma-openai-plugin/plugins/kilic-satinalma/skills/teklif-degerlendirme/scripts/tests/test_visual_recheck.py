from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import json_text, sha256_file
from db import connect, init_db
from record_results import record_task_result
from run_compatibility import execution_contract, pin_dispatch
from visual_recheck import adopt_recheck, create_recheck
from qa import _visual_tasks


class VisualRecheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name)
        init_db(self.run)
        self.pdf = self.run / "review.pdf"
        self.pdf.write_bytes(b"fixed pdf bytes")
        self.art_hash = sha256_file(self.pdf)
        self.images = []
        for number in (1, 2):
            path = self.run / f"page-{number}.png"
            path.write_bytes(f"page {number}".encode())
            self.images.append({"page": number, "render_key": f"page:{number}", "image_path": str(path), "sha256": sha256_file(path)})
        self.payload = {"artifact_id": "pdf-1", "artifact_path": str(self.pdf.resolve()), "pages": self.images}
        con = connect(self.run)
        try:
            con.execute("INSERT INTO artifacts(artifact_id,artifact_type,relative_path,sha256,status,created_at) VALUES (?,?,?,?,?,?)", ["pdf-1", "pdf", "review.pdf", self.art_hash, "ready", "now"])
            for page in self.images:
                con.execute("INSERT INTO render_hashes VALUES (?,?,?,?,?)", ["pdf-1", page["render_key"], page["sha256"], "fail", "old failure"])
                con.execute("INSERT INTO qa_findings(finding_id,artifact_id,finding_type,locator_json,severity,status,message,finding_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                            [f"finding-{page['page']}", "pdf-1", "visual_layout", json_text({"render_key": page["render_key"]}), "critical", "open", "old failure", f"hash-{page['page']}", "now"])
            con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        ["original", "QA", "visual_exception", "artifact_visual_review", json_text(self.payload), 80, True, "completed", 1, "now"])
            con.execute("INSERT INTO model_receipts(receipt_id,task_id,model_name,reasoning_effort,input_tokens,cached_input_tokens,output_tokens,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                        ["old-receipt", "original", "real-model", "medium", 1, 0, 1, "now"])
            con.execute("INSERT INTO run_meta(key,value) VALUES (?,?)", ["execution_contract", json_text(execution_contract(Path(__file__).resolve().parents[2]))])
            con.commit()
        finally:
            con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, page=1, supplementary_images=None):
        obj = create_recheck(self.run, "original", f"finding-{page}", f"page:{page}", "Original review conflicts with the visible page", supplementary_images)
        tid = obj["task_id"]
        context = self.run / "tasks" / tid / "context.json"
        context.parent.mkdir(parents=True, exist_ok=True)
        if not context.exists():
            context.write_text(json.dumps({"task": {"task_id": tid}}), encoding="utf-8")
            pin_dispatch(self.run, {"task_id": tid}, context, Path(__file__).resolve().parents[2])
        return obj

    def record(self, task_id, key="page:1", status="PASS"):
        return record_task_result(self.run, task_id, {"pages": [{"render_key": key, "status": status, "observations": "Readable on visual inspection"}]},
                                  model_name="actual-model", reasoning_effort="medium", response_id="r1", input_tokens=8, output_tokens=4)

    def row(self, sql, params=()):
        con = connect(self.run)
        try:
            return con.execute(sql, list(params)).fetchone()
        finally:
            con.close()

    def test_pass_requires_explicit_adoption_and_preserves_history(self):
        task = self.make()
        self.assertEqual(self.make()["status"], "already_created")
        self.record(task["task_id"])
        self.assertEqual(self.record(task["task_id"])["status"], "already_completed")
        self.assertEqual(self.row("SELECT qa_status FROM render_hashes WHERE render_key='page:1'")[0], "fail")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "open")
        self.assertEqual(self.row("SELECT result_status FROM visual_rechecks WHERE recheck_id=?", [task["recheck_id"]])[0], "pass")
        adopted = adopt_recheck(self.run, task["recheck_id"], "Verified full page and crop show no clipping")
        self.assertEqual(adopted["status"], "adopted")
        self.assertEqual(adopt_recheck(self.run, task["recheck_id"], "Verified full page and crop show no clipping")["status"], "already_adopted")
        self.assertEqual(create_recheck(self.run, "original", "finding-1", "page:1", "Original review conflicts with the visible page")["status"], "already_created")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "superseded")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-2'")[0], "open")
        self.assertEqual(self.row("SELECT status FROM task_queue WHERE task_id='original'")[0], "completed")
        self.assertEqual(self.row("SELECT count(*) FROM model_receipts WHERE task_id='original'")[0], 1)
        self.assertEqual(self.row("SELECT count(*) FROM qa_finding_supersessions WHERE finding_id='finding-1'")[0], 1)

    def test_wrong_or_partial_page_and_failed_recheck_never_close_finding(self):
        task = self.make()
        for result in ({"pages": []}, {"pages": [{"render_key": "page:2", "status": "PASS"}]},
                       {"pages": [{"render_key": "page:1", "status": "PASS"}, {"render_key": "page:1", "status": "PASS"}]}):
            with self.assertRaises(ValueError):
                record_task_result(self.run, task["task_id"], result, model_name="actual", reasoning_effort="medium", input_tokens=1, output_tokens=1)
        self.assertEqual(self.row("SELECT count(*) FROM model_receipts WHERE task_id=?", [task["task_id"]])[0], 0)
        self.record(task["task_id"], status="FAIL")
        with self.assertRaises(ValueError):
            adopt_recheck(self.run, task["recheck_id"], "Visual defect remains on selected page")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "open")

    def test_stale_pdf_and_image_reject_before_state_write(self):
        task = self.make()
        image = Path(self.images[0]["image_path"])
        image.write_bytes(b"modified")
        with self.assertRaises(ValueError):
            self.record(task["task_id"])
        self.assertEqual(self.row("SELECT attempts FROM task_queue WHERE task_id=?", [task["task_id"]])[0], 0)
        self.assertIsNone(self.row("SELECT result_status FROM visual_rechecks WHERE recheck_id=?", [task["recheck_id"]])[0])
        image.write_bytes(b"page 1")
        self.record(task["task_id"])
        self.pdf.write_bytes(b"modified pdf")
        with self.assertRaises(ValueError):
            adopt_recheck(self.run, task["recheck_id"], "Visible page supports a different conclusion")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "open")

    def test_automatic_qa_does_not_requeue_existing_fail(self):
        con = connect(self.run)
        try:
            before = con.execute("SELECT count(*) FROM task_queue").fetchone()[0]
            _visual_tasks(con, self.run, {"artifact_id": "pdf-1", "relative_path": "review.pdf"},
                          [{"page": p["page"], "path": p["image_path"], "sha256": p["sha256"]} for p in self.images], True)
            con.commit()
            self.assertEqual(con.execute("SELECT count(*) FROM task_queue").fetchone()[0], before)
            self.assertEqual(con.execute("SELECT qa_status FROM render_hashes WHERE render_key='page:1'").fetchone()[0], "fail")
        finally:
            con.close()

    def test_initial_review_requires_all_pages_and_dispatch_identity(self):
        con = connect(self.run)
        try:
            con.execute("INSERT INTO task_queue(task_id,phase,role,task_kind,payload_json,priority,critical,status,attempts,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        ["fresh", "QA", "visual_exception", "artifact_visual_review", json_text(self.payload), 80, True, "pending", 0, "now"])
            con.commit()
        finally:
            con.close()
        context = self.run / "tasks" / "fresh" / "context.json"
        context.parent.mkdir(parents=True)
        context.write_text(json.dumps({"task": {"task_id": "fresh"}}), encoding="utf-8")
        pin_dispatch(self.run, {"task_id": "fresh"}, context, Path(__file__).resolve().parents[2])
        with self.assertRaises(ValueError):
            self.record("fresh")
        self.assertEqual(self.row("SELECT count(*) FROM model_receipts WHERE task_id='fresh'")[0], 0)
        context.write_text(json.dumps({"task": {"task_id": "wrong"}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            record_task_result(self.run, "fresh", {"pages": [{"render_key": "page:1", "status": "PASS"}, {"render_key": "page:2", "status": "PASS"}]},
                               model_name="actual", reasoning_effort="medium", input_tokens=1, output_tokens=1)
        self.assertEqual(self.row("SELECT status FROM task_queue WHERE task_id='fresh'")[0], "pending")

    def test_changed_original_finding_hash_blocks_adoption(self):
        task = self.make()
        self.record(task["task_id"])
        con = connect(self.run)
        try:
            con.execute("UPDATE qa_findings SET finding_hash='changed' WHERE finding_id='finding-1'")
            con.commit()
        finally:
            con.close()
        with self.assertRaises(ValueError):
            adopt_recheck(self.run, task["recheck_id"], "Reinspect the original page and resolve the finding")
        self.assertEqual(self.row("SELECT count(*) FROM qa_finding_supersessions")[0], 0)

    def test_supplementary_crop_is_hash_pinned_and_not_an_extra_page(self):
        crop = self.run / "top-half.png"
        crop.write_bytes(b"top half")
        task = create_recheck(self.run, "original", "finding-1", "page:1", "Compare the clipped heading with the crop", [crop])
        con = connect(self.run)
        try:
            payload = json.loads(con.execute("SELECT payload_json FROM task_queue WHERE task_id=?", [task["task_id"]]).fetchone()[0])
        finally:
            con.close()
        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(payload["supplementary_images"][0]["sha256"], sha256_file(crop))
        context = self.run / "tasks" / task["task_id"] / "context.json"
        context.parent.mkdir(parents=True)
        context.write_text(json.dumps({"task": {"task_id": task["task_id"]}}), encoding="utf-8")
        pin_dispatch(self.run, {"task_id": task["task_id"]}, context, Path(__file__).resolve().parents[2])
        crop.write_bytes(b"changed crop")
        with self.assertRaises(ValueError):
            self.record(task["task_id"])
        self.assertIsNone(self.row("SELECT result_status FROM visual_rechecks WHERE recheck_id=?", [task["recheck_id"]])[0])

    def test_image_changed_after_record_blocks_adoption(self):
        task = self.make()
        self.record(task["task_id"])
        Path(self.images[0]["image_path"]).write_bytes(b"changed after recording")
        with self.assertRaises(ValueError):
            adopt_recheck(self.run, task["recheck_id"], "Rechecked the full page and source image")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "open")
        self.assertEqual(self.row("SELECT count(*) FROM qa_finding_supersessions")[0], 0)

    def test_crop_changed_after_record_blocks_adoption(self):
        crop = self.run / "crop.png"
        crop.write_bytes(b"original crop")
        task = self.make(supplementary_images=[crop])
        self.record(task["task_id"])
        crop.write_bytes(b"changed after recording")
        with self.assertRaises(ValueError):
            adopt_recheck(self.run, task["recheck_id"], "Rechecked the full page and cropped heading")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "open")
        self.assertEqual(self.row("SELECT count(*) FROM qa_finding_supersessions")[0], 0)

    def test_other_open_finding_on_same_page_keeps_page_failed(self):
        task = self.make()
        self.record(task["task_id"])
        con = connect(self.run)
        try:
            con.execute("INSERT INTO qa_findings(finding_id,artifact_id,finding_type,locator_json,severity,status,message,finding_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        ["other-same-page", "pdf-1", "visual_layout", json_text({"render_key": "page:1"}), "critical", "open", "Another visible defect", "other-hash", "now"])
            con.commit()
        finally:
            con.close()
        self.assertEqual(adopt_recheck(self.run, task["recheck_id"], "Only the original alleged clipping is disproved")["status"], "adopted")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='finding-1'")[0], "superseded")
        self.assertEqual(self.row("SELECT status FROM qa_findings WHERE finding_id='other-same-page'")[0], "open")
        self.assertEqual(self.row("SELECT qa_status FROM render_hashes WHERE render_key='page:1'")[0], "fail")


if __name__ == "__main__":
    unittest.main()
