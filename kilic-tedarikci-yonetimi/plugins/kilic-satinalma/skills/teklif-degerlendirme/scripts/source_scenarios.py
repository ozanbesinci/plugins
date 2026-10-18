"""Project verified source facts and explicitly recorded assumptions into scenarios."""
import json
import math

def decode(value,default=None):
    if isinstance(value,(dict,list)):return value
    try:return json.loads(value)
    except (TypeError,ValueError):return default

def numeric(value):
    if value is None or isinstance(value,bool):return None
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) and value>=0 else None

def from_sources(model):
    if model.get('content_status')=='SAFETY_NOTICE' or model.get('decision_assurance')=='BLOCKED_INTEGRITY':return []
    docs={d['document_id']:d for d in model.get('documents',[])}
    evidence={e['evidence_id']:e for e in model.get('evidence',[])}
    names={s['supplier_id']:s['display_name'] for s in model.get('suppliers',[])}
    params=decode(model.get('meta',{}).get('financial_parameters'),{}) or {}
    scenarios=[]
    for offer in model.get('offers',[]):
        oid=offer['offer_id']
        if offer.get('status')!='active':continue
        facts={}
        for fact in model.get('facts',[]):
            if fact.get('offer_id')!=oid or fact.get('evidence_status')!='verified':continue
            ev=evidence.get(fact.get('evidence_id'),{});doc=docs.get(ev.get('document_id'),{})
            if ev.get('evidence_status')!='verified' or not doc or not ev.get('source_sha256') or ev['source_sha256']!=doc.get('sha256'):continue
            if doc.get('offer_id')!=oid or doc.get('supplier_id')!=offer['supplier_id']:continue
            facts.setdefault(fact['field_key'],[]).append(fact)
        def one(key):
            values=facts.get(key,[])
            return values[0] if len(values)==1 else {}
        total=one('total');amount=numeric(total.get('value_number'))
        currency=one('currency').get('value_text')
        if amount is None:continue
        all_params=params.get('offer_parameters') or {}
        per_offer=(all_params.get(oid) or {}) if isinstance(all_params,dict) else {}
        vat=per_offer.get('vat',{}) if isinstance(per_offer.get('vat'),dict) else {}
        recorded=per_offer.get('excel_scenario')
        recorded=recorded if isinstance(recorded,dict) else {}
        recorded_financial=recorded.get('financial') or {}
        target_currency=((recorded_financial.get('policy') or {}).get('base_currency') or params.get('base_currency'))
        discounts=per_offer.get('discounts') or []
        inputs={'quantity':1,'unit_price':amount,'discount':0}
        # 1 is the algebraic multiplier of the quoted total, never a supplier quantity.
        pricing={'price_unit':1,'price_includes_vat':0 if vat.get('price_basis')=='net_ex_vat' else None,'discounts':discounts}
        for key,target in (('rate','vat_rate'),('deductible_share','vat_deductible')):
            if numeric(vat.get(key)) is not None:inputs[target]=numeric(vat[key])
        rates=params.get('discount_rates') or {}
        rate=rates.get(target_currency) if isinstance(rates,dict) and target_currency else None
        if isinstance(rate,dict):rate=rate.get('annual_effective_rate')
        if rate is None and target_currency and params.get('annual_discount_rate_currency')==target_currency:rate=params.get('annual_discount_rate')
        if numeric(rate) is not None:inputs['annual_rate']=numeric(rate)
        schedule=per_offer.get('payment_schedule')
        if schedule is None:schedule=(decode(one('payment').get('normalized_json'),{}) or {}).get('payment_schedule')
        if any(r.get('offer_id')==oid and r.get('kind')=='payment_terms' for r in model.get('buyer_declarations',[])):schedule=None
        financial={}
        if isinstance(schedule,list) and 0<len(schedule)<=12:
            payments=[]
            for event in schedule:
                if not isinstance(event,dict) or set(event)-{'ratio','amount','days'}:break
                share=numeric(event.get('ratio'));days=numeric(event.get('days'))
                if share is None or share>1 or days is None or int(days)!=days:break
                payments.append({'percent':share,'days':int(days)})
            if len(payments)==len(schedule) and abs(sum(p['percent'] for p in payments)-1)<1e-8:
                financial['payments']=payments
                if len(payments)==1:inputs['days']=payments[0]['days']
        # Only a recorded explicit scenario is copied. Market FX is never silently projected.
        if isinstance(recorded,dict):
            for key,value in (recorded.get('inputs') or {}).items():
                from scenario_formulas import INPUTS
                if key in INPUTS and numeric(value) is not None:inputs[key]=numeric(value)
            financial.update(recorded_financial)
        scenario={'id':f"{names.get(offer['supplier_id'],offer['supplier_id'])} / {oid}",'offer_id':oid,
                  'inputs':inputs,'pricing':pricing,'financial':financial,'source_fact_ids':[total['fact_id']],
                  'basis':'Doğrulanmış beyan toplamı. Miktar=1 teklif toplamı çarpanıdır, fiziksel miktar değildir. Ek iskonto=0 başlangıç senaryosudur; eksik vergi/kur/gider varsayımları boş bırakılır.'}
        scenarios.append(scenario)
        # Retain source line quantities/prices as additional, explicitly separate scenarios.
        for group in facts.values():
            for fact in group:
                normalized=decode(fact.get('normalized_json'),{}) or {}
                for item in normalized.get('items',[]):
                    if item.get('evidence_status',fact['evidence_status'])!='verified':continue
                    q=numeric(item.get('quantity'));p=numeric(item.get('unit_price'))
                    if p is None and item.get('amount_basis')=='unit_price':p=numeric(item.get('amount'))
                    if q is None or q<=0 or p is None:continue
                    iid=item.get('item_id')
                    if not iid:continue
                    ident=f"{scenario['id']} / {iid}"
                    if any(s['id']==ident for s in scenarios):continue
                    line={'quantity':q,'unit_price':p,'discount':0}
                    source_pricing=item.get('pricing') or {}
                    source_vat=source_pricing.get('vat') or {}
                    source_discounts=(source_pricing.get('discounts') or {}).get('percentages')
                    if numeric(source_vat.get('percent')) is not None:line['vat_rate']=numeric(source_vat['percent'])/100
                    scenarios.append({'id':ident,'offer_id':oid,'item_id':iid,'inputs':line,
                                      'pricing':{'price_unit':numeric((source_pricing.get('price_unit') or {}).get('value')) or 1,
                                                 'price_includes_vat':int(source_vat['basis']=='included') if source_vat.get('basis') in {'included','excluded'} else None,
                                                 'discounts':[numeric(p)/100 for p in source_discounts] if source_discounts and all(numeric(p) is not None for p in source_discounts) else []},
                                      'source_fact_ids':[fact['fact_id']],
                                      'basis':'Doğrulanmış kaynak kalemi; teklif toplamı senaryosundan ayrıdır, iki tutar toplanmaz. İskonto girdisi ek senaryo iskontosudur.'})
    return scenarios

