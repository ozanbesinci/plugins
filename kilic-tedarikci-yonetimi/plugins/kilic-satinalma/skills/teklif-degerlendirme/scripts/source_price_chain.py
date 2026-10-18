"""Evidence-bound source unit-price arithmetic; buyer cost/scenarios stay separate."""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from db import one_as_dict, rows_as_dict

CONTRACT = 'teklif-source-pricing/v1'


def _fold(value):
    value = str(value or '').replace('ı', 'i').replace('İ', 'I')
    return ''.join(c for c in unicodedata.normalize('NFKD', value).casefold()
                   if not unicodedata.combining(c))


def _label(value):
    return re.sub(r'[^a-z0-9]+', ' ', _fold(value)).strip()


def number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Source pricing requires finite numeric values')
    try:
        value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('Source pricing requires finite numeric values') from exc
    if not value.is_finite() or value < 0:
        raise ValueError('Source pricing requires non-negative finite values')
    return value


def _has_number(text, value, tokens, tolerance=Decimal('0.00000001')):
    return any(abs(token - number(value)) <= tolerance for token in tokens(str(text)))


def _context(con, ref, offer_id, supplier_id, check_ref):
    check_ref(ref)
    ev = one_as_dict(con, 'SELECT * FROM evidence WHERE evidence_id=?', [ref]) or {}
    doc = one_as_dict(con, 'SELECT * FROM documents WHERE document_id=?', [ev.get('document_id')]) or {}
    if (ev.get('evidence_status') != 'verified' or ev.get('extraction_path') == 'vision'
            or not doc.get('active') or ev.get('source_sha256') != doc.get('sha256')
            or doc.get('offer_id') != offer_id or doc.get('supplier_id') != supplier_id):
        raise ValueError('Source pricing needs current non-pixel evidence from the same offer/supplier')
    result = {'ref': ref, 'ev': ev, 'doc': doc, 'quote': str(ev.get('quote') or ''), 'cells': []}
    if doc.get('format_family') != 'csv':
        return result
    loc = json.loads(ev.get('locator_json') or '{}')
    row, first = loc.get('row'), loc.get('column'); last = loc.get('end_column', first)
    end_row = loc.get('end_row', row)
    if any(type(x) is not int or x < 1 for x in (row, first, last, end_row)) or row == 1 or end_row != row or last < first:
        raise ValueError('Source pricing CSV evidence must identify one data row and its columns')
    header = values = None; data_rows = set()
    units = rows_as_dict(con, "SELECT * FROM document_units WHERE document_id=? AND unit_type='csv_chunk' ORDER BY unit_index", [doc['document_id']])
    for unit in units:
        ul = json.loads(unit.get('locator_json') or '{}'); st = json.loads(unit.get('structured_json') or '{}')
        start = ul.get('start_row'); rows = st.get('rows', [])
        if type(start) is not int or not isinstance(rows, list):
            continue
        if start == 1 and rows and isinstance(rows[0], list):
            header = rows[0]
        for offset, cells in enumerate(rows):
            if start + offset > 1 and isinstance(cells, list) and any(str(v or '').strip() for v in cells):
                data_rows.add(start + offset)
        if start <= row < start + len(rows) and (not ev.get('unit_id') or ev['unit_id'] == unit['unit_id']):
            values = rows[row-start]
    if not isinstance(header, list) or not isinstance(values, list) or last > min(len(header), len(values)):
        raise ValueError('Source pricing CSV locator has no current row/header')
    result.update(row=row, headers=header, values=values, data_row_count=len(data_rows))
    result['cells'] = [{'column': c+1, 'label': _label(header[c]), 'value': values[c], 'context': result}
                       for c in range(first-1, last)]
    return result


_ROLES = {
    'quantity': {'miktar', 'quantity', 'qty'},
    'unit_price': {'birim fiyat', 'birim fiyati', 'unit price', 'unit cost'},
    'currency': {'para birimi', 'currency'},
    'vat_rate': {'kdv yuzde', 'kdv orani', 'vat percent', 'vat rate', 'vat percentage'},
    'vat_basis': {'fiyat kdv durumu', 'kdv durumu', 'kdv', 'vat basis', 'price vat basis', 'price includes vat'},
    'price_unit': {'fiyat birimi', 'price unit', 'price denominator'},
    'offer_net': {'net toplam kdv haric', 'net toplam', 'net total', 'offer net total'},
    'offer_vat': {'kdv tutari', 'vat amount', 'total vat'},
    'offer_gross': {'toplam kdv dahil', 'brut toplam', 'gross total', 'grand total'},
    'line_net': {'satir net', 'satir net tutari', 'kalem net', 'line net', 'line net total'},
    'line_vat': {'satir kdv', 'satir kdv tutari', 'line vat', 'line vat amount'},
    'line_gross': {'satir brut', 'satir toplam kdv dahil', 'line gross', 'line gross total'},
}


def _discount_order(label):
    m = re.fullmatch(r'(?:iskonto|discount)(?: (\d+))?(?: yuzde| percent| percentage| pct| orani)?', label)
    return int(m[1]) if m and m[1] else 0 if m else None


def _basis(value):
    from normalize import vat_basis
    return vat_basis(str(value))


def validate_item_pricing(con, item, offer_id, supplier_id, check_ref, numeric_tokens):
    """Called after shape validation, before any canonical fact/receipt commit."""
    pricing = item.get('pricing')
    if pricing is None:
        return
    if item.get('evidence_status') != 'verified':
        return
    owner = con.execute('SELECT supplier_id FROM offers WHERE offer_id=?', [offer_id]).fetchone()
    if not owner or (supplier_id and supplier_id != owner[0]):
        raise ValueError('Source pricing requires the canonical offer supplier')
    supplier_id = owner[0]
    base = [_context(con, ref, offer_id, supplier_id, check_ref) for ref in item['evidence_refs']]
    csv_base = [c for c in base if c['doc'].get('format_family') == 'csv']
    anchor = None
    if csv_base:
        anchors = {(c['doc']['document_id'], c['row']) for c in csv_base for cell in c['cells']
                   if cell['label'] in _ROLES['unit_price']
                   and _has_number(cell['value'], item['amount'], numeric_tokens)
                   and _has_number(c['quote'], item['amount'], numeric_tokens)}
        if len(anchors) != 1:
            raise ValueError('Source pricing needs one unambiguous source unit-price row')
        anchor = next(iter(anchors))
        for role, value in [('quantity', item['quantity']), ('currency', item['currency'])]:
            found = False
            for c in csv_base:
                if (c['doc']['document_id'], c['row']) != anchor:
                    continue
                for cell in c['cells']:
                    if cell['label'] not in _ROLES[role]:
                        continue
                    if (str(cell['value']).upper() == str(value).upper() if role == 'currency'
                            else _has_number(cell['value'], value, numeric_tokens) and _has_number(c['quote'], value, numeric_tokens)):
                        found = True
            if not found:
                raise ValueError('Source pricing quantity/currency requires its own evidence on the price row')
    else:
        currency = str(item.get('currency') or '').upper()
        aliases = {'TRY': ('try', 'tl', '₺'), 'EUR': ('eur', '€'),
                   'USD': ('usd', '$'), 'GBP': ('gbp', '£')}.get(currency, (currency.casefold(),))
        if not currency or not any(any(alias in _fold(c['quote']) for alias in aliases) for c in base):
            raise ValueError('Source pricing item currency needs its own source evidence')

    def contexts(group):
        result = [_context(con, ref, offer_id, supplier_id, check_ref) for ref in group['evidence_refs']]
        for c in result:
            if c['doc'].get('format_family') == 'csv' and (c['doc']['document_id'], c['row']) != anchor:
                raise ValueError('Source pricing cannot borrow another CSV row/document')
        return result

    discount_group = pricing['discounts']; rates = discount_group['percentages']
    for rate in rates:
        if number(rate) >= 100:
            raise ValueError('Source discount percent must be less than100')
    dc = contexts(discount_group); csv_dc = [c for c in dc if c['doc'].get('format_family') == 'csv']
    if csv_dc:
        source = csv_dc[0]
        expected = [(i+1, _discount_order(_label(label))) for i, label in enumerate(source['headers'])
                    if _discount_order(_label(label)) is not None]
        expected.sort(key=lambda pair: pair[1])
        orders = [n for _, n in expected]
        if not expected or (len(expected) > 1 and orders != list(range(1, len(expected)+1))) or (len(expected) == 1 and orders[0] not in (0, 1)):
            raise ValueError('Source discount stage order is ambiguous')
        if len(rates) != len(expected):
            raise ValueError('Source discount chain must cover every staged discount column')
        for rate, (column, _) in zip(rates, expected):
            if not any(cell['column'] == column and _has_number(cell['value'], rate, numeric_tokens)
                       and _has_number(c['quote'], rate, numeric_tokens) for c in csv_dc for cell in c['cells']):
                raise ValueError('Source discount percent/order lacks its own column evidence')
    else:
        wanted = [number(r) for r in rates]; supported = False
        for c in dc:
            text = _fold(c['quote'])
            if wanted == [Decimal(0)] and re.fullmatch(r'(?:iskonto\s*[:=]?\s*(?:yok|uygulanmamis)|no\s+discount|discount\s*[:=]?\s*none)[. ]*', text.strip()):
                supported = True; break
            m = re.search(r'\b(?:iskonto|discount)\b(.*)', text)
            if not m:
                continue
            segment = re.split(r'\b(?:kdv|vat|payment|odeme)\b', m[1], maxsplit=1)[0]
            values = [a or b for a, b in re.findall(r'%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%', segment)]
            if values and [Decimal(v.replace(',', '.')) for v in values] == wanted:
                supported = True; break
        if not supported:
            raise ValueError('Source discounts need a complete explicitly ordered percent phrase')

    vat = pricing['vat']; percent = number(vat['percent'])
    if percent > 100 or vat['basis'] not in ('included', 'excluded'):
        raise ValueError('Invalid source VAT terms')
    vc = contexts(vat); csv_vc = [c for c in vc if c['doc'].get('format_family') == 'csv']
    if csv_vc:
        rate_ok = any(cell['label'] in _ROLES['vat_rate'] and _has_number(cell['value'], percent, numeric_tokens)
                      and _has_number(c['quote'], percent, numeric_tokens) for c in csv_vc for cell in c['cells'])
        basis_ok = any(cell['label'] in _ROLES['vat_basis'] and _basis(cell['value']) == vat['basis']
                       for c in csv_vc for cell in c['cells'])
    else:
        rate_ok = False
        for c in vc:
            text = _fold(c['quote'])
            matches = re.findall(r'\b(?:kdv|vat)\b\s*(?:orani|rate)?\s*(?:%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%)', text)
            matches += re.findall(r'%\s*(\d+(?:[.,]\d+)?)\s*(?:kdv|vat)\b|(\d+(?:[.,]\d+)?)\s*%\s*(?:kdv|vat)\b', text)
            if any(Decimal((a or b).replace(',', '.')) == percent for a, b in matches):
                rate_ok = True
        basis_ok = any(_basis(c['quote']) == vat['basis'] for c in vc)
    if not rate_ok or not basis_ok:
        raise ValueError('Source VAT percent and included/excluded basis need their own evidence')

    if 'price_unit' in pricing:
        unit = pricing['price_unit']; value = number(unit['value'])
        if value <= 0:
            raise ValueError('Source price unit must be positive')
        uc = contexts(unit)
        if not any((cell['label'] in _ROLES['price_unit'] and _has_number(cell['value'], value, numeric_tokens))
                   for c in uc for cell in c['cells']) and not any(
                   c['doc'].get('format_family') != 'csv' and re.search(r'price\s+unit|fiyat\s+birimi', _fold(c['quote']))
                   and _has_number(c['quote'], value, numeric_tokens) for c in uc):
            raise ValueError('Source price unit requires explicit denominator evidence')

    stated = pricing.get('stated_amounts') or {}
    scope = stated.get('scope')
    for field in ('net', 'vat', 'gross'):
        if field not in stated:
            continue
        claim = stated[field]; value = number(claim['amount']); cs = contexts(claim); role = scope+'_'+field
        found = False
        for c in cs:
            for cell in c['cells']:
                allowed = _ROLES[role]
                if scope == 'line' and c['data_row_count'] == 1:
                    allowed = allowed | _ROLES['offer_'+field]
                if cell['label'] in allowed and _has_number(cell['value'], value, numeric_tokens) and _has_number(c['quote'], value, numeric_tokens, Decimal('.01')):
                    found = True
            if c['doc'].get('format_family') != 'csv':
                labels = {'net': r'net\s+(?:toplam|tutar|total|amount)', 'vat': r'(?:kdv\s+tutar|vat\s+amount)',
                          'gross': r'brut\s+toplam|kdv\s+dahil\s+toplam|gross\s+total|grand\s+total'}
                if re.search(labels[field], _fold(c['quote'])) and _has_number(c['quote'], value, numeric_tokens, Decimal('.01')):
                    found = True
        if not found:
            raise ValueError('Source stated '+field+' amount requires its own '+str(scope)+' amount evidence')


def calculate_item_pricing(item):
    if item.get('evidence_status') != 'verified' or item.get('amount_basis') != 'unit_price':
        raise ValueError('Source chain needs a verified unit-price item')
    pricing = item['pricing']; quantity = number(item['quantity']); price = number(item['amount'])
    unit = number((pricing.get('price_unit') or {}).get('value', 1))
    if quantity <= 0 or unit <= 0 or not item.get('currency'):
        raise ValueError('Source chain needs positive quantity/unit and identified currency')
    before = quantity * price / unit; discounted = before
    rates = pricing['discounts']['percentages']
    if not rates:
        raise ValueError('Unknown source discounts are not zero discounts')
    for raw in rates:
        percent = number(raw)
        if percent >= 100:
            raise ValueError('Invalid discount percentage')
        discounted *= 1 - percent / 100
    vat = pricing['vat']; vat_percent = number(vat['percent'])
    if vat_percent > 100:
        raise ValueError('Source VAT percentage exceeds the supported range')
    tax_rate = vat_percent / 100
    if vat['basis'] == 'excluded':
        net = discounted; tax = net * tax_rate; gross = net + tax
    elif vat['basis'] == 'included':
        gross = discounted; net = gross / (1 + tax_rate); tax = gross - net
    else:
        raise ValueError('Unknown source VAT basis')
    return {'item_id': item['item_id'], 'currency': str(item['currency']).upper(),
            'quantity': str(quantity), 'unit_price': str(price), 'price_unit': str(unit),
            'discount_percentages': [str(number(r)) for r in rates], 'vat_percent': str(number(vat['percent'])),
            'price_vat_basis': vat['basis'], 'pre_discount_source_amount': str(before),
            'discounted_source_amount': str(discounted), 'net': str(net), 'vat': str(tax), 'gross': str(gross)}


def calculate_offer_pricing(inputs):
    items = inputs['items']; rows = []; mismatches = []; reconciliations = []; reasons = []
    seen = set(); declarations = {}
    for item in items:
        if item.get('item_id') in seen:
            reasons.append('duplicate source price item identity'); continue
        seen.add(item.get('item_id'))
        try:
            row = calculate_item_pricing(item); rows.append(row)
        except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
            reasons.append(str(exc)); continue
        stated = item['pricing'].get('stated_amounts') or {}
        for field in ('net', 'vat', 'gross'):
            if field not in stated:
                continue
            claim = stated[field]; key = (stated['scope'], item['item_id'] if stated['scope']=='line' else '', field)
            value = number(claim['amount'])
            if key in declarations and declarations[key]['amount'] != value:
                reasons.append('conflicting stated source amounts')
            else:
                declarations[key] = {'amount': value, 'evidence_refs': claim['evidence_refs']}
    currencies = {r['currency'] for r in rows}
    if len(currencies) != 1:
        reasons.append('source price currencies missing or mixed')
    totals = {field: sum((number(r[field]) for r in rows), Decimal(0)) for field in ('net','vat','gross')}
    for (scope, item_id, field), claim in declarations.items():
        candidates = [r for r in rows if r['item_id']==item_id]
        calculated = totals[field] if scope=='offer' else number(candidates[0][field]) if len(candidates)==1 else None
        if calculated is None:
            reasons.append('stated line has no matching source calculation'); continue
        residual = calculated - claim['amount']
        detail = {'scope': scope, 'item_id': item_id or None, 'field': field, 'stated': str(claim['amount']),
                  'calculated': str(calculated), 'residual': str(residual), 'evidence_refs': claim['evidence_refs']}
        reconciliations.append(detail)
        if abs(residual) > Decimal('.01'):
            mismatches.append(detail)
    total = inputs.get('stated_total') or {}
    basis = total.get('vat_basis')
    if total.get('amount') is not None and basis in ('included','excluded') and len(currencies)==1:
        if str(total.get('currency') or '').upper() != next(iter(currencies)):
            reasons.append('stated total currency differs from source items')
        else:
            field = 'gross' if basis=='included' else 'net'; stated = number(total['amount']); residual = totals[field]-stated
            detail = {'scope':'offer','field':field,'stated':str(stated),'calculated':str(totals[field]),
                      'residual':str(residual),'fact_id':total.get('fact_id')}
            reconciliations.append(detail)
            if abs(residual)>Decimal('.01'):
                mismatches.append(detail)
    complete = bool(items) and len(rows)==len(items) and not reasons and not mismatches
    return {'contract': CONTRACT, 'known': bool(rows), 'complete': complete,
            'status':'mismatch' if mismatches else 'complete' if complete else 'incomplete',
            'currency': next(iter(currencies)) if len(currencies)==1 else None, 'items':rows,
            'net_total':str(totals['net']) if rows else None,'vat_total':str(totals['vat']) if rows else None,
            'gross_total':str(totals['gross']) if rows else None,'reconciliations':reconciliations,
            'mismatches':mismatches,'incomplete_reasons':reasons,
            'is_buyer_adjusted_cost_basis':False, 'vat_deductibility_assumed':False}


def source_pricing_inputs(con, offer):
    facts = rows_as_dict(con, "SELECT * FROM facts WHERE offer_id=? AND evidence_status='verified' ORDER BY fact_id", [offer['offer_id']])
    items = []; fact_ids = []
    for fact in facts:
        try:
            normalized = json.loads(fact.get('normalized_json') or '{}')
        except (ValueError, TypeError):
            continue
        if not isinstance(normalized, dict) or not isinstance(normalized.get('items', []), list):
            continue
        selected = [item for item in normalized.get('items', []) if isinstance(item, dict) and item.get('amount_basis') in ('unit_price', 'line_total')]
        if selected:
            items.extend(selected); fact_ids.append(fact['fact_id'])
    if not items or not any(item.get('pricing') is not None for item in items):
        return None
    total = next((f for f in facts if f.get('field_key')=='total'), {})
    currency = next((f.get('value_text') for f in facts if f.get('field_key')=='currency'), None)
    vat = next((f for f in facts if f.get('field_key')=='vat'), {})
    from normalize import vat_basis
    return {'contract': CONTRACT, 'source_fact_ids':fact_ids,'items':items,
            'stated_total':{'fact_id':total.get('fact_id'),'amount':total.get('value_number'),
                            'currency':currency,'vat_basis':vat_basis(vat.get('value_text'))}}
