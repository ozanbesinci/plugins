"""Read explicit buyer declarations without upgrading supplier evidence."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from common import sha256_file
from db import rows_as_dict


def validate_commercial_input(kind: str, item: dict) -> None:
    """Validate buyer terms without converting events into dated cash flows."""
    base = {'issue_id', 'scope_sha256', 'answer_text', 'kind', 'offer_id',
            'declaration', 'provenance', 'source_hashes'}
    if kind in {'validity_date', 'quote_date'}:
        if set(item) not in ({'date_status', 'value'}, base | {'date_status', 'value'}):
            raise ValueError('Tarih beyanı alanları geçersiz')
        status, value = item.get('date_status'), item.get('value')
        if status == 'unknown':
            if value is not None:
                raise ValueError('Bilinmeyen tarih null olmalıdır')
        elif status == 'known':
            if not isinstance(value, str):
                raise ValueError('Bilinen tarih ISO gün olmalıdır')
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError('Geçersiz tarih') from exc
            if parsed.isoformat() != value:
                raise ValueError('Tarih YYYY-MM-DD olmalıdır')
        else:
            raise ValueError('Tarih known veya unknown olmalıdır')
    elif kind == 'payment_terms':
        if set(item) not in ({'milestones'}, base | {'milestones'}):
            raise ValueError('Ödeme koşulu alanları geçersiz')
        milestones = item.get('milestones')
        if (not isinstance(milestones, list) or len(milestones) != 2 or
                [row.get('trigger') if isinstance(row, dict) else None for row in milestones]
                != ['work_start', 'work_delivery']):
            raise ValueError('Ödeme yalnız işe başlama ve iş teslimi olaylarına bağlanmalıdır')
        for row in milestones:
            if set(row) != {'trigger', 'percent'} or type(row['percent']) not in (int, float) or not 0 <= row['percent'] <= 100:
                raise ValueError('Ödeme yüzdesi 0–100 aralığında sayı olmalıdır')
        if sum(row['percent'] for row in milestones) != 100:
            raise ValueError('Ödeme yüzdelerinin toplamı 100 olmalıdır')
    elif kind == 'warranty_terms':
        if set(item) not in ({'duration_years', 'scope'}, base | {'duration_years', 'scope'}):
            raise ValueError('Garanti koşulu alanları geçersiz')
        years = item.get('duration_years')
        if type(years) is not int or years <= 0 or item.get('scope') != 'whole_work':
            raise ValueError('Garanti pozitif tam yıl ve işin tamamı kapsamı gerektirir')


def inputs_for(con, offer_id: str, kind: str) -> list[dict]:
    """Return current declarations whose cited source documents still match."""
    row = con.execute("SELECT value FROM run_meta WHERE key='financial_parameters'").fetchone()
    try:
        params = json.loads(row[0]) if row else {}
    except (TypeError, ValueError) as exc:
        raise ValueError('financial_parameters geçersiz') from exc
    declared = params.get('buyer_inputs', []) if isinstance(params, dict) else []
    if not isinstance(declared, list):
        raise ValueError('buyer_inputs geçersiz')
    if not declared:
        return []
    parent_row = con.execute("SELECT value FROM run_meta WHERE key='parent_user_response'").fetchone()
    if not parent_row:
        raise ValueError('Alıcı beyanının onaylı yanıt kaydı yok')
    try:
        parent = json.loads(parent_row[0])
        record_path = Path(parent['path'])
        if not record_path.is_file() or sha256_file(record_path) != parent['sha256']:
            raise ValueError('Alıcı yanıtı kaydı eksik veya değişmiş')
        response = json.loads(record_path.read_text(encoding='utf-8'))
        resume = response['authorized_resume']
        if resume['financial_parameters'] != params:
            raise ValueError('Alıcı beyanı onaylı yanıtla eşleşmiyor')
        run_root = Path(resume['run'])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError('Alıcı yanıtı kayıt sözleşmesi geçersiz') from exc
    documents = {r['document_id']: r for r in rows_as_dict(con,
        "SELECT document_id,sha256,offer_id,active,metadata_json FROM documents")}
    active_offer = con.execute("SELECT 1 FROM offers WHERE offer_id=? AND status='active'", [offer_id]).fetchone()
    if not active_offer:
        raise ValueError('Alıcı beyanının aktif teklif hedefi yok')
    result = []
    for item in declared:
        if not isinstance(item, dict) or item.get('offer_id') != offer_id or item.get('kind') != kind:
            continue
        hashes = item.get('source_hashes')
        if (item.get('declaration') != 'buyer_explicit' or
                item.get('provenance') != 'user_response' or
                not item.get('issue_id') or not item.get('scope_sha256') or
                not isinstance(hashes, dict) or not hashes):
            raise ValueError('Alıcı beyanının kapsam/provenance bağı geçersiz')
        if kind in {'payment_terms', 'warranty_terms', 'validity_date', 'quote_date'}:
            validate_commercial_input(kind, item)
        if any(doc_id not in documents or not documents[doc_id]['active'] or
               documents[doc_id]['sha256'] != sha or
               documents[doc_id]['offer_id'] != offer_id
               for doc_id, sha in hashes.items()):
            raise ValueError('Alıcı beyanı kaynak hash bağı stale veya eksik')
        for doc_id, sha in hashes.items():
            try:
                relative = json.loads(documents[doc_id]['metadata_json'] or '{}')['archived_source_path']
                archived = (run_root / relative).resolve()
                if not archived.is_relative_to(run_root.resolve()) or sha256_file(archived) != sha:
                    raise ValueError('Alıcı beyanı kaynak arşivi stale veya eksik')
            except (KeyError, TypeError, json.JSONDecodeError, OSError) as exc:
                raise ValueError('Alıcı beyanı kaynak arşivi stale veya eksik') from exc
        result.append(dict(item))
    return result
