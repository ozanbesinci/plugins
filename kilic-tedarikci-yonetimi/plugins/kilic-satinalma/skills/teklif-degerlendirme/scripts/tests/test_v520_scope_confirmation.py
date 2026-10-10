import json,unittest
import test_v518_transition_contracts as base
from active_records import current_calculations
from common import json_text
from evidence_confirmation import confirm

class ScopeConfirmation(base.TransitionContracts):
    def issue(self,kind='independent_confirmation_required',extra=False):
        keys=['total','currency','quantity','scope_signature','quote_date','payment','delivery','validity']
        refs=['pix-'+key for key in keys]+(['other'] if extra else [])
        self.con.execute("INSERT INTO open_issues(issue_id,owner,severity,issue_type,question,fact_ids_json,evidence_ids_json,status,created_at) VALUES ('rfi','IDARE','critical',?,'Confirm only these cited values',?,?,'open','before')",[kind,json_text(['o/field/'+key for key in keys]),json_text(refs)]);self.con.commit()

    def test_linked_support_cost_is_not_current_decision_calculation(self):
        self.confirmation_sources()
        for cid,oid in [('live','o'),('support','corrob'),('global',None)]:
            self.con.execute("INSERT INTO calculations(calculation_id,offer_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status,updated_at) VALUES (?,?,'cost_summary','{}','{}','fixture','hash','complete','now')",[cid,oid])
        self.con.commit()
        self.assertEqual({r['calculation_id'] for r in current_calculations(self.con)},{'live','global'})
        self.assertEqual(self.con.execute('SELECT count(*) FROM calculations').fetchone()[0],3)

    def test_orphan_calculation_does_not_disappear_silently(self):
        self.con.execute("INSERT INTO calculations(calculation_id,offer_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status,updated_at) VALUES ('orphan','absent','cost_summary','{}','{}','fixture','hash','complete','now')");self.con.commit()
        with self.assertRaisesRegex(ValueError,'Orphan'):
            current_calculations(self.con)

    def test_pure_confirmation_rfi_closes_with_audited_independent_proof(self):
        self.confirmation_sources();self.issue();result=confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0],'resolved')
        audit=json.loads(self.con.execute("SELECT value FROM run_meta WHERE key='independent_confirmation_issue_resolutions'").fetchone()[0])['rfi']
        self.assertEqual(len(audit['confirmation_ids']),8)
        self.assertEqual(audit['rule'],'ALL_BOUND_FACTS_INDEPENDENTLY_CONFIRMED_V1')
        state=self.con.execute("SELECT status,resolved_at FROM open_issues WHERE issue_id='rfi'").fetchone()
        confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status,resolved_at FROM open_issues WHERE issue_id='rfi'").fetchone(),state)
        self.assertEqual(json.loads(self.con.execute("SELECT value FROM run_meta WHERE key='independent_confirmation_issue_resolutions'").fetchone()[0])['rfi'],audit)

    def test_commercial_approval_issue_is_never_auto_closed(self):
        self.confirmation_sources();self.issue('commercial_approval');confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0],'open')

    def test_extra_issue_evidence_keeps_rfi_open(self):
        self.confirmation_sources();self.issue(extra=True);confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0],'open')

    def test_partial_mismatch_keeps_all_fact_confirmation_issue_open(self):
        self.confirmation_sources(('quantity',11));self.issue();confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0],'open')

    def test_changed_verified_value_does_not_inherit_old_confirmation(self):
        self.confirmation_sources();confirm(self.run);self.issue()
        self.con.execute("UPDATE facts SET value_number=999 WHERE field_key='total'");self.con.commit();confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0],'open')

    def test_empty_bindings_do_not_close_reserved_rfi(self):
        self.confirmation_sources();self.issue()
        self.con.execute("UPDATE open_issues SET fact_ids_json='[]',evidence_ids_json='[]' WHERE issue_id='rfi'");self.con.commit();confirm(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM open_issues WHERE issue_id='rfi'").fetchone()[0],'open')

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ScopeConfirmation(name) for name in sorted(ScopeConfirmation.__dict__) if name.startswith('test_'))
