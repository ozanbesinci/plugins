"""Read-only buyer authority projection before decision/cost gates complete."""
from decimal import Decimal
from buyer_inputs import inputs_for
from buyer_controls import currency_basis
from buyer_quantity import validated_rows, number
from common import json_text
from display_values import structured

KINDS={'currency','reference_quantity','scope_cost','payment_terms','warranty_terms','validity_date','quote_date'}

def project(con, model):
    import json
    meta=con.execute("SELECT value FROM run_meta WHERE key='financial_parameters'").fetchone()
    params=json.loads(meta[0]) if meta else {}
    declared=params.get('buyer_inputs',[]) if isinstance(params,dict) else []
    if not isinstance(declared,list):raise ValueError('Invalid buyer declaration list')
    active={o['offer_id']:o for o in model['offers'] if o.get('status')=='active'}
    if any(not isinstance(d,dict) or d.get('offer_id') not in active or d.get('kind') not in KINDS for d in declared):
        raise ValueError('Buyer declaration has no active offer/allowed kind')
    rows=[];totals=[]
    for oid in active:
        checked={kind:inputs_for(con,oid,kind) for kind in sorted(KINDS)}
        for kind,items in checked.items():
            for item in items:
                if kind in {'validity_date','quote_date'}:
                    value=item['value'] if item['date_status']=='known' else 'Bilinmiyor (kullanıcı yanıtı)'
                elif kind=='reference_quantity':value=item['quantity']
                elif kind=='currency':value=item['value']
                elif kind=='scope_cost':value=item['amount']
                elif kind=='payment_terms':value=structured(item['milestones'])
                else:value=structured({'duration_years':item['duration_years'],'scope':item['scope']})
                rows.append({'offer_id':oid,'kind':kind,'value':value,'unit':item.get('unit') or item.get('currency'),
                             'target':item.get('quantity_item_id') or item.get('scope_id'),
                             'answer_text':item.get('answer_text'),'issue_id':item['issue_id'],
                             'scope_sha256':item['scope_sha256'],'source_hashes':item['source_hashes'],
                             'assurance':'BUYER_DECLARATION_PENDING_REVIEW'})
        quantities=checked['reference_quantity']
        if not quantities:continue
        basis=currency_basis(con,oid);currency=basis['value'] if basis else None
        # Validate the row binding even when the monetary currency is unknown.
        lines=validated_rows(con,oid,quantities,currency or '')
        source=[f for f in model['facts'] if f.get('offer_id')==oid and f.get('field_key')=='total'
                and f.get('evidence_status')=='verified' and f.get('value_number') is not None]
        if len(source)>1:raise ValueError('Ambiguous source total for buyer quantity reference')
        if not source or not currency:continue
        total=number(source[0]['value_number'])
        delta=sum(((number(r['reference_quantity'])-number(r['original_quantity']))*number(r['unit_price']) for r in lines),Decimal(0))
        adjusted=total+delta
        if adjusted<0:raise ValueError('Negative quantity reference subtotal')
        totals.append({'offer_id':oid,'source_total':str(total),'quantity_adjusted_total':str(adjusted),
                       'currency':currency,'delta':str(delta),'rows':lines,'source_fact_id':source[0]['fact_id'],
                       'assurance':'BUYER_QUANTITY_REFERENCE_ONLY',
                       'limitation':'Yalnız kaynak satırları ve kullanıcı miktarıyla ara tutar; kapsam, vergi, ödeme ve tam TCO/sıralama değildir.'})
    return rows,totals
