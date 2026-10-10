"""Decision bases retain supplier observations and independently checked user evidence."""
from datetime import date
from decimal import Decimal
import json,re
from active_records import current_calculations
from db import rows_as_dict

def _meta(con,key,default=None,parse_json=False):
    row=con.execute('SELECT value FROM run_meta WHERE key=?',[key]).fetchone()
    if not row:return default
    return _j(row[0]) if parse_json else row[0]

def _j(raw):
    try:return json.loads(raw or '{}')
    except (TypeError,ValueError):return {}

def _checked_cost(con,offer_id):
    rows=[r for r in current_calculations(con) if r.get('offer_id')==offer_id and r.get('calculation_type')=='cost_summary']
    if len(rows)!=1 or rows[0]['status']!='complete':return None
    row=rows[0]; obj=_j(row['result_json'])
    if not obj.get('complete') or not obj.get('known'):return None
    independent=rows_as_dict(con,'SELECT * FROM independent_calculations WHERE calculation_id=? AND offer_id=?',[row['calculation_id'],offer_id])
    if len(independent)!=1 or independent[0]['status']!='pass' or independent[0]['input_hash']!=row['input_hash']:return None
    return row,obj,independent[0]

def unknown_quote_is_nonmaterial(con,offer_id):
    """A scoped unknown issue date cannot negate an independently applied current validity."""
    from scope_ledger import buyer_authority
    quote=buyer_authority(con,offer_id,'quote_date')
    validity=buyer_authority(con,offer_id,'validity')
    if not quote or quote['value'].get('date_status')!='unknown' or not validity or validity['value'].get('date_status')!='known':return False
    try:
        analysis=date.fromisoformat(str(_meta(con,'analysis_date')))
        return date.fromisoformat(validity['value']['value'])>=analysis
    except (ValueError,TypeError):return False

def _fold(x):
    return ' '.join(str(x or '').translate(str.maketrans('ıİşŞğĞüÜöÖçÇ','iissgguuoocc')).casefold().split())

def _line_basis(con,offer_id):
    from buyer_quantity import _source_loci,_cell,number
    checked=_checked_cost(con,offer_id)
    facts=rows_as_dict(con,"SELECT * FROM facts WHERE offer_id=? AND field_key='quantity'",[offer_id])
    if not checked or len(facts)!=1 or facts[0]['evidence_status'] in {'conflicting','unreadable'}:return None
    normalized=_j(facts[0]['normalized_json']); items=normalized.get('items',[])
    if not isinstance(items,list) or len(items)<2 or len({str(x.get('unit') or '').casefold() for x in items})<2:return None
    row,cost,independent=checked
    changes={x['quantity_item_id']:x for x in cost.get('buyer_quantity_rows',[])}
    records=[]; seen=set(); source_sum=Decimal(0)
    try:
        for item in items:
            if item.get('evidence_status')!='verified' and item.get('item_id') not in changes:return None
            loci=_source_loci(con,item)
            change=changes.get(item['item_id'])
            if change:
                proof=change.get('source') or {}
                match=re.fullmatch(r'[A-Z]+(\d+)',str(proof.get('quantity_cell') or ''))
                if not match or not proof.get('document_id') or not proof.get('unit_id'):return None
                loci={(proof['document_id'],proof['unit_id'],match[1])}
            if len(loci)!=1:return None
            document_id,unit_id,line=next(iter(loci)); line=int(line)
            source=rows_as_dict(con,'SELECT u.structured_json,d.sha256,d.active,d.offer_id FROM document_units u JOIN documents d ON d.document_id=u.document_id WHERE u.unit_id=? AND d.document_id=?',[unit_id,document_id])
            if len(source)!=1 or not source[0]['active'] or source[0]['offer_id']!=offer_id:return None
            if change and change['source'].get('document_sha256')!=source[0]['sha256']:return None
            structured=_j(source[0]['structured_json']); cells=structured.get('cells',[])
            columns={}
            for cell in cells:
                address=str(cell.get('cell') or ''); match=re.fullmatch(r'([A-Z]+)(\d+)',address)
                if not match or int(match[2])>=line:continue
                val=_fold(cell.get('calculated_value') if cell.get('calculated_value') is not None else cell.get('formula_or_value'))
                key=('unit_price' if val in {'birim fiyat','unit price'} else 'quantity' if val in {'metraj','miktar','quantity','qty'} else 'unit' if val in {'birim','unit'} else 'total' if val in {'tutar','line total','amount'} else None)
                if key:columns[key]=match[1]
            if set(columns)!={'quantity','unit_price','unit','total'}:return None
            addresses={k:v+str(line) for k,v in columns.items()}
            q=number(_cell(cells,addresses['quantity'])); p=number(_cell(cells,addresses['unit_price'])); total=number(_cell(cells,addresses['total'],allow_cached=True)); unit=str(_cell(cells,addresses['unit']))
            if q!=number(item['quantity']) or _fold(unit)!=_fold(item['unit']) or q*p!=total:return None
            identity=(unit_id,line)
            if identity in seen:return None
            seen.add(identity); source_sum+=total
            labels=tuple(_fold(c.get('calculated_value') if c.get('calculated_value') is not None else c.get('formula_or_value')) for c in sorted(cells,key=lambda x:str(x.get('cell') or '')) if re.fullmatch(r'[A-Z]+'+str(line),str(c.get('cell') or '')) and str(c['cell'])[:-len(str(line))]<columns['unit'])
            if not labels or not any(labels):return None
            key=(str(structured.get('title') or ''),line,labels,_fold(unit))
            effective=changes.get(item['item_id'],{}).get('reference_quantity',str(q))
            records.append({'item_id':item['item_id'],'comparison_key':key,'source_quantity':str(q),'quantity':str(effective),'unit':unit,'unit_price':str(p),'line_total':str(total),'document_id':document_id,'source_sha256':source[0]['sha256'],'unit_id':unit_id,'source_cells':addresses,'evidence_ids':item['evidence_refs']})
        if source_sum!=Decimal(cost['stated_total']):return None
    except (ValueError,TypeError,KeyError):return None
    return {'method':'source_bound_line_quantities','field':'quantity','value':records,'calculation_id':row['calculation_id'],'independent_id':independent['independent_id'],'rationale':'Karma birimler tek miktarda toplanmaz; her kaynak satırı miktar, birim, fiyat ve tutarıyla uzlaştırılmıştır.'}

def line_quantity_basis(con,offer_id):
    """Use exact source row/label/unit identities; never fuzzy-align unrelated items."""
    active=[x['offer_id'] for x in rows_as_dict(con,"SELECT offer_id FROM offers WHERE status='active'")]
    if offer_id not in active or len(active)<2:return None
    bases={oid:_line_basis(con,oid) for oid in active}
    if not all(bases.values()):return None
    signatures=[{tuple([r['comparison_key'][0],r['comparison_key'][1],tuple(r['comparison_key'][2]),r['comparison_key'][3]]):r['quantity'] for r in b['value']} for b in bases.values()]
    if any(x!=signatures[0] for x in signatures[1:]):return None
    return bases[offer_id]

def incoterm_not_applicable(con,offer_id):
    """Honor the existing explicit same-or-not-stated comparison contract, with no import bridge."""
    cost=_checked_cost(con,offer_id)
    if not cost:return None
    active={x['offer_id'] for x in rows_as_dict(con,"SELECT offer_id FROM offers WHERE status='active'")}
    if offer_id not in active:return None
    facts=rows_as_dict(con,"SELECT offer_id,value_text,evidence_status FROM facts WHERE field_key='incoterms'")
    if any(x['offer_id'] in active and (x['value_text'] or x['evidence_status'] in {'conflicting','unreadable'}) for x in facts):return None
    checks=rows_as_dict(con,"SELECT check_id,dimension,status FROM comparability_checks WHERE dimension IN ('incoterm_basis','scope_identity')")
    if {x['dimension'] for x in checks}!={'incoterm_basis','scope_identity'} or any(x['status']!='pass' for x in checks):return None
    financial=_meta(con,'financial_parameters',{},parse_json=True) or {}
    params=financial.get('offer_parameters',{})
    if any((params.get(oid) or {}).get('import_bridge') for oid in active):return None
    return {'method':'not_applicable','field':'incoterms','value':None,'rationale':'Tüm etkin tekliflerde Incoterm belirtilmemiştir; mevcut kapsam ve teslim şekli karşılaştırma sözleşmesi geçmiştir. Incoterm dönüşümü veya ithalat köprüsü uygulanmaz; teslim taahhüdü ayrıca değerlendirilir.','check_ids':[x['check_id'] for x in checks],'calculation_id':cost[0]['calculation_id'],'independent_id':cost[2]['independent_id']}

def basis(con,offer_id,field):
    if not offer_id:return None
    from scope_ledger import buyer_authority
    buyer=buyer_authority(con,offer_id,field)
    if buyer:
        unknown=isinstance(buyer['value'],dict) and buyer['value'].get('date_status')=='unknown'
        if unknown and not (field=='quote_date' and unknown_quote_is_nonmaterial(con,offer_id)):return None
        return {**buyer,'decision_material':not unknown,'rationale':('Teklif tarihi bilinmiyor; güncel fiyat geçerliliği ayrı kullanıcı kanıtıyla doğrulanmıştır. Tarih/yaş bilgisi uydurulmaz.' if unknown else 'Kaynak/hash/firma/alan kapsamlı kullanıcı cevabı bağımsız doğrulanan hesapta uygulanmıştır.')}
    if field=='quantity':return line_quantity_basis(con,offer_id)
    if field=='incoterms':return incoterm_not_applicable(con,offer_id)
    return None
