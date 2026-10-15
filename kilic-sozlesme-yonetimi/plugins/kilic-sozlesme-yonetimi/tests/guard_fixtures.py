"""Isolated synthetic identity/backend. Never production configuration or company authority."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from sozlesme_cekirdek.guard import TestIdentity, TestQA, payload_digest
from sozlesme_cekirdek.safety import hash_value
from reader_fixtures import docx_bytes

KEY = b"synthetic-fixture-only-not-a-secret-0123456789"
NOW = datetime(2026, 10, 4, 18, 30, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.value = NOW
    def __call__(self):
        return self.value


class Host:
    def __init__(self, case):
        self.identity = TestIdentity("synthetic-actor", "test-identity-1", "test-policy-1", "synthetic-company",
                                     frozenset([case]), frozenset(["BUILD_DOCUMENT", "APPLY_TRACK_CHANGES", "CREATE_CLEAN_COPY"]),
                                     None, corporate_authorized=True, quality_ready=True)
    def __call__(self):
        return self.identity
    def authorize(self, request):
        self.identity = replace(self.identity, explicit_request_digest=payload_digest(request))


from process_fixtures import abrupt_exit


class Backend:
    synthetic_only = True
    version = "synthetic-backend-1"
    def __init__(self, log=None):
        self.log = Path(log) if log else None
        self.prepared = 0
        self.sent = 0
        self.data = docx_bytes()  # A fixed golden fixture, never a Track Changes generator.
        self.good_qa = True
        self.on_prepare = None
        self.on_qa = None
        self.crash_after_prepare = False
    def prepare_document(self, request, snapshots):
        self.prepared += 1
        if self.log:
            with self.log.open("a", encoding="utf-8") as writer:
                writer.write(request["plan"]["operation_id"] + "\n")
                writer.flush()
                os.fsync(writer.fileno())
        if self.crash_after_prepare:
            if getattr(self,"phase_log",None):
                with self.phase_log.open("a",encoding="utf-8") as stream:
                    stream.write(json.dumps({"phase":"BEFORE_DELIBERATE_EXIT_19","pid":os.getpid()})+"\n")
                    stream.flush();os.fsync(stream.fileno())
            abrupt_exit(19)
        if self.on_prepare:
            self.on_prepare()
        return self.data
    def verify_document(self, request, data):
        if self.on_qa:
            self.on_qa()
        return TestQA(self.good_qa and data == self.data, hashlib.sha256(data).hexdigest())


def request(case, version, sha, *, mail=False, operation=None):
    operation = operation or str(uuid4())
    payload = {"company_scope_id": "synthetic-company"}
    if mail:
        payload.update(body_utf8="Sentetik gövde. İ ı ş ğ ç ö ü.", tenant_id="synthetic-tenant", mailbox_id="synthetic-mailbox")
        parameters = {"account_id": "synthetic-account", "from_address": "sender@example.invalid", "to": ["recipient@example.invalid"],
                      "cc": [], "bcc": [], "subject": "Sentetik konu", "body_media_type": "text/plain",
                      "body_sha256": hashlib.sha256(payload["body_utf8"].encode("utf-8")).hexdigest(),
                      "attachments": [{"version_id": version, "sha256": sha, "filename": "sentetik-ek.txt"}]}
    else:
        payload.update(content_plan={"body_text": "Sentetik iç taslak"}, changes=[])
        parameters = {"output_format": "DOCX", "target_relative_path": "ciktilar/" + operation + " İı.docx",
                      "content_plan_sha256": hash_value(payload["content_plan"]), "change_plan_sha256": None}
    return {"schema_version": "p4-1.0", "plan": {"schema_version": "1.0", "operation_id": operation, "case_id": case,
            "action_type": "SEND_EMAIL" if mail else "BUILD_DOCUMENT", "purpose": "EXTERNAL_DRAFT" if mail else "INTERNAL_DRAFT",
            "source_versions": [{"version_id": version, "sha256": sha}], "parameters": parameters}, "payload": payload}
