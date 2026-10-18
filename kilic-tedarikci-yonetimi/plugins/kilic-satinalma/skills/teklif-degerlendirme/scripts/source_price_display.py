"""Display frozen source pricing calculations; never recalculate or query live facts."""
import json

SHEET = 'Kaynak Fiyat Zinciri'
HEADERS = ['Teklif', 'Kalem', 'Alan', 'Değer', 'Para Birimi', 'Hesap Durumu', 'Hesap Kimliği']
STATUS = {'complete':'Mutabık', 'mismatch':'Beyan ile farklı', 'incomplete':'Eksik kaynak girdisi'}
BASIS = {'included':'KDV dahil', 'excluded':'KDV hariç'}


def chains(model):
    if model.get('content_status') == 'SAFETY_NOTICE' or model.get('decision_assurance') == 'BLOCKED_INTEGRITY':
        return []
    active = {o['offer_id'] for o in model.get('offers', []) if o.get('status') == 'active'}
    selected = []
    for calc in model.get('calculations', []):
        if calc.get('calculation_type') != 'source_price_chain' or calc.get('offer_id') not in active:
            continue
        result = calc.get('result')
        if result is None:
            result = json.loads(calc.get('result_json') or '{}')
        selected.append((calc, result))
    return selected


def sheet_entries(model):
    entries = []
    for calc, result in chains(model):
        oid = calc['offer_id']; cid = calc['calculation_id']; currency = result.get('currency')
        status = STATUS.get(result.get('status'), 'Eksik kaynak girdisi')
        def add(item, title, value, path, *, monetary=True):
            entries.append({'values':[oid, item, title, value, currency if monetary else None, status, cid],
                            'calculation_id':cid, 'value_path':path})
        for i, item in enumerate(result.get('items', [])):
            iid = item['item_id']; prefix = 'items.' + str(i) + '.'
            for key, title in [('quantity','Kaynak miktarı'), ('unit_price','Kaynak birim fiyatı'),
                               ('price_unit','Fiyatın miktar böleni'), ('pre_discount_source_amount','İskonto öncesi kaynak tutarı')]:
                add(iid, title, item.get(key), prefix + key, monetary=key not in ('quantity', 'price_unit'))
            for j, rate in enumerate(item.get('discount_percentages', [])):
                add(iid, 'Kaynak iskonto ' + str(j+1) + ' (%)', rate, prefix+'discount_percentages.'+str(j), monetary=False)
            for key, title in [('vat_percent','Kaynak KDV (%)'), ('price_vat_basis','Birim fiyat KDV esası'),
                               ('discounted_source_amount','İskonto sonrası kaynak tutarı'), ('net','KDV hariç net'),
                               ('vat','KDV tutarı'), ('gross','KDV dahil brüt')]:
                # Preserve exact frozen values for cell lineage; labels describe the basis.
                add(iid, title, item.get(key), prefix+key, monetary=key not in ('vat_percent', 'price_vat_basis'))
        for key, title in [('net_total','Kaynak kalemleri net toplamı'), ('vat_total','Kaynak kalemleri KDV toplamı'),
                           ('gross_total','Kaynak kalemleri brüt toplamı')]:
            add('Toplam', title, result.get(key), key)
        for i, row in enumerate(result.get('reconciliations', [])):
            ident = row.get('item_id') or 'Teklif toplamı'
            title = {'net':'Net', 'vat':'KDV', 'gross':'Brüt'}.get(row.get('field'), str(row.get('field')))
            for key, suffix in [('stated','kaynak beyanı'), ('calculated','hesap'), ('residual','hesap eksi beyan farkı')]:
                add(ident, title+' '+suffix, row.get(key), 'reconciliations.'+str(i)+'.'+key)
    return entries


def pdf_rows(model):
    rows = []
    for calc, result in chains(model):
        status = STATUS.get(result.get('status'), 'Eksik kaynak girdisi')
        for item in result.get('items', []):
            rows.append([str(calc['offer_id'])+' / '+str(item['item_id'])+'\nMiktar: '+str(item['quantity'])+
                         ' | Birim fiyat: '+str(item['unit_price'])+' / '+str(item['price_unit'])+' '+str(item['currency']),
                         'İskonto sırası (%): '+' → '.join(item['discount_percentages'])+'\nKDV: %'+str(item['vat_percent'])+
                         ' | '+BASIS.get(item['price_vat_basis'], 'Bilinmiyor'),
                         'Net: '+str(item['net'])+'\nKDV: '+str(item['vat'])+'\nBrüt: '+str(item['gross'])+' '+str(item['currency'])+'\n'+status])
        for row in result.get('reconciliations', []):
            title = {'net':'Net', 'vat':'KDV', 'gross':'Brüt'}.get(row.get('field'), str(row.get('field')))
            rows.append([str(calc['offer_id'])+' / '+str(row.get('item_id') or 'Teklif toplamı'),
                         title+' kaynak beyanı: '+str(row['stated'])+'\nHesap: '+str(row['calculated']),
                         'Hesap eksi beyan: '+str(row['residual'])+' '+str(result.get('currency') or '')+'\n'+status])
    return rows
