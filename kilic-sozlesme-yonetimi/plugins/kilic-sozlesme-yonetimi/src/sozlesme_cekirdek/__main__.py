"""Agent-facing allowlisted commands; no arbitrary SQL/shell or production writes."""
import argparse
import hashlib
import json
import sys
from uuid import uuid4
from .store import Store
from .errors import CoreError
from .safety import confined, native_path
from .runtime_identity import component_identity, component_policy

TOOL_VERSION = component_policy()["core_version"]


def inventory(data):
    return {"schema_version": "1.0", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    from pathlib import Path
    import os
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
    try:
        from bootstrap_integrity import verify_package
        verify_package(Path(__file__).resolve().parents[2])
        from runtime_registry import entry_gate
        runtime_binding=entry_gate()
    except Exception as exc:
        print(json.dumps({"status":"BLOCKED","error_code":getattr(exc,"code","PAKET_BUTUNLUK"),
            "message":str(exc),"business_acceptance":"NOT_GRANTED"},ensure_ascii=False))
        raise SystemExit(2)
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--source-root", action="append", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("case-create")
    create.add_argument("--title", required=True)
    doc = commands.add_parser("document-create")
    doc.add_argument("--case-id", required=True)
    doc.add_argument("--title", required=True)
    doc.add_argument("--expected-revision", required=True, type=int)
    statement = commands.add_parser("statement-register")
    statement.add_argument("--case-id", required=True)
    statement.add_argument("--request", required=True)
    statement.add_argument("--expected-revision", required=True, type=int)
    ingest = commands.add_parser("source-ingest")
    ingest.add_argument("--case-id", required=True)
    ingest.add_argument("--document-id", required=True)
    ingest.add_argument("--source", required=True)
    ingest.add_argument("--expected-revision", required=True, type=int)
    ingest.add_argument("--parent-version-id")
    context = commands.add_parser("context")
    context.add_argument("--case-id", required=True)
    capacity=commands.add_parser("capacity")
    capacity.add_argument("--case-id",required=True)
    compare=commands.add_parser("version-compare")
    compare.add_argument("--case-id",required=True)
    compare.add_argument("--reference-version-id",required=True)
    compare.add_argument("--current-target-version-id",required=True)
    output_inspect=commands.add_parser("output-inspect")
    output_inspect.add_argument("--case-id",required=True)
    portfolio=commands.add_parser("portfolio-overview")
    portfolio.add_argument("--request",required=True)
    rebind=commands.add_parser("context-rebind")
    rebind.add_argument("--case-id",required=True)
    rebind.add_argument("--expected-revision",required=True,type=int)
    rebind.add_argument("--policy-version",default="1")
    read = commands.add_parser("document-read")
    read.add_argument("--case-id", required=True)
    read.add_argument("--version-id", required=True)
    read.add_argument("--format", required=True, choices=["DOCX", "PDF", "XLSX", "EML"])
    checks = commands.add_parser("verification-check")
    checks.add_argument("--case-id", required=True)
    checks.add_argument("--version-id", required=True)
    checks.add_argument("--request", required=True)
    checks.add_argument("--method", required=True, choices=["EXTRACTED_TEXT_MATCH", "PDF_PAGE_RENDER"])
    checks.add_argument("--expected-revision", required=True, type=int)
    checks.add_argument("--policy-version", default="1")
    history = commands.add_parser("verification-history")
    history.add_argument("--case-id", required=True)
    history.add_argument("--version-id", required=True)
    history.add_argument("--policy-version", default="1")
    for name in ("context-node-register", "context-relation-register", "context-pack"):
        command = commands.add_parser(name)
        command.add_argument("--case-id", required=True)
        command.add_argument("--request", required=True)
        if name != "context-pack":
            command.add_argument("--expected-revision", required=True, type=int)
        if name == "context-node-register":
            command.add_argument("--policy-version", default="1")
    for name in ("context-source-map", "context-pack-history"):
        command = commands.add_parser(name)
        command.add_argument("--case-id", required=True)
    guard = commands.add_parser("action-evaluate")
    guard.add_argument("--request", required=True)
    action_status = commands.add_parser("action-status")
    action_status.add_argument("--case-id", required=True)
    action_status.add_argument("--operation-id", required=True)
    docx_history = commands.add_parser("docx-output-history")
    docx_history.add_argument("--case-id", required=True)
    skill=commands.add_parser("skill-evaluate")
    skill.add_argument("--request",required=True)
    for name in ("business-fact-register", "obligation-register", "business-event-register", "business-overview"):
        business = commands.add_parser(name)
        business.add_argument("--case-id", required=True)
        business.add_argument("--request", required=True)
        business.add_argument("--policy-version", default="1")
        if name != "business-overview":
            business.add_argument("--expected-revision", required=True, type=int)
    commands.add_parser("reconcile")
    args = parser.parse_args()
    operation_id=str(uuid4())
    components = None
    try:
        components = dict(component_identity(), execution_profile=runtime_binding['execution_profile'])
        store = Store(args.workspace, source_roots=args.source_root, output_root=args.output_root)
        if args.command == "case-create":
            result = {"case_id": store.create_case(args.title)}
        elif args.command == "document-create":
            result = {"document_id": store.create_document(args.case_id, args.title, expected_revision=args.expected_revision)}
        elif args.command == "statement-register":
            from .workflows import checked
            path = native_path(confined(args.request, store.source_roots))
            if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 65536:
                raise CoreError("GECERSIZ_GIRDI", "Beyan isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as exc:
                raise CoreError("SEMA_HATASI", "Beyan JSON isteği geçersiz") from exc
            checked("statement_request", request)
            rid = store.add_statement(args.case_id, request["text"], expected_revision=args.expected_revision,
                                      session_ref=request.get("session_ref"), message_ref=request.get("message_ref"))
            result = {"statement_id": rid, "trust": "UNVERIFIED_LOCAL_STATEMENT", "authority": "NOT_VERIFIED"}
        elif args.command == "source-ingest":
            result = store.ingest(args.case_id, args.document_id, args.source, expected_revision=args.expected_revision,parent_version_id=args.parent_version_id)
        elif args.command == "context":
            result = store.context(args.case_id)
        elif args.command == "capacity":
            result = store.capacity(args.case_id)
        elif args.command == "version-compare":
            result = store.compare_source_roles(args.case_id,args.reference_version_id,args.current_target_version_id)
        elif args.command == "output-inspect":
            result = store.inspect_outputs(args.case_id)
        elif args.command == "portfolio-overview":
            path = native_path(confined(args.request, store.source_roots))
            if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 65536:
                raise CoreError("GECERSIZ_GIRDI", "Portföy isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as exc:
                raise CoreError("SEMA_HATASI", "Portföy JSON isteği geçersiz") from exc
            result = store.portfolio_overview(request)
        elif args.command == "context-rebind":
            result = store.rebind_context(args.case_id, expected_revision=args.expected_revision, policy_version=args.policy_version)
        elif args.command == "document-read":
            result = store.read_document(args.case_id, args.version_id, format=args.format)
        elif args.command == "verification-check":
            path = native_path(confined(args.request, store.source_roots))
            if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 65536:
                raise CoreError("GECERSIZ_GIRDI", "Kontrol isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as exc:
                raise CoreError("SEMA_HATASI", "Kontrol JSON isteği geçersiz") from exc
            action = store.verify_excerpt if args.method == "EXTRACTED_TEXT_MATCH" else store.prepare_pdf_review
            result = action(args.case_id, args.version_id, request=request, expected_revision=args.expected_revision, policy_version=args.policy_version)
        elif args.command == "verification-history":
            result = store.verification_history(args.case_id, args.version_id, policy_version=args.policy_version)
        elif args.command in {"context-node-register", "context-relation-register", "context-pack"}:
            path = native_path(confined(args.request, store.source_roots))
            if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 65536:
                raise CoreError("GECERSIZ_GIRDI", "Bağlam isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as exc:
                raise CoreError("SEMA_HATASI", "Bağlam JSON isteği geçersiz") from exc
            if args.command == "context-pack":
                result = store.context_pack(args.case_id, request=request)
            elif args.command == "context-node-register":
                result = store.register_context_node(args.case_id, spec=request, expected_revision=args.expected_revision, policy_version=args.policy_version)
            else:
                result = store.register_context_relation(args.case_id, spec=request, expected_revision=args.expected_revision)
        elif args.command == "context-source-map":
            result = store.context_source_map(args.case_id)
        elif args.command == "context-pack-history":
            result = store.context_pack_history(args.case_id)
        elif args.command == "action-evaluate":
            path = native_path(confined(args.request, store.source_roots))
            if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 65536:
                raise CoreError("GECERSIZ_GIRDI", "Muhafız isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as exc:
                raise CoreError("SEMA_HATASI", "Muhafız JSON isteği geçersiz") from exc
            result = store.evaluate_action(request=request)
        elif args.command == "action-status":
            result = store.action_status(args.case_id, args.operation_id)
        elif args.command == "docx-output-history":
            result = store.docx_output_history(args.case_id)
        elif args.command in {"business-fact-register", "obligation-register", "business-event-register", "business-overview"}:
            from .context import checked
            path = native_path(confined(args.request, store.source_roots))
            if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 65536:
                raise CoreError("GECERSIZ_GIRDI", "İş kayıt isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request = json.loads(path.read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeError) as exc:
                raise CoreError("SEMA_HATASI", "İş kayıt JSON isteği geçersiz") from exc
            if args.command == "business-overview":
                checked("p6_business_overview_request", request)
                result = store.business_overview(args.case_id, as_of=request["as_of"], scope_keys=request["scope_keys"],
                    selected_versions=request["selected_versions"], expected_revision=request["context_version"], policy_version=args.policy_version)
            else:
                action = {"business-fact-register": store.register_business_fact, "obligation-register": store.register_obligation,
                    "business-event-register": store.register_business_event}[args.command]
                result = action(args.case_id, spec=request, expected_revision=args.expected_revision, policy_version=args.policy_version)
        elif args.command == "skill-evaluate":
            from .workflows import evaluate
            path=native_path(confined(args.request,store.source_roots))
            if path.suffix.lower()!=".json" or not path.is_file() or path.stat().st_size>65536:
                raise CoreError("GECERSIZ_GIRDI","Skill isteği izinli kökte küçük JSON dosyası olmalı")
            try:
                request_bytes=path.read_bytes()
                request=json.loads(request_bytes.decode("utf-8-sig"))
            except (ValueError,UnicodeError) as exc:raise CoreError("SEMA_HATASI","Skill JSON isteği geçersiz") from exc
            if runtime_binding["execution_profile"] != "DEVELOPMENT":
                from runtime_registry import claim_execution, RuntimeErrorDetail
                try:claim_execution(path, request, runtime_binding, store.root, store.output_root, store.source_roots, request_bytes)
                except RuntimeErrorDetail as exc:raise CoreError(exc.code,str(exc)) from exc
            result=evaluate(store,request,operation_id=operation_id)
        else:
            result = store.reconcile()
        print(json.dumps({"schema_version":"1.0","operation_id":operation_id,"status":"SUCCEEDED","technical_status":"SUCCEEDED",
                          "business_status":result.get("status","NOT_RUN") if args.command=="skill-evaluate" else "NOT_RUN",
                          "business_acceptance":"NOT_GRANTED","result":result,
                          "result_refs":[],"evidence_refs":[],"warnings":[],"limitations":["P1/P2/P3/P4/P5 teknik kayıt; kritik sadakat PARTIAL, üretim eylemleri kapalı, hukuki doğrulama NOT_RUN."],
                          "error_code":None,"retry_safety":"READ_ONLY" if args.command in {"context","capacity","version-compare","output-inspect","portfolio-overview"} else "NO_BLIND_RETRY",
                          "tool_version":TOOL_VERSION,"components":components,"case_id":getattr(args,"case_id",None),"analysis_status":"NOT_RUN","authority":"NOT_VERIFIED"}, ensure_ascii=False))
    except CoreError as exc:
        print(json.dumps({"schema_version":"1.0","operation_id":operation_id,"status":"BLOCKED","technical_status":"BLOCKED",
                          "business_status":"NOT_RUN","business_acceptance":"NOT_GRANTED","error_code":exc.code,"message":str(exc),
                          "result_refs":[],"evidence_refs":[],"warnings":[],"limitations":[],"retry_safety":"NO_BLIND_RETRY","tool_version":TOOL_VERSION,"components":components}, ensure_ascii=False))
        raise SystemExit(2)
    except Exception as exc:
        print(json.dumps({"schema_version":"1.0","operation_id":operation_id,"status":"BLOCKED","technical_status":"BLOCKED",
                          "business_status":"NOT_RUN","business_acceptance":"NOT_GRANTED","error_code":"TEKNIK_HATA",
                          "result_refs":[],"evidence_refs":[],"warnings":[],"limitations":[],"retry_safety":"NO_BLIND_RETRY","tool_version":TOOL_VERSION,"components":components}, ensure_ascii=False))
        print(type(exc).__name__,file=sys.stderr)
        raise SystemExit(3)


if __name__ == "__main__":
    main()
