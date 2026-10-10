"""Show applied buyer terms from the frozen reviewed calculation, not source guesses."""
from display_values import label

def buyer_term(cost, field):
    if cost.get('complete') is not True or cost.get('known') is not True:
        return None
    kind={'payment':'payment_terms','validity':'validity_date'}.get(field)
    if not kind:return None
    basis='payment_basis' if field=='payment' else 'validity_date_basis'
    if cost.get(basis)!='buyer_declaration':return None
    applied=cost.get(kind)
    items=(cost.get('buyer_inputs') or {}).get(kind) or []
    if field=='payment':
        steps=(applied or {}).get('milestones')
        if not steps or not any(x.get('milestones')==steps for x in items):return None
        return {'value':'; '.join(f"{label(x.get('trigger'))}: %{x.get('percent')}" for x in steps),
                'path':'payment_terms.milestones'}
    if not isinstance(applied,dict) or not any({'date_status':x.get('date_status'),'value':x.get('value')}==applied for x in items):return None
    if applied.get('date_status')=='known' and applied.get('value'):
        return {'value':applied['value'],'path':'validity_date.value'}
    if applied.get('date_status')=='unknown' and applied.get('value') is None:
        return {'value':'Bilinmiyor (kullanıcı yanıtı)','path':'validity_date.date_status'}
    return None

def weighted_score_display(scoring, value, visible):
    if not visible:return None
    if value is not None:return float(value)
    if scoring.get('status')=='cost_only':
        return 'Hesaplanmadı: yalnız maliyet puanı'
    return None
