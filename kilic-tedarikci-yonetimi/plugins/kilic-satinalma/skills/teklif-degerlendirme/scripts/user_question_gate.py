"""Source-scoped user questions and auditable, non-verifying responses."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from common import iter_source_files, json_text, sha256_file, stable_id, utc_now
from db import connect, get_meta, rows_as_dict
from buyer_inputs import validate_commercial_input
from run_compatibility import assert_compatible

QUESTION_TYPES = {
    'source_authority_conflict', 'revision_relation', 'supplier_identity_unresolved',
    'critical_field', 'requirement_unresolved', 'source_unreadable',
    'offer_validity', 'offer_age', 'payment_comparability',
    'scope_comparability', 'comparability_contract',
}
INTERNAL_RESOLUTION_ISSUE_TYPES = {'cost_calculation','adjudication_open','parser_error',
    'calculation_error','independent_recompute_failure','qa_failure',
    'independent_confirmation_required'}
FIELD_NAMES = {
    'total': 'teklif toplamı', 'currency': 'para birimi', 'payment': 'ödeme koşulu',
    'delivery': 'teslim koşulu', 'quote_date': 'teklif tarihi', 'validity': 'teklif geçerliliği',
    'quantity': 'miktar', 'unit': 'birim', 'vat': 'KDV esası',
}
COMPARISON_DIMENSIONS = {
    'total': 'teklif toplamı',
    'currency': 'para birimi',
    'quantity': 'ortak miktar ve birim',
    'scope_identity': 'ürün veya kapsam kimliği',
    'currency_basis': 'ortak para birimi ve kur dayanağı',
    'payment_basis': 'ödeme koşullarının karşılaştırma esası',
    'incoterm_basis': 'teslim şeklinin karşılaştırma esası',
    'vat_basis': 'KDV esası',
    'scope_basis': 'teklif kapsamı ve eksik maliyet kalemleri',
}


def _refs(raw: str | None) -> list[str]:
    try:
        value = json.loads(raw or '[]')
        return [str(x) for x in value] if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _question(row: dict, documents: list[dict], comparison_dimension: str | None = None) -> str:
    kind = str(row['issue_type'])
    fact_refs = _refs(row.get('fact_ids_json'))
    field = next((x.rsplit('/field/', 1)[-1] for x in fact_refs if '/field/' in x), None)
    owner = str(row.get('owner') or 'ilgili kapsam')
    if kind in {'source_authority_conflict', 'revision_relation'}:
        return f'{owner} kapsamında hangi belge ve revizyon geçerlidir? Geçerli belge kimliğini ve dayanağını belirtiniz.'
    if kind == 'supplier_identity_unresolved':
        return f'{owner} kapsamındaki belgenin tedarikçi firması hangisidir? Firma kimliğinin dayanağını belirtiniz.'
    if kind == 'critical_field':
        label = FIELD_NAMES.get(field or '', field or 'kritik teklif bilgisi')
        return f'{owner} için {label} hangi belgede ve hangi değerle doğrulanmaktadır? Belge konumunu belirtiniz.'
    if kind == 'requirement_unresolved':
        return f'{owner} için açık kritik şartname maddesini hangi belge ve ifade karşılamaktadır? Kaynak konumunu belirtiniz.'
    if kind == 'source_unreadable':
        return 'Kritik teklif veya şartname kaynağının okunabilir nüshası sağlanabilir mi?'
    if kind in {'offer_validity', 'offer_age'}:
        return f'{owner} için güncel ve geçerli teklif veya yazılı geçerlilik teyidi sağlanabilir mi? Belge tarihini belirtiniz.'
    if kind == 'payment_comparability':
        match=re.search(r'\bfor\s+([A-Z]{3}(?:,\s*[A-Z]{3})*)\s+to compare',str(row.get('question') or ''))
        currencies=match.group(1) if match else 'ilgili para birimlerinde'
        return f'Ödeme koşullarını karşılaştırmak için {currencies} yıllık efektif finansman veya iskonto oranı nedir? Oranların dayanağını belirtiniz.'
    if kind == 'scope_comparability':
        return 'Teklifleri karşılaştırmak için esas alınacak ortak miktar ve birim nedir? Dayanağını belirtiniz.'
    if kind == 'comparability_contract' and comparison_dimension:
        label = COMPARISON_DIMENSIONS.get(comparison_dimension)
        if label:
            return (f'Karşılaştırma için {label} hangi teklif belgelerinde hangi değer veya kapsamla '
                    'doğrulanmaktadır? Belge konumlarını ve karşılaştırma üzerindeki etkisini belirtiniz.')
    label=FIELD_NAMES.get(field or '', field or 'belirtilen ticari alan')
    return f'{owner} için {label} hangi kaynak ve değerle doğrulanmaktadır? Belge konumunu ve karar üzerindeki etkisini belirtiniz.'


def questions(run_root: Path, *, limit: int = 3, include_medium: bool = False, include_low: bool = False) -> dict:
    """Return a bounded group; never convert an issue into verified evidence."""
    con = connect(run_root)
    try:
        # Comparison checks are provisional while bounded source extraction can
        # still supply their missing facts. Keep the issues open for validation,
        # but do not turn them into premature user questions.
        extraction_pending = bool(con.execute("""SELECT count(*) FROM task_queue
            WHERE status='pending' AND phase IN ('REQUIREMENTS','EXTRACT')""").fetchone()[0])
        registry_row = con.execute("SELECT value FROM run_meta WHERE key='generated_issue_ownership_v1'").fetchone()
        registry = json.loads(registry_row[0]) if registry_row else {}
        severities = "('critical','high','medium','low')" if include_low else "('critical','high','medium')" if include_medium else "('critical','high')"
        rows = rows_as_dict(con, f"""SELECT * FROM open_issues WHERE status='open'
            AND severity IN {severities} ORDER BY created_at,owner,issue_id""")
        rows = [r for r in rows if r['issue_type'] in QUESTION_TYPES or
                (r['issue_type'] not in INTERNAL_RESOLUTION_ISSUE_TYPES and
                 (r['owner'] in {'IDARE','TUM_FIRMALAR'} or str(r['owner']).startswith('FIRMA:')))]
        if extraction_pending:
            rows = [r for r in rows if r['issue_type'] != 'comparability_contract']
        selected = rows[:limit]
        result = []
        for row in selected:
            ownership = registry.get(row['issue_id']) or {}
            dimension = ownership.get('key') if ownership.get('component') == 'comparison_contract' else None
            owner = str(row.get('owner') or '')
            supplier_id = owner.removeprefix('FIRMA:') if owner.startswith('FIRMA:') else None
            fact_ids = _refs(row.get('fact_ids_json'))
            evidence_ids = _refs(row.get('evidence_ids_json'))
            docs = rows_as_dict(con, """SELECT d.document_id,d.filename,d.sha256,d.revision_label,d.offer_id,
                   NULL AS locator_json FROM documents d WHERE d.active=true AND d.supplier_id=?
                   ORDER BY d.filename""", [supplier_id]) if supplier_id else []
            if not docs and fact_ids:
                placeholders=','.join('?' for _ in fact_ids)
                docs = rows_as_dict(con, f"""SELECT DISTINCT d.document_id,d.filename,d.sha256,d.revision_label,d.offer_id,e.locator_json
                    FROM facts f JOIN evidence e ON e.evidence_id=f.evidence_id JOIN documents d ON d.document_id=e.document_id
                    WHERE f.fact_id IN ({placeholders}) AND d.active=true ORDER BY d.filename""", fact_ids)
            if not docs and row['issue_type']=='source_authority_conflict':
                docs=rows_as_dict(con,"""SELECT document_id,filename,sha256,revision_label,offer_id,NULL AS locator_json
                    FROM documents WHERE active=true AND document_role='specification' ORDER BY filename""")
            if not docs and row['issue_type']=='source_unreadable':
                docs=rows_as_dict(con,"""SELECT document_id,filename,sha256,revision_label,offer_id,NULL AS locator_json
                    FROM documents WHERE active=true AND parse_status='unreadable' ORDER BY filename""")
            fact_scope=[]
            if fact_ids:
                placeholders=','.join('?' for _ in fact_ids)
                fact_scope=rows_as_dict(con,f"""SELECT fact_id,offer_id,field_key,value_text,value_number,value_date,
                    unit,currency,evidence_status,evidence_id,normalized_json FROM facts
                    WHERE fact_id IN ({placeholders}) ORDER BY fact_id""",fact_ids)
            locations = []
            for d in docs[:4]:
                locations.append({k:d.get(k) for k in ('document_id','filename','sha256','revision_label','offer_id','locator_json')})
            signature = hashlib.sha256(json_text([row['issue_id'],owner,row['severity'],row['issue_type'],row['question'],
                fact_ids,evidence_ids,fact_scope,[(d['document_id'],d['sha256']) for d in docs]]).encode('utf-8')).hexdigest()
            rate_match=re.search(r'\bfor\s+([A-Z]{3}(?:,\s*[A-Z]{3})*)\s+to compare',str(row.get('question') or ''))
            required_currencies=[x.strip() for x in rate_match.group(1).split(',')] if rate_match else []
            state=con.execute("SELECT value FROM run_meta WHERE key=?",['question_fields:'+row['issue_id']]).fetchone()
            partial=json.loads(state[0]) if state else {}
            if partial.get('scope_sha256')!=signature:partial={}
            text=_question(row,docs,dimension)
            if partial.get('answered_fields') and partial.get('remaining_fields'):
                labels=', '.join(FIELD_NAMES.get(x.rsplit('/field/',1)[-1],x.rsplit('/field/',1)[-1]) for x in partial['remaining_fields'])
                text=f'{owner} için yalnız açık kalan alanlar: {labels}. Bilgiyi firma ve alan bazında belirtiniz; bilinmiyorsa bilinmiyor yazınız.'
            result.append({'issue_id':row['issue_id'], 'scope_sha256':signature,
                'owner':owner,'issue_type':row['issue_type'],'severity':row['severity'],
                'question':text,'fact_ids':fact_ids,'evidence_ids':evidence_ids,
                'answered_fields':partial.get('answered_fields',[]),'remaining_fields':partial.get('remaining_fields',fact_ids),
                'sources':locations,'required_currencies':required_currencies,
                'decision_effect':'İlgili hesap, karşılaştırma ve karar çıktısı yanıt ile yeniden doğrulama tamamlanana kadar bekler.'})
        return {'questions':result,'open_question_count':len(rows),'remaining_question_count':max(0,len(rows)-len(result))}
    finally:
        con.close()


def waiting(run_root: Path) -> dict | None:
    state = questions(run_root)
    if not state['questions']:
        return None
    return {'status':'NEEDS_USER_INPUT',**state,'deliverable_artifacts':False,
            'next_action':'Soruların kaynak ve kapsamı teyit edilmelidir; yanıt kayıt altına alındıktan sonra bağlı değerlendirme yeni girdiyle yeniden yürütülür.'}


def source_manifest(source: Path) -> dict[str,str]:
    root=source.resolve()
    files=iter_source_files(root)
    return {str(p.resolve().relative_to(root)) if root.is_dir() else p.name:sha256_file(p)
            for p in sorted(files,key=lambda x:str(x).casefold())}


def _buyer_number(value, field: str) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value,float) and not math.isfinite(value)) or value < 0:
        raise ValueError(f'{field} sıfır veya pozitif sonlu JSON sayı olmalıdır')
    return value


def _buyer_currency(value) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z]{3}', value):
        raise ValueError('Para birimi ISO3 büyük harf kodu olmalıdır')
    return value


def _buyer_declarations(con, response: dict, question: dict) -> list[dict]:
    raw = response.get('buyer_inputs')
    if not isinstance(raw, list) or not raw:
        raise ValueError('buyer_inputs boş olmayan liste olmalıdır')
    registry_row = con.execute("SELECT value FROM run_meta WHERE key='generated_issue_ownership_v1'").fetchone()
    registry = json.loads(registry_row[0]) if registry_row else {}
    ownership = registry.get(question['issue_id']) or {}
    dimension = ownership.get('key') if ownership.get('component') == 'comparison_contract' else None
    issue_type = question['issue_type']
    owner = question['owner']
    scoped_ids = set(question['fact_ids'])
    active = rows_as_dict(con, """SELECT o.offer_id,o.supplier_id,s.display_name FROM offers o
        JOIN suppliers s ON s.supplier_id=o.supplier_id WHERE o.status='active'""")
    offers = {x['offer_id']: x for x in active}
    def normalize_name(value):
        return ' '.join(str(value or '').split()).casefold()
    result = []
    seen = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError('buyer_inputs kayıtları nesne olmalıdır')
        kind = entry.get('kind')
        offer_id = entry.get('offer_id')
        if kind not in {'currency', 'reference_quantity', 'scope_cost', 'payment_terms', 'warranty_terms', 'validity_date', 'quote_date'} or not isinstance(offer_id, str) or offer_id not in offers:
            raise ValueError('Alıcı girdisi türü veya aktif teklif hedefi geçersiz')
        if owner.startswith('FIRMA:') and normalize_name(owner.removeprefix('FIRMA:')) not in {
                normalize_name(offers[offer_id]['supplier_id']), normalize_name(offers[offer_id]['display_name'])}:
            # A source's legal/trading name can differ from the buyer-confirmed
            # supplier display name. Only exact, active question scope can replace
            # that name match; no fuzzy alias or supplier identity is inferred.
            if not scoped_ids:
                raise ValueError('Alıcı girdisi soru sahibinin teklif kapsamı dışında: boş veri bağı')
            placeholders = ','.join('?' for _ in scoped_ids)
            scoped_facts = rows_as_dict(con, f'SELECT fact_id,offer_id FROM facts WHERE fact_id IN ({placeholders})',
                                        sorted(scoped_ids))
            if {f['fact_id'] for f in scoped_facts} != scoped_ids or any(f['offer_id'] != offer_id for f in scoped_facts):
                raise ValueError('Alıcı girdisi soru sahibinin teklif kapsamı dışında: veri bağı')
            source_docs = rows_as_dict(con, 'SELECT document_id FROM documents WHERE offer_id=? AND active=true', [offer_id])
            if not source_docs:
                raise ValueError('Alıcı girdisi soru sahibinin teklif kapsamı dışında: aktif kaynak yok')
            evidence_ids = set(question['evidence_ids'])
            if not evidence_ids:
                raise ValueError('Alıcı girdisi soru sahibinin teklif kapsamı dışında: kanıt bağı yok')
            placeholders = ','.join('?' for _ in evidence_ids)
            scoped_evidence = rows_as_dict(con, f'''SELECT e.evidence_id,d.offer_id,d.active FROM evidence e
                JOIN documents d ON d.document_id=e.document_id WHERE e.evidence_id IN ({placeholders})''',
                sorted(evidence_ids))
            if ({e['evidence_id'] for e in scoped_evidence} != evidence_ids or
                    any(e['offer_id'] != offer_id or not e['active'] for e in scoped_evidence)):
                raise ValueError('Alıcı girdisi soru sahibinin teklif kapsamı dışında: kanıt kaynağı')
        if owner not in {'IDARE', 'TUM_FIRMALAR'} and not owner.startswith('FIRMA:'):
            raise ValueError('Alıcı girdisinin soru sahibi kapsamı belirsiz')
        facts = rows_as_dict(con, "SELECT fact_id,field_key,normalized_json FROM facts WHERE offer_id=?", [offer_id])
        fact_fields = {f['field_key'] for f in facts if f['fact_id'] in scoped_ids}
        synthetic_fields = {x.rsplit('/field/', 1)[1] for x in scoped_ids
                            if x.startswith(f'{offer_id}/field/') or f'/offer/{offer_id}/field/' in x}
        allowed_fields = fact_fields | synthetic_fields
        global_question = owner in {'IDARE', 'TUM_FIRMALAR'}
        if kind == 'currency':
            allowed = ('currency' in allowed_fields or
                       (global_question and issue_type == 'comparability_contract' and dimension in {'currency', 'currency_basis'}))
            if not allowed:
                raise ValueError('Para birimi hedefi soru boyutu/fact_ids dışında')
            if set(entry) != {'kind','offer_id','value'}:
                raise ValueError('Para birimi girdisi alanları geçersiz')
            fields = {'value': _buyer_currency(entry['value'])}
            verified = con.execute("""SELECT value_text FROM facts WHERE offer_id=? AND field_key='currency'
                AND evidence_status='verified' AND value_text IS NOT NULL""", [offer_id]).fetchall()
            if any(str(row[0]).upper() != fields['value'] for row in verified):
                raise ValueError('Alıcı para birimi doğrulanmış tedarikçi para birimiyle çelişiyor')
        elif kind == 'reference_quantity':
            allowed = ('quantity' in allowed_fields or
                       (global_question and (issue_type == 'scope_comparability' or
                                             (issue_type == 'comparability_contract' and dimension == 'quantity'))))
            if not allowed:
                raise ValueError('Miktar hedefi soru boyutu/fact_ids dışında')
            required = {'kind','offer_id','quantity_item_id','quantity','unit'}
            optional = {'unit_price_item_id','source_row'}
            if not required <= set(entry) or set(entry) - required - optional or bool(entry.get('unit_price_item_id')) == bool(entry.get('source_row')):
                raise ValueError('Miktar kaynağı item_id veya source_row ile açıkça belirtilmelidir')
            if not isinstance(entry['quantity_item_id'], str) or not entry['quantity_item_id']:
                raise ValueError('quantity_item_id zorunludur')
            if not isinstance(entry['unit'], str) or not entry['unit'].strip():
                raise ValueError('Birim açıkça belirtilmelidir')
            fields = {'quantity_item_id':entry['quantity_item_id'],
                      'quantity':_buyer_number(entry['quantity'],'quantity'), 'unit':entry['unit'].strip()}
            items = {}
            for fact in facts:
                try:
                    normalized = json.loads(fact.get('normalized_json') or '{}')
                except ValueError:
                    continue
                if isinstance(normalized, dict):
                    items.update({x.get('item_id'):x for x in normalized.get('items', [])
                                  if isinstance(x, dict) and isinstance(x.get('item_id'),str)})
            item_ids = set(items)
            if fields['quantity_item_id'] not in item_ids:
                raise ValueError('quantity_item_id mevcut teklif kalemine bağlanmıyor')
            if entry.get('unit_price_item_id'):
                if not isinstance(entry['unit_price_item_id'], str) or entry['unit_price_item_id'] not in item_ids:
                    raise ValueError('unit_price_item_id mevcut teklif kalemine bağlanmıyor')
                fields['unit_price_item_id'] = entry['unit_price_item_id']
            else:
                source_row = entry['source_row']
                names = {'unit_id','quantity_cell','unit_price_cell','line_total_cell','unit_cell'}
                if not isinstance(source_row, dict) or set(source_row) != names or not all(isinstance(source_row[k],str) and source_row[k] for k in names):
                    raise ValueError('source_row tam kaynak hücre adresleri gerektirir')
                match = con.execute("""SELECT u.structured_json,d.offer_id,d.extension FROM document_units u
                    JOIN documents d ON d.document_id=u.document_id WHERE u.unit_id=? AND d.active=true""", [source_row['unit_id']]).fetchone()
                if not match or match[1] != offer_id or str(match[2]).lower() not in {'.xlsx','.xlsm'}:
                    raise ValueError('source_row aktif teklif XLSX kaynağına bağlanmıyor')
                payload = json.loads(match[0] or '{}')
                cells = {c.get('cell'):c for c in payload.get('cells',[]) if isinstance(c,dict)}
                coords = [source_row[k].upper() for k in ('quantity_cell','unit_price_cell','line_total_cell','unit_cell')]
                if any(c not in cells for c in coords) or len(set(coords)) != 4:
                    raise ValueError('source_row hücreleri mevcut ve ayrı olmalıdır')
                rows = {re.search(r'\d+$', c).group() if re.search(r'\d+$', c) else None for c in coords}
                if len(rows) != 1 or None in rows:
                    raise ValueError('source_row hücreleri aynı satırda olmalıdır')
                for coord in coords[:2]:
                    cell = cells[coord]
                    value = cell.get('formula_or_value')
                    if cell.get('is_formula') or isinstance(value,bool) or not isinstance(value,(int,float)) or (isinstance(value,float) and not math.isfinite(value)):
                        raise ValueError('source_row açık numeric/nonformula miktar ve birim fiyat içermelidir')
                total_cell = cells[coords[2]]
                total_value = total_cell.get('calculated_value') if total_cell.get('is_formula') else total_cell.get('formula_or_value')
                if (total_cell.get('is_formula') and not total_cell.get('calculated_available')) or isinstance(total_value,bool) or not isinstance(total_value,(int,float)) or (isinstance(total_value,float) and not math.isfinite(total_value)):
                    raise ValueError('source_row satır toplamının geçerli hesaplı değeri olmalıdır')
                if not math.isclose(cells[coords[0]]['formula_or_value'] * cells[coords[1]]['formula_or_value'], total_value, rel_tol=1e-9, abs_tol=0.01):
                    raise ValueError('source_row miktar × birim fiyat cached toplamla uyuşmuyor')
                if cells[coords[3]].get('is_formula') or not str(cells[coords[3]].get('formula_or_value') or '').strip():
                    raise ValueError('source_row açık birim hücresi içermelidir')
                refs = items[fields['quantity_item_id']].get('evidence_refs') or []
                if not isinstance(refs,list) or not refs:
                    raise ValueError('source_row item kaynak kanıtına bağlanmıyor')
                evidence = rows_as_dict(con, "SELECT unit_id,locator_json FROM evidence WHERE evidence_id IN (" + ','.join('?' for _ in refs) + ')',refs)
                def colnum(text):
                    n=0
                    for char in text:
                        n=n*26+ord(char)-64
                    return n
                covered=set()
                for ev in evidence:
                    if ev['unit_id'] != source_row['unit_id']:
                        continue
                    try:
                        from xlsx_locator import address as xlsx_address
                        loc=xlsx_address(json.loads(ev['locator_json'] or '{}')) or ''
                    except ValueError:
                        continue
                    m=re.fullmatch(r'([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?',loc)
                    if not m:
                        continue
                    c1,r1,c2,r2=m.group(1),int(m.group(2)),m.group(3) or m.group(1),int(m.group(4) or m.group(2))
                    for coord in coords:
                        cm=re.fullmatch(r'([A-Z]+)(\d+)',coord)
                        if cm and min(colnum(c1),colnum(c2)) <= colnum(cm.group(1)) <= max(colnum(c1),colnum(c2)) and min(r1,r2) <= int(cm.group(2)) <= max(r1,r2):
                            covered.add(coord)
                if covered != set(coords):
                    raise ValueError('source_row hücreleri item evidence locator kapsamına bağlanmıyor')
                fields['source_row'] = dict(source_row)
        elif kind in {'validity_date', 'quote_date'}:
            field = 'validity' if kind == 'validity_date' else 'quote_date'
            if field not in allowed_fields:
                raise ValueError('Tarih hedefi soru boyutu/fact_ids dışında')
            if set(entry) != {'kind', 'offer_id', 'date_status', 'value'}:
                raise ValueError('Tarih beyanı alanları geçersiz')
            fields = {'date_status': entry['date_status'], 'value': entry['value']}
            validate_commercial_input(kind, fields)
        elif kind in {'payment_terms', 'warranty_terms'}:
            field = 'payment' if kind == 'payment_terms' else 'warranty'
            allowed = (field in allowed_fields or
                       (kind == 'payment_terms' and global_question and
                        issue_type == 'comparability_contract' and dimension == 'payment_basis'))
            if not allowed:
                raise ValueError('Ticari koşul soru boyutu/fact_ids dışında')
            if kind == 'payment_terms':
                if set(entry) != {'kind', 'offer_id', 'milestones'}:
                    raise ValueError('Ödeme koşulu alanları geçersiz')
                fields = {'milestones': entry['milestones']}
            else:
                if set(entry) != {'kind', 'offer_id', 'duration_years', 'scope'}:
                    raise ValueError('Garanti koşulu alanları geçersiz')
                fields = {'duration_years': entry['duration_years'], 'scope': entry['scope']}
            validate_commercial_input(kind, fields)
        else:
            allowed = (global_question and issue_type == 'comparability_contract' and dimension == 'scope_basis') or bool({'scope','scope_signature'} & allowed_fields)
            if not allowed:
                raise ValueError('Kapsam maliyeti soru boyutu/fact_ids dışında')
            if set(entry) != {'kind','offer_id','scope_id','amount','currency'} or not isinstance(entry['scope_id'],str):
                raise ValueError('Kapsam maliyeti alanları geçersiz')
            target = rows_as_dict(con, """SELECT scope_id,description,classification,cost_role,evidence_ids_json
                FROM scope_items WHERE scope_id=? AND offer_id=?""", [entry['scope_id'],offer_id])
            if not target:
                raise ValueError('scope_id mevcut teklif kapsamına bağlanmıyor')
            target = target[0]
            related_evidence = set(question['evidence_ids'])
            for fact in facts:
                if fact['fact_id'] in scoped_ids:
                    fact_ev = con.execute('SELECT evidence_id FROM facts WHERE fact_id=?',[fact['fact_id']]).fetchone()
                    if fact_ev and fact_ev[0]:
                        related_evidence.add(fact_ev[0])
            try:
                target_evidence = set(json.loads(target.get('evidence_ids_json') or '[]'))
            except ValueError:
                target_evidence = set()
            if not related_evidence & target_evidence:
                raise ValueError('scope_id soru kanıtıyla bağlanmıyor')
            fields = {'scope_id':entry['scope_id'], 'amount':_buyer_number(entry['amount'],'amount'),
                      'currency':_buyer_currency(entry['currency'])}
        documents = rows_as_dict(con, "SELECT document_id,sha256 FROM documents WHERE active=true AND offer_id=? ORDER BY document_id", [offer_id])
        if not documents:
            raise ValueError('Teklifin aktif kaynak belgesi yok')
        identity = (kind,offer_id,fields.get('scope_id'),fields.get('quantity_item_id'))
        if identity in seen:
            raise ValueError('Aynı hedefe birden fazla alıcı girdisi verilemez')
        seen.add(identity)
        result.append({'issue_id':question['issue_id'],'scope_sha256':question['scope_sha256'],
            'answer_text':response['answer_text'].strip(),'kind':kind,'offer_id':offer_id,**fields,
            'declaration':'buyer_explicit','provenance':'user_response',
            'source_hashes':{d['document_id']:d['sha256'] for d in documents}})
    return result


def open_correction(run_root: Path, offer_id: str, field_key: str, user_message: str) -> dict:
    """Bind an explicit buyer correction to a question; never change source facts."""
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    if not isinstance(offer_id,str) or not isinstance(field_key,str) or field_key not in {'quantity','validity'} or not isinstance(user_message,str) or not user_message.strip() or len(user_message)>6000:
        raise ValueError('Explicit quantity/validity correction message required')
    con=connect(run_root)
    try:
        if con.execute("SELECT 1 FROM workflow_state WHERE phase='COMPLETE' AND status IN ('PASS','PARTIAL')").fetchone():
            raise ValueError('Tamamlanmış koşuya düzeltme eklenemez; yeni koşu gerekir')
        fact=con.execute("SELECT f.fact_id FROM facts f JOIN offers o ON o.offer_id=f.offer_id WHERE f.offer_id=? AND f.field_key=? AND o.status='active'",[offer_id,field_key]).fetchall()
        if len(fact)!=1:raise ValueError('Correction requires one exact active offer/field')
        docs=rows_as_dict(con,'SELECT document_id,sha256,metadata_json FROM documents WHERE offer_id=? AND active=true',[offer_id])
        if not docs:raise ValueError('Correction requires active source documents')
        for doc in docs:
            relative=json.loads(doc['metadata_json'] or '{}').get('archived_source_path')
            archived=(run_root/relative).resolve() if isinstance(relative,str) else None
            if not archived or not archived.is_relative_to(run_root.resolve()) or not archived.is_file() or sha256_file(archived)!=doc['sha256']:
                raise ValueError('Correction source archive integrity failed')
        issue_id=stable_id('buyer_correction',offer_id,field_key,user_message,length=24)
        if not con.execute('SELECT 1 FROM open_issues WHERE issue_id=?',[issue_id]).fetchone():
            con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",[issue_id,'IDARE','critical','critical_field','Açık kullanıcı düzeltmesi: '+user_message,json_text([fact[0][0]]),'[]','open',utc_now()])
            con.execute('INSERT INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)',[stable_id('event',issue_id,length=24),'SUFFICIENCY','buyer_correction_requested',json_text({'offer_id':offer_id,'field_key':field_key,'user_message':user_message,'source_hashes':{d['document_id']:d['sha256'] for d in docs}}),utc_now()])
            con.commit()
    finally:con.close()
    question=next(q for q in questions(run_root,limit=10000,include_medium=True)['questions'] if q['issue_id']==issue_id)
    return {'status':'CORRECTION_QUESTION_OPEN','question':question,'source_facts_changed':False,'issue_resolved':False}

def record_response(run_root: Path, response: dict, next_run: Path) -> dict:
    """Audit an actual user response and create a new-run request. No fact is verified here."""
    assert_compatible(run_root, Path(__file__).resolve().parents[1])
    issue_id = str(response.get('issue_id') or '')
    scope = str(response.get('scope_sha256') or '')
    answer = str(response.get('answer_text') or '').strip()
    kind = str(response.get('answer_kind') or '')
    if not answer or len(answer) > 6000 or kind not in {'financial_rate','new_source','clarification'}:
        raise ValueError('Yanıt metni ve desteklenen answer_kind zorunludur')
    active = {q['issue_id']:q for q in questions(run_root, limit=10000, include_medium=True)['questions']}
    question = active.get(issue_id)
    if not question or question['scope_sha256'] != scope:
        raise ValueError('Soru veya kaynak kapsamı değişti; yanıt eski bağlama yazılamaz')
    con=connect(run_root)
    try:
        source_rows=rows_as_dict(con,"SELECT document_id,sha256,metadata_json FROM documents WHERE active=true")
        for row in source_rows:
            try:
                relative=json.loads(row.get('metadata_json') or '{}').get('archived_source_path')
            except ValueError:
                relative=None
            if not relative or not (run_root/relative).is_file() or sha256_file(run_root/relative)!=row['sha256']:
                raise ValueError('Kaynak arşivinin bütünlüğü bozuldu; yanıt bu koşuya yazılamaz')
    finally:
        con.close()
    source = Path(str(response.get('source') or get_meta(run_root,'source_root',''))).resolve()
    if not source.exists() or next_run.exists() or next_run.resolve()==run_root.resolve():
        raise ValueError('Yeni kaynak mevcut ve yeni koşu yolu boş olmalıdır')
    finance = get_meta(run_root,'financial_parameters',{},parse_json=True) or {}
    structured = kind == 'clarification' and 'buyer_inputs' in response
    declarations = []
    if structured:
        con = connect(run_root)
        try:
            declarations = _buyer_declarations(con, response, question)
        finally:
            con.close()
        finance = dict(finance)
        existing_inputs = finance.get('buyer_inputs', [])
        if not isinstance(existing_inputs, list):
            raise ValueError('Mevcut buyer_inputs biçimi geçersiz')
        for new in declarations:
            for prior in existing_inputs:
                if isinstance(prior,dict) and prior.get('kind') == new['kind'] and prior.get('offer_id') == new['offer_id'] and prior.get('scope_id') == new.get('scope_id') and prior.get('quantity_item_id') == new.get('quantity_item_id') and prior != new:
                    raise ValueError('Mevcut alıcı beyanıyla çelişki var')
        finance['buyer_inputs'] = [*existing_inputs, *declarations]
    if kind == 'financial_rate':
        if question['issue_type'] != 'payment_comparability':
            raise ValueError('Finans oranı yalnız ödeme karşılaştırma sorusuna uygulanabilir')
        currency = str(response.get('currency') or '').upper()
        if not question['required_currencies'] or currency not in question['required_currencies']:
            raise ValueError('Finans oranı bu soruda istenen para birimine ait değildir')
        value = response.get('annual_effective_rate')
        if len(currency)!=3 or not currency.isalpha() or isinstance(value,bool) or not isinstance(value,(int,float)) or not (0 <= value < 1):
            raise ValueError('Para birimi ve 0–1 aralığında yıllık efektif oran gereklidir')
        finance = dict(finance)
        rates = dict(finance.get('discount_rates') or {})
        if currency in rates and rates[currency] != value:
            raise ValueError('Mevcut finans oranıyla çelişki var; yeni koşu girdisi ayrıca incelenmelidir')
        rates[currency] = value
        finance['discount_rates'] = rates
    elif kind == 'new_source':
        if source.resolve() == Path(str(get_meta(run_root,'source_root'))).resolve():
            raise ValueError('Yeni belge kaynağı önceki kaynakla aynı dizin olamaz')
    else:
        # A free-form statement is retained as an answer, not as a source fact.
        source = Path(str(get_meta(run_root,'source_root'))).resolve()
    contract_path=run_root/'run_contract.json'
    if kind!='new_source' and contract_path.is_file():
        contract=json.loads(contract_path.read_text(encoding='utf-8'))
        expected={str(x['relative_path']):str(x['sha256']) for x in contract.get('expected_sources',[])}
        if expected != source_manifest(source):
            raise ValueError('Mevcut kaynak dosyaları hazırlık sonrasında değişti; ayrı yeni kaynak koşusu gereklidir')
    resume_core={'schema':'teklif-resume/v1','source':str(source),'run':str(next_run.resolve()),
                 'profile':get_meta(run_root,'profile','standart'),
                 'analysis_date':get_meta(run_root,'analysis_date'),
                 'financial_parameters':finance or None,
                 'scoring_parameters':get_meta(run_root,'scoring_parameters',{},parse_json=True) or None,
                 'skill_version':(Path(__file__).resolve().parents[1]/'VERSION').read_text(encoding='utf-8').strip()}
    declaration_meta = get_meta(run_root,'supplier_folder_declaration_v1',{},parse_json=True) or {}
    if declaration_meta:
        declaration_path = declaration_meta.get('declaration_file_path')
        declaration_sha = declaration_meta.get('declaration_file_sha256')
        if not isinstance(declaration_path,str) or not isinstance(declaration_sha,str) or not Path(declaration_path).is_file() or sha256_file(Path(declaration_path)) != declaration_sha:
            raise ValueError('Supplier folder declaration path/hash changed; response cannot authorize a new run')
        resume_core['supplier_folder_declaration'] = str(Path(declaration_path).resolve())
        resume_core['supplier_folder_declaration_sha256'] = declaration_sha
    response_content_sha256 = hashlib.sha256(json_text(response).encode('utf-8')).hexdigest()
    payload = {'issue_id':issue_id,'scope_sha256':scope,'answer_text':answer,'answer_kind':kind,
               'response_content_sha256':response_content_sha256,
               'buyer_inputs':declarations if structured else None,
               'source':str(source),'question':question,'recorded_at':utc_now(),
               'authorized_resume':resume_core if kind!='clarification' or structured else None,
               'authorized_source_manifest':source_manifest(source) if kind!='clarification' or structured else None}
    event_id = stable_id('user-response',issue_id,scope,answer,kind,length=30)
    con = connect(run_root)
    try:
        existing = con.execute("SELECT payload_json FROM workflow_events WHERE event_id=? AND event_type='user_response_recorded'",[event_id]).fetchone()
        if existing:
            stored=json.loads(existing[0])
            for field in ('issue_id','scope_sha256','answer_text','answer_kind','response_content_sha256','buyer_inputs','source','question',
                          'authorized_resume','authorized_source_manifest'):
                if stored.get(field)!=payload.get(field):
                    raise ValueError('Önceki yanıt kaydı aynı metinle farklı girdi veya koşuya bağlanamaz')
            path=run_root/'user_responses'/f'{event_id}.resume.json'
            record=run_root/'user_responses'/f'{event_id}.json'
            if record.exists() and json_text(json.loads(record.read_text(encoding='utf-8'))) != existing[0]:
                raise ValueError('Önceki yanıt dosyası audit kaydından farklı; koşu korunur')
            if not record.exists():
                record.parent.mkdir(parents=True,exist_ok=True)
                record.write_text(json.dumps(json.loads(existing[0]),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            return {'status':'ALREADY_RECORDED','event_id':event_id,
                    'resume_request':str(path) if path.is_file() else None,'issue_resolved':False}
        if con.execute('SELECT 1 FROM workflow_state WHERE phase=? AND status IN (?,?)',['COMPLETE','PASS','PARTIAL']).fetchone():
            raise ValueError('Tamamlanmış koşuya kullanıcı yanıtı eklenemez')
        con.execute('INSERT INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)',
                    [event_id,'SUFFICIENCY','user_response_recorded',json_text(payload),payload['recorded_at']])
        con.commit()
    finally:
        con.close()
    folder = run_root/'user_responses'
    folder.mkdir(parents=True,exist_ok=True)
    record_path = folder/f'{event_id}.json'
    record_path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    request = {**resume_core,'user_response_record':str(record_path),'user_response_sha256':sha256_file(record_path)}
    if kind=='clarification' and not structured:
        return {'status':'RECORDED_STILL_WAITING','event_id':event_id,'response_sha256':sha256_file(record_path),
                'issue_resolved':False,'old_artifacts_deliverable':False}
    request_path=folder/f'{event_id}.resume.json'
    request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'RECORDED_NEW_RUN_REQUIRED','event_id':event_id,'response_sha256':sha256_file(record_path),
            'resume_request':str(request_path),'issue_resolved':False,'old_artifacts_deliverable':False}


def main() -> None:
    ap=argparse.ArgumentParser(description='Kaynak kapsamına bağlı kullanıcı yanıtı kaydı')
    ap.add_argument('--run',required=True)
    action=ap.add_mutually_exclusive_group(required=True)
    action.add_argument('--response-file')
    action.add_argument('--correction-file')
    ap.add_argument('--next-run')
    a=ap.parse_args()
    if a.correction_file:
        request=json.loads(Path(a.correction_file).read_text(encoding='utf-8-sig'))
        if not isinstance(request,dict) or set(request)!={'offer_id','field_key','user_message'}:ap.error('Correction fields invalid')
        result=open_correction(Path(a.run),**request)
    else:
        if not a.next_run:ap.error('--next-run required for response')
        result=record_response(Path(a.run),json.loads(Path(a.response_file).read_text(encoding='utf-8-sig')),Path(a.next_run))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
