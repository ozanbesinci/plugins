"""V4 workbook and independently checkable calculation contract. No cached values."""
from __future__ import annotations
import argparse
import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
from teklif_motoru import cost_summary, price_line, score_suppliers
from veri_kontrol import digest, bound_scoring
from sunum import Presentation, text_value, LABELS

PROFILES = {'hizli', 'standart', 'yuksek_guvence'}
CORE = ['Özet', 'Karar Özeti', 'Fiyat ve Kapsam', 'Bilgi Talepleri']
MONEY = '#,##0.00;[Red](#,##0.00);0.00'
PROFILE_LABELS = {'hizli': 'Hızlı', 'standart': 'Standart', 'yuksek_guvence': 'Yüksek güvence'}


def sensitivity_specs(scoring):
    criteria = scoring['criteria']; specs = scoring.get('sensitivity', [])
    if len(criteria) == 1:
        if specs: raise ValueError('Tek kriterde farklı ağırlık senaryosu kurulamaz.')
        return []
    ids = {c['criterion_id'] for c in criteria}; base = {c['criterion_id']: Decimal(str(c['weight'])) for c in criteria}
    if len(specs) < 2: raise ValueError('Baz yanında en az iki ağırlık senaryosu gerekli.')
    seen_ids, seen_weights = set(), {tuple(sorted(base.items()))}
    for spec in specs:
        sid = spec.get('id'); weights = spec.get('weights', {})
        if not sid or sid in seen_ids or set(weights) != ids: raise ValueError('Duyarlılık kimliği/ağırlık kapsamı geçersiz.')
        parsed = {k: Decimal(str(v)) for k, v in weights.items()}
        if any(not v.is_finite() or v < 0 for v in parsed.values()) or sum(parsed.values()) != 100:
            raise ValueError('Her duyarlılık ağırlık toplamı 100 olmalı.')
        signature = tuple(sorted(parsed.items()))
        if signature in seen_weights: raise ValueError('Duyarlılık senaryosu bazdan ve diğerlerinden farklı olmalı.')
        seen_ids.add(sid); seen_weights.add(signature)
    return specs


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('Sonlu sayı gerekli.')
        return str(value)
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def number(value, *, missing=True):
    if value is None and missing:
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean sayı değildir.')
    try:
        n = Decimal(str(value))
    except Exception as e:
        raise ValueError('Geçerli ondalık sayı gerekli.') from e
    if not n.is_finite() or not math.isfinite(float(n)):
        raise ValueError('Sonlu Excel sayısı gerekli.')
    return float(n)


def validate(data):
    if data.get('schema') != 'teklif-data/v4':
        raise ValueError('Merkezi veri şeması teklif-data/v4 olmalı.')
    dt.date.fromisoformat(data['analysis_date'])
    if not isinstance(data.get('project'), str) or not data['project'].strip():
        raise ValueError('Proje adı gerekli.')
    offers = data.get('offers')
    if not isinstance(offers, list) or not offers:
        raise ValueError('En az bir teklif gerekli.')
    ids = [o.get('id') for o in offers]
    if any(not isinstance(x, str) or not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('Teklif kimlikleri benzersiz olmalı.')
    if set(data.get('costs', {})) - set(ids):
        raise ValueError('Maliyet bilinmeyen firmaya bağlı.')
    for p in data.get('costs', {}).values():
        cost_summary(normalized(p))
    for o in offers:
        if not o.get('name'):
            raise ValueError('Firma adı gerekli.')
        for line in o.get('lines', []):
            if all(line.get(k) is not None for k in ('quantity', 'unit_price', 'vat_rate')):
                price_line(normalized(line))
    if data.get('scoring'):
        if len({o.get('supplier_id', o['id']) for o in offers}) < 2:
            raise ValueError('Tek bağımsız tedarikçi puanlanamaz.')
        if set(data.get('costs', {})) != set(ids) or any(cost_summary(normalized(p))['status'] != 'complete_cost_inputs' for p in data['costs'].values()):
            raise ValueError('Eksik maliyetle puanlama yapılamaz.')
        score_suppliers(bound_scoring(normalized(data), {oid: cost_summary(normalized(p)) for oid, p in data['costs'].items()}))
        sensitivity_specs(data['scoring'])
    return data


def build(data, output, profile='standart', inventory=None, qa=None, decision=None, display_names=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter as colname
    from openpyxl.workbook.properties import CalcProperties
    validate(data)
    presentation = Presentation(data, display_names)
    if profile not in PROFILES:
        raise ValueError('Profil geçersiz.')
    if qa is not None and (qa.get('status') != 'PASS' or qa.get('data_sha256') != digest(data)):
        raise ValueError('Tamlık kontrolü geçmemiş veya başka veriye bağlı.')
    if decision is not None and (decision.get('data_sha256') != digest(data) or not isinstance(decision.get('summary'), str) or not decision['summary'].strip()):
        raise ValueError('Hakem özeti güncel merkezi veriye bağlı değil.')
    output = Path(output).resolve(); cp = output.with_suffix(output.suffix + '.contract.json')
    if output.exists() or cp.exists():
        raise ValueError('Var olan çıktı üzerine yazılmaz; yeni revizyon adı seçin.')
    version = Path(__file__).resolve().parents[1].joinpath('VERSION').read_text(encoding='utf-8').strip()
    tabs = list(CORE)
    if profile != 'hizli':
        tabs += ['Elemeli Değerlendirme', 'Ticari ve Sözleşme', 'Kaynaklar']
        if data.get('requirements'): tabs += ['Şartname Uygunluğu']
        if data.get('scoring'): tabs += ['Puanlama']
    if profile == 'yuksek_guvence': tabs += ['Yeterlilik ve Risk', 'Uzman Teyidi']
    modules = {'import': 'İthalat', 'financing': 'Finansman', 'tco': 'Toplam Sahip Olma', 'cash': 'Nakit', 'stock': 'Stok', 'quality': 'Kalite'}
    if profile != 'hizli': tabs += [v for k, v in modules.items() if data.get('modules', {}).get(k)]
    if data.get('change_log'): tabs += ['Değişim Kaydı']
    wb = Workbook(); wb.remove(wb.active)
    sheets = {n: wb.create_sheet(n) for n in tabs}
    contract = {'schema': 'teklif-excel-contract/v4', 'profile': profile, 'version': version, 'data_sha256': digest(data),
                'inventory_sha256': digest(inventory) if inventory is not None else None, 'qa_sha256': digest(qa) if qa is not None else None, 'inputs': [], 'outputs': [],
                'formulas': [], 'sheets': tabs, 'pdf_required': profile == 'yuksek_guvence',
                'decision_sha256': digest(decision) if decision is not None else None, 'decision_cells': [],
                'presentation_version': 1, 'hyperlinks_allowed': False,
                'display_names': {o['id']:presentation.name(o['id']) for o in data['offers']}}
    facts = {f['fact_id']: f for f in data.get('facts', [])}
    sources = {}
    for source in (inventory or {}).get('entries', []):
        s = dict(source)
        if not s.get('path') and s.get('relative_path') and (inventory or {}).get('root'):
            root = Path(inventory['root']).resolve(); p = (root / s['relative_path']).resolve()
            if not p.is_relative_to(root): raise ValueError('Kaynak bağlantısı envanter kökü dışına çıkıyor.')
            s['path'] = str(p)
        sources[s['source_id']] = s
    for index, source in enumerate(sources.values(),1):
        source['label'] = f'Kaynak {index}'

    def row(ws, values, header=False):
        ws.append([presentation.text(v) for v in values] if values else [None])
        for c in ws[ws.max_row]:
            if isinstance(c.value, str): c.data_type = 's'
            c.font = Font(name='Arial', size=10, bold=header, color='FFFFFF' if header else '17324D')
            c.alignment = Alignment(vertical='top', wrap_text=True)
            if header: c.fill = PatternFill('solid', fgColor='17324D')
        ws.row_dimensions[ws.max_row].height = 30 if header else 25
        return ws.max_row

    def prose(ws, value):
        if isinstance(value, (dict, list)): value = json.dumps(value, ensure_ascii=False)
        for para in str(value or '').splitlines() or ['']:
            if not para.strip(): continue
            n = row(ws, [para]); ws.merge_cells(start_row=n, start_column=1, end_row=n, end_column=6)

    def formula(ws, cell, value, descriptor=None):
        ws[cell] = value; ws[cell].font = Font(name='Arial', size=10, color='000000'); ws[cell].number_format = MONEY
        contract['formulas'].append({'sheet': ws.title, 'cell': cell, 'formula': value})
        if descriptor: contract['outputs'].append({'sheet': ws.title, 'cell': cell, **descriptor})

    def inp(ws, cell, value, path, kind='number'):
        if value is None: ws[cell] = None
        elif kind == 'date':
            ws[cell] = dt.datetime.combine(dt.date.fromisoformat(value), dt.time()); ws[cell].number_format = 'dd.mm.yyyy'
        else:
            ws[cell] = number(value, missing=False); ws[cell].number_format = MONEY
        ws[cell].font = Font(name='Arial', size=10, color='0000FF')
        contract['inputs'].append({'sheet': ws.title, 'cell': cell, 'path': path, 'kind': kind, 'default': value})

    def citation(item):
        ids = list(item.get('fact_ids', [])) + list(item.get('bindings', {}).values())
        if item.get('fact_id'): ids += [item['fact_id']]
        refs, paths = [], []
        for fid in dict.fromkeys(ids):
            fact = facts.get(fid, {}); src = sources.get(fact.get('source_id'), {})
            name = src.get('name') or Path(src.get('path', fact.get('source_id', ''))).name
            if name: refs.append(f"{src.get('label',name)} · {fact.get('location', '')}")
            if src.get('path'): paths.append(src)
        return '; '.join(dict.fromkeys(refs)) or str(item.get('source', 'Kaynak bağı merkezi veride')), paths

    def evidence(ws, cell, item):
        text, paths = citation(item); ws[cell] = text; ws[cell].data_type = 's'

    for ws in sheets.values():
        row(ws, []); row(ws, [ws.title]); row(ws, [])
        ws['A2'].font = Font(name='Arial', size=15, bold=True, color='17324D')
    summary = sheets['Özet']
    label = ('DOĞRULAMA TASLAĞI' if qa is None or decision is None else
             'ÖN SONUÇ — KESİN SATINALMA ÖNERİSİ DEĞİLDİR' if qa.get('open_issues') else 'SATINALMA KARAR DOSYASI')
    for text in [data['project'], label,
                 f'Bu analiz teklif-degerlendirme {version} ile üretilmiştir. Profil: {PROFILE_LABELS[profile]}.',
                 'Mavi değerler düzenlenebilir. Bilinmeyen tutarlar boştur; bilinen ara toplam nihai KTM değildir.']:
        prose(summary, text)
    analysis_row = row(summary, ['Analiz tarihi', None])
    inp(summary, f'B{analysis_row}', data['analysis_date'], ['analysis_date'], 'date')
    selection = data.get('profile_selection', {})
    if selection.get('downgraded'):
        prose(summary, f"Profil kullanıcı tarafından düşürüldü: {selection.get('recommended')} önerildi; {profile} seçildi. Kör okuma {'yapılmadı' if profile == 'hizli' else 'profil kapsamında'}.")
    totals = [(i,f) for i,f in enumerate(data.get('facts',[])) if f.get('fact_id') in {o['id']+'/field/total' for o in data['offers']} and f.get('evidence_status')=='verified' and f.get('value') is not None]
    if totals:
        row(summary, ['Firma', 'Teklif tutarı', 'Döviz', 'KDV', 'Teklif kapsamı', 'Kaynak'], True)
        for i,f in totals:
            oid=f['fact_id'].split('/')[0]; offer=next(o for o in data['offers'] if o['id']==oid)
            quantity=facts.get(oid+'/field/quantity',{}).get('value')
            n=row(summary,[offer['name'],None,f.get('currency',offer.get('currency')),text_value(facts.get(oid+'/field/vat',{}).get('value')),text_value(quantity),None])
            inp(summary,f'B{n}',f['value'],['facts',i,'value'],'quoted_total'); evidence(summary,f'F{n}',f)
        prose(summary,'Teklif tutarları firmaların beyanıdır. Eşit kapsamlı toplam maliyet değildir; kapsam farkları giderilmeden fiyat sıralaması yapılmaz.')
    prose(summary,'Karşılaştırılabilir maliyet — eksik kapsam ve ödeme verileri tamamlandığında hesaplanır.')
    row(summary, ['Firma', 'Döviz', 'Bilinen tutar', 'Net bugünkü değer', 'Baz döviz', 'Baz net bugünkü değer', 'Durum'], True)
    ws = sheets['Fiyat ve Kapsam']; prose(ws, 'Benzersiz maliyet olayları. NBD: yıllık efektif oran, ACT/365. Farklı dövizler doğrudan toplanmaz.')
    if data.get('costs'): row(ws, ['Firma', 'Parametre', 'Değer', 'Döviz', 'Dayanak'], True)
    else: prose(ws,'Eşit kapsamlı maliyet hesabı için eksik işler ve ödeme tarihleri tamamlanmalıdır. Firmaların beyan ettiği teklif tutarları Özet bölümündedir.')
    params = {}; offer_base_cells = {}
    for oid, p in data.get('costs', {}).items():
        assumptions = p.get('assumption_sources', {})
        if isinstance(assumptions, str):
            assumptions = {key: assumptions for key in ('base_date', 'annual_rates', 'fx_rates')}
        if not isinstance(assumptions, dict):
            raise ValueError('Varsayım dayanağı açıklama metni veya nesne olmalı.')
        n = row(ws, [presentation.name(oid), 'Değerleme tarihi', None, '', str(assumptions.get('base_date', data['analysis_date']))])
        inp(ws, f'C{n}', p['base_date'], ['costs', oid, 'base_date'], 'date'); params[oid, 'base_date'] = f'$C${n}'
        for curr, value in p['annual_rates'].items():
            n = row(ws, [presentation.name(oid), 'Yıllık efektif oran', None, curr, str(assumptions.get('annual_rates', 'Merkezi veri varsayımı'))])
            inp(ws, f'C{n}', value, ['costs', oid, 'annual_rates', curr], 'rate'); ws[f'C{n}'].number_format = '0.00%'
            params[oid, 'rate', curr] = f'$C${n}'
        for curr, quote in p.get('fx_rates', {}).items():
            for field, label in [('forex_selling', 'Döviz satış kuru'), ('unit', 'Kur birimi')]:
                n = row(ws, [presentation.name(oid), label, None, curr, str(assumptions.get('fx_rates', 'Merkezi veri varsayımı'))])
                inp(ws, f'C{n}', quote[field], ['costs', oid, 'fx_rates', curr, field], field); params[oid, field, curr] = f'$C${n}'
    if data.get('costs'):
        row(ws, []); row(ws, ['Firma', 'Maliyet olayı', 'Basamak', 'Nominal tutar', 'Döviz', 'Ödeme tarihi', 'Yıl', 'Yıllık oran', 'NBD', 'Baz NBD', 'Kaynak', 'Durum'], True)
    for offer in data['offers']:
        oid = offer['id']; p = data.get('costs', {}).get(oid)
        if not p:
            row(summary, [offer['name'], offer.get('currency'), None, None, None, None, 'Eşit kapsamlı maliyet hesaplanamadı']); continue
        result = cost_summary(normalized(p)); groups = {}
        for index, event in enumerate(p['events']):
            curr, eid, known = event.get('currency'), event['event_id'], event['known']
            n = row(ws, [offer['name'], eid, event.get('stage', event.get('classification', '')), None, curr, None, None, None, None, None, None, 'Bilinen' if known else 'Fiyatlanmamış'])
            if known: inp(ws, f'D{n}', event['amount'], ['costs', oid, 'events', index, 'amount'], 'amount')
            else: ws[f'D{n}'].fill = PatternFill('solid', fgColor='FFF2CC')
            if event.get('payment_date'): inp(ws, f'F{n}', event['payment_date'], ['costs', oid, 'events', index, 'payment_date'], 'date')
            base = params[oid, 'base_date']
            formula(ws, f'G{n}', f'=IF(COUNT(F{n},{base})=2,(F{n}-{base})/365,"")')
            if (oid, 'rate', curr) in params:
                formula(ws, f'H{n}', '=' + params[oid, 'rate', curr]); ws[f'H{n}'].number_format = '0.00%'
            formula(ws, f'I{n}', f'=IF(COUNT(D{n},G{n},H{n})=3,D{n}/(1+H{n})^G{n},"")', {'kind': 'event_pv', 'offer_id': oid, 'event_id': eid})
            if (oid, 'forex_selling', curr) in params:
                formula(ws, f'J{n}', f'=IF(ISNUMBER(I{n}),I{n}*{params[oid,"forex_selling",curr]}/{params[oid,"unit",curr]},"")', {'kind': 'event_base', 'offer_id': oid, 'event_id': eid})
            evidence(ws, f'K{n}', event)
            if known: groups.setdefault(curr, []).append(n)
        if not groups:
            row(summary, [offer['name'], None, None, None, p.get('base_currency'), None, 'Bilinen maliyet yok; toplam hesaplanamadı'])
        for curr, rows in groups.items():
            n = row(summary, [offer['name'], curr, None, None, p.get('base_currency'), None, 'Eksik maliyet var; bilinen ara toplam' if result['unknown_event_ids'] else 'Sayısal maliyet girdileri tamam'])
            for dest, src, kind in [('C', 'D', 'nominal'), ('D', 'I', 'pv')]:
                formula(summary, f'{dest}{n}', '=SUM(' + ','.join(f"'Fiyat ve Kapsam'!{src}{r}" for r in rows) + ')', {'kind': kind, 'offer_id': oid, 'currency': curr})
            if p.get('base_currency'):
                formula(summary, f'F{n}', '=SUM(' + ','.join(f"'Fiyat ve Kapsam'!J{r}" for r in rows) + ')', {'kind': 'base_currency_total', 'offer_id': oid, 'currency': curr})
                offer_base_cells.setdefault(oid, []).append(f"'Özet'!F{n}")
    row(summary, [])
    row(summary, ['Firma', 'Teklif tarihi', 'Son geçerlilik', 'Yaş (gün)', 'Geçerlilik testi', 'Yaş testi', 'Kaynak'], True)
    fact_indices = {f['fact_id']: i for i, f in enumerate(data.get('facts', []))}
    for offer in data['offers']:
        oid = offer['id']; n = row(summary, [offer['name']])
        for field, col in [('quote_date', 'B'), ('validity', 'C')]:
            fid = f'{oid}/field/{field}'; fact = facts.get(fid, {})
            if fact.get('evidence_status') == 'verified':
                inp(summary, f'{col}{n}', fact['value'], ['facts', fact_indices[fid], 'value'], 'date')
        analysis_ref = f'$B${analysis_row}'
        formula(summary, f'D{n}', f'=IF(ISNUMBER(B{n}),{analysis_ref}-B{n},"")', {'kind': 'quote_age', 'offer_id': oid}); summary[f'D{n}'].number_format = '0'
        formula(summary, f'E{n}', f'=IF(ISNUMBER(C{n}),IF(C{n}<{analysis_ref},"Geçerlilik dolmuş","Süre içinde"),"Geçerlilik teyidi yok")', {'kind': 'validity', 'offer_id': oid})
        formula(summary, f'F{n}', f'=IF(ISNUMBER(D{n}),IF(OR(D{n}>60,D{n}<0),"Güncel teklif teyidi","Yaş sınırı içinde"),"Teklif tarihi yok")', {'kind': 'age_status', 'offer_id': oid})
        evidence(summary, f'G{n}', {'fact_ids': [f'{oid}/field/quote_date', f'{oid}/field/validity']})
    if data.get('scope_items'):
        row(ws, []); row(ws, ['Kapsam kimliği', 'Firma/sınıf', 'Konu', 'Tutar', 'Döviz', 'RFI', 'Kaynak'], True)
        for item in data['scope_items']:
            n = row(ws, [item.get('id'), presentation.name(item.get('offer_id', 'ORTAK')) + ' / ' + str(item.get('classification', '')), item.get('description'), number(item.get('amount')), item.get('currency'), item.get('rfi'), None]); evidence(ws, f'G{n}', item)
        prose(ws, 'Kapsam tablosu açıklamadır; toplama yalnız yukarıdaki benzersiz maliyet olayları girer.')
    for oi, offer in enumerate(data['offers']):
        for li, line in enumerate(offer.get('lines', [])):
            row(ws, []); prose(ws, f"{offer['name']} — {line.get('description', line.get('id', 'Kalem'))}"); cells = {}
            for field, default in [('quantity', None), ('unit_price', None), ('price_unit', 1), ('vat_rate', None)]:
                n = row(ws, [LABELS.get(field,field), None]); inp(ws, f'B{n}', line.get(field, default), ['offers', oi, 'lines', li, field], field); cells[field] = f'B{n}'
            discounts = []
            for di, discount in enumerate(line.get('discounts', [])):
                n = row(ws, ['Ardışık iskonto', None]); inp(ws, f'B{n}', discount, ['offers', oi, 'lines', li, 'discounts', di], 'discount'); discounts.append(f'(1-B{n})')
            q, pr, u, v = (cells[k] for k in ('quantity', 'unit_price', 'price_unit', 'vat_rate'))
            n = row(ws, ['KDV hariç net', None, 'KDV', None, 'KDV dahil toplam', None])
            amount = f'{q}*{pr}/{u}' + ''.join('*' + d for d in discounts)
            net = f'({amount})/(1+{v})' if line.get('price_includes_vat', False) else amount
            guard = f'COUNT({q},{pr},{u},{v})=4'
            for cell, expr, field in [(f'B{n}', net, 'net_excluding_vat'), (f'D{n}', f'B{n}*{v}', 'vat_amount'), (f'F{n}', f'B{n}+D{n}', 'total_including_vat')]:
                formula(ws, cell, f'=IF({guard},{expr},"")', {'kind': 'line', 'offer_index': oi, 'line_index': li, 'field': field})
    decision_payload = decision
    decision = sheets['Karar Özeti']; prose(decision, 'Sonuç ve Öneri')
    # Keep adjudicator text separate from its hashed source data.
    adjudication = decision_payload
    prose(decision, adjudication['summary'] if adjudication is not None else 'Hakemin gerekçeli karar özeti bekleniyor.')
    contract['decision_cells'] = [{'cell': c.coordinate, 'value': c.value} for rows in decision for c in rows if isinstance(c.value, str)]
    if (qa or {}).get('open_issues'):
        prose(decision, f"{len(qa['open_issues'])} açık kontrol konusu bulunuyor. Ayrıntılar RFI, Şartname Uygunluğu ve Fiyat ve Kapsam bölümlerindedir.")
        represented=set(facts)
        for issue in qa['open_issues']:
            # Dates and unavailable comparable costs already appear in Özet.
            in_summary=any(str(issue).startswith(o['id']+suffix) for o in data['offers'] for suffix in ('/quote_date:', '/validity:', ': karşılaştırılabilir maliyet'))
            if issue not in represented and not in_summary: prose(decision, 'Açık konu: '+str(issue))
    if not data.get('requirements'): prose(decision, 'Şartname yok: teknik denklik doğrulanmadı.')
    if profile == 'hizli': prose(decision, 'Hızlı profil: kör okuma yapılmadı; kritik alanlar hedefli görüntü kontrolü kapsamındadır.')

    def table(name, headers, records, mapper):
        if name not in sheets: return
        target = sheets[name]; row(target, headers, True)
        for item in records:
            row(target, mapper(item))
        target.auto_filter.ref=f'A4:{colname(target.max_column)}{target.max_row}'
        target.print_title_rows='1:4'
        if not records: prose(target, 'Kayıt yok; kontrolün durumu merkezi veride değerlendirilir.')
    table('Bilgi Talepleri', ['Kimlik', 'Muhatap', 'Soru', 'İlgili konu', 'Durum', 'Kaynak'], data.get('rfi', []), lambda x: [x.get('id'), presentation.name(x.get('owner')), x.get('question'), '\n'.join(presentation.ref(f) for f in x.get('fact_ids', [])), text_value(x.get('status', 'Yanıt bekleniyor')), citation(x)[0]])
    table('Elemeli Değerlendirme', ['Firma', 'Karar', 'Gerekçe', 'Kanıt'], data.get('exclusions', []), lambda x: [presentation.name(x.get('offer_id')), x.get('decision'), x.get('reason'), citation(x)[0]])
    table('Ticari ve Sözleşme', ['Firma', 'Konu', 'Değer', 'Kanıt durumu', 'Kaynak', 'Kaynak ifadesi / Türkçe karşılığı'], [f for f in data.get('facts', []) if '/field/' in f.get('fact_id', '')], lambda x: [*presentation.fact(x['fact_id']), text_value(x.get('value')), text_value(x.get('evidence_status')), citation(x)[0], x.get('quote')])
    table('Kaynaklar', ['Kaynak', 'Dosya', 'SHA-256', 'Kanıt durumu'], list(sources.values()), lambda x: [x['label'], x.get('name') or Path(x.get('path', '')).name, x.get('sha256'), 'Envanter kaydı'])
    table('Şartname Uygunluğu', ['Firma', 'Madde', 'Hüküm', 'Durum', 'Kaynak', 'Kaynak ifadesi / Türkçe karşılığı'], [f for f in data.get('facts', []) if 'requirement/' in f.get('fact_id', '')], lambda x: [*presentation.fact(x['fact_id']), text_value(x.get('value')), text_value(x.get('evidence_status')), citation(x)[0], x.get('quote')])
    table('Yeterlilik ve Risk', ['Firma', 'Konu', 'Risk', 'Kanıt'], data.get('risks', []), lambda x: [presentation.name(x.get('offer_id')), x.get('description'), x.get('severity'), citation(x)[0]])
    table('Uzman Teyidi', ['Muhatap', 'Konu', 'Gerekçe', 'Durum'], data.get('expert_confirmations', []), lambda x: [x.get('owner'), x.get('question'), x.get('reason'), x.get('status', 'Bekliyor')])
    table('Değişim Kaydı', ['Firma', 'Değişen kalem', 'Önceki', 'Yeni', 'KTM etkisi', 'Cevapsız RFI'], data.get('change_log', []), lambda x: [str(x.get(k, '')) for k in ('offer_id', 'field', 'before', 'after', 'cost_effect', 'unanswered_rfi')])
    for key, name in modules.items():
        records = data.get('modules', {}).get(key, [])
        table(name, ['Firma', 'Konu', 'Değer', 'Birim', 'Kaynak'], records if isinstance(records, list) else [records], lambda x: [presentation.name(x.get('offer_id')), x.get('description'), text_value(x.get('value')), x.get('unit'), citation(x)[0]])
    if 'Puanlama' in sheets:
        scoring = bound_scoring(normalized(data), {oid: cost_summary(normalized(p)) for oid, p in data['costs'].items()}); target = sheets['Puanlama']; suppliers = scoring['suppliers']; eligible = [i for i, s in enumerate(suppliers) if s['eligible']]
        row(target, ['Kriter', 'Ağırlık'] + [s['supplier_id'] for s in suppliers], True); original_rows = []
        for ci, criterion in enumerate(scoring['criteria']):
            n = row(target, [criterion['criterion_id']]); original_rows.append(n)
            inp(target, f'B{n}', criterion['weight'], ['scoring', 'criteria', ci, 'weight'], 'weight')
            for si, supplier in enumerate(suppliers):
                binding = criterion['bindings'][supplier['supplier_id']]; cell = f'{colname(si+3)}{n}'
                if binding['kind'] == 'cost':
                    formula(target, cell, '=SUM(' + ','.join(offer_base_cells[binding['offer_id']]) + ')', {'kind': 'criterion_value', 'criterion_id': criterion['criterion_id'], 'supplier_id': supplier['supplier_id']})
                else:
                    fi = fact_indices[binding['fact_id']]
                    inp(target, cell, data['facts'][fi]['value'], ['facts', fi, 'value'], 'criterion')
        row(target, []); row(target, ['Normalleştirilmiş puan', 'Ayırt edici ağırlık'] + [s['supplier_id'] for s in suppliers], True); score_rows = []
        for ci, criterion in enumerate(scoring['criteria']):
            orig = original_rows[ci]; n = row(target, [criterion['criterion_id']]); score_rows.append(n)
            refs = ','.join(f'{colname(i+3)}{orig}' for i in eligible)
            formula(target, f'B{n}', f'=IF(MAX({refs})<>MIN({refs}),B{orig},0)')
            for si in eligible:
                col = colname(si+3); value = f'{col}{orig}'
                if criterion['direction'] == 'direct': expr = value
                elif criterion.get('method', 'proportional') == 'proportional': expr = f'10*MIN({refs})/{value}' if criterion['direction'] == 'lower' else f'10*{value}/MAX({refs})'
                else:
                    term = f'MAX({refs})-{value}' if criterion['direction'] == 'lower' else f'{value}-MIN({refs})'
                    expr = f'IF(MAX({refs})=MIN({refs}),10,10*({term})/(MAX({refs})-MIN({refs})))'
                formula(target, f'{col}{n}', '=' + expr, {'kind': 'criterion_score', 'supplier_id': suppliers[si]['supplier_id'], 'criterion_id': criterion['criterion_id']})
        n = row(target, ['Toplam puan / ayırt edici ağırlık'])
        formula(target, f'B{n}', f'=SUM(B{score_rows[0]}:B{score_rows[-1]})', {'kind': 'distinguishing_weight'})
        for si in eligible:
            col = colname(si+3)
            formula(target, f'{col}{n}', f'=SUMPRODUCT(B{original_rows[0]}:B{original_rows[-1]},{col}{score_rows[0]}:{col}{score_rows[-1]})/100', {'kind': 'score', 'supplier_id': suppliers[si]['supplier_id']})
        rank = row(target, ['Puan sırası'])
        for si in eligible:
            col = colname(si+3)
            formula(target, f'{col}{rank}', f'=1+COUNTIF(C{n}:{colname(len(suppliers)+2)}{n},">"&{col}{n})', {'kind': 'rank', 'supplier_id': suppliers[si]['supplier_id']})
            target[f'{col}{rank}'].number_format = '0'
        prose(target, 'Elenen teklifler normalleştirme ve puan dışında. Eşit puan aynı sıra alır. Puan tek başına satınalma önerisi değildir.')
        scenarios = sensitivity_specs(scoring)
        if not scenarios:
            prose(target, 'Tek kriterde ağırlık alternatifi yoktur; fiyat ve kur parametreleri düzenlenebilir.')
        else:
            row(target, []); row(target, ['Duyarlılık senaryosu', 'Ayırt edici oran'] + [s['supplier_id'] for s in suppliers], True)
            baseline_row = row(target, ['Baz'])
            formula(target, f'B{baseline_row}', f'=B{n}/100'); target[f'B{baseline_row}'].number_format = '0.0%'
            for si in eligible: formula(target, f'{colname(si+3)}{baseline_row}', f'={colname(si+3)}{n}')
            for scenario_index, scenario in enumerate(scenarios):
                row(target, []); row(target, [scenario.get('label', scenario['id']), 'Ağırlık'], True); weight_rows = []
                for criterion in scoring['criteria']:
                    r = row(target, [criterion['criterion_id']]); weight_rows.append(r)
                    inp(target, f'B{r}', scenario['weights'][criterion['criterion_id']], ['scoring', 'sensitivity', scenario_index, 'weights', criterion['criterion_id']], 'sensitivity_weight')
                total_row = row(target, ['Ağırlık toplamı'])
                formula(target, f'B{total_row}', f'=SUM(B{weight_rows[0]}:B{weight_rows[-1]})', {'kind': 'sensitivity_weight_total', 'scenario_id': scenario['id']})
                row(target, ['Senaryo sonucu', 'Ayırt edici oran'] + [s['supplier_id'] for s in suppliers], True)
                result_row = row(target, [scenario.get('label', scenario['id'])])
                terms = []
                for ci, weight_row in enumerate(weight_rows):
                    refs = ','.join(f'{colname(i+3)}{original_rows[ci]}' for i in eligible)
                    terms.append(f'IF(MAX({refs})<>MIN({refs}),B{weight_row},0)')
                formula(target, f'B{result_row}', '=SUM(' + ','.join(terms) + ')/100', {'kind': 'sensitivity_ratio', 'scenario_id': scenario['id']}); target[f'B{result_row}'].number_format = '0.0%'
                for si in eligible:
                    col = colname(si+3)
                    formula(target, f'{col}{result_row}', f'=SUMPRODUCT(B{weight_rows[0]}:B{weight_rows[-1]},{col}{score_rows[0]}:{col}{score_rows[-1]})/100', {'kind': 'sensitivity_score', 'scenario_id': scenario['id'], 'supplier_id': suppliers[si]['supplier_id']})
                rank_row = row(target, ['Senaryo sırası'])
                for si in eligible:
                    col = colname(si+3)
                    formula(target, f'{col}{rank_row}', f'=1+COUNTIF(C{result_row}:{colname(len(suppliers)+2)}{result_row},">"&{col}{result_row})', {'kind': 'sensitivity_rank', 'scenario_id': scenario['id'], 'supplier_id': suppliers[si]['supplier_id']}); target[f'{col}{rank_row}'].number_format = '0'
            prose(target, 'Ayırt edici oran %60 altında olduğunda aynı sıra, kararın sağlamlığını tek başına göstermez. Ağırlık tercihi karar merciine aittir.')
    widths = {
        'Özet':[28,16,13,14,24,23,24], 'Karar Özeti':[15,15,15,15,15,15],
        'Bilgi Talepleri':[12,24,62,35,18,27],
        'Elemeli Değerlendirme':[25,23,65,32],
        'Ticari ve Sözleşme':[25,22,55,18,28,55],
        'Şartname Uygunluğu':[24,28,55,18,27,55],
        'Yeterlilik ve Risk':[25,85,15,32], 'Uzman Teyidi':[27,55,50,18],
        'Kaynaklar':[14,80,68,20], 'Toplam Sahip Olma':[25,65,20,18,30],
        'Nakit':[25,65,22,20,30],
    }
    for target in wb:
        target.merge_cells(start_row=2,start_column=1,end_row=2,end_column=max(2,target.max_column))
        target.sheet_view.showGridLines = False; target.sheet_properties.pageSetUpPr.fitToPage = True
        target.page_setup.orientation = 'landscape'; target.page_setup.paperSize = target.PAPERSIZE_A3
        if target.title == 'Karar Özeti':
            target.page_setup.paperSize=target.PAPERSIZE_A4
        if target.title=='Karar Özeti': target.page_setup.orientation='portrait'
        target.page_margins.left=0.25; target.page_margins.right=0.25
        target.page_margins.top=0.35; target.page_margins.bottom=0.4
        target.page_setup.fitToWidth = 1; target.page_setup.fitToHeight = 0
        if target.title == 'Özet': target.page_setup.fitToHeight = 1
        target.oddFooter.center.text = f'teklif-degerlendirme {version} | &P / &N'
        target.freeze_panes = 'A5'
        for col in range(1, target.max_column+1):
            spec=widths.get(target.title,[])
            target.column_dimensions[colname(col)].width = spec[col-1] if col<=len(spec) else 22
        if target.title == 'Fiyat ve Kapsam':
            if data.get('costs'):
                target.column_dimensions['K'].width = 45
                for col in ('D', 'F', 'G', 'H', 'I', 'J'): target.column_dimensions[col].width = 17
            else:
                for i,width in enumerate([14,30,60,18,12,18,28],1): target.column_dimensions[colname(i)].width=width
        for cells in target.iter_rows():
            height = target.row_dimensions[cells[0].row].height or 25
            for c in cells:
                if isinstance(c.value, (int, float)) or c.data_type == 'f':
                    c.alignment = Alignment(horizontal='right', vertical='top', indent=1)
                if c.data_type == 'f' or not isinstance(c.value, str): continue
                merged=next((a for a in target.merged_cells.ranges if c.coordinate in a),None)
                if merged:
                    width=sum(target.column_dimensions[colname(i)].width for i in range(merged.min_col,merged.max_col+1))
                    count=sum(max(1,math.ceil(len(s)/max(width-8,8))) for s in c.value.splitlines())
                    height=max(height,14*count+12)
                    continue
                width = target.column_dimensions[c.column_letter].width or 22
                count = sum(max(1, math.ceil(len(s)/max(width-2, 8))) for s in c.value.splitlines())
                height = max(height, 14*count+8); c.alignment = Alignment(vertical='top', wrap_text=True)
            target.row_dimensions[cells[0].row].height = min(409, height)
        target.print_area = target.dimensions
    wb.calculation = CalcProperties(calcId=191029, fullCalcOnLoad=True, forceFullCalc=True)
    output.parent.mkdir(parents=True, exist_ok=True); wb.save(output); wb.close()
    contract['workbook_sha256'] = file_hash(output)
    cp.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'status': 'DRAFT_RECALC_REQUIRED', 'output': str(output), 'contract': str(cp), 'sheets': tabs, 'data_sha256': digest(data), 'contract_sha256': file_hash(cp)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--data', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p.add_argument('--profile', choices=sorted(PROFILES), default='standart'); p.add_argument('--inventory', type=Path); p.add_argument('--qa', type=Path); p.add_argument('--decision', type=Path); p.add_argument('--display-names',type=Path)
    a = p.parse_args(); read = lambda f: json.loads(f.read_text(encoding='utf-8')) if f else None
    print(json.dumps(build(read(a.data), a.output, a.profile, read(a.inventory), read(a.qa), read(a.decision),read(a.display_names)), ensure_ascii=False))
