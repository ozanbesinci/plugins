from __future__ import annotations

import json
from common import json_text, stable_id, utc_now
from db import rows_as_dict

REGISTRY = 'generated_issue_ownership_v1'
SIGNATURE_FIELDS = ('owner', 'severity', 'issue_type', 'question', 'fact_ids_json', 'evidence_ids_json')


def _registry(con):
    row = con.execute('SELECT value FROM run_meta WHERE key=?', [REGISTRY]).fetchone()
    return json.loads(row[0]) if row else {}


def is_generated_issue(con, issue_id):
    return issue_id in _registry(con)


class GeneratedIssues:
    """Resolve only unchanged questions with explicit generator ownership."""
    def __init__(self, con, component):
        self.con, self.component = con, component
        self.registry = _registry(con)
        self.active = set()

    def emit(self, key, owner, severity, issue_type, question, fact_ids):
        signature = dict(zip(SIGNATURE_FIELDS, (owner, severity, issue_type, question, json_text(fact_ids), '[]')))
        iid = stable_id('issue', 'generated', self.component, key, length=22)
        suffix = 0
        while True:
            rows = rows_as_dict(self.con, 'SELECT * FROM open_issues WHERE issue_id=?', [iid])
            row = rows[0] if rows else None
            prior = self.registry.get(iid)
            owned = bool(row and prior and prior['component'] == self.component and prior['key'] == key
                         and all(row.get(f) == prior['signature'][f] for f in SIGNATURE_FIELDS))
            if row is None or owned:
                break
            # An existing unowned or manually edited question must survive intact.
            suffix += 1
            iid = stable_id('issue', 'generated', self.component, key, json_text(signature), suffix, length=22)
        self.con.execute('INSERT OR REPLACE INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at,resolved_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                         [iid, owner, severity, issue_type, question, signature['fact_ids_json'], '[]', 'open', row['created_at'] if row else utc_now(), None])
        self.registry[iid] = {'component': self.component, 'key': key, 'signature': signature}
        self.active.add(iid)
        return iid

    def finish(self, evaluated_keys=None):
        for iid, ownership in self.registry.items():
            if ownership['component'] != self.component or iid in self.active:
                continue
            if evaluated_keys is not None and ownership['key'] not in evaluated_keys:
                continue
            rows = rows_as_dict(self.con, 'SELECT * FROM open_issues WHERE issue_id=?', [iid])
            if rows and all(rows[0].get(f) == ownership['signature'][f] for f in SIGNATURE_FIELDS):
                self.con.execute("UPDATE open_issues SET status='resolved',resolved_at=? WHERE issue_id=? AND status='open'", [utc_now(), iid])
        self.con.execute('INSERT OR REPLACE INTO run_meta(key,value) VALUES (?,?)', [REGISTRY, json_text(self.registry)])
