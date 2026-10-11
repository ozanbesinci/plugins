"""Explicit scenario payment/TCO assumptions; never alter or verify source facts."""
from datetime import date
from decimal import Decimal as D
import math
import re
from procurement_math import present_value_days

FINANCIAL_FIELDS = {"payments", "vat_refund_days", "policy", "base_present_value", "cost_mode", "annual_costs"}
COST_MODES = {"CONSTANT_ANNUAL", "YEARLY_SCHEDULE"}
MAX_COST_YEARS = 100


def scenario_date(value):
    """Canonical Gregorian date in the shared Python/Excel supported range."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Scenario date must use YYYY-MM-DD")
    parsed = date.fromisoformat(value)
    if parsed.year < 1900:
        raise ValueError("Scenario date must be supported by Excel: 1900..9999")
    return parsed


def lifecycle_reference(values, financial):
    """Year-end base-currency user costs; missing years/categories are unknown."""
    mode = financial.get("cost_mode", "CONSTANT_ANNUAL")
    if mode is not None and (not isinstance(mode, str) or mode not in COST_MODES):
        raise ValueError("Unknown lifecycle cost mode")
    years = number(values.get("years"), "years", whole=True, upper=MAX_COST_YEARS)
    if years == 0:
        raise ValueError("Positive financial horizon required")
    rate = number(values.get("annual_rate"), "annual_rate", upper=10)
    schedule = financial.get("annual_costs")
    if schedule is None:
        schedule = []
    if not isinstance(schedule, list) or len(schedule) > MAX_COST_YEARS:
        raise ValueError("Annual costs must be a list of at most 100 years")
    result = {"mode": mode, "nominal": None, "present_value": None, "rows": [], "status": "INCOMPLETE"}
    if mode == "CONSTANT_ANNUAL":
        if schedule:
            raise ValueError("Yearly costs require YEARLY_SCHEDULE mode")
        energy = number(values.get("energy_annual"), "energy_annual")
        maintenance = number(values.get("maintenance_annual"), "maintenance_annual")
        result["coverage"] = "Constant energy/maintenance only; other lifecycle costs excluded"
        if years is not None and energy is not None and maintenance is not None:
            result["nominal"] = float((energy+maintenance)*years)
            if rate is not None:
                result.update(status="SCENARIO_CALCULATED", present_value=float(sum(
                    present_value_days(energy+maintenance, 365*y, rate) for y in range(1, int(years)+1))))
        return result
    result["coverage"] = "Explicit energy/maintenance/other for every year; base-currency year-end user costs"
    if mode is None:
        result["coverage"] = "Unknown lifecycle cost mode; no cost total"
    by_year = {}
    for item in schedule:
        if not isinstance(item, dict) or set(item)-{"year", "energy", "maintenance", "other"}:
            raise ValueError("Unknown annual cost field")
        year = number(item.get("year"), "annual_costs.year", whole=True, upper=MAX_COST_YEARS)
        if year is None or year == 0:
            raise ValueError("Annual cost year required")
        year = int(year)
        if year in by_year:
            raise ValueError("Duplicate annual cost year")
        if years is not None and year > years:
            raise ValueError("Annual cost outside declared horizon")
        costs = [number(item.get(key), "annual_costs."+key) for key in ("energy", "maintenance", "other")]
        nominal = None if any(value is None for value in costs) else sum(costs)
        pv = None if nominal is None or rate is None else present_value_days(nominal, 365*year, rate)
        by_year[year] = {"year": year, "nominal": None if nominal is None else float(nominal),
                         "present_value": None if pv is None else float(pv)}
    result["rows"] = [by_year[year] for year in sorted(by_year)]
    if mode is None or years is None or set(by_year) != set(range(1, int(years)+1)):
        return result
    if any(row["nominal"] is None for row in result["rows"]):
        return result
    result["nominal"] = sum(row["nominal"] for row in result["rows"])
    if rate is not None:
        result.update(status="SCENARIO_CALCULATED", present_value=sum(row["present_value"] for row in result["rows"]))
    return result

def number(value, key, *, whole=False, upper=None):
    if value is None: return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid financial scenario number: " + key)
    if whole and value != int(value): raise ValueError("Whole number required: " + key)
    if upper is not None and value > upper: raise ValueError("Financial scenario limit exceeded: " + key)
    return D(str(value))

def policy_valid(policy, fx_rate=None):
    if not policy: return False
    allowed = {"base_currency", "source_currency", "rate_date", "rate_source", "direction", "kind"}
    if set(policy) - allowed: raise ValueError("Unknown scenario currency policy field")
    if any(not isinstance(policy.get(k), str) or not policy[k].strip() for k in allowed): return False
    if policy["direction"] != "TARGET_PER_SOURCE" or policy["kind"] != "FIXED_SCENARIO":
        raise ValueError("Explicit target/source fixed-scenario rate policy required")
    for key in ("base_currency", "source_currency"):
        value = policy[key]
        if len(value) != 3 or not value.isascii() or not value.isalpha() or value != value.upper():
            raise ValueError("Three uppercase currency letters required: " + key)
    scenario_date(policy["rate_date"])
    if fx_rate is None: return False
    rate = number(fx_rate, "fx_rate")
    if rate <= 0: raise ValueError("Positive rate required")
    if policy["base_currency"] == policy["source_currency"] and rate != 1:
        raise ValueError("Same-currency scenario rate must be one")
    return True

def payment_reference(cash, rate, payments):
    cash = number(cash, "cash")
    rate = number(rate, "annual_rate", upper=10)
    if payments is None: payments = []
    if not isinstance(payments, list) or len(payments) > 12:
        raise ValueError("Payment schedule must contain at most twelve rows")
    rows = []
    for payment in payments:
        if not isinstance(payment, dict) or set(payment) - {"percent", "days"}:
            raise ValueError("Unknown payment schedule field")
        percent = number(payment.get("percent"), "payment.percent", upper=1)
        days = number(payment.get("days"), "payment.days", whole=True, upper=36500)
        rows.append((percent, days))
    result = {"nominal": None, "present_value": None, "status": "INCOMPLETE"}
    if cash is None or rate is None or not rows or any(p is None or d is None for p, d in rows): return result
    if abs(sum(p for p, _ in rows) - 1) > D("0.00000001"):
        raise ValueError("Payment percentages must sum to one")
    result.update(nominal=float(cash), present_value=float(sum(present_value_days(cash*p,int(days),rate) for p,days in rows)), status="SCENARIO_CALCULATED")
    return result

def finance_reference(values, financial=None, *, cash=None, cost=None):
    """Gross payments minus discounted recoverable VAT plus OPEX minus residual."""
    financial = {} if financial is None else financial
    if not isinstance(financial, dict) or set(financial) - FINANCIAL_FIELDS:
        raise ValueError("Unknown financial scenario field")
    if not financial:
        return {"status":"INCOMPLETE", **{key:None for key in ("payment_present_value","recoverable_vat_present_value","opex_present_value","residual_present_value","total_present_value","baseline_present_value","difference","relative_difference")}, "basis":"USER_SCENARIO_ONLY"}
    cash = number(cash, "cash"); cost = number(cost, "cost")
    rate = number(values.get("annual_rate"), "annual_rate", upper=10)
    years = number(values.get("years"), "years", whole=True, upper=100)
    if years is not None and years == 0: raise ValueError("Positive financial horizon required")
    energy = number(values.get("energy_annual"), "energy_annual")
    maintenance = number(values.get("maintenance_annual"), "maintenance_annual")
    residual = number(values.get("residual"), "residual")
    refund_days = number(financial.get("vat_refund_days"), "vat_refund_days", whole=True, upper=36500)
    baseline = number(financial.get("base_present_value"), "base_present_value")
    lifecycle = lifecycle_reference(values, financial)
    payment = payment_reference(None if cash is None else float(cash), None if rate is None else float(rate), financial.get("payments"))
    output = {"status": "INCOMPLETE", "payment_present_value": None, "recoverable_vat_present_value": None,
              "opex_present_value": None, "residual_present_value": None, "total_present_value": None,
              "baseline_present_value": None, "difference": None, "relative_difference": None,
              "lifecycle": lifecycle,
              "basis": "USER_SCENARIO_ONLY; "+lifecycle["coverage"]+"; 365-day effective rate; no supplier ranking"}
    if not policy_valid(financial.get("policy"), values.get("fx_rate")): return output
    if baseline is not None: output['baseline_present_value']=float(baseline)
    output["payment_present_value"] = payment["present_value"]
    if cash is not None and cost is not None:
        credit = cash-cost
        if credit < 0: raise ValueError("Recoverable VAT cannot be negative")
        if credit == 0: output["recoverable_vat_present_value"] = 0.0
        elif rate is not None and refund_days is not None:
            output["recoverable_vat_present_value"] = float(present_value_days(credit,int(refund_days),rate))
    if rate is not None and years is not None:
        output["opex_present_value"] = lifecycle["present_value"]
        if residual is not None:
            output["residual_present_value"] = float(present_value_days(residual,365*int(years),rate))
    fields = [output[k] for k in ("payment_present_value", "recoverable_vat_present_value", "opex_present_value", "residual_present_value")]
    if any(x is None for x in fields): return output
    output.update(status="SCENARIO_CALCULATED", total_present_value=fields[0]-fields[1]+fields[2]-fields[3])
    if baseline is not None:
        output.update(baseline_present_value=float(baseline), difference=output["total_present_value"]-float(baseline))
        if baseline != 0: output["relative_difference"] = output["difference"]/float(baseline)
    return output
