"""Consume scoped buyer declarations without rewriting supplier facts."""
from __future__ import annotations
import json
from pathlib import Path
from buyer_inputs import inputs_for
from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict
from active_records import current_calculations


def currency_basis(con, offer_id: str) -> dict | None:
    declared = inputs_for(con, offer_id, 'currency')
    if declared:
        values = {x['value'] for x in declared}
        if len(values) != 1:
            raise ValueError('Conflicting buyer currencies')
        return {'value': values.pop(), 'basis': 'buyer_declaration', 'reference': declared}
    source = con.execute("SELECT fact_id,value_text FROM facts WHERE offer_id=? AND field_key='currency' AND evidence_status='verified' ORDER BY updated_at DESC LIMIT 1", [offer_id]).fetchone()
    if source and source[1]:
        value = str(source[1]).upper()
        if declared and any(x['value'] != value for x in declared):
            raise ValueError('Buyer currency conflicts with the supplier source')
        return {'value': value, 'basis': 'supplier_fact', 'reference': source[0]}
    if not declared:
        return None
    values = {x['value'] for x in declared}
    if len(values) != 1:
        raise ValueError('Conflicting buyer currencies')
    return {'value': values.pop(), 'basis': 'buyer_declaration', 'reference': declared}


def _commercial_basis(con, offer_id: str, kind: str, fields: tuple[str, ...]) -> dict | None:
    declared = inputs_for(con, offer_id, kind)
    if not declared:
        return None
    values = [{field: entry[field] for field in fields} for entry in declared]
    if any(value != values[0] for value in values[1:]):
        raise ValueError(f'Conflicting buyer {kind}')
    # This is a separate buyer authority even if a supplier fact says otherwise.
    return {'value': values[0], 'basis': 'buyer_declaration', 'reference': declared}


def payment_basis(con, offer_id: str) -> dict | None:
    return _commercial_basis(con, offer_id, 'payment_terms', ('milestones',))


def warranty_basis(con, offer_id: str) -> dict | None:
    return _commercial_basis(con, offer_id, 'warranty_terms', ('duration_years', 'scope'))


def date_basis(con, offer_id: str, field: str) -> dict | None:
    if field not in {'validity', 'quote_date'}:
        raise ValueError('Unsupported date field')
    kind = 'validity_date' if field == 'validity' else 'quote_date'
    return _commercial_basis(con, offer_id, kind, ('date_status', 'value'))


def _scope_targets(con, question: dict) -> set[tuple[str, str]]:
    """Only source scope rows actually named by the question's evidence."""
    evidence = set(question.get('evidence_ids') or [])
    # An explicit question locator is narrower than a general scope-signature
    # fact. Do not append unrelated included work to a watering-cost answer.
    if not evidence:
        for fact_id in question.get('fact_ids') or []:
            row = con.execute('SELECT evidence_id FROM facts WHERE fact_id=?', [fact_id]).fetchone()
            if row and row[0]:
                evidence.add(row[0])
    targets = set()
    if evidence:
        for row in rows_as_dict(con, 'SELECT offer_id,scope_id,evidence_ids_json FROM scope_items'):
            try:
                refs = set(json.loads(row.get('evidence_ids_json') or '[]'))
            except (TypeError, ValueError):
                refs = set()
            if refs & evidence:
                targets.add((row['offer_id'], row['scope_id']))
    return targets


def _quantity_targets(con, question: dict) -> set[tuple[str, str]]:
    """Identify exactly the item rows evidenced by this question."""
    issue_evidence = set(question.get('evidence_ids') or [])
    if not issue_evidence:
        return set()
    targets = set()
    refs = question.get('fact_ids') or []
    if not refs:
        return set()
    facts = rows_as_dict(con, 'SELECT fact_id,offer_id,field_key,normalized_json FROM facts WHERE fact_id IN ('
                         + ','.join('?' for _ in refs) + ')', refs)
    if len(facts) != len(refs) or any(f['field_key'] != 'quantity' for f in facts):
        return set()
    for fact in facts:
        try:
            normalized = json.loads(fact.get('normalized_json') or '{}')
        except (TypeError, ValueError):
            return set()
        for item in normalized.get('items', []) if isinstance(normalized, dict) else []:
            if (isinstance(item, dict) and item.get('evidence_status') == 'verified'
                    and set(item.get('evidence_refs') or []) & issue_evidence):
                targets.add((fact['offer_id'], item['item_id']))
    return targets


def _applied(entry: dict, result: dict) -> bool:
    recorded = (result.get('buyer_inputs') or {}).get(entry['kind']) or []
    if entry not in recorded:
        return False
    if entry['kind'] == 'currency':
        return result.get('currency_basis') == 'buyer_declaration' and result.get('currency') == entry['value']
    if entry['kind'] == 'reference_quantity':
        return any(r.get('quantity_item_id') == entry.get('quantity_item_id')
                   and r.get('reference_quantity') == str(entry.get('quantity'))
                   and r.get('unit', '').casefold() == str(entry.get('unit') or '').casefold()
                   for r in result.get('buyer_quantity_rows') or [])
    if entry['kind'] == 'scope_cost':
        return any(s.get('stage') == 'buyer_scope_cost' and s.get('scope_id') == entry.get('scope_id')
                   and s.get('amount') == str(entry.get('amount')) and s.get('currency') == entry.get('currency')
                   for s in result.get('steps') or [])
    if entry['kind'] in {'validity_date', 'quote_date'}:
        return (result.get(entry['kind'] + '_basis') == 'buyer_declaration' and
                result.get(entry['kind']) == {'date_status': entry['date_status'], 'value': entry['value']})
    if entry['kind'] == 'payment_terms':
        return (result.get('payment_basis') == 'buyer_declaration' and
                result.get('payment_terms') == {'milestones': entry.get('milestones')})
    if entry['kind'] == 'warranty_terms':
        return (result.get('warranty_basis') == 'buyer_declaration' and
                result.get('warranty_terms') == {'duration_years': entry.get('duration_years'),
                                                 'scope': entry.get('scope')})
    return False


def _quantity_discrepancy_answered(con, question: dict, entries: list[dict], costs: dict) -> bool:
    """Resolve only evidenced quantity targets using freshly reconciled rows."""
    from buyer_quantity import validated_rows
    refs = question.get('fact_ids') or []
    evidence = set(question.get('evidence_ids') or [])
    if not refs or not evidence or len(refs) != len(set(refs)):
        return False
    facts = rows_as_dict(con, 'SELECT fact_id,offer_id,field_key,normalized_json FROM facts WHERE fact_id IN ('
                         + ','.join('?' for _ in refs) + ')', refs)
    if len(facts) != len(refs) or any(f['field_key'] != 'quantity' or
            f['fact_id'] != f"{f['offer_id']}/field/quantity" for f in facts):
        return False
    available, targets = set(), set()
    for fact in facts:
        try:
            normalized = json.loads(fact.get('normalized_json') or '{}')
        except (TypeError, ValueError):
            return False
        for item in normalized.get('items', []) if isinstance(normalized, dict) else []:
            if not isinstance(item, dict) or not item.get('item_id'):
                continue
            key = (fact['offer_id'], item['item_id'])
            available.add(key)
            if set(item.get('evidence_refs') or []) & evidence:
                targets.add(key)
    answered = {(e['offer_id'], e['quantity_item_id']) for e in entries}
    if not targets or not targets <= answered <= available or len(answered) != len(entries):
        return False
    try:
        for offer_id in {e['offer_id'] for e in entries}:
            selected = [e for e in entries if e['offer_id'] == offer_id]
            rows = validated_rows(con, offer_id, selected, costs.get(offer_id, {}).get('currency'))
            if len(rows) != len(selected):
                return False
    except (ValueError, TypeError, KeyError):
        return False
    return True


def _commercial_targets(con, question: dict, field: str) -> set[str]:
    # These issues ask for more than the field value, regardless of which
    # fact happened to be attached by the issue producer.
    if question.get('issue_type') in {'source_authority_conflict', 'revision_relation',
            'supplier_identity_unresolved', 'requirement_unresolved', 'source_unreadable',
            'comparability_contract', 'scope_comparability', 'payment_comparability'}:
        return set()
    refs = question.get('fact_ids') or []
    if not refs or len(refs) != len(set(refs)) or any(not isinstance(ref, str) for ref in refs):
        return set()
    rows = rows_as_dict(con, 'SELECT fact_id,offer_id,field_key FROM facts WHERE fact_id IN ('
                        + ','.join('?' for _ in refs) + ')', refs)
    absent = set(refs) - {row['fact_id'] for row in rows}
    inferred = set()
    if absent and field in {'validity', 'quote_date'}:
        active = {row['offer_id'] for row in rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active'")}
        inferred = {offer for offer in active if f'{offer}/field/{field}' in absent}
        if {f'{offer}/field/{field}' for offer in inferred} != absent:
            return set()
    if len(rows) + len(inferred) != len(refs) or any(row['field_key'] != field or
            row['fact_id'] != f"{row['offer_id']}/field/{field}" for row in rows):
        return set()
    return {row['offer_id'] for row in rows} | inferred


def _resolve_derived_commercial_aliases(con, active: dict, costs: dict, resolved: list[str]) -> None:
    """Close a renewed single-field question after the same hashed buyer input applied."""
    for issue_id, question in active.items():
        if issue_id in resolved:
            continue
        for kind, field in (('payment_terms', 'payment'), ('warranty_terms', 'warranty'), ('validity_date', 'validity'), ('quote_date', 'quote_date')):
            offers = _commercial_targets(con, question, field)
            if not offers:
                continue
            applied = []
            for offer_id in sorted(offers):
                # inputs_for checks the answer record and every cited source hash.
                declarations = inputs_for(con, offer_id, kind)
                if len(declarations) != 1 or declarations[0].get('issue_id') == issue_id:
                    break
                result = costs.get(offer_id, {})
                if not result.get('known') or not _applied(declarations[0], result):
                    break
                applied.append(declarations[0])
            if len(applied) != len(offers):
                continue
            event = {'issue_id': issue_id, 'scope_sha256': question['scope_sha256'],
                     'original_answer_issue_ids': sorted({entry['issue_id'] for entry in applied}),
                     'buyer_inputs': applied, 'resolution_basis': 'same_source_hashed_buyer_terms_applied',
                     'supplier_facts_modified': False}
            event_id = stable_id('buyer-derived-terms-resolution', issue_id, question['scope_sha256'],
                                 json_text(applied), length=24)
            con.execute("INSERT OR IGNORE INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)",
                        [event_id, 'SUFFICIENCY', 'buyer_response_applied_derived', json_text(event), utc_now()])
            con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'",
                        [utc_now(), issue_id])
            resolved.append(issue_id)
            break



def _derived_currency_targets(con, question: dict, *, allow_missing_currency: bool = False) -> set[str]:
    """Accept exact currency scope, plus an already verified source total if linked.

    A currency declaration can establish the denomination of a verified total;
    it cannot answer a question about an unverified total or another field.
    """
    refs = question.get('fact_ids') or []
    # A comparison contract is a separate multi-offer decision even if its
    # provisional fact refs currently mention only one currency field.
    if question.get('issue_type') in {'comparability_contract', 'scope_comparability',
                                      'payment_comparability'}:
        return set()
    if not refs or len(refs) != len(set(refs)) or any(not isinstance(ref, str) for ref in refs):
        return set()
    rows = rows_as_dict(con, "SELECT fact_id,offer_id,field_key,evidence_status,evidence_id FROM facts WHERE fact_id IN ("
                        + ','.join('?' for _ in refs) + ')', refs)
    if len(rows) != len(refs):
        if not allow_missing_currency or any(not ref.endswith('/field/currency') for ref in refs):
            return set()
        active_offers = {row['offer_id'] for row in rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active'")}
        if any(ref != f'{offer_id}/field/currency' for ref in refs for offer_id in active_offers if ref.startswith(f'{offer_id}/')):
            return set()
        absent = set(refs) - {row['fact_id'] for row in rows}
        inferred = {ref.removesuffix('/field/currency') for ref in absent}
        if inferred - active_offers or len(inferred) != len(absent):
            return set()
    else:
        inferred = set()
    by_offer: dict[str, set[str]] = {}
    evidence = set(question.get('evidence_ids') or [])
    for row in rows:
        offer_id, field = row['offer_id'], row['field_key']
        if row['fact_id'] != f'{offer_id}/field/{field}' or field not in {'currency', 'total'}:
            return set()
        if field == 'total' and (question.get('issue_type') not in {'missing_currency', 'currency_confirmation'}
                                 or row['evidence_status'] != 'verified' or not row['evidence_id']
                                 or row['evidence_id'] not in evidence):
            return set()
        fields = by_offer.setdefault(offer_id, set())
        if field in fields:
            return set()
        fields.add(field)
    if any('currency' not in fields for fields in by_offer.values()):
        return set()
    return set(by_offer) | inferred


def _resolve_derived_currency_aliases(con, active: dict, costs: dict, resolved: list[str]) -> None:
    """Close a second currency question only after the same explicit input took effect."""
    for issue_id, question in active.items():
        if issue_id in resolved:
            continue
        offers = _derived_currency_targets(con, question)
        if not offers:
            continue
        applied = []
        for offer_id in sorted(offers):
            # inputs_for verifies parent response, source archive and document hashes.
            declarations = inputs_for(con, offer_id, 'currency')
            if len(declarations) != 1 or declarations[0].get('issue_id') == issue_id:
                break
            result = costs.get(offer_id, {})
            if not result.get('known') or not _applied(declarations[0], result):
                break
            applied.append(declarations[0])
        if len(applied) != len(offers):
            continue
        original_issues = sorted({entry['issue_id'] for entry in applied})
        event = {'issue_id': issue_id, 'scope_sha256': question['scope_sha256'],
                 'original_answer_issue_ids': original_issues, 'buyer_inputs': applied,
                 'resolution_basis': 'same_source_hashed_currency_declaration_applied',
                 'supplier_facts_modified': False}
        event_id = stable_id('buyer-derived-currency-resolution', issue_id, question['scope_sha256'],
                             json_text(original_issues), json_text(applied), length=24)
        con.execute("INSERT OR IGNORE INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)",
                    [event_id, 'SUFFICIENCY', 'buyer_response_applied_derived', json_text(event), utc_now()])
        con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'",
                    [utc_now(), issue_id])
        resolved.append(issue_id)


def _resolve_field_groups(con,active,costs,resolved):
    """Track each canonical field independently without changing the question identity."""
    from scope_ledger import BUYER_FIELDS,buyer_authority
    active_offers={x['offer_id'] for x in rows_as_dict(con,"SELECT offer_id FROM offers WHERE status='active'")}
    excluded={'source_authority_conflict','revision_relation','supplier_identity_unresolved',
              'requirement_unresolved','source_unreadable','comparability_contract',
              'scope_comparability','payment_comparability','offer_age','offer_validity'}
    for issue_id,q in active.items():
        refs=q.get('fact_ids') or []
        if issue_id in resolved or q['issue_type'] in excluded or not refs or len(refs)!=len(set(refs)):continue
        targets=[]
        for ref in refs:
            parts=ref.rsplit('/field/',1)
            if len(parts)!=2 or parts[0] not in active_offers or parts[1] not in BUYER_FIELDS:break
            row=con.execute('SELECT offer_id,field_key FROM facts WHERE fact_id=?',[ref]).fetchone()
            if row and tuple(row)!=(parts[0],parts[1]):break
            if not row and parts[1] not in {'quote_date','validity'}:break
            targets.append((ref,parts[0],parts[1]))
        if len(targets)!=len(refs):continue
        answered=[]; remaining=[]; proofs=[]
        for ref,offer,field in targets:
            proof=buyer_authority(con,offer,field)
            (answered if proof else remaining).append(ref)
            if proof:proofs.append(proof)
        if not answered:continue
        state={'issue_id':issue_id,'scope_sha256':q['scope_sha256'],
               'answered_fields':answered,'remaining_fields':remaining,'basis':proofs}
        con.execute('INSERT OR REPLACE INTO run_meta(key,value) VALUES (?,?)',
                    ['question_fields:'+issue_id,json_text(state)])
        eid=stable_id('buyer-field-resolution',issue_id,q['scope_sha256'],json_text(state),length=24)
        con.execute('INSERT OR IGNORE INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)',
                    [eid,'SUFFICIENCY','buyer_question_fields_applied',json_text(state),utc_now()])
        if not remaining:
            con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'",[utc_now(),issue_id])
            resolved.append(issue_id)


def _resolve_scoped_aliases(con,active,costs,resolved):
    from effective_fields import _checked_cost,line_quantity_basis
    for issue_id,q in active.items():
        if issue_id in resolved:continue
        proof=None
        if q['issue_type'] in {'unresolved_scope_adjustment','unpriced_employer_responsibility'}:
            targets=_scope_targets(con,q)
            if not targets:continue
            applied=[]
            for offer,scope in sorted(targets):
                entries=[e for e in inputs_for(con,offer,'scope_cost') if e.get('scope_id')==scope]
                if len(entries)!=1 or not _checked_cost(con,offer) or not _applied(entries[0],costs.get(offer,{})):break
                applied.append(entries[0])
            if len(applied)==len(targets):proof={'buyer_inputs':applied,'resolution_basis':'exact_source_scope_cost_applied'}
        elif q['issue_type']=='mixed_unit_quantity':
            refs=q.get('fact_ids') or []
            if not refs or any(not r.endswith('/field/quantity') for r in refs):continue
            bases=[line_quantity_basis(con,r.removesuffix('/field/quantity')) for r in refs]
            if all(bases):proof={'bases':bases,'resolution_basis':'source_bound_mixed_unit_rows_reconciled'}
        if proof:
            event={'issue_id':issue_id,'scope_sha256':q['scope_sha256'],'supplier_facts_modified':False,**proof}
            eid=stable_id('buyer-scoped-alias',issue_id,json_text(event),length=24)
            con.execute('INSERT OR IGNORE INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)',
                        [eid,'SUFFICIENCY','buyer_scoped_alias_resolved',json_text(event),utc_now()])
            con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'",[utc_now(),issue_id])
            resolved.append(issue_id)


def resolve_answered_questions(run_root: Path) -> dict:
    """Close only the original, unchanged question after its calculation succeeds."""
    from user_question_gate import questions
    active = {q['issue_id']: q for q in questions(run_root, limit=10000, include_medium=True, include_low=True)['questions']}
    con = connect(run_root)
    resolved = []
    try:
        if con.execute("SELECT 1 FROM task_queue WHERE status='pending' AND phase IN ('REQUIREMENTS','EXTRACT') LIMIT 1").fetchone():
            return {'resolved': [], 'reason': 'source extraction still pending'}
        costs = {r['offer_id']: json.loads(r['result_json']) for r in current_calculations(con) if r['calculation_type']=='cost_summary'}
        grouped = {}
        for offer in rows_as_dict(con, "SELECT offer_id FROM offers WHERE status='active'"):
            for kind in ('currency','reference_quantity','scope_cost','payment_terms','warranty_terms','validity_date','quote_date'):
                for entry in inputs_for(con, offer['offer_id'], kind):
                    grouped.setdefault(entry['issue_id'], []).append(entry)
                    if _applied(entry,costs.get(offer['offer_id'],{})):
                        # A new gate already consumes a scoped date and therefore
                        # may never regenerate the original question. Record its
                        # actual application independently of question recurrence.
                        event={'issue_id':entry['issue_id'],'scope_sha256':entry['scope_sha256'],
                               'buyer_inputs':[entry],'supplier_facts_modified':False,
                               'resolution_basis':'source_hashed_buyer_basis_applied'}
                        eid=stable_id('buyer-field-basis',json_text(entry),length=24)
                        con.execute("INSERT OR IGNORE INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)",
                                    [eid,'SUFFICIENCY','buyer_basis_applied',json_text(event),utc_now()])
        allowed = {'currency': {'missing_currency','currency_confirmation','critical_field'},
                   'reference_quantity': {'scope_comparability','quantity_scope_confirmation','quantity_discrepancy'},
                   'scope_cost': {'unpriced_employer_responsibility','scope_comparability'},
                   'payment_terms': {'payment_timing_and_basis','payment_terms_confirmation','critical_field'},
                   'warranty_terms': {'missing_warranty','warranty_confirmation','critical_field'}}
        for issue_id, entries in grouped.items():
            q = active.get(issue_id)
            if not q or any(e['scope_sha256'] != q['scope_sha256'] for e in entries):
                continue
            # Currency-only fact scope is sufficient even when an upstream
            # producer uses a new issue_type spelling (for example
            # currency_missing). Mixed-field questions retain the stricter
            # type and verified-total checks below.
            if any(e['kind'] not in {'currency', 'payment_terms', 'warranty_terms', 'validity_date', 'quote_date'}
                   and q['issue_type'] not in allowed[e['kind']]
                   for e in entries):
                continue
            if any(not _applied(entry, costs.get(entry['offer_id'], {})) for entry in entries):
                continue
            kinds = {entry['kind'] for entry in entries}
            if len(kinds) != 1:
                continue
            kind = next(iter(kinds))
            if kind == 'currency':
                target_offers = _derived_currency_targets(con, q, allow_missing_currency=True)
                if not target_offers or target_offers != {entry['offer_id'] for entry in entries}:
                    continue
            elif kind == 'scope_cost':
                targets = _scope_targets(con, q)
                if not targets or targets != {(entry['offer_id'], entry['scope_id']) for entry in entries}:
                    continue
            elif kind in {'payment_terms', 'warranty_terms', 'validity_date', 'quote_date'}:
                field = {'payment_terms':'payment', 'warranty_terms':'warranty', 'validity_date':'validity', 'quote_date':'quote_date'}[kind]
                targets = _commercial_targets(con, q, field)
                if not targets or targets != {entry['offer_id'] for entry in entries} or any(
                        not costs.get(entry['offer_id'], {}).get('known') for entry in entries):
                    continue
            else:
                if q['issue_type'] == 'quantity_discrepancy':
                    if not _quantity_discrepancy_answered(con, q, entries, costs):
                        continue
                else:
                    if q['issue_type'] not in {'quantity_scope_confirmation', 'scope_comparability'}:
                        continue
                    targets = _quantity_targets(con, q)
                    if not targets or targets != {(entry['offer_id'], entry['quantity_item_id']) for entry in entries}:
                        continue
            event = {'issue_id':issue_id,'scope_sha256':q['scope_sha256'],'buyer_inputs':entries,
                     'resolution_basis':'buyer_declaration_applied_to_calculation','supplier_facts_modified':False}
            eid = stable_id('buyer-resolution',issue_id,q['scope_sha256'],json_text(entries),length=24)
            con.execute("INSERT OR IGNORE INTO workflow_events(event_id,phase,event_type,payload_json,created_at) VALUES (?,?,?,?,?)", [eid,'SUFFICIENCY','buyer_response_applied',json_text(event),utc_now()])
            con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'", [utc_now(),issue_id])
            resolved.append(issue_id)
        _resolve_derived_currency_aliases(con, active, costs, resolved)
        _resolve_derived_commercial_aliases(con, active, costs, resolved)
        _resolve_field_groups(con, active, costs, resolved)
        _resolve_scoped_aliases(con, active, costs, resolved)
        con.commit()
        return {'resolved':resolved}
    finally:
        con.close()
