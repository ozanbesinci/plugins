"""Calculated item subtotal is separate from an offer's stated grand total."""
from decimal import Decimal, InvalidOperation


def calculate(items: list[dict]) -> dict:
    total=Decimal(0); currencies=set(); reasons=[]
    identities=[item.get('item_id') for item in items]
    if len(identities)!=len(set(identities)):
        reasons.append('duplicate_item_identity')
    # Different bases can be two views of the same commercial line. Without
    # an explicit reconciliation, a subtotal must not add those views twice.
    bases={item.get('amount_basis') for item in items if item.get('amount') is not None}
    if len(bases)>1:
        reasons.append('mixed_price_bases_require_reconciliation')
    for item in items:
        basis=item.get('amount_basis')
        try:
            amount=Decimal(str(item['amount']))
            if not amount.is_finite() or amount<0:raise ValueError('invalid amount')
            if basis=='unit_price':
                quantity=Decimal(str(item['quantity']))
                if not quantity.is_finite() or quantity<0:raise ValueError('invalid quantity')
                amount*=quantity
            elif basis!='line_total':
                raise ValueError('not an additive line amount')
            if not item.get('currency') or item.get('evidence_status')!='verified':
                raise ValueError('unconfirmed amount or currency')
            currencies.add(item['currency']);total+=amount
        except (KeyError,ValueError,TypeError,InvalidOperation):
            reasons.append(str(item.get('item_id') or 'unknown item'))
    complete=bool(items) and not reasons and len(currencies)==1
    return {'status':'calculated' if complete else 'incomplete','amount':str(total) if complete else None,
            'currency':next(iter(currencies)) if complete else None,'unresolved_items':reasons,
            'basis':'calculated_item_subtotal','is_stated_grand_total':False}
