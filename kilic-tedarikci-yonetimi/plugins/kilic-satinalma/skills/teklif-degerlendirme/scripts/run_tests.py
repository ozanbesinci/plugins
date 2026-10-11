"""Run each requested DB engine in a separate process; record actual connections."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import sqlite3
import subprocess
import shutil
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parents[2]

def source_fingerprint(source_root=None):
    source_root = SOURCE_ROOT if source_root is None else Path(source_root)
    # Output ancestors are not plugin contents. A frozen checkout can itself
    # live below test-results without excluding every source file.
    return {str(p.relative_to(source_root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source_root.rglob("*")) if p.is_file()
            and not {"__pycache__", "test-results", ".git"}.intersection(p.relative_to(source_root).parts)
            and (p.suffix in {".py", ".json", ".sql", ".md", ".txt", ".toml", ".yaml", ".yml"} or p.name == "VERSION")}

def connection_engine(con):
    if isinstance(con, sqlite3.Connection):
        return "sqlite"
    import duckdb
    if isinstance(con, duckdb.DuckDBPyConnection):
        return "duckdb"
    raise AssertionError(f"Unknown connection class: {type(con)}")

def assert_engine(con, expected):
    actual = connection_engine(con)
    if actual != expected:
        raise AssertionError(f"DB engine mismatch: requested={expected}, actual={actual}")
    return actual

class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = []
    def addSuccess(self, test):
        self.passed_ids.append(test.id())
        super().addSuccess(test)

def child(engine, pattern, output, source_head=None, run_id=None, duckdb_threads=1):
    # expected is a CLI value captured by the closure, never derived from env.
    os.environ["TEKLIF_TEST_SQLITE"] = "1" if engine == "sqlite" else "0"
    import test_engine_support
    test_engine_support.EXPECTED_ENGINE = engine
    import db
    if engine == "duckdb" and duckdb_threads:
        import duckdb
        native_connect = duckdb.connect
        def fixture_connect(*args, **kwargs):
            config = dict(kwargs.pop("config", {}) or {})
            config.setdefault("threads", str(duckdb_threads))
            return native_connect(*args, config=config, **kwargs)
        duckdb.connect = fixture_connect
    original_connect = db.connect
    observed = {}
    def checked_connect(*args, **kwargs):
        con = original_connect(*args, **kwargs)
        try:
            actual = assert_engine(con, engine)
        except BaseException:
            con.close()
            raise
        key = f"{actual}:{type(con).__module__}.{type(con).__name__}"
        observed[key] = observed.get(key, 0) + 1
        return con
    db.connect = checked_connect  # BEFORE discovery/from-imports
    report = {"requested_engine": engine, "python": sys.version,
              "platform": platform.platform(), "executable": sys.executable,
              "pattern": pattern, "run_id": run_id, "observed_connections": observed,
              "source_fingerprint_scope": "kilic-satinalma plugin runtime and instructions"}
    source = {}
    try:
        source = source_fingerprint()
        if not source:
            raise RuntimeError("Empty plugin source fingerprint; test run refused")
        with tempfile.TemporaryDirectory() as td:
            probe = checked_connect(Path(td))
            probe.execute("SELECT 1").fetchone()
            report["duckdb_threads"] = int(probe.execute("SELECT current_setting('threads')").fetchone()[0]) if engine == "duckdb" else None
            probe.close()
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
        report["discovered"] = suite.countTestCases()
        result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
        report.update(executed=result.testsRun, passed=len(result.passed_ids),
                      failed=len(result.failures), errors=len(result.errors),
                      skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                      unexpected_successes=len(result.unexpectedSuccesses),
                      pass_ids=result.passed_ids,
                      failures=[{"test": t.id(), "traceback": s} for t, s in result.failures],
                      error_details=[{"test": t.id(), "traceback": s} for t, s in result.errors],
                      skip_details=[{"test": t.id(), "reason": s} for t, s in result.skipped],
                      status="PASS" if result.testsRun > 0 and result.wasSuccessful() and not result.skipped
                      and not result.expectedFailures else "INCOMPLETE")
        code = 0 if report["status"] == "PASS" else 1
    except BaseException as exc:
        report.update(status="NOT_RUN", error=str(exc), executed=0)
        code = 1
    report["source_files"] = source
    report["source_unchanged_during_run"] = bool(source) and source == source_fingerprint()
    if not source:
        report["status"] = "NOT_RUN_SOURCE_INVALID"
        code = 1
    elif not report["source_unchanged_during_run"]:
        report["status"] = "INCOMPLETE_SOURCE_CHANGED"
        code = 1
    report["source_sha256"] = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    report["head"] = source_head or (head.stdout.strip() if head.returncode == 0 else None)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in
                      {"pass_ids", "failures", "error_details", "skip_details", "source_files"}}, ensure_ascii=False))
    return code


def validate_child_report(path, engine, run_id, process_code, expected_source=None):
    """Exit zero cannot substitute for a fresh, complete child test report."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        fresh = report.get("run_id") == run_id and report.get("requested_engine") == engine
        classes = report.get("observed_connections", {})
        actual_class = "sqlite:sqlite3.Connection" if engine == "sqlite" else "duckdb:_duckdb.DuckDBPyConnection"
        count_keys=('discovered','executed','passed','failed','errors','skipped','expected_failures','unexpected_successes')
        counts_valid=all(type(report.get(k)) is int and report[k]>=0 for k in count_keys)
        no_nonpass=counts_valid and all(report[k]==0 for k in count_keys[3:])
        source = report.get('source_files')
        source_valid = (type(source) is dict and bool(source)
                        and all(type(name) is str and name and ':' not in name and '\x00' not in name
                                and not PurePosixPath(name.replace('\\', '/')).is_absolute()
                                and PurePosixPath(name.replace('\\', '/')).parts
                                and '..' not in PurePosixPath(name.replace('\\', '/')).parts
                                and type(digest) is str and len(digest) == 64
                                and all(c in '0123456789abcdef' for c in digest)
                                for name, digest in source.items()))
        source_valid = (source_valid
                        and report.get('source_sha256') == hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()
                        and (expected_source is None or source == expected_source))
        valid = (fresh and report.get("status") == "PASS" and report.get("source_unchanged_during_run") is True
                 and no_nonpass and source_valid
                 and report.get("executed", 0) > 0 and report.get("passed") == report.get("executed")
                 and report.get("discovered") == report.get("executed")
                 and set(classes) == {actual_class} and type(classes[actual_class]) is int and classes[actual_class] > 0)
        return 0 if process_code == 0 and valid else 1
    except (OSError, ValueError, TypeError):
        return 1

def main():
    # Windows legacy code pages cannot print emoji/Turkish output paths.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--engine", choices=["sqlite", "duckdb", "both"], default="both")
    ap.add_argument("--pattern", default="test_*.py")
    ap.add_argument("--output-dir", type=Path, default=ROOT / "test-results")
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--source-head", help=argparse.SUPPRESS)
    ap.add_argument("--run-id", help=argparse.SUPPRESS)
    ap.add_argument("--duckdb-threads", type=int, default=1,
                    help="Native fixture worker limit (default 1); 0 uses DuckDB defaults")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.child:
        if args.engine == "both":
            ap.error("child requires one engine")
        return child(args.engine, args.pattern, args.output_dir / f"{args.engine}.json", args.source_head, args.run_id, args.duckdb_threads)
    # Freeze the whole plugin subtree (including sibling policies/vendor) once.
    # Concurrent development cannot alter a running test's compatibility hashes.
    source_root = ROOT.parents[4]
    frozen = Path(tempfile.mkdtemp(prefix="source-", dir=args.output_dir.resolve())) / source_root.name
    shutil.copytree(source_root, frozen, ignore=shutil.ignore_patterns("__pycache__", "test-results", ".git"))
    frozen_source = source_fingerprint(frozen / SOURCE_ROOT.relative_to(source_root))
    if not frozen_source:
        raise RuntimeError("Empty frozen plugin source fingerprint; test run refused")
    frozen_runner = frozen / Path(__file__).resolve().relative_to(source_root)
    head_result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    source_head = head_result.stdout.strip() if head_result.returncode == 0 else "UNKNOWN"
    engines = ["sqlite", "duckdb"] if args.engine == "both" else [args.engine]
    codes = []
    for engine in engines:
        run_id = uuid.uuid4().hex
        cmd = [sys.executable, str(frozen_runner), "--child", "--engine", engine,
               "--pattern", args.pattern, "--output-dir", str(args.output_dir.resolve()),
               "--source-head", source_head, "--run-id", run_id,
               "--duckdb-threads", str(args.duckdb_threads)]
        with (args.output_dir / f"{engine}.log").open("w", encoding="utf-8") as log:
            try:
                proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                      timeout=args.timeout,
                                      env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
                code = proc.returncode
            except subprocess.TimeoutExpired:
                (args.output_dir / f"{engine}.json").write_text(json.dumps({
                    "requested_engine":engine,"status":"NOT_RUN_TIMEOUT",
                    "complete_run":False,"timeout_seconds":args.timeout}),encoding="utf-8")
                code = 1
        report_path = args.output_dir / f"{engine}.json"
        validated_code = validate_child_report(report_path, engine, run_id, code, expected_source=frozen_source)
        if validated_code and code == 0:
            report_path.write_text(json.dumps({"requested_engine": engine, "run_id": run_id,
                "status": "NOT_RUN_INVALID_CHILD_REPORT", "complete_run": False,
                "reason": "Process exit zero without a fresh complete PASS report"}), encoding="utf-8")
        code = validated_code
        codes.append(code)
        print(f"{engine}: exit={code}; evidence={args.output_dir / (engine + '.json')}")
    return 0 if all(code == 0 for code in codes) else 1

if __name__ == "__main__":
    raise SystemExit(main())
