"""Persistent question dependencies. No clock, implicit answer or global agent stop."""
from __future__ import annotations

import argparse
import json
import os
import inspect
import tempfile
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any

from common import json_text, stable_id, utc_now
from db import connect, rows_as_dict


class UserAnswerRequired(RuntimeError):
    """Expected suspension, not a failed model attempt or technical error."""


SOURCE_QUESTIONS = {'source_authority_conflict', 'revision_relation',
                    'supplier_identity_unresolved', 'source_unreadable'}
READ_TASKS = {'document_classification', 'requirements_extraction',
              'offer_semantic_fields', 'visual_source_review'}


def _table_exists(con, name='user_question_waits') -> bool:
    if isinstance(con, sqlite3.Connection):
        return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",[name]).fetchone())
    return name in {row[0] for row in con.execute('SHOW TABLES').fetchall()}


def _ensure(con):
    con.execute('''CREATE TABLE IF NOT EXISTS user_question_waits (
        question_key VARCHAR PRIMARY KEY, issue_id VARCHAR NOT NULL,
        scope_sha256 VARCHAR NOT NULL, question_json VARCHAR NOT NULL,
        dependency_json VARCHAR NOT NULL, state VARCHAR NOT NULL,
        answer_json VARCHAR, created_at VARCHAR NOT NULL)''')


def _publish_control(con, run_root):
    rows = rows_as_dict(con, "SELECT * FROM user_question_waits WHERE state IN ('waiting','new_run_required') ORDER BY created_at,question_key")
    tasks = rows_as_dict(con, "SELECT * FROM task_queue WHERE status='pending'") if _table_exists(con, 'task_queue') else []
    for row in rows:
        row['question'] = json.loads(row.pop('question_json'))
        row['dependency'] = json.loads(row.pop('dependency_json'))
        inferred = {task['task_id'] for task in tasks if _blocks(row, task)}
        row['dependency']['task_ids'] = sorted(set(row['dependency']['task_ids']) | inferred)
    directory = run_root / 'user_wait_control'
    if not directory.resolve().is_relative_to(run_root.resolve()):
        raise ValueError('Bekleme kaydı koşu dışına çıkamaz')
    directory.mkdir(exist_ok=True)
    path = directory / 'state.json'
    data = json_text({'schema':'kilic-question-waits/v1', 'questions':rows}).encode('utf-8')
    if path.is_file() and path.read_bytes() == data: return
    with tempfile.NamedTemporaryFile(dir=directory, prefix='state-', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    try: os.replace(temporary, path)
    finally:
        if temporary.exists(): temporary.unlink()


def _strings(value) -> set[str]:
    return {x for x in value if isinstance(x, str) and x} if isinstance(value, list) else set()


def _references(value) -> set[str]:
    """Exact identifiers only; never infer dependencies from free-form prose."""
    if isinstance(value, dict):
        return set().union(*(_references(v) for k, v in value.items() if k != 'goal')) if value else set()
    if isinstance(value, list):
        return set().union(*(_references(v) for v in value)) if value else set()
    return {value} if isinstance(value, str) else set()


def register(run_root: Path, question: dict, *, task_ids=None, agent_ids=None) -> str:
    """Call before displaying a question. Explicit bindings cover optional/approval asks."""
    if not isinstance(question, dict) or not all(isinstance(question.get(k), str) and question[k].strip()
            for k in ('issue_id', 'scope_sha256', 'question')):
        raise ValueError('Soru kimliği, kapsamı ve metni zorunludur')
    tasks = _strings(task_ids if task_ids is not None else question.get('dependent_task_ids', []))
    agents = _strings(agent_ids if agent_ids is not None else question.get('dependent_agent_ids', []))
    if not tasks and not agents and question.get('issue_type') in {'optional', 'preference', 'approval'}:
        raise ValueError('Bu sorunun cevabını bekleyen ajan veya görev açıkça bağlanmalıdır')
    key = stable_id('user-wait', question['issue_id'], question['scope_sha256'], length=30)
    con = connect(run_root)
    try:
        _ensure(con)
        docs = {d['document_id'] for d in question.get('sources', []) if isinstance(d, dict) and d.get('document_id')}
        offers = {d['offer_id'] for d in question.get('sources', []) if isinstance(d, dict) and d.get('offer_id')}
        facts = _strings(question.get('fact_ids', []))
        fields = {x.rsplit('/field/', 1)[-1] for x in facts if '/field/' in x}
        requirements = set()
        if facts:
            placeholders = ','.join('?' for _ in facts)
            for f in rows_as_dict(con, f'SELECT field_key,offer_id,requirement_id FROM facts WHERE fact_id IN ({placeholders})', sorted(facts)):
                if f['field_key']: fields.add(f['field_key'])
                if f['offer_id']: offers.add(f['offer_id'])
                if f['requirement_id']: requirements.add(f['requirement_id'])
        # Display is bounded to four sources; the dependency must retain every
        # source belonging to the exact supplier, not merely those displayed.
        owner = str(question.get('owner') or '')
        if owner.startswith('FIRMA:'):
            for d in rows_as_dict(con, 'SELECT document_id,offer_id FROM documents WHERE active=true AND supplier_id=?', [owner.removeprefix('FIRMA:')]):
                docs.add(d['document_id'])
                if d['offer_id']: offers.add(d['offer_id'])
        dependency = {'task_ids': sorted(tasks), 'agent_ids': sorted(agents),
                      'document_ids': sorted(docs), 'offer_ids': sorted(offers),
                      'fact_ids': sorted(facts), 'fields': sorted(fields),
                      'requirement_ids': sorted(requirements),
                      'source_question': question.get('issue_type') in SOURCE_QUESTIONS,
                      'aggregate_operation': question.get('issue_type') not in {'optional', 'preference', 'approval'}}
        prior = con.execute('SELECT question_json,dependency_json FROM user_question_waits WHERE question_key=?', [key]).fetchone()
        if prior:
            # Repeated next calls do not create a new ask or reset an answer.
            old = json.loads(prior[1])
            if old != dependency:
                raise ValueError('Soru bağımlılığı değişti; yeni kapsam kimliği gerekir')
            _publish_control(con, run_root)
            return key
        # A materially changed question replaces its old dependency; it never
        # pretends the old question was answered or allows an old-scope reply.
        con.execute("UPDATE user_question_waits SET state='superseded' WHERE issue_id=? AND state IN ('waiting','new_run_required')", [question['issue_id']])
        con.execute('INSERT INTO user_question_waits VALUES (?,?,?,?,?,?,?,?)',
                    [key, question['issue_id'], question['scope_sha256'], json_text(question),
                     json_text(dependency), 'waiting', None, utc_now()])
        con.commit()
        _publish_control(con, run_root)
        return key
    finally:
        con.close()


def active(run_root: Path) -> list[dict]:
    # The tiny control mirror survives a corrupt analytical DB. Before any ask
    # there is no directory; after publication a lost/bad index fails closed.
    directory = run_root / 'user_wait_control'
    if not directory.exists(): return []
    try:
        value = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
        if value.get('schema') != 'kilic-question-waits/v1' or not isinstance(value.get('questions'), list):
            raise ValueError('Invalid wait state')
        for row in value['questions']:
            if row.get('state') not in {'waiting','new_run_required'} or not isinstance(row.get('dependency'),dict):
                raise ValueError('Invalid wait dependency')
        return value['questions']
    except (OSError, ValueError, TypeError) as exc:
        raise UserAnswerRequired('Bekleme kaydı okunamadı; bağlı işler korunarak durduruldu') from exc


def _blocks(row: dict, task: dict, agent_id: str | None = None) -> bool:
    dep = row['dependency']
    if task.get('task_id') in dep['task_ids'] or (agent_id and agent_id in dep['agent_ids']): return True
    payload = task.get('payload_json') or '{}'
    payload = json.loads(payload) if isinstance(payload, str) else payload
    refs = _references(payload) | _references({k: task.get(k) for k in ('document_id', 'offer_id', 'requirement_id')})
    kind = task.get('task_kind')
    if kind in {'decision_summary', 'artifact_visual_review'} and dep['aggregate_operation']: return True
    if dep['source_question']:
        ids = set(dep['document_ids']) | set(dep['offer_ids'])
        return bool(refs & ids) or not ids
    if refs & set(dep['fact_ids']): return True
    if refs & set(dep['requirement_ids']):
        # Requirement IDs are shared by every offer. A supplier-specific ask
        # must not suspend another supplier's assessment of the same criterion.
        firm_scoped = str(row['question'].get('owner') or '').startswith('FIRMA:')
        return not (firm_scoped and dep['offer_ids'] and not (refs & set(dep['offer_ids'])))
    if kind == 'offer_semantic_fields' and refs & set(dep['offer_ids']):
        return bool(_strings(payload.get('fields', [])) & set(dep['fields']))
    if kind in {'technical_exception', 'contract_exception', 'independent_fact_review', 'adjudicate_differences'}:
        # These packets can explicitly name a disjoint subset of facts/fields.
        # A full-offer review without such a subset remains answer-dependent.
        if _strings(payload.get('fact_ids', [])) or _strings(payload.get('fields', [])):
            return bool(_strings(payload.get('fields', [])) & set(dep['fields'])) and bool(refs & set(dep['offer_ids']))
        return bool(refs & set(dep['offer_ids'])) and dep['aggregate_operation']
    return False


def task_waits(run_root: Path, task: dict, *, agent_id=None) -> list[dict]:
    return [row for row in active(run_root) if _blocks(row, task, agent_id)]


def assert_agent_allowed(run_root: Path, agent_id: str, *, task: dict | None = None):
    """Use before the agent's next tool/model/read/write operation, never poll."""
    waits = task_waits(run_root, task or {}, agent_id=agent_id)
    if waits:
        raise UserAnswerRequired('Ajan kullanıcı yanıtını bekliyor: ' + ', '.join(w['issue_id'] for w in waits))


def assert_task_allowed(run_root: Path, task: dict | str, *, agent_id=None):
    if isinstance(task, str):
        con = connect(run_root)
        try:
            rows = rows_as_dict(con, 'SELECT * FROM task_queue WHERE task_id=?', [task])
        finally: con.close()
        if not rows: raise ValueError('Unknown task_id: ' + task)
        task = rows[0]
    waits = task_waits(run_root, task, agent_id=agent_id or os.environ.get('KILIC_AGENT_ID'))
    if waits:
        raise UserAnswerRequired('Görev kullanıcı yanıtını bekliyor: ' + ', '.join(w['issue_id'] for w in waits))


def assert_operation_allowed(run_root: Path, operation: str, *, agent_id=None, task_id=None):
    """Whole-run calculations/reports depend on all unresolved business asks."""
    agent_id = agent_id or os.environ.get('KILIC_AGENT_ID')
    task_id = task_id or os.environ.get('KILIC_TASK_ID')
    rows = active(run_root)
    waits = [r for r in rows if r['dependency']['aggregate_operation'] or
             (agent_id and agent_id in r['dependency']['agent_ids']) or
             (task_id and task_id in r['dependency']['task_ids'])]
    if waits: raise UserAnswerRequired(operation + ': kullanıcı yanıtına bağlı işlem bekletildi')


def guard_run_operation(fn):
    """Guard direct entry points as well as coordinator calls, before any work."""
    @wraps(fn)
    def guarded(*args, **kwargs):
        bound = inspect.signature(fn).bind(*args, **kwargs)
        assert_operation_allowed(Path(bound.arguments['run_root']), fn.__module__ + '.' + fn.__name__)
        return fn(*args, **kwargs)
    return guarded


def run_guarded_main(main):
    """Expected waiting is a control result, never a repair-triggering traceback."""
    try:
        result = main()
        return result if type(result) is int else 0
    except UserAnswerRequired as exc:
        print(json.dumps({'status':'NEEDS_USER_INPUT', 'wait_policy':'dependent_tasks_only_no_timeout',
                          'reason':str(exc)}, ensure_ascii=False))
        return 4


def record_answer(run_root: Path, issue_id: str, scope_sha256: str, answer_text: str,
                  *, sufficient: bool, response_sha256: str, new_run_required=False) -> dict:
    """Only the coordinator's validated, actual answer can release that dependency."""
    if not isinstance(sufficient, bool) or not isinstance(answer_text, str) or not answer_text.strip():
        raise ValueError('Gerçek kullanıcı yanıtı ve açık yeterlilik sonucu zorunludur')
    if answer_text.strip().casefold() in {'devam', 'continue'} and sufficient:
        raise ValueError('Devam ifadesi eksik iş bilgisi veya onay yerine geçmez')
    if not isinstance(response_sha256, str) or len(response_sha256) != 64 or any(c not in '0123456789abcdef' for c in response_sha256):
        raise ValueError('Yanıt kaydının SHA-256 değeri zorunludur')
    key = stable_id('user-wait', issue_id, scope_sha256, length=30)
    con = connect(run_root)
    try:
        if not _table_exists(con): raise ValueError('Bekleyen soru kaydı bulunamadı')
        row = con.execute('SELECT state,answer_json FROM user_question_waits WHERE question_key=?', [key]).fetchone()
        if not row: raise ValueError('Yanıt farklı veya eski soru kapsamına ait')
        payload = json_text({'answer_text': answer_text, 'sufficient': sufficient,
                             'response_sha256': response_sha256, 'new_run_required': new_run_required})
        target = ('new_run_required' if new_run_required else 'answered') if sufficient else 'waiting'
        if row[1] == payload:
            _publish_control(con, run_root)
            return {'status': 'ALREADY_RECORDED', 'state': row[0], 'resumed': False}
        if row[0] != 'waiting': raise ValueError('Cevaplanmış soru değiştirilemez; yeni kapsam gerekir')
        con.execute('UPDATE user_question_waits SET state=?,answer_json=? WHERE question_key=?', [target, payload, key])
        con.commit()
        _publish_control(con, run_root)
        return {'status': 'ANSWER_RECORDED', 'state': target, 'resumed': target == 'answered'}
    finally: con.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--question-file')
    parser.add_argument('--answer-file')
    parser.add_argument('--agent-id')
    parser.add_argument('--task-id')
    args = parser.parse_args()
    root = Path(args.run)
    if sum(bool(x) for x in (args.question_file, args.answer_file, args.agent_id, args.task_id)) != 1:
        parser.error('Bir soru, yanıt, ajan veya görev seçilmelidir')
    if args.question_file:
        q = json.loads(Path(args.question_file).read_text(encoding='utf-8-sig'))
        print(json.dumps({'question_key': register(root, q), 'status': 'DEPENDENT_TASKS_WAITING'}, ensure_ascii=False))
    elif args.answer_file:
        a = json.loads(Path(args.answer_file).read_text(encoding='utf-8-sig'))
        print(json.dumps(record_answer(root, **a), ensure_ascii=False))
    else:
        try:
            if args.task_id: assert_task_allowed(root, args.task_id)
            else: assert_agent_allowed(root, args.agent_id)
        except UserAnswerRequired as exc:
            print(json.dumps({'status':'NEEDS_USER_INPUT','reason':str(exc)}, ensure_ascii=False))
            raise SystemExit(4)
        print(json.dumps({'status':'ALLOWED'}, ensure_ascii=False))


if __name__ == '__main__': main()
