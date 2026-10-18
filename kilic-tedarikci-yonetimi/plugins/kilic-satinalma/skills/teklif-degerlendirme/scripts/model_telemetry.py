"""Task telemetry is an audit record, separate from business-result validation.

HOST_UNAVAILABLE is a reserved marker, never an actual model/effort identity.
Unreported token counts remain NULL; historical unexplained gaps fail closed.
"""
from __future__ import annotations

UNKNOWN = "HOST_UNAVAILABLE"


def receipt_values(*, model_name=None, reasoning_effort=None, response_id=None,
                   input_tokens=None, cached_input_tokens=None, output_tokens=None,
                   telemetry_status="measured", telemetry_reason=None):
    if telemetry_status not in {"measured", "host_unavailable"}:
        raise ValueError("Unknown telemetry status")
    reason = str(telemetry_reason or "").strip()
    if telemetry_status == "host_unavailable":
        if not reason:
            raise ValueError("Host-unavailable telemetry requires an explicit reason")
        if any(v is not None for v in (input_tokens, cached_input_tokens, output_tokens)):
            raise ValueError("Host-unavailable telemetry cannot contain measured or fabricated token counts")
        model_name = model_name or UNKNOWN
        reasoning_effort = reasoning_effort or UNKNOWN
    else:
        if not model_name or not reasoning_effort or UNKNOWN in {model_name, reasoning_effort}:
            raise ValueError("Successful model task recording requires actual model_name and reasoning_effort receipt metadata")
        if input_tokens is None or output_tokens is None:
            raise ValueError("Successful model task recording requires actual input_tokens and output_tokens")
        for value in (input_tokens, cached_input_tokens, output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Token receipt values must be non-negative integers")
        if cached_input_tokens is not None and cached_input_tokens > input_tokens:
            raise ValueError("Cached input tokens exceed input tokens")
    return dict(model_name=model_name, reasoning_effort=reasoning_effort, response_id=response_id,
                input_tokens=input_tokens, cached_input_tokens=cached_input_tokens, output_tokens=output_tokens,
                telemetry_status=telemetry_status, telemetry_reason=reason or None)


def inspect_receipts(con):
    from db import rows_as_dict
    invalid = []
    unavailable = []
    totals = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0)
    for row in rows_as_dict(con, "SELECT * FROM model_receipts"):
        try:
            # A missing status in a migrated historical receipt is measured,
            # so a NULL token count never acquires an invented explanation.
            values = receipt_values(**{k: row.get(k) for k in (
                "model_name", "reasoning_effort", "response_id", "input_tokens",
                "cached_input_tokens", "output_tokens", "telemetry_reason")},
                telemetry_status=row.get("telemetry_status") or "measured")
        except ValueError:
            invalid.append(row["receipt_id"])
            continue
        if values["telemetry_status"] == "host_unavailable":
            unavailable.append(dict(receipt_id=row["receipt_id"], task_id=row["task_id"],
                                    reason=values["telemetry_reason"]))
        else:
            for key in totals:
                totals[key] += values[key] or 0
    return dict(known_totals=totals, invalid_receipts=invalid, unavailable_receipts=unavailable)
