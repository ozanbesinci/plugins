"""Release evidence and disjoint test execution, outside the shipped product.

Uses the product's existing manifest, discovery and digest rules. No installation,
host restart, company-source access, automatic approval or change to runtime gates.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4

sys.dont_write_bytecode = True

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = PROJECT / "plugins/kilic-sozlesme-yonetimi"


def owning_checkout(start=PROJECT):
    """Nearest Git checkout (worktree .git file or directory) that owns the project."""
    start = Path(start).resolve()
    return next((path for path in (start, *start.parents) if (path / ".git").exists()), start)


def outside_repository(path, checkout=None):
    """Private receipts and observations never land inside a committable tree."""
    folder = Path(path).resolve()
    for root in {PACKAGE.resolve(), PROJECT.resolve(), Path(checkout or owning_checkout()).resolve()}:
        if folder == root or folder.is_relative_to(root):
            raise ValueError("Evidence must remain outside the product and its Git repository: " + str(folder))
    return folder


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_evidence(path, expected_hash=None):
    """Hash and decode the same read, including while another process writes."""
    path = Path(path).resolve()
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if expected_hash is not None and actual != expected_hash:
        raise ValueError("Evidence hash mismatch: " + str(path))
    return json.loads(data.decode("utf-8-sig")), {"path": str(path), "sha256": actual}


def changed_evidence(refs):
    changed = []
    for ref in refs:
        try:
            matches = sha(ref["path"]) == ref["sha256"]
        except OSError:
            matches = False
        if not matches:
            changed.append("EVIDENCE_CHANGED_OR_MISSING:" + ref["path"])
    return changed


def product_runner(package):
    spec = importlib.util.spec_from_file_location("contract_product_runner", package / "scripts/run_product_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(package, manifest):
    """Real unittest discovery includes dynamically generated K00..K29 tests."""
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(package / "tests"), str(package / "src")]
    found = {}
    for name in manifest["classes"]:
        mod, cls = name.rsplit(".", 1)
        module = importlib.import_module(mod)
        if Path(module.__file__).resolve().parent != (package / "tests").resolve():
            raise ValueError("Test module belongs to another package: " + mod)
        for test in unittest.defaultTestLoader.loadTestsFromTestCase(getattr(module, cls)):
            if test.id() in found:
                raise ValueError("Duplicate test in manifest: " + test.id())
            found[test.id()] = name
    if set(manifest["excluded"]) - found.keys():
        raise ValueError("Manifest exclusions are absent from discovery")
    core = importlib.import_module("sozlesme_cekirdek")
    if Path(core.__file__).resolve() != (package / "src/sozlesme_cekirdek/__init__.py").resolve():
        raise ValueError("Core discovery loaded another package")
    return found


def partition(found, excluded, count):
    if not 1 <= count <= 16:
        raise ValueError("Shard count must be 1..16")
    classes = {}
    for name, cls in found.items():
        if name not in excluded:
            classes.setdefault(cls, []).append(name)
    groups = [[] for _ in range(min(count, len(classes))) ]
    for cls, names in sorted(classes.items(), key=lambda item: (-len(item[1]), item[0])):
        target = min(range(len(groups)), key=lambda i: (len(groups[i]), i))
        groups[target].extend(sorted(names))
    return groups


def verify_receipts(receipts, current, manifest, found, digest):
    """Require exact current bytes and every effective test exactly once."""
    expected = set(found) - set(manifest["excluded"])
    seen = set()
    issues = []
    first_environment = None
    for number, receipt in enumerate(receipts):
        prefix = f"receipt[{number}]"
        classes = receipt.get("classes")
        selection = receipt.get("test_selection")
        suite = receipt.get("suite")
        suite_classes = manifest["classes"] if suite == "full" else manifest.get("suites", {}).get(suite)
        valid_classes = (isinstance(classes, list) and all(isinstance(c, str) for c in classes)
                         and suite_classes is not None and classes == suite_classes)
        available = {name for name, cls in found.items() if valid_classes and cls in classes}
        valid_selection = (isinstance(selection, list) and all(isinstance(n, str) for n in selection)
                           and len(selection) == len(set(selection)) and set(selection) <= available)
        selected = set(selection or []) if valid_selection else set()
        expected_local = selected if selected else available
        environment = {key: receipt.get(key) for key in ("platform", "python", "python_abi", "dependencies")}
        valid_environment = (all(isinstance(environment[key], str) and environment[key] for key in ("platform", "python", "python_abi"))
                             and environment["platform"].startswith("Windows")
                             and isinstance(environment["dependencies"], dict) and bool(environment["dependencies"])
                             and all(isinstance(k, str) and isinstance(v, str) and v for k, v in environment["dependencies"].items()))
        if first_environment is None:
            first_environment = environment
        checks = {
            "schema": receipt.get("schema") == "contract-product-test-receipt/v1",
            "final_pass": receipt.get("receipt_phase") == "FINAL" and receipt.get("status") == "PASS",
            "exit": type(receipt.get("exit_code")) is int and receipt["exit_code"] == 0,
            "no_failures": all(type(receipt.get(key)) is int and receipt[key] == 0 for key in ("failures", "errors", "skipped")),
            "source": receipt.get("source_before") == current == receipt.get("source_after"),
            "unchanged": receipt.get("source_unchanged") is True and receipt.get("original_source_unchanged") is True,
            "digest": receipt.get("source_digest") == digest(current),
            "manifest": receipt.get("manifest_digest") == digest(manifest),
            "classes": valid_classes and receipt.get("classes_not_run") == {},
            "selection": valid_selection,
            "unselected": receipt.get("unselected_not_run") == (sorted(available - selected) if selected else []),
            "environment": valid_environment and environment == first_environment,
        }
        issues.extend(prefix + ":" + key for key, ok in checks.items() if not ok)
        records = receipt.get("records", [])
        local = set()
        passed = 0
        for record in records:
            name = record.get("test_id")
            if name in local or name in seen:
                issues.append(prefix + ":duplicate:" + str(name))
            local.add(name)
            if name in manifest["excluded"]:
                if record.get("status") != "NOT_RUN":
                    issues.append(prefix + ":exclusion_promoted:" + name)
                continue
            if name not in expected or record.get("status") != "PASS":
                issues.append(prefix + ":invalid_test:" + str(name))
            else:
                passed += 1
        if local != expected_local:
            issues.append(prefix + ":selection_coverage")
        if type(receipt.get("methods_run")) is not int or receipt["methods_run"] != passed:
            issues.append(prefix + ":method_count")
        seen.update(local)
    missing = sorted(expected - seen)
    if not receipts:
        issues.append("NO_RECEIPTS")
    if missing:
        issues.append("MISSING_TESTS")
    return {"status": "PASS" if not issues else "BLOCKED", "issues": issues,
            "effective_test_count": len(expected), "covered_test_count": len(expected & seen),
            "missing_tests": missing, "excluded_tests": manifest["excluded"],
            "new_product_test_run": False, "release_acceptance": "NOT_GRANTED"}


def pointer(document, path):
    if path == "":
        return document
    if not path.startswith("/"):
        raise ValueError("JSON pointer must start with /")
    value = document
    for part in path[1:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def observation(row, base, source_digest):
    """Check supplied observations, never authenticate a human or host identity."""
    result = {key: row[key] for key in ("id", "title", "scope")}
    result["status"] = "RECORDED"
    result["evidence"] = []
    errors = []
    source_bound = False
    if row.get("source_digest") != source_digest:
        result["status"] = "STALE_SOURCE"
    if not row.get("artifacts"):
        errors.append("NO_ARTIFACTS")
    for item in row.get("artifacts", []):
        path = (base / item["path"]).resolve()
        try:
            data = path.read_bytes()
            actual = hashlib.sha256(data).hexdigest()
            if actual != item["sha256"]:
                errors.append("HASH_MISMATCH:" + item["path"])
            else:
                if item.get("checks"):
                    document = json.loads(data.decode("utf-8-sig"))
                    for check in item["checks"]:
                        actual_value = pointer(document, check["pointer"])
                        if type(actual_value) is not type(check["equals"]) or actual_value != check["equals"]:
                            errors.append("VALUE_MISMATCH:" + item["path"] + check["pointer"])
                        elif (check["pointer"] in {"/source_digest", "/product_source_digest", "/candidate_source_digest"}
                              and actual_value == row.get("source_digest")):
                            source_bound = True
            result["evidence"].append({"path": str(path), "sha256": actual})
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            errors.append("UNREADABLE_EVIDENCE:" + item["path"])
    if not source_bound:
        errors.append("SOURCE_DIGEST_NOT_BOUND_TO_ARTIFACT")
    if errors:
        result["status"] = "INVALID_EVIDENCE"
    result["issues"] = errors
    result["attestation"] = "LOCAL_RECORDED_OBSERVATION_NOT_INDEPENDENT_ACCEPTANCE"
    return result


def overall_status(report):
    return "PASS" if (report["technical"]["status"] == "PASS" and not report.get("evidence_issues")
                      and all(row["status"] == "RECORDED" for row in report.get("observations", []))) else "BLOCKED"


def save(output_root, report):
    report["status"] = overall_status(report)
    folder = outside_repository(output_root) / ("release-" + uuid4().hex[:10])
    folder.mkdir(parents=True)
    (folder / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    date = datetime.now(timezone.utc).date().isoformat()
    lines = ["---", "title: Sözleşme sürüm durumu", "created: " + date, "modified: " + date,
             "type: development", "status: 🟡 kabul işleri açık", "tags: [is, sozlesme, kabul]",
             "visibility: private", "tazele: " + date, "---", "",
             "Ürün kaynak kimliği: `" + report["source_digest"] + "`.", "",
             f"Kanıt bütünlüğü: **{report['status']}**.", "",
             f"Teknik kapsam: **{report['technical']['status']}**, {report['technical']['covered_test_count']}/{report['technical']['effective_test_count']}.",
             "Kararlı yayın kabulü: **NOT_GRANTED**. Yerel kayıt doğrulaması insan/kurum yetkisi oluşturmaz.", ""]
    for issue in report.get("evidence_issues", []) + report["technical"]["issues"]:
        lines.append("- Engel: " + issue)
    for row in report.get("observations", []):
        lines.append(f"- {row['title']}: **{row['status']}** — {row['scope']}")
    lines += ["", "Sonraki işler (birbirinden bağımsız hatlar birlikte ilerleyebilir):", ""]
    for row in report.get("remaining_work", []):
        lines.append(f"- **{row['lane']} / {row['id']}**: {row['next_action']} Bitiş kanıtı: {row['done_when']}")
    (folder / "DURUM.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(folder / "result.json"), "status": report["status"],
                      "stable_release": False}, ensure_ascii=False))
    return folder


def group_command(package, names, destination, number, timeout_seconds, complete_selection=None):
    if not names or len(names) != len(set(names)):
        raise ValueError("Empty or duplicate selection")
    command = [sys.executable, "-B", "-X", "utf8", str(package / "scripts/run_product_tests.py"),
               "--output-root", str(destination), "--suite", "full", "--label", f"shard-{number}",
               "--timeout-seconds", str(timeout_seconds)]
    # A single complete group uses the product runner's native full discovery.
    # Expanding 514 test names exceeds Windows CreateProcess's command limit.
    if complete_selection is None or set(names) != set(complete_selection):
        for name in names:
            command.extend(["--test", name])
    if len(subprocess.list2cmdline(command).encode("utf-16-le")) // 2 + 1 > 32767:
        raise ValueError("Windows command limit exceeded; use more shards or a shorter output path")
    return command


def run_groups(package, groups, output_root, workers, timeout_seconds, source_digest, complete_selection=None):
    """Keep each existing product runner/receipt intact; only schedule processes."""
    if not 1 <= workers <= 4:
        raise ValueError("Worker count must be 1..4")
    run_root = outside_repository(output_root) / ("tests-" + uuid4().hex[:10])
    if run_root.is_relative_to(package.resolve()):
        raise ValueError("Test output must be outside the product")
    run_root.mkdir(parents=True)
    (run_root / "plan.json").write_text(json.dumps({"groups": groups, "source_digest": source_digest}, indent=2), encoding="utf-8")

    def run(item):
        number, names = item
        destination = run_root / str(number)
        command = group_command(package, names, destination, number, timeout_seconds, complete_selection)
        process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1"),
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (run_root / f"shard-{number}.log").write_text(process.stdout + process.stderr, encoding="utf-8")
        paths = list(destination.glob("*/result.json"))
        if len(paths) != 1 or process.returncode != 0:
            raise RuntimeError(f"Shard {number} failed; evidence preserved at {run_root}")
        return paths[0]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(run, enumerate(groups)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status", help="Verify recorded evidence; never run tests")
    status.add_argument("--evidence", type=Path, required=True)
    status.add_argument("--output-root", type=Path, required=True)
    tests = sub.add_parser("test", help="Run disjoint groups, then verify complete coverage")
    tests.add_argument("--output-root", type=Path, required=True)
    tests.add_argument("--shards", type=int, default=4)
    tests.add_argument("--workers", type=int, default=2)
    tests.add_argument("--timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    runner = product_runner(PACKAGE)
    current = runner.snapshot(PACKAGE)
    manifest = read(PACKAGE / "tests/manifest.json")
    found = inventory(PACKAGE, manifest)
    observations = []
    receipt_paths = []
    receipts = []
    evidence_refs = []
    index_ref = None
    if args.command == "status":
        index, index_ref = read_evidence(args.evidence)
        evidence_refs.append(index_ref)
        if index.get("schema") != "contract-release-evidence/v1":
            raise ValueError("Unknown evidence index")
        base = args.evidence.resolve().parent
        for entry in index["technical_receipts"]:
            path = (base / entry["path"]).resolve()
            receipt, ref = read_evidence(path, entry["sha256"])
            receipts.append(receipt)
            evidence_refs.append(ref)
        observations = [observation(row, base, runner.digest(current)) for row in index["observations"]]
    else:
        groups = partition(found, manifest["excluded"], args.shards)
        receipt_paths = run_groups(PACKAGE, groups, args.output_root, args.workers,
                                   args.timeout_seconds, runner.digest(current), set(found) - set(manifest["excluded"]))
        for path in receipt_paths:
            receipt, ref = read_evidence(path)
            receipts.append(receipt)
            evidence_refs.append(ref)
    technical = verify_receipts(receipts, current, manifest, found, runner.digest)
    if runner.snapshot(PACKAGE) != current:
        technical["status"] = "BLOCKED"
        technical["issues"].append("SOURCE_CHANGED_DURING_CHECK")
    technical["new_product_test_run"] = args.command == "test"
    report = {"schema": "contract-release-status/v1", "generated_at": datetime.now(timezone.utc).isoformat(),
              "source_digest": runner.digest(current), "product_files": len(current), "technical": technical,
              "technical_receipts": [ref for ref in evidence_refs if ref is not index_ref],
              "evidence_index": index_ref,
              "evidence_issues": changed_evidence(evidence_refs + [ref for row in observations for ref in row["evidence"]]),
              "observations": observations, "remaining_work": read(PROJECT / "release/remaining-work.json"),
              "scope_reduced": False, "stable_release": False, "release_acceptance": "NOT_GRANTED",
              "release_tool_can_change_runtime_gates": False}
    save(args.output_root, report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError) as exc:
        # Malformed evidence indexes are reported as BLOCKED, never as a traceback.
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
