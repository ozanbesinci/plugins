"""Attach a safe paired report to business/technical waiting results, without approval."""
from functools import wraps
from pathlib import Path
import sqlite3
from report_delivery import export_preliminary

TERMINALS={"NEEDS_USER_INPUT","BLOCKED","BLOCKED_ENVIRONMENT","MANUAL_REVIEW_REQUIRED",
           "BUDGET_EXHAUSTED","PRELIMINARY"}

def terminal_reports(run_arg=0):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            run_root=Path(kwargs.get("run_root") or args[run_arg])
            physical_errors = (OSError, sqlite3.DatabaseError)
            try:
                import duckdb
                physical_errors += (duckdb.IOException,)
            except ImportError:
                pass
            try:
                result=fn(*args,**kwargs)
            except physical_errors as exc:
                # A physical failure remains BLOCKED; a safety pair is a separate delivery.
                result={"status":"BLOCKED", "reason":"Fiziksel çalışma arızası: " + str(exc),
                        "physical_error_type":type(exc).__name__}
            if not isinstance(result,dict) or result.get("status") not in TERMINALS: return result
            if result.get("preliminary_report"): return result
            reason=result.get("reason") or (
                "Kritik iş bilgisi teyit bekliyor; kesin karar ve etkilenen hesaplar bekletildi."
                if result.get("status")=="NEEDS_USER_INPUT" else
                "Analiz veya kaynak kontrolleri tamamlanamadı: "+str(result.get("status")))
            try:
                report=export_preliminary(run_root,str(reason))
            except Exception as exc:
                report={"delivery_status":"FAILED","deliverable_artifacts":False,"error":str(exc)}
            return {**result,"preliminary_report":report,
                    "deliverable_artifacts":report.get("deliverable_artifacts",False),
                    "report_delivery_status":report["delivery_status"],
                    "decision_assurance":report.get("decision_assurance","NO_DECISION")}
        return wrapped
    return decorate
