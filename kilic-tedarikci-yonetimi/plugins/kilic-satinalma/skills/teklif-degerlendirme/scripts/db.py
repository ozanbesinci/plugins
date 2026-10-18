from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from common import SCHEMA_VERSION, json_text, stable_id, utc_now


def db_path(run_root: Path) -> Path:
    return run_root / "analysis.duckdb"


def _sqlite_test_mode() -> bool:
    return os.environ.get("TEKLIF_TEST_SQLITE", "").strip() == "1"


def connect(run_root: Path):
    run_root.mkdir(parents=True, exist_ok=True)
    if _sqlite_test_mode():
        con = sqlite3.connect(str(run_root / "analysis.test.sqlite"))
        return con
    try:
        import duckdb  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "DuckDB Python package is required for production v5 runs. "
            "Install it through the managed environment; the skill never installs dependencies automatically."
        ) from exc
    return duckdb.connect(str(db_path(run_root)))


def execute_script(con, sql: str) -> None:
    if isinstance(con, sqlite3.Connection):
        con.executescript(sql)
    else:
        con.execute(sql)


def rows_as_dict(con, sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    cur = con.execute(sql, list(params or []))
    rows = cur.fetchall()
    desc = cur.description or []
    cols = [x[0] for x in desc]
    return [dict(zip(cols, row)) for row in rows]


def one_as_dict(con, sql: str, params: Iterable[Any] | None = None) -> dict[str, Any] | None:
    cur = con.execute(sql, list(params or []))
    row = cur.fetchone()
    if row is None:
        return None
    cols = [x[0] for x in (cur.description or [])]
    return dict(zip(cols, row))


def scalar(con, sql: str, params: Iterable[Any] | None = None, default: Any = None) -> Any:
    cur = con.execute(sql, list(params or []))
    row = cur.fetchone()
    return default if row is None else row[0]


def init_db(run_root: Path, skill_root: Path | None = None) -> Path:
    skill_root = skill_root or Path(__file__).resolve().parents[1]
    schema_path = skill_root / "config" / "schema.sql"
    con = connect(run_root)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} if isinstance(con, sqlite3.Connection) else {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        if "run_meta" in tables:
            old = con.execute("SELECT value FROM run_meta WHERE key='schema_version'").fetchone()
            if old and old[0] not in {"5.0.3", "5.0.4", "5.0.5", SCHEMA_VERSION}:
                raise RuntimeError(f"Unsupported database schema {old[0]}; database was not migrated")
        execute_script(con, schema_path.read_text(encoding="utf-8"))
        # Forward-compatible local migration for runs created by v5.0.3.
        # Fresh databases already contain this column; existing databases must
        # gain it before claim-registry writes can be recorded atomically.
        for table, column in [("claims", "assertions_json"), ("scope_items", "cost_role"),
                              ("model_receipts", "telemetry_status"), ("model_receipts", "telemetry_reason")]:
            columns = {r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
            if column not in columns:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR")
            if column not in {r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()}:
                raise RuntimeError(f"Migration did not create {table}.{column}")
        meta = {
            "schema_version": SCHEMA_VERSION,
            "created_at": utc_now(),
            "db_engine": "sqlite-test" if isinstance(con, sqlite3.Connection) else "duckdb",
        }
        for key, value in meta.items():
            con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES (?,?)", [key, str(value)])
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    return run_root / ("analysis.test.sqlite" if _sqlite_test_mode() else "analysis.duckdb")


def set_meta(run_root: Path, key: str, value: Any) -> None:
    con = connect(run_root)
    try:
        if not isinstance(value, str):
            value = json_text(value)
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES (?,?)", [key, value])
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()


def get_meta(run_root: Path, key: str, default: Any = None, parse_json: bool = False) -> Any:
    con = connect(run_root)
    try:
        row = con.execute("SELECT value FROM run_meta WHERE key=?", [key]).fetchone()
        if not row:
            return default
        value = row[0]
        if parse_json:
            try:
                return json.loads(value)
            except Exception:
                return default
        return value
    finally:
        con.close()


def add_event(run_root: Path, event_type: str, phase: str | None = None, payload: dict[str, Any] | None = None) -> str:
    event_id = stable_id("evt", utc_now(), event_type, json_text(payload or {}), length=24)
    con = connect(run_root)
    try:
        con.execute(
            "INSERT INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)",
            [event_id, phase, event_type, json_text(payload or {}), utc_now()],
        )
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    return event_id


def set_state(run_root: Path, phase: str, status: str, detail: dict[str, Any] | None = None) -> None:
    con = connect(run_root)
    try:
        existing = con.execute("SELECT started_at FROM workflow_state WHERE phase=?", [phase]).fetchone()
        started = existing[0] if existing else utc_now()
        completed = utc_now() if status in {"PASS", "PARTIAL", "BLOCKED", "SKIPPED"} else None
        con.execute(
            "INSERT OR REPLACE INTO workflow_state(phase,status,started_at,completed_at,detail_json) VALUES (?,?,?,?,?)",
            [phase, status, started, completed, json_text(detail or {})],
        )
        if hasattr(con, "commit"):
            con.commit()
    finally:
        con.close()
    add_event(run_root, "state_change", phase, {"status": status, "detail": detail or {}})


def get_state(run_root: Path) -> list[dict[str, Any]]:
    con = connect(run_root)
    try:
        return rows_as_dict(
            con,
            "SELECT phase,status,started_at,completed_at,detail_json FROM workflow_state ORDER BY started_at",
        )
    finally:
        con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Run state store")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("--run", required=True)
    p = sub.add_parser("state")
    p.add_argument("--run", required=True)
    p = sub.add_parser("meta")
    p.add_argument("--run", required=True)
    p.add_argument("--key", required=True)
    args = ap.parse_args()
    run = Path(args.run)
    if args.cmd == "init":
        print(init_db(run))
    elif args.cmd == "state":
        print(json.dumps(get_state(run), ensure_ascii=False, indent=2, default=str))
    else:
        print(get_meta(run, args.key, ""))


if __name__ == "__main__":
    main()
