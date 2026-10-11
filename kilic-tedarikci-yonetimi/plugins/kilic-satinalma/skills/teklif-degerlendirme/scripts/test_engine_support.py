"""Runner-owned fixture selection, independent of mutable environment."""
EXPECTED_ENGINE = None

def sqlite_modes():
    return (EXPECTED_ENGINE == "sqlite",) if EXPECTED_ENGINE else (False, True)


def artifact_path(run_root, kind="xlsx"):
    """Resolve the registered artifact so mutation tests target the delivered file."""
    from db import connect
    from active_records import current_artifacts
    con = connect(run_root)
    try:
        artifact = current_artifacts(con).get(kind)
        if artifact:
            return run_root / artifact["relative_path"]
    finally:
        con.close()
    return run_root / "output" / ("Teklif_Degerlendirme." + kind)


class ReportFixtureConnection:
    """Presentation-only fixture; real transaction behavior has separate tests."""
    def __init__(self, snapshot_sha):
        self.snapshot_sha = snapshot_sha
    def execute(self, sql, params=()):
        import json
        from types import SimpleNamespace
        if sql == "BEGIN TRANSACTION": return
        if sql == "SELECT value FROM run_meta WHERE key='reviewed_snapshot'":
            return SimpleNamespace(fetchone=lambda: [json.dumps({"sha256": self.snapshot_sha})])
        if sql.startswith("INSERT OR REPLACE INTO run_meta"):
            if sql.endswith("VALUES ('official_report_delivery',?)") or params[0].startswith("formula_contract_"):
                return
        raise AssertionError("Unexpected SQL in presentation-only fixture: " + sql)
    def commit(self): pass
    def rollback(self): pass
    def close(self): pass
