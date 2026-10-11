"""User-declared dated cost ledger; projected cash-date FX, never source facts."""
from decimal import Decimal as D
from scenario_finance import number,scenario_date
from procurement_math import present_value_days

MAX_FLOWS=48
CATEGORIES=('PURCHASE','FREIGHT','INSURANCE','DUTY','VAT_PAYMENT','VAT_REFUND',
            'ENERGY','MAINTENANCE','CONSUMABLES','RENEWAL','OTHER','RESIDUAL')
CATEGORY_LABELS={'PURCHASE':'Satınalma','FREIGHT':'Navlun','INSURANCE':'Sigorta','DUTY':'Gümrük',
 'VAT_PAYMENT':'KDV ödemesi','VAT_REFUND':'KDV geri kazanımı','ENERGY':'Enerji','MAINTENANCE':'Bakım',
 'CONSUMABLES':'Sarf','RENEWAL':'Yenileme','OTHER':'Diğer','RESIDUAL':'Kalıntı geri dönüşü'}
METHOD='USER_PROJECTED_CASH_DATE_TARGET_NPV'
SCOPE='DECLARED_COMPLETE_TCO'
FLOW_FIELDS={'cost_id','category','amount','currency','cash_date','rate_date','fx_rate','rate_source'}

def validate_ledger_input(kind,value):
    if value is None:return
    key=kind.removeprefix('ledger_')
    if key=='currency':currency_code(value)
    elif key=='date':scenario_date(value)
    elif key in ('amount','baseline','rate','fx','count'):
        n=number(value,key,whole=key=='count',upper=48 if key=='count' else 10 if key=='rate' else None)
        if key in ('fx','count') and n<=0:raise ValueError('Positive ledger FX/count required')
    elif key in ('id','text'):
        if not isinstance(value,str) or not value.strip() or len(value)>(100 if key=='id' else 200):raise ValueError('Invalid ledger identity/source label')
    elif key in ('category','scope','method'):
        allowed=CATEGORIES if key=='category' else (SCOPE,) if key=='scope' else (METHOD,)
        if not isinstance(value,str) or value not in allowed:raise ValueError('Invalid ledger '+key)
    else:raise ValueError('Unknown ledger input kind')

def currency_code(value):
    if value is None:return None
    if not isinstance(value,str) or len(value)!=3 or not value.isascii() or not value.isalpha() or value!=value.upper():
        raise ValueError('Cash-flow currency must use three uppercase letters')
    return value

def optional_date(value):return None if value is None else scenario_date(value)

def ledger_reference(ledger=None):
    ledger={} if ledger is None else ledger
    if not isinstance(ledger,dict) or set(ledger)-{'valuation_date','base_currency','annual_rate','baseline','scope','method','flows'}:
        raise ValueError('Unknown dated cash-flow ledger field')
    scope=ledger.get('scope');method=ledger.get('method')
    if scope is not None and scope!=SCOPE:raise ValueError('Explicit declared complete TCO scope required')
    if method is not None and method!=METHOD:raise ValueError('Projected cash-date target-currency NPV method required')
    origin=optional_date(ledger.get('valuation_date'));base=currency_code(ledger.get('base_currency'))
    rate=number(ledger.get('annual_rate'),'cashflows.annual_rate',upper=10)
    baseline=number(ledger.get('baseline'),'cashflows.baseline')
    flows=ledger.get('flows')
    if flows is None:flows=[]
    if not isinstance(flows,list) or len(flows)>MAX_FLOWS:raise ValueError('At most 48 dated cash flows')
    ids=set();categories=set();rows=[]
    for flow in flows:
        if not isinstance(flow,dict) or set(flow)-FLOW_FIELDS:raise ValueError('Unknown cash-flow field')
        identity=flow.get('cost_id');kind=flow.get('category')
        if identity is not None:
            if not isinstance(identity,str) or not identity.strip() or len(identity)>100:raise ValueError('Invalid cash-flow cost identity')
            if identity in ids:raise ValueError('Duplicate cost identity; no double counting')
            ids.add(identity)
        if kind is not None:
            if not isinstance(kind,str) or kind not in CATEGORIES:raise ValueError('Unknown cash-flow category')
            categories.add(kind)
        amount=number(flow.get('amount'),'cashflows.amount');currency=currency_code(flow.get('currency'))
        when=optional_date(flow.get('cash_date'));rate_date=optional_date(flow.get('rate_date'))
        fx=number(flow.get('fx_rate'),'cashflows.fx_rate')
        if fx is not None and fx<=0:raise ValueError('Positive cash-date FX required')
        label=flow.get('rate_source')
        if label is not None and (not isinstance(label,str) or not label.strip() or len(label)>200):raise ValueError('Invalid cash-flow rate source')
        if when is not None and rate_date is not None and when!=rate_date:raise ValueError('FX must be a declared cash-date projection; spot-date conversion forbidden')
        if base is not None and currency==base and fx is not None and fx!=1:raise ValueError('Same-currency cash flow requires rate one')
        days=None if when is None or origin is None else (when-origin).days
        if days is not None and not 0<=days<=36500:raise ValueError('Cash-flow date outside valuation horizon')
        known=all(value is not None for value in (identity,kind,amount,currency,when,rate_date,fx,label,days,base)) and method==METHOD
        sign=-1 if kind in ('VAT_REFUND','RESIDUAL') else 1
        nominal=None if not known else amount*fx*sign
        pv=None if nominal is None or rate is None else present_value_days(abs(nominal),days,rate)*sign
        rows.append({'cost_id':identity,'category':kind,'days':days,'nominal':None if nominal is None else float(nominal),'present_value':None if pv is None else float(pv)})
    complete=bool(flows) and scope==SCOPE and categories==set(CATEGORIES) and len(ids)==len(flows)
    nominal=None if not complete or any(r['nominal'] is None for r in rows) else sum(r['nominal'] for r in rows)
    pv=None if not complete or any(r['present_value'] is None for r in rows) else sum(r['present_value'] for r in rows)
    difference=None if pv is None or baseline is None else pv-float(baseline)
    return {'status':'USER_SCENARIO_CALCULATED' if pv is not None else 'INCOMPLETE','rows':rows,
            'known_subtotal':sum(r['nominal'] for r in rows if r['nominal'] is not None),
            'nominal':nominal,'present_value':pv,'difference':difference,
            'relative_difference':None if difference is None or baseline==0 else difference/float(baseline),
            'missing_categories':sorted(set(CATEGORIES)-categories),
            'basis':'USER_DECLARED_SCOPE_ONLY; independent ledger; automatic price/payment/annual totals are not added; projected cash-date FX then target-currency 365-day effective NPV'}
