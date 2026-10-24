"""Run selected synthetic tests on exact product bytes in an owned staging copy.

No installers, network, production credentials or real company documents.
Evidence is written outside the source package; Store/Windows lock are not mocked.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import sys
import time
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()
            and not any(part in {"__pycache__", ".runtime"} for part in p.relative_to(root).parts)}


def source_git_context(package=ROOT):
    """Optional base-commit context, never an attestation of the tested bytes."""
    unknown = {"source_commit": None, "dirty_source": None, "source_git_root": None,
               "source_git_status": "NOT_RUN", "source_git_reason": None,
               "source_commit_attestation": "UNVERIFIED"}
    executable = shutil.which("git")
    if executable is None:
        return dict(unknown, source_git_reason="GIT_UNAVAILABLE")
    package = Path(package).resolve()
    repo = next((path for path in (package, *package.parents)
                 if (path / ".git").is_file() or (path / ".git").is_dir()), None)
    if repo is None:
        return dict(unknown, source_git_reason="NO_OWNING_GIT_CHECKOUT")
    def git(*values):
        return subprocess.run([executable, "--no-optional-locks", "-c", "safe.directory=" + str(repo),
                               "-C", str(repo), *values], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        marker = (package / "plugin.json").relative_to(repo).as_posix()
        tracked = git("ls-files", "--error-unmatch", "--", marker)
        if tracked.returncode == 1:
            return dict(unknown, source_git_reason="PACKAGE_NOT_TRACKED_BY_ANCESTOR")
        tracked.check_returncode()
        top = git("rev-parse", "--show-toplevel"); top.check_returncode()
        if Path(top.stdout.strip()).resolve() != repo:
            raise ValueError("Git root does not own the package")
        head = git("rev-parse", "HEAD"); head.check_returncode()
        commit = head.stdout.strip()
        if len(commit) not in (40, 64) or any(c not in "0123456789abcdef" for c in commit):
            raise ValueError("Invalid Git commit response")
        relative = package.relative_to(repo).as_posix()
        state = git("status", "--porcelain", "--", relative); state.check_returncode()
        return {"source_commit": commit, "dirty_source": bool(state.stdout.strip()),
                "source_git_root": str(repo), "source_git_status": "OBSERVED", "source_git_reason": None,
                "source_commit_attestation": "BASE_COMMIT_CONTEXT_ONLY"}
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return dict(unknown, source_git_status="ERROR", source_git_reason=type(exc).__name__)


class RecordedResult(unittest.TextTestResult):
    event_path = None
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
    def startTest(self, test):
        self.started = time.perf_counter()
        self.event({"test_id": test.id(), "status": "STARTED"})
        super().startTest(test)
    def event(self, value):
        if self.event_path is not None:
            with self.event_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(value, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
    def record(self, test, status, detail=None):
        value = {"test_id": test.id(), "status": status, "detail": detail,
                 "seconds": round(time.perf_counter() - self.started, 4)}
        self.records.append(value)
        self.event(value)
    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, "PASS")
    def addError(self, test, err):
        super().addError(test, err); self.record(test, "ERROR", self._exc_info_to_string(err, test))
    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, "FAIL", self._exc_info_to_string(err, test))
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, "NOT_RUN", reason)
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.record(subtest, "FAIL" if issubclass(err[0], test.failureException) else "ERROR",
                        self._exc_info_to_string(err, test))


def interrupted_report(output,reason):
    inventory_path=output.with_suffix(".inventory.json")
    discovery_complete=False
    try:
        inventory=json.loads(inventory_path.read_text(encoding="utf-8"))
        if not isinstance(inventory.get('tests'),list) or any(not isinstance(n,str) for n in inventory['tests']):raise ValueError('Invalid inventory')
        discovery_complete=True
    except (OSError,ValueError,TypeError,AttributeError):inventory={"tests":[]}
    event_path=output.with_suffix(".events.jsonl")
    events=[];corrupt=False
    if event_path.exists():
        if event_path.stat().st_size>16*1024*1024:corrupt=True
        else:
            for line in event_path.read_bytes().splitlines():
                try:
                    event=json.loads(line.decode("utf-8"))
                    if (not isinstance(event,dict) or not isinstance(event.get('test_id'),str)
                            or event.get('status') not in {'STARTED','PASS','FAIL','ERROR','NOT_RUN'}):raise ValueError('Invalid event')
                    events.append(event)
                except (ValueError,UnicodeError):corrupt=True;break
    terminals=[e for e in events if e.get("status") in {"PASS","FAIL","ERROR","NOT_RUN"}]
    completed={e.get("test_id") for e in terminals}
    not_run=[{"test_id":name,"status":"NOT_RUN","detail":"No durable terminal test record"}
             for name in inventory["tests"] if name not in completed]
    return {"schema":"contract-product-test-receipt/v1","status":"ERROR","reason":reason,
            "event_log_corrupt_or_partial":corrupt,"records":terminals+not_run+inventory.get('excluded',[]),"events":events,
            "methods_started":len({e.get('test_id') for e in events if e.get('status')=='STARTED'}),
            "methods_completed":len(completed),"methods_run":len(completed),
            "failures":sum(e['status']=='FAIL' for e in terminals),"errors":1+sum(e['status']=='ERROR' for e in terminals),
            "skipped":len(not_run),"discovery_complete":discovery_complete,
            "unselected_not_run":inventory.get('unselected_not_run',[]),
            "classes_not_run":{} if discovery_complete else {"ALL_SELECTED_CLASSES":"NOT_RUN: discovery/terminal receipt missing"},
            "full_product_acceptance":"NOT_GRANTED","release_acceptance":"BLOCKED","production_approved":False}


def run_child(output, suite_name, selection):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / "tests")); sys.path.insert(0, str(ROOT / "src"))
    os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONPATH=str(ROOT / "src"), SOZLESME_DEVELOPMENT="1")
    manifest = json.loads((ROOT / "tests/manifest.json").read_text(encoding="utf-8"))
    before = snapshot(ROOT)
    suite = unittest.TestSuite()
    excluded = []
    available = set()
    classes = manifest["classes"] if suite_name == "full" else manifest["suites"][suite_name]
    for name in classes:
        module_name, class_name = name.rsplit(".", 1)
        module = importlib.import_module(module_name)
        if Path(module.__file__).resolve().parent != (ROOT / "tests").resolve():
            raise RuntimeError("Test module did not load from the staged test source")
        for test in unittest.defaultTestLoader.loadTestsFromTestCase(getattr(module, class_name)):
            available.add(test.id())
            if selection and test.id() not in selection:
                continue
            if test.id() in manifest["excluded"]:
                excluded.append({"test_id": test.id(), "status": "NOT_RUN", "detail": manifest["excluded"][test.id()]})
            else:
                suite.addTest(test)
    if set(selection) - available:
        raise ValueError("Requested test is not in the selected immutable manifest")
    import duckdb
    import sozlesme_cekirdek
    actual = Path(sozlesme_cekirdek.__file__).resolve()
    if actual != (ROOT / "src/sozlesme_cekirdek/__init__.py").resolve():
        raise RuntimeError("Product module did not load from the exact staged source")
    RecordedResult.event_path = output.with_suffix(".events.jsonl")
    output.with_suffix(".inventory.json").write_text(json.dumps({"tests":[test.id() for test in suite],"excluded":excluded,
        "unselected_not_run":sorted(available-set(selection)) if selection else []},ensure_ascii=False)+"\n",encoding="utf-8")
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    after = snapshot(ROOT)
    report = {"schema": "contract-product-test-receipt/v1", "receipt_phase": "CHILD_TERMINAL_ONLY",
              "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "platform": platform.platform(), "python": sys.version, "python_abi": sys.implementation.cache_tag,
              "product_module": str(actual), "duckdb_connection_class": str(duckdb.DuckDBPyConnection),
              "dependencies": {n: importlib.metadata.version(n) for n in ["duckdb", "jsonschema", "lxml", "openpyxl", "pypdf", "pypdfium2", "Pillow"]},
              "manifest_digest": digest(manifest), "source_before": before, "source_after": after,
              "source_unchanged": before == after, "source_digest": digest(before),
              "methods_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "records": result.records + excluded,
              "acceptance_not_run": manifest["acceptance_not_run"], "production_approved": False,
              "scope": manifest["scope"], "suite": suite_name, "classes": classes,
              "execution_profile": "DEVELOPMENT_WITH_ISOLATED_NATIVE_ACCEPTANCE_TESTS",
              "test_selection": selection, "unselected_not_run": sorted(available - set(selection)) if selection else [],
              "classes_not_run": manifest.get("classes_not_run", {}),
              "release_acceptance": "BLOCKED", "full_product_acceptance": "NOT_GRANTED"}
    report["status"] = "PASS" if result.wasSuccessful() and not result.skipped and before == after else "FAIL"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--label", default="product")
    parser.add_argument("--suite", choices=("full", "core", "a0", "identity", "quality", "bootstrap", "budget", "readers", "lifecycle", "objects", "publication", "processing", "startup", "capacity", "source_roles", "inspector", "recovery", "receipt_faults", "migration"), default="full")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--test", action="append", default=[], dest="selection")
    parser.add_argument("--child-report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child_report is not None:
        return run_child(args.child_report, args.suite, args.selection)
    if os.name != "nt":
        raise SystemExit("NOT_RUN: this integration suite requires the real Windows lock provider")
    if not 1 <= args.timeout_seconds <= 3600:
        raise SystemExit("Test timeout must be between 1 and 3600 seconds")
    area = args.output_root.resolve()
    if area == ROOT or area.is_relative_to(ROOT):
        raise SystemExit("Evidence output must be outside the source package")
    if not args.label.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("Only letters, numbers, hyphens and underscores are allowed in label")
    area.mkdir(parents=True, exist_ok=True)
    run_dir = area / (args.label + "-" + uuid4().hex[:10])
    run_dir.mkdir()
    before = snapshot(ROOT)
    git_context = source_git_context()
    # Store/lock tests run outside the mirrored vault to avoid Drive temp writers
    # racing cleanup. Evidence still goes to the requested source-linked folder.
    stage = Path(tempfile.mkdtemp(prefix="cs-product-")) / "package"
    shutil.copytree(ROOT, stage, ignore=shutil.ignore_patterns("__pycache__", ".runtime"))
    if snapshot(stage) != before:
        raise SystemExit("Staged source bytes differ")
    command = [sys.executable, "-X", "utf8", str(stage / "scripts/run_product_tests.py"),
               "--output-root", str(run_dir), "--suite", args.suite, "--child-report", str(run_dir / "result.json")]
    for name in args.selection:
        command += ["--test", name]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONPATH=str(stage / "src"))
    manifest = json.loads((ROOT / "tests/manifest.json").read_text(encoding="utf-8"))
    active_classes = manifest["classes"] if args.suite == "full" else manifest["suites"][args.suite]
    needs_legacy = "test_migration_acceptance.LegacyCompatibilityTests" in active_classes
    if args.selection:
        needs_legacy = needs_legacy and any(name.startswith("test_migration_acceptance.LegacyCompatibilityTests.") for name in args.selection)
    if needs_legacy:
        from legacy_reference import prepare_audit_reference
        reference_receipt = run_dir / "audit-reference.json"
        try:
            if git_context["source_git_status"] != "OBSERVED":
                raise RuntimeError("Owning source checkout is unavailable for the immutable audit reference")
            prepare_audit_reference(Path(git_context["source_git_root"]), stage.parent / "audit-reference", manifest["immutable_audit_reference"], reference_receipt)
        except Exception as exc:
            receipt={"schema":"contract-product-test-receipt/v1","receipt_phase":"FINAL","status":"NOT_RUN","reason":"AUDIT_REFERENCE_UNAVAILABLE",
                     "detail":type(exc).__name__+": "+str(exc),"methods_run":0,"records":[],
                     "classes_not_run":{name:"NOT_RUN: immutable audit reference unavailable" for name in active_classes},
                     "source_before":before,"source_after":snapshot(ROOT),"source_digest":digest(before),
                     "manifest_digest":digest(manifest),"source_unchanged":snapshot(stage)==before,
                     "original_source_unchanged":snapshot(ROOT)==before,"acceptance_not_run":manifest['acceptance_not_run'],
                     "production_approved":False,"full_product_acceptance":"NOT_GRANTED","release_acceptance":"BLOCKED", **git_context}
            (run_dir/'result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({"status":"NOT_RUN","report":str(run_dir/'result.json'),"reason":"AUDIT_REFERENCE_UNAVAILABLE"}))
            return 1
        env["CONTRACT_AUDIT_REFERENCE_RECEIPT"] = str(reference_receipt)
    timed_out = False
    with (run_dir / "console.log").open("wb") as log:
        try:
            child = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout_seconds,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            exit_code = child.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = 124
    after = snapshot(ROOT)
    receipt_path = run_dir / "result.json"
    report = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else interrupted_report(receipt_path,"CHILD_TERMINAL_RECEIPT_MISSING")
    if timed_out:
        report=interrupted_report(receipt_path,"TEST_TIME_LIMIT")
        report.update(status="NOT_RUN",
                      source_digest=digest(before), suite=args.suite, full_product_acceptance="NOT_GRANTED", release_acceptance="BLOCKED")
    if not receipt_path.exists() or timed_out:
        staged_after=snapshot(stage)
        report.update(source_before=before,source_after=staged_after,source_unchanged=before==staged_after,
                      source_digest=digest(before),manifest_digest=digest(manifest),acceptance_not_run=manifest['acceptance_not_run'])
    report.update(git_context)
    report.update(receipt_phase="FINAL", staging_package=str(stage),
                  source_package=str(ROOT), original_source_unchanged=before == after, command=command,
                  exit_code=exit_code, console_sha256=hashlib.sha256((run_dir / "console.log").read_bytes()).hexdigest())
    if before != after or exit_code and not timed_out:
        report["status"] = "FAIL"
    receipt_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(receipt_path), "methods_run": report.get("methods_run"),
                      "failures": report.get("failures"), "errors": report.get("errors"), "exit_code": exit_code}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
