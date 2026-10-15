import copy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
from xml.sax.saxutils import escape

import duckdb
from sozlesme_cekirdek import Store, CoreError
from sozlesme_cekirdek.safety import hash_file
from reader_fixtures import docx_parts, package_bytes

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = "Garanti 24 ay. Bedel 100.000,50 TRY. Vade 30 takvim günü. Son gün 2026-10-31. İş tamamlanmadı."
POSITION = "Garanti 36 ay istiyorum. Kabul 2026-10-01 tarihinde yapıldı. İş tamamlandı."


def exact_span(text, literal):
    start = text.index(literal)
    return {"start": start, "end": start + len(literal), "text": literal}


class BusinessTests(unittest.TestCase):
    def setUp(self):
        # Staging excludes .runtime; a shard may start with this class.
        (ROOT / "tests/.runtime").mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="iş-İı-", dir=ROOT / "tests/.runtime")
        self.addCleanup(temp.cleanup)
        self.area = Path(temp.name)
        self.sources = self.area / "sources"
        self.sources.mkdir()
        self.store = Store(self.area / "work", source_roots=[self.sources], output_root=self.area)
        self.case = self.store.create_case("Sentetik iş dosyası")
        self.versions = []
        self.node, self.path = self.document(CONTRACT)
        self.texts = {self.node: CONTRACT}
        statement = self.store.add_statement(self.case, POSITION, expected_revision=self.rev())
        self.statement = self.store.register_context_node(self.case, spec={"node_kind": "USER_STATEMENT", "title": "Pozisyon", "record_id": statement}, expected_revision=self.rev())["node_id"]
        self.texts[self.statement] = POSITION

    def rev(self):
        return self.store.case_revision(self.case)

    def document(self, text):
        path = self.sources / (str(uuid4()) + " sözleşme.docx")
        parts = docx_parts()
        parts["word/document.xml"] = parts["word/document.xml"].replace("<w:body>", "<w:body><w:p><w:r><w:t>" + escape(text) + "</w:t></w:r></w:p>")
        path.write_bytes(package_bytes(parts))
        document = self.store.create_document(self.case, "Sentetik", expected_revision=self.rev())
        version = self.store.ingest(self.case, document, path, expected_revision=self.rev())["version_id"]
        reading = self.store.read_document(self.case, version, format="DOCX")
        unit = next(u for u in reading["result"]["units"] if u["views"]["RAW"] == text)
        target = {"format": "DOCX", "unit_id": unit["unit_id"], "view": "RAW", "start": 0, "end": len(text), "expected_text": text, "field_kind": "OBLIGATION"}
        node = self.store.register_context_node(self.case, spec={"node_kind": "SOURCE_UNIT", "title": "Kaynak", "role": "CLAUSE", "version_id": version, "reading_id": reading["processing_id"], "target": target}, expected_revision=self.rev())["node_id"]
        self.versions.append(version)
        if hasattr(self, "texts"):
            self.texts[node] = text
        return node, path

    def fact_spec(self, literal="24", *, node=None, field="warranty", plane="WRITTEN", method="INTEGER", unit="months", unit_literal="ay", currency=None, scope="main"):
        node = node or self.node
        text = self.texts[node]
        return {"source_node_id": node, "scope_key": scope, "field": field, "plane": plane, "normalization": method,
            "value_span": exact_span(text, literal), "unit": unit, "unit_span": exact_span(text, unit_literal) if unit_literal else None,
            "currency": currency, "currency_span": exact_span(text, currency) if currency else None}

    def fact(self, literal="24", **kwargs):
        return self.store.register_business_fact(self.case, spec=self.fact_spec(literal, **kwargs), expected_revision=self.rev())["fact_id"]

    def overview(self, **changes):
        args = {"as_of": "2026-11-02", "scope_keys": ["main"], "selected_versions": self.versions}
        args.update(changes)
        return self.store.business_overview(self.case, **args)

    def obligation_spec(self, *, date_fact=None, rule=None):
        return {"source_node_id": self.node, "scope_key": "main", "description": "Teslim adayı", "completion_criterion": "Kabul belgesi kontrolü",
            "obligated_party": None, "due_fact_id": date_fact, "due_rule": rule, "missing_due_reason": None if date_fact or rule else "Başlangıç/kural eksik"}

    def obligation(self, **kwargs):
        return self.store.register_obligation(self.case, spec=self.obligation_spec(**kwargs), expected_revision=self.rev())["obligation_id"]

    def rule(self, *, start=True, days=True):
        count = self.fact("30", field="delivery_days", unit="calendar_days" if days else "days", unit_literal="takvim günü" if days else "günü")
        start_fact = self.fact("2026-10-01", node=self.statement, field="accepted_on", plane="REPORTED_EVENT", method="DATE_ISO", unit=None, unit_literal=None) if start else None
        return {"start_fact_id": start_fact, "count_fact_id": count, "anchor_event": "Kabul", "include_start": False, "month_end": None,
            "weekend": [], "holidays": [], "holiday_calendar_complete": None, "calendar_version": None}

    def error(self, code, function):
        with self.assertRaises(CoreError) as caught:
            function()
        self.assertEqual(code, caught.exception.code)

    def test_normalized_months_remain_source_candidate(self):
        before = hash_file(self.path)
        self.fact()
        value = self.overview()["facts"][0]
        self.assertEqual({"type": "decimal", "value": "24"}, value["value"])
        self.assertEqual("UNVERIFIED", value["meaning_status"])
        self.assertEqual("NOT_GRANTED", value["business_approval"])
        self.assertEqual(before, hash_file(self.path))

    def test_mismatched_value_or_out_of_range_span_rejected(self):
        for mutation in ({"text": "36"}, {"end": 10000}):
            spec = self.fact_spec()
            spec["value_span"].update(mutation)
            self.error("KAYNAK_ALINTISI", lambda: self.store.register_business_fact(self.case, spec=spec, expected_revision=self.rev()))

    def test_model_value_authority_and_unknown_plane_rejected(self):
        for key, value in [("value", "36"), ("approved", True), ("authority", "ADMIN"), ("plane", "AUTHORIZED_DECISION")]:
            spec = self.fact_spec()
            spec[key] = value
            self.error("SEMA_HATASI", lambda: self.store.register_business_fact(self.case, spec=spec, expected_revision=self.rev()))

    def test_turkish_decimal_no_float_or_rounding(self):
        self.fact("100.000,50", field="price", method="DECIMAL_TR", unit="money", unit_literal="Bedel", currency="TRY")
        value = self.overview()["facts"][0]
        self.assertEqual("100000.50", value["value"]["value"])
        self.assertEqual("TRY", value["currency"])

    def test_wrong_decimal_locale_is_not_guessed(self):
        self.error("SAYI_KAYNAGI", lambda: self.fact("100.000,50", field="price", method="DECIMAL_CANONICAL", unit="money", unit_literal="Bedel", currency="TRY"))

    def test_percentage_is_source_anchored_fraction(self):
        node, _ = self.document("Avans %12,5 oranındadır.")
        self.fact("12,5", node=node, field="advance", method="PERCENT_TR", unit="ratio", unit_literal="%")
        self.assertEqual("0.125", self.overview()["facts"][0]["value"]["value"])
        self.error("BIRIM_KAYNAGI", lambda: self.fact("12,5", node=node, field="advance", method="DECIMAL_TR", unit="ratio", unit_literal="%"))

    def test_decimal_storage_limit_rejects_without_partial_fact(self):
        node, _ = self.document("Bedel 1000000000000000000.000001 TRY.")
        self.error("ONDALIK_SINIRI", lambda: self.fact("1000000000000000000.000001", node=node, field="price", method="DECIMAL_CANONICAL", unit="money", unit_literal="Bedel", currency="TRY"))
        self.assertEqual([], self.overview()["facts"])

    def test_source_currency_or_unit_cannot_be_invented(self):
        spec = self.fact_spec()
        spec["unit"] = "calendar_days"
        self.error("BIRIM_KAYNAGI", lambda: self.store.register_business_fact(self.case, spec=spec, expected_revision=self.rev()))
        spec = self.fact_spec("100.000,50", field="price", method="DECIMAL_TR", unit="money", unit_literal="Bedel", currency="TRY")
        spec["currency"] = "EUR"
        self.error("PARA_BIRIMI", lambda: self.store.register_business_fact(self.case, spec=spec, expected_revision=self.rev()))

    def test_position_does_not_replace_written_warranty(self):
        self.fact()
        self.fact("36", node=self.statement, plane="USER_POSITION")
        comparison = self.overview()["comparisons"][0]
        self.assertEqual("VALUE_MISMATCH", comparison["status"])
        self.assertEqual({"WRITTEN", "USER_POSITION"}, set(comparison["planes"]))
        self.assertFalse(comparison["contract_amended"])
        self.assertFalse(comparison["authorized_decision"])

    def test_document_and_statement_planes_cannot_be_swapped(self):
        self.error("BILGI_DUZLEMI", lambda: self.fact("36", node=self.statement, plane="WRITTEN"))
        self.error("BILGI_DUZLEMI", lambda: self.fact(plane="USER_POSITION"))

    def test_price_comparison_never_converts_currency(self):
        plan, _ = self.document("Bedel 100.000,50 EUR.")
        self.fact("100.000,50", field="price", method="DECIMAL_TR", unit="money", unit_literal="Bedel", currency="TRY")
        self.fact("100.000,50", node=plan, field="price", plane="PLANNED", method="DECIMAL_TR", unit="money", unit_literal="Bedel", currency="EUR")
        self.assertEqual("CURRENCY_MISMATCH_NO_FX", self.overview()["comparisons"][0]["status"])

    def test_comparisons_respect_subject_scope(self):
        self.fact()
        self.fact("36", node=self.statement, plane="USER_POSITION", scope="other_machine")
        self.assertEqual([], self.overview(scope_keys=["main", "other_machine"])["comparisons"])

    def test_numeric_without_unit_is_not_comparable(self):
        self.fact(unit=None, unit_literal=None)
        self.fact("36", node=self.statement, plane="USER_POSITION", unit=None, unit_literal=None)
        self.assertEqual("UNIT_REQUIRED", self.overview()["comparisons"][0]["status"])

    def test_duplicate_fact_does_not_bump_or_write(self):
        fact = self.fact()
        revision = self.rev()
        result = self.store.register_business_fact(self.case, spec=self.fact_spec(), expected_revision=revision)
        self.assertEqual({"fact_id": fact, "reused": True}, result)
        self.assertEqual(revision, self.rev())

    def test_supersession_preserves_history_and_same_plane(self):
        fact = self.fact()
        node, _ = self.document("Garanti 30 ay.")
        spec = self.fact_spec("30", node=node)
        spec["supersedes_id"] = fact
        new = self.store.register_business_fact(self.case, spec=spec, expected_revision=self.rev())["fact_id"]
        rows = {row["fact_id"]: row for row in self.overview()["facts"]}
        self.assertEqual("SUPERSEDED", rows[fact]["state"])
        self.assertEqual("24", rows[fact]["value"]["value"])
        self.assertEqual("CURRENT_CANDIDATE", rows[new]["state"])
        bad = self.fact_spec("36", node=self.statement, plane="USER_POSITION")
        bad["supersedes_id"] = new
        self.error("BILGI_DUZLEMI", lambda: self.store.register_business_fact(self.case, spec=bad, expected_revision=self.rev()))

    def test_case_version_conflict_prevents_second_fact(self):
        revision = self.rev()
        self.fact()
        self.error("SURUM_CAKISMASI", lambda: self.store.register_business_fact(self.case, spec=self.fact_spec(), expected_revision=revision))

    def test_cross_case_repository_and_database_reject(self):
        other = self.store.create_case("Başka")
        self.error("KAYNAK_KAPSAMI", lambda: self.store.register_business_fact(other, spec=self.fact_spec(), expected_revision=0))
        fact = self.fact()
        with self.assertRaises(duckdb.ConstraintException):
            with self.store._db() as db:
                db.execute("INSERT INTO is_bilgisi_baglari SELECT ?,record_id,source_node_id,scope_key,plane,fact_digest,payload,payload_digest FROM is_bilgisi_baglari WHERE record_id=?", [other, fact])

    def test_failed_binding_transaction_rolls_back_candidate_and_revision(self):
        revision = self.rev()
        with patch.object(self.store, "_business_links", side_effect=RuntimeError("Sentetik kesinti")):
            with self.assertRaises(RuntimeError):
                self.fact()
        self.assertEqual(revision, self.rev())
        self.assertEqual([], self.overview()["facts"])
        self.assertEqual([], self.store.context(self.case)["candidates"])

    def test_tampered_normalized_fact_payload_rejected(self):
        fact = self.fact()
        with self.store._db() as db:
            value = json.loads(db.execute("SELECT payload FROM is_bilgisi_baglari WHERE record_id=?", [fact]).fetchone()[0])
            value["candidate"]["value"]["value"] = "36"
            db.execute("UPDATE is_bilgisi_baglari SET payload=? WHERE record_id=?", [json.dumps(value), fact])
        self.error("IS_KAYDI_BOZUK", self.overview)

    def test_changed_source_is_visible_stale_and_not_compared(self):
        self.fact()
        self.path.write_bytes(b"Changed source")
        report = self.overview()
        self.assertEqual("NEEDS_REVIEW", report["facts"][0]["state"])
        self.assertEqual([], report["comparisons"])
        self.assertFalse(report["all_selected_sources_current"])

    def test_revoked_access_blocks_old_cache(self):
        self.fact()
        self.path.unlink()
        self.error("ERISIM_YOK", self.overview)

    def test_selected_version_scope_rejects_current_outside_source(self):
        self.fact()
        self.error("KAYNAK_KAPSAMI", lambda: self.overview(selected_versions=[]))

    def test_policy_change_marks_fact_for_review(self):
        self.fact()
        self.assertEqual("NEEDS_REVIEW", self.overview(policy_version="2")["facts"][0]["state"])

    def test_explicit_deadline_and_missing_responsible_party(self):
        due = self.fact("2026-10-31", field="due_date", method="DATE_ISO", unit=None, unit_literal=None)
        self.obligation(date_fact=due)
        obligation = self.overview()["obligations"][0]
        self.assertEqual("2026-10-31", obligation["due_date"])
        self.assertEqual("PAST_DUE_CANDIDATE", obligation["date_position"])
        self.assertIsNone(obligation["obligated_party"])
        self.assertFalse(obligation["closed"])

    def test_relative_date_from_reported_event_stays_candidate(self):
        self.obligation(rule=self.rule())
        obligation = self.overview()["obligations"][0]
        self.assertEqual("2026-10-31", obligation["due_date"])
        self.assertEqual("REPORTED_EVENT", obligation["start_plane"])
        self.assertEqual("CALCULATED_CANDIDATE", obligation["due_status"])
        self.assertFalse(obligation["close_allowed"])

    def test_missing_start_never_infers_today(self):
        self.obligation(rule=self.rule(start=False))
        obligation = self.overview()["obligations"][0]
        self.assertIsNone(obligation["due_date"])
        self.assertIn("Başlangıç olayı", obligation["missing_due_reason"])

    def test_missing_include_start_is_explicit_and_no_date(self):
        rule = self.rule()
        rule["include_start"] = None
        self.obligation(rule=rule)
        self.assertIsNone(self.overview()["obligations"][0]["due_date"])

    def test_reported_completion_does_not_close_obligation(self):
        obligation = self.obligation()
        date_fact = self.fact("2026-10-01", node=self.statement, field="event_date", plane="REPORTED_EVENT", method="DATE_ISO", unit=None, unit_literal=None)
        spec = {"obligation_id": obligation, "source_node_id": self.statement, "description": "Kullanıcı tamamlandı dedi", "event_date_fact_id": date_fact, "reports_completion": True}
        self.store.register_business_event(self.case, spec=spec, expected_revision=self.rev())
        report = self.overview()
        self.assertEqual("REPORTED_EVENT", report["events"][0]["event_kind"])
        self.assertFalse(report["events"][0]["actual_completion_verified"])
        self.assertFalse(report["obligations"][0]["closed"])
        self.assertEqual(1, len(report["obligations"][0]["completion_claim_ids"]))

    def test_document_completion_claim_is_not_authenticated(self):
        obligation = self.obligation()
        node, _ = self.document("Teslim tamamlandı denmiştir; geçerliliği doğrulanmadı.")
        spec = {"obligation_id": obligation, "source_node_id": node, "description": "Belge yorum adayı", "event_date_fact_id": None, "reports_completion": True}
        self.store.register_business_event(self.case, spec=spec, expected_revision=self.rev())
        report = self.overview()
        self.assertEqual("DOCUMENT_BACKED_REPORT", report["events"][0]["event_kind"])
        self.assertFalse(report["events"][0]["actual_completion_verified"])
        self.assertFalse(report["obligations"][0]["closed"])

    def test_unknown_due_does_not_invent_date_or_monitor(self):
        self.obligation()
        report = self.overview()
        self.assertIsNone(report["obligations"][0]["due_date"])
        self.assertFalse(report["automated_monitoring"])

    def test_superseded_obligation_cannot_be_reused_as_current(self):
        original=self.obligation_spec()
        old=self.store.register_obligation(self.case,spec=original,expected_revision=self.rev())['obligation_id']
        newer=dict(original,description='Yeni yükümlülük adayı',supersedes_id=old)
        self.store.register_obligation(self.case,spec=newer,expected_revision=self.rev())
        self.error('YENIDEN_INCELE',lambda:self.store.register_obligation(self.case,spec=original,expected_revision=self.rev()))

    def test_position_date_is_not_start_event_or_written_deadline(self):
        date_fact = self.fact("2026-10-01", node=self.statement, field="event_date", plane="USER_POSITION", method="DATE_ISO", unit=None, unit_literal=None)
        self.error("BILGI_DUZLEMI", lambda: self.obligation(date_fact=date_fact))
        rule = self.rule(start=False)
        rule["start_fact_id"] = date_fact
        self.error("BILGI_DUZLEMI", lambda: self.obligation(rule=rule))

    def test_fact_supersession_invalidates_due_obligation(self):
        date_fact = self.fact("2026-10-31", field="due_date", method="DATE_ISO", unit=None, unit_literal=None)
        self.obligation(date_fact=date_fact)
        node, _ = self.document("Son gün 2026-11-30.")
        spec = self.fact_spec("2026-11-30", node=node, field="due_date", method="DATE_ISO", unit=None, unit_literal=None)
        spec["supersedes_id"] = date_fact
        self.store.register_business_fact(self.case, spec=spec, expected_revision=self.rev())
        obligation = self.overview()["obligations"][0]
        self.assertEqual("NEEDS_REVIEW", obligation["state"])
        self.assertIsNone(obligation["due_date"])

    def test_invalid_overview_date_scope_or_stale_revision_rejected(self):
        self.error("TARIH_KURALI", lambda: self.overview(as_of="2026-02-30"))
        self.error("GECERSIZ_GIRDI", lambda: self.overview(scope_keys=[{}]))
        self.error("SURUM_CAKISMASI", lambda: self.overview(expected_revision=0))

    def test_real_005_database_upgrade_and_006_digest_guard(self):
        from sozlesme_cekirdek.store import MIGRATION, MIGRATION_VERIFIER, MIGRATION_CONTEXT, MIGRATION_GUARD, MIGRATION_DOCX, NOW
        system = self.area / "older/.sistem"
        system.mkdir(parents=True)
        with duckdb.connect(str(system / "sozlesme.duckdb")) as db:
            for index, path in enumerate([MIGRATION, MIGRATION_VERIFIER, MIGRATION_CONTEXT, MIGRATION_GUARD, MIGRATION_DOCX], 1):
                script = path.read_text(encoding="utf-8")
                db.execute(script)
                db.execute("INSERT INTO sema_gecmisi VALUES(?,?,?,?)", [index, "old", hashlib.sha256(script.encode()).hexdigest(), NOW()])
            db.execute("INSERT INTO dosyalar VALUES(?,?,0,'NEW',?)", [self.case, "Existing", NOW()])
        upgraded = Store(self.area / "older", source_roots=[self.sources], output_root=self.area)
        self.assertEqual(0, upgraded.case_revision(self.case))
        with upgraded._db() as db:
            self.assertEqual(23, db.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='main'").fetchone()[0])
        wrong = self.area / "wrong.sql"
        wrong.write_text("-- altered", encoding="utf-8")
        with patch("sozlesme_cekirdek.store.MIGRATION_BUSINESS", wrong):
            self.error("SEMA_DRIFT", lambda: Store(upgraded.root, source_roots=[self.sources], output_root=self.area))

    def skill_request(self, skill="K23", roots=None):
        return {"request_id": str(uuid4()), "case_id": self.case, "skill_id": skill, "intent": "Kaynaklı iş durumunu göster",
            "context_version": self.rev(), "selected_versions": self.versions, "root_ids": roots or [], "max_context_bytes": 65536,
            "policy_version": "1", "requested_output": "CHAT", "business_context": {"as_of": "2026-11-02", "scope_keys": ["main"]}}

    def test_real_skills_compare_and_track_without_reasking_existing_facts(self):
        from sozlesme_cekirdek.workflows import evaluate
        self.fact()
        self.fact("36", node=self.statement, plane="USER_POSITION")
        self.obligation(rule=self.rule())
        for skill in ("K03", "K23", "K24", "K25", "K26"):
            result = evaluate(self.store, self.skill_request(skill))
            self.assertEqual("p6-1.2", result["schema_version"])
            self.assertEqual("KISMI", result["status"])
            self.assertTrue(result["business_overview"]["comparisons"])
            self.assertEqual("2026-10-31", result["business_overview"]["obligations"][0]["due_date"])
            self.assertEqual([], result["open_questions"])
            self.assertEqual([], result["output_ids"])
            self.assertFalse(result["critical_analysis_allowed"])

    def test_combined_context_and_business_budget_does_not_hide_extra_bytes(self):
        from sozlesme_cekirdek.workflows import evaluate
        self.fact()
        request = self.skill_request(roots=[self.node])
        result = evaluate(self.store, request)
        required = result["business_budget"]["required_bytes"]
        request["max_context_bytes"] = required - 1
        blocked = evaluate(self.store, request)
        self.assertIsNone(blocked["business_overview"])
        self.assertEqual("BILGI_GEREKLI", blocked["status"])
        self.assertEqual(required, blocked["business_budget"]["required_bytes"])
        request["max_context_bytes"] = required
        complete = evaluate(self.store, request)
        self.assertIsNotNone(complete["business_overview"])
        self.assertEqual(required, complete["business_budget"]["used_bytes"])

    def test_missing_required_exception_stops_business_skill_context(self):
        from sozlesme_cekirdek.workflows import evaluate
        self.fact()
        self.store.register_context_relation(self.case, spec={"from_id": self.node, "relation": "EXCEPTION", "unresolved_reference": "Eksik özel koşul", "rationale": "Kaynaklı test"}, expected_revision=self.rev())
        result = evaluate(self.store, self.skill_request(roots=[self.node]))
        self.assertIsNone(result["business_overview"])
        self.assertEqual("BILGI_GEREKLI", result["status"])
        self.assertEqual([], result["findings"])

    def test_source_change_during_skill_recheck_blocks_stale_business_view(self):
        from sozlesme_cekirdek.workflows import evaluate
        self.fact()
        original = self.store.business_overview
        def edited(*args, **kwargs):
            result = original(*args, **kwargs)
            self.path.write_bytes(b"Source changed after assembly")
            return result
        with patch.object(self.store, "business_overview", side_effect=edited):
            with self.assertRaises(CoreError):
                evaluate(self.store, self.skill_request())

    def test_empty_business_scope_does_not_fabricate_success_or_findings(self):
        from sozlesme_cekirdek.workflows import evaluate
        result = evaluate(self.store, self.skill_request())
        self.assertEqual("BILGI_GEREKLI", result["status"])
        self.assertEqual([], result["business_overview"]["facts"])
        request = self.skill_request()
        request["business_context"]["approved"] = True
        self.error("SEMA_HATASI", lambda: evaluate(self.store, request))

    def test_real_cli_registers_fact_and_reads_overview_in_confined_path(self):
        request_path = self.sources / "İş isteği.json"
        request_path.write_text(json.dumps(self.fact_spec(), ensure_ascii=False), encoding="utf-8")
        base = [sys.executable, "-B", "-X", "utf8", "-m", "sozlesme_cekirdek", "--workspace", str(self.store.root), "--output-root", str(self.area), "--source-root", str(self.sources)]
        registered = subprocess.run(base + ["business-fact-register", "--case-id", self.case, "--request", str(request_path), "--expected-revision", str(self.rev())], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, registered.returncode, registered.stdout + registered.stderr)
        self.assertFalse(json.loads(registered.stdout)["result"]["reused"])
        request_path.write_text(json.dumps({"as_of": "2026-11-02", "scope_keys": ["main"], "selected_versions": self.versions, "context_version": self.rev()}), encoding="utf-8")
        command = base + ["business-overview", "--case-id", self.case, "--request", str(request_path)]
        report = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, report.returncode, report.stdout + report.stderr)
        self.assertEqual("24", json.loads(report.stdout)["result"]["facts"][0]["value"]["value"])
        outside = self.area / "outside.json"
        outside.write_bytes(request_path.read_bytes())
        command[-1] = str(outside)
        denied = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(2, denied.returncode)
        self.assertEqual("ERISIM_YOK", json.loads(denied.stdout)["error_code"])

    def test_business_ledger_round_trip_snapshot_preserves_semantics(self):
        self.fact()
        self.obligation(rule=self.rule())
        before = self.overview()
        snapshot = self.area / "snapshot"
        self.store.snapshot(snapshot)
        restored = Store.restore(snapshot, self.area / "restored", source_roots=[self.sources], output_root=self.area)
        after = restored.business_overview(self.case, as_of="2026-11-02", scope_keys=["main"], selected_versions=self.versions)
        self.assertEqual(before, after)

    def test_business_calendar_version_and_holidays_are_explicit(self):
        node, _ = self.document("Teslim 2 iş günü içinde.")
        count = self.fact("2", node=node, field="delivery_days", unit="business_days", unit_literal="iş günü")
        start = self.fact("2026-10-01", node=self.statement, field="accepted_on", plane="REPORTED_EVENT", method="DATE_ISO", unit=None, unit_literal=None)
        rule = {"count_fact_id": count, "start_fact_id": start, "anchor_event": "Kabul", "include_start": False, "month_end": None,
            "weekend": [5, 6], "holidays": ["2026-10-02"], "holiday_calendar_complete": True, "calendar_version": None}
        first = self.obligation(rule=rule)
        rule["calendar_version"] = "USER_CALENDAR_2026_V1"
        second = self.obligation(rule=rule)
        rows = {row["obligation_id"]: row for row in self.overview()["obligations"]}
        self.assertIsNone(rows[first]["due_date"])
        self.assertIn("takvimi sürümü", rows[first]["missing_due_reason"])
        self.assertEqual("2026-10-06", rows[second]["due_date"])


if __name__ == "__main__":
    unittest.main()
