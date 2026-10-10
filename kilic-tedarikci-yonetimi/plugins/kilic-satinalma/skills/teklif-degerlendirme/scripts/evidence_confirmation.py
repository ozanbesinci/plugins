"""Bounded mechanical confirmation before decision sufficiency, without model guesses."""
import json
from decimal import Decimal
from pathlib import Path
from common import json_text, sha256_file, stable_id, utc_now
from db import connect, rows_as_dict
from field_extract import _sheet_candidates, _fold, _has_material_conflict
from normalize import vat_basis


def _matches(fact: dict, candidate: dict) -> bool:
    field = fact['field_key']
    if field in {'total','quantity'}:
        if fact.get('value_number') is None or candidate.get('value_number') is None:
            return False
        if Decimal(str(fact['value_number'])) != Decimal(str(candidate['value_number'])):
            return False
        if field == 'quantity':
            left=_fold(fact.get('unit') or ''); right=_fold(candidate.get('fact_unit') or '')
            if not left or not right or left!=right:
                return False
        return True
    if field == 'quote_date':
        return bool(fact.get('value_date')) and fact.get('value_date') == candidate.get('value_date')
    if field == 'vat':
        fact_basis = vat_basis(fact.get('value_text'))
        candidate_basis = vat_basis(candidate.get('value_text'))
        return fact_basis is not None and fact_basis == candidate_basis
    return bool(fact.get('value_text')) and _fold(str(fact['value_text'])) == _fold(str(candidate.get('value_text') or ''))


def _resolve_confirmation_issues(con, confirmed_now: dict) -> list[str]:
    """Reserved type means only confirmation of exactly the bound pixel facts.

    Commercial approval, extra evidence, empty/partial bindings and stale proofs
    remain open. Recheck current values and independently matched source units,
    not merely the fact's verified label. Store an immutable closure receipt.
    """
    prior = con.execute("SELECT value FROM run_meta WHERE key='independent_confirmation_issue_resolutions'").fetchone()
    audit = json.loads(prior[0]) if prior else {}
    closed = []
    issues = rows_as_dict(con, "SELECT * FROM open_issues WHERE status='open' AND issue_type='independent_confirmation_required' ORDER BY issue_id")
    for issue in issues:
        fids = json.loads(issue['fact_ids_json'] or '[]')
        eids = json.loads(issue['evidence_ids_json'] or '[]')
        if not fids or not eids or len(fids) != len(set(fids)) or len(eids) != len(set(eids)):
            continue
        proofs = []
        for fid in fids:
            facts = rows_as_dict(con, 'SELECT f.* FROM facts f JOIN offers o ON o.offer_id=f.offer_id WHERE f.fact_id=? AND o.status=\'active\'', [fid])
            if len(facts) != 1:
                break
            fact = facts[0]
            detail = json.loads(fact.get('normalized_json') or '{}')
            pointer = detail.get('independent_confirmation', {})
            proof_rows = rows_as_dict(con, 'SELECT * FROM fact_confirmations WHERE confirmation_id=? AND fact_id=?', [pointer.get('confirmation_id'), fid])
            if len(proof_rows) != 1:
                break
            proof = proof_rows[0]
            value = {k:fact.get(k) for k in ('value_text','value_number','value_date','unit','currency')}
            validated = confirmed_now.get((proof['relation_id'], fid))
            if (fact['extraction_path'] != 'vision' or fact['evidence_status'] != 'verified'
                    or fact['evidence_id'] != proof['confirmation_evidence_id']
                    or pointer.get('original_evidence_id') != proof['original_evidence_id']
                    or pointer.get('confirmation_evidence_id') != proof['confirmation_evidence_id']
                    or pointer.get('relation_id') != proof['relation_id']
                    or json.loads(proof['value_json']) != value
                    or not validated
                    or validated['original_sha256'] != proof['original_sha256']
                    or validated['confirmation_sha256'] != proof['confirmation_sha256']):
                break
            original = con.execute('SELECT document_id,source_sha256 FROM evidence WHERE evidence_id=?', [proof['original_evidence_id']]).fetchone()
            confirmation = con.execute('SELECT document_id,source_sha256,evidence_status,extraction_path FROM evidence WHERE evidence_id=?', [proof['confirmation_evidence_id']]).fetchone()
            if original != (validated['target_document_id'], proof['original_sha256']) or confirmation != (validated['source_document_id'], proof['confirmation_sha256'], 'verified', 'independent_structured_confirmation'):
                break
            proofs.append((fact, proof))
        if (len(proofs) != len(fids)
                or {p['original_evidence_id'] for _, p in proofs} != set(eids)
                or len({f['offer_id'] for f, _ in proofs}) != 1):
            continue
        offer_suppliers = []
        for offer_id in sorted({f['offer_id'] for f, _ in proofs}):
            offer = rows_as_dict(con, "SELECT offer_id,supplier_id FROM offers WHERE offer_id=? AND status='active'", [offer_id])
            if len(offer) != 1:
                break
            offer_suppliers.append(offer[0])
        if len(offer_suppliers) != len({f['offer_id'] for f, _ in proofs}):
            continue
        owner = issue.get('owner')
        supplier_ids = {offer.get('supplier_id') for offer in offer_suppliers}
        owner_matches = owner in {'IDARE', 'TUM_FIRMALAR'} or (
            len(supplier_ids) == 1 and None not in supplier_ids
            and owner == f"FIRMA:{next(iter(supplier_ids))}"
        )
        if not owner_matches:
            continue
        at = utc_now()
        receipt = {'rule':'ALL_BOUND_FACTS_INDEPENDENTLY_CONFIRMED_V1', 'owner':owner,
                   'offer_supplier_ids':offer_suppliers, 'resolved_at':at,
                   'fact_ids':sorted(fids), 'original_evidence_ids':sorted(eids),
                   'confirmation_ids':sorted(p['confirmation_id'] for _,p in proofs),
                   'proofs':[{'fact_id':f['fact_id'], 'confirmation_id':p['confirmation_id'],
                              'relation_id':p['relation_id'], 'original_sha256':p['original_sha256'],
                              'confirmation_sha256':p['confirmation_sha256'], 'value':json.loads(p['value_json'])}
                             for f,p in sorted(proofs, key=lambda x:x[0]['fact_id'])]}
        if issue['issue_id'] in audit:
            raise ValueError('Confirmation issue resolution receipt already exists for an open issue')
        audit[issue['issue_id']] = receipt
        con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'", [at,issue['issue_id']])
        closed.append(issue['issue_id'])
    if closed:
        con.execute("INSERT OR REPLACE INTO run_meta(key,value) VALUES ('independent_confirmation_issue_resolutions',?)", [json_text(audit)])
    return closed


def confirm(run_root: Path) -> dict:
    con = connect(run_root)
    result = {'confirmed': [], 'unresolved': []}
    try:
        con.execute('BEGIN TRANSACTION')
        relations = rows_as_dict(con, "SELECT r.*,s.offer_id,s.source_path,s.sha256,t.source_path AS target_path,t.sha256 AS target_sha,t.offer_id AS target_offer,s.active,t.active AS target_active FROM source_relations r JOIN documents s ON s.document_id=r.source_document_id JOIN documents t ON t.document_id=r.target_document_id WHERE r.relation_type='corroborates'")
        confirmed_now = {}
        for relation in relations:
            if not relation['active'] or not relation['target_active'] or relation['offer_id'] != relation['target_offer']:
                raise ValueError('Confirmation relation ownership or activity changed')
            if relation['sha256'] != relation['source_sha256'] or relation['target_sha'] != relation['target_sha256'] or sha256_file(Path(relation['source_path'])) != relation['source_sha256'] or sha256_file(Path(relation['target_path'])) != relation['target_sha256']:
                raise ValueError('Confirmation relation source hash changed')
            units = rows_as_dict(con, 'SELECT * FROM document_units WHERE document_id=?', [relation['source_document_id']])
            candidates = {}
            for unit in units:
                for key, values in _sheet_candidates(unit).items():
                    candidates.setdefault(key, []).extend(c for c in values if float(c.get('score',0)) >= .8)
            facts = rows_as_dict(con, "SELECT * FROM facts WHERE offer_id=? AND extraction_path='vision'", [relation['offer_id']])
            by_field = {f['field_key']: f for f in facts}
            # Same amount alone is insufficient. Match commercial identity
            # anchors before confirming any field; never resolve a conflict.
            anchors = ['currency','quantity','scope_signature','quote_date']
            matching_context = all(key in by_field and by_field[key]['evidence_status'] in {'requires_confirmation','verified'} and candidates.get(key) and not _has_material_conflict(key,candidates[key]) and all(_matches(by_field[key],c) for c in candidates[key]) for key in anchors)
            if not matching_context:
                result['unresolved'].append({'relation_id': relation['relation_id'], 'reason': 'currency/quantity/UOM/scope/date mismatch or missing anchor'})
                continue
            for fact in facts:
                if fact['evidence_status'] not in {'requires_confirmation','verified'} or not fact.get('evidence_id'):
                    continue
                key = fact['field_key']; peers = candidates.get(key, [])
                detail = json.loads(fact.get('normalized_json') or '{}')
                if not peers or _has_material_conflict(key, peers) or not all(_matches(fact,c) for c in peers) or len(detail.get('items', [])) > 1:
                    result['unresolved'].append({'fact_id':fact['fact_id'], 'reason':'unmatched, conflicting or multiple-item source'})
                    continue
                confirmed_now[(relation['relation_id'], fact['fact_id'])] = {
                    'original_sha256':relation['target_sha256'], 'confirmation_sha256':relation['source_sha256'],
                    'target_document_id':relation['target_document_id'], 'source_document_id':relation['source_document_id']}
                if fact['evidence_status'] == 'verified':
                    continue
                original = con.execute('SELECT document_id,source_sha256 FROM evidence WHERE evidence_id=?', [fact['evidence_id']]).fetchone()
                if not original or original[0] != relation['target_document_id'] or original[1] != relation['target_sha256']:
                    raise ValueError('Original pixel evidence hash/ownership mismatch')
                candidate = peers[0]; unit = candidate['source_unit']; locator = json.loads(unit['locator_json'])
                eid = stable_id('confirm_ev', relation['relation_id'], key, json_text(locator), candidate['quote'], length=24)
                cid = stable_id('confirm', relation['relation_id'], fact['fact_id'], fact['evidence_id'], eid, length=24)
                value = {k:fact.get(k) for k in ('value_text','value_number','value_date','unit','currency')}
                con.execute('INSERT OR REPLACE INTO evidence(evidence_id,document_id,unit_id,locator_json,quote,evidence_status,extraction_path,confidence,source_sha256) VALUES (?,?,?,?,?,?,?,?,?)',
                            [eid, relation['source_document_id'], unit['unit_id'], json_text(locator), candidate['quote'], 'verified', 'independent_structured_confirmation', candidate['score'], relation['source_sha256']])
                con.execute('INSERT OR REPLACE INTO fact_confirmations(confirmation_id,fact_id,original_evidence_id,confirmation_evidence_id,relation_id,original_sha256,confirmation_sha256,value_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)',
                            [cid, fact['fact_id'], fact['evidence_id'], eid, relation['relation_id'], relation['target_sha256'], relation['source_sha256'], json_text(value), utc_now()])
                detail['independent_confirmation'] = {'confirmation_id':cid,'original_evidence_id':fact['evidence_id'],'confirmation_evidence_id':eid,'relation_id':relation['relation_id']}
                con.execute("UPDATE facts SET evidence_status='verified',evidence_id=?,normalized_json=?,updated_at=? WHERE fact_id=?", [eid,json_text(detail),utc_now(),fact['fact_id']])
                result['confirmed'].append(fact['fact_id'])
        result['resolved_confirmation_issues'] = _resolve_confirmation_issues(con, confirmed_now)
        con.commit()
        return result
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
