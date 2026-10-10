import json
import tempfile
import unittest
from pathlib import Path
from db import init_db, connect, set_state
from common import json_text
from field_extract import _upsert_fact, _mark_conflicting
from normalize import normalize
from procurement_engine import calculate_costs
from record_results import _upsert_fact as record_fact
from workflow import _completed_verified_result


class TransitionContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name)
        init_db(self.run)
        self.con = connect(self.run)
        self.con.execute("INSERT INTO suppliers(supplier_id,display_name,identification_status) VALUES ('s','Supplier','confirmed')")
        self.con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('o','s','active','[]')")
        for field, number, text in [('total',110000,None),('currency',None,'EUR')]:
            self.con.execute("INSERT INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,evidence_status,critical,extraction_path,normalized_json) VALUES (?,?,?,?,?,?,'verified',true,'semantic_llm','{}')", ['o/field/'+field,'o','s',field,number,text])

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def test_refresh_preserves_three_items_and_evidence_twice(self):
        details = {'items': [{'item_id':str(n),'amount':v,'evidence_refs':['e'+str(n)]} for n,v in enumerate([418500,1046000,1130000])]}
        self.con.execute("UPDATE facts SET value_number=NULL,evidence_status='requires_confirmation',normalized_json=? WHERE fact_id='o/field/total'",[json_text(details)])
        candidates = [{'score':.95,'value_number':v,'quote':str(v),'source_unit':{'document_id':'d','locator_json':'{}'}} for v in [418500,1046000,1130000]]
        for _ in range(2):
            _upsert_fact(self.con,'o','s','total',None)
            _mark_conflicting(self.con,'o','total',candidates)
            row=self.con.execute("SELECT normalized_json,value_number FROM facts WHERE fact_id='o/field/total'").fetchone()
            self.assertEqual(json.loads(row[0]).get('items'),details['items'])
            self.assertIsNone(row[1])

    def add_scope(self,classification,amount,status='verified'):
        self.con.execute("INSERT INTO scope_items(scope_id,offer_id,classification,description,status,amount,currency,evidence_ids_json) VALUES ('scope','o',?,'10 pumps',?,?,'EUR','[]')",[classification,status,amount])

    def cost(self):
        calculate_costs(self.con,{})
        return json.loads(self.con.execute("SELECT result_json FROM calculations WHERE offer_id='o' AND calculation_type='cost_summary'").fetchone()[0])

    def test_included_product_without_separate_price_is_not_unknown_extra(self):
        self.add_scope('included_in_price',None)
        self.assertEqual(self.cost()['unknown_scope_items'],0)

    def test_included_product_price_is_not_added_twice(self):
        self.add_scope('included_in_price',110000)
        self.assertEqual(float(self.cost()['acquisition_cost_basis']),110000)

    def test_unconfirmed_extra_amount_is_not_decision_grade(self):
        self.add_scope('incremental_adjustment',500,'requires_confirmation')
        self.assertFalse(self.cost()['complete'])

    def test_current_of_one_independent_offer_does_not_supersede_other(self):
        self.con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('other','s','active','[\"d2\"]')")
        for did,oid,current in [('d1','o','current'),('d2','other',None)]:
            self.con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,offer_id,revision_status,sha256,size_bytes,parse_status,active) VALUES (?,?,?,'pdf','offer','s',?,?,?,10,'read',true)",[did,did,did,oid,current,did+'hash'])
        self.con.commit()
        normalize(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM offers WHERE offer_id='other'").fetchone()[0],'active')

    def test_pixel_only_verified_number_requires_independent_confirmation(self):
        self.con.execute("INSERT INTO evidence(evidence_id,document_id,locator_json,quote,evidence_status,extraction_path) VALUES ('e','d','{}','110000 EUR','verified','vision')")
        with self.assertRaisesRegex(ValueError,'confirmation|corroboration'):
            record_fact(self.con,{'offer_id':'o','field_key':'total','value_number':110000,'evidence_status':'verified'},'e','vision')

    def test_old_complete_label_without_valid_artifacts_is_not_reused(self):
        self.con.commit()
        set_state(self.run,'COMPLETE','PASS',{})
        (self.run/'output').mkdir()
        (self.run/'output/verification.json').write_text(json.dumps({'status':'VERIFIED'}))
        self.assertIsNone(_completed_verified_result(self.run))

    def test_unknown_extra_remains_incomplete(self):
        self.add_scope('unresolved_adjustment',None)
        self.assertFalse(self.cost()['complete'])

    def confirmation_sources(self, mismatch=None, copied=False, same_offer=False):
        from common import sha256_file
        from source_relations import declare
        self.con.execute("INSERT INTO offers(offer_id,supplier_id,status,source_document_ids_json) VALUES ('corrob','s','active','[\"sheet\"]')")
        for did,oid,fmt,content in [('image','o','image',b'original image'),('sheet','corrob','xlsx',b'original image' if copied else b'independent structured capture')]:
            path=self.run/did; path.write_bytes(content)
            self.con.execute("INSERT INTO documents(document_id,relative_path,source_path,filename,format_family,document_role,supplier_id,offer_id,sha256,size_bytes,parse_status,active) VALUES (?,?,?, ?,?,'offer','s',?,?,?,'read',true)",[did,did,str(path),did,fmt,oid,sha256_file(path),len(content)])
        values={'total':115000,'currency':'EUR','quantity':10,'scope_signature':'Pompa','quote_date':'2026-10-03','payment':'%100 60 gün','delivery':'30 gün','validity':'90 gün'}
        labels={'total':'Genel Toplam','currency':'Para Birimi','quantity':'Miktar','scope_signature':'Ürün','quote_date':'Teklif Tarihi','payment':'Ödeme','delivery':'Teslim','validity':'Geçerlilik'}
        cells=[]
        for idx,(key,value) in enumerate(values.items(),1):
            self.con.execute("INSERT OR REPLACE INTO evidence(evidence_id,document_id,locator_json,quote,evidence_status,extraction_path,source_sha256) VALUES (?,?, '{}',?,'requires_confirmation','vision',?)",['pix-'+key,'image',str(value),sha256_file(self.run/'image')])
            self.con.execute("INSERT OR REPLACE INTO facts(fact_id,offer_id,supplier_id,field_key,value_number,value_text,value_date,unit,evidence_status,evidence_id,extraction_path,normalized_json,critical) VALUES (?,?, 's',?,?,?,?,?,'requires_confirmation',?,'vision','{}',true)",['o/field/'+key,'o',key,value if key in {'total','quantity'} else None,str(value),value if key=='quote_date' else None,'adet' if key=='quantity' else None,'pix-'+key])
            other=mismatch[1] if mismatch and mismatch[0]==key else value
            cells.extend([{'cell':'A'+str(idx),'formula_or_value':labels[key]},{'cell':'B'+str(idx),'formula_or_value':other}])
            if key=='quantity':cells.append({'cell':'C'+str(idx),'formula_or_value':'adet'})
        structure=json_text({'title':'Teklif','cells':cells})
        self.con.execute("INSERT INTO document_units(unit_id,document_id,unit_type,unit_index,locator_json,text_content,structured_json,content_sha256) VALUES ('u','sheet','sheet',1,'{}','',?,'unit-hash')",[structure])
        if same_offer:
            self.con.execute("UPDATE documents SET offer_id='o' WHERE document_id='sheet'")
            self.con.execute("DELETE FROM offers WHERE offer_id='corrob'")
        self.con.commit()
        return declare(self.run,'sheet','image','corroborates',{'authority':'test author','reason':'separately authored same commercial offer','same_offer_confirmed':True,'independent_capture':True})

    def test_explicit_independent_confirmation_matches_115000_with_context(self):
        from evidence_confirmation import confirm
        from source_authority import refresh
        self.confirmation_sources()
        result=confirm(self.run)
        self.assertIn('o/field/total',result['confirmed'])
        row=self.con.execute("SELECT value_number,evidence_status,evidence_id FROM facts WHERE fact_id='o/field/total'").fetchone()
        self.assertEqual(row[:2],(115000,'verified'))
        self.assertNotEqual(row[2],'pix-total')
        self.assertEqual(self.con.execute('SELECT count(*) FROM fact_confirmations').fetchone()[0],8)
        self.assertEqual(confirm(self.run)['confirmed'],[])
        authority=refresh(self.run)
        self.assertEqual(authority['controlling'],1)
        self.assertEqual(authority['unresolved'],0)
        normalize(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM offers WHERE offer_id='o'").fetchone()[0],'active')

    def test_equal_amount_with_quantity_mismatch_cannot_confirm(self):
        from evidence_confirmation import confirm
        self.confirmation_sources(('quantity',11))
        self.assertEqual(confirm(self.run)['confirmed'],[])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/total'").fetchone()[0],'requires_confirmation')

    def test_same_offer_confirmation_keeps_commercial_offer_active(self):
        from source_authority import refresh
        self.confirmation_sources(same_offer=True)
        normalize(self.run);refresh(self.run)
        self.assertEqual(self.con.execute("SELECT status FROM offers WHERE offer_id='o'").fetchone()[0],'active')
        self.assertEqual(self.con.execute("SELECT document_role FROM documents WHERE document_id='sheet'").fetchone()[0],'support')

    def test_empty_quantity_uom_is_not_an_identity_match(self):
        from evidence_confirmation import confirm,_matches
        self.assertFalse(_matches({'field_key':'quantity','value_number':10,'unit':None},{'value_number':10,'fact_unit':None}))
        self.confirmation_sources()
        self.con.execute("UPDATE facts SET unit=NULL WHERE field_key='quantity'")
        structured=json.loads(self.con.execute("SELECT structured_json FROM document_units WHERE unit_id='u'").fetchone()[0])
        structured['cells']=[cell for cell in structured['cells'] if cell['cell']!='C3']
        self.con.execute("UPDATE document_units SET structured_json=? WHERE unit_id='u'",[json_text(structured)]);self.con.commit()
        self.assertEqual(confirm(self.run)['confirmed'],[])

    def test_conflicting_scope_anchor_cannot_authorize_confirmation(self):
        from evidence_confirmation import confirm
        self.confirmation_sources();self.con.execute("UPDATE facts SET evidence_status='conflicting' WHERE field_key='scope_signature'");self.con.commit()
        self.assertEqual(confirm(self.run)['confirmed'],[])

    def test_same_amount_different_product_cannot_confirm(self):
        from evidence_confirmation import confirm
        self.confirmation_sources(('scope_signature','Ağ'))
        self.assertEqual(confirm(self.run)['confirmed'],[])

    def test_same_amount_different_date_cannot_confirm(self):
        from evidence_confirmation import confirm
        self.confirmation_sources(('quote_date','2026-10-04'))
        self.assertEqual(confirm(self.run)['confirmed'],[])

    def test_mismatching_amount_cannot_confirm_total(self):
        from evidence_confirmation import confirm
        self.confirmation_sources(('total',120000))
        result=confirm(self.run)
        self.assertNotIn('o/field/total',result['confirmed'])
        self.assertEqual(self.con.execute("SELECT evidence_status FROM facts WHERE fact_id='o/field/total'").fetchone()[0],'requires_confirmation')

    def test_copied_bytes_are_not_independent_confirmation(self):
        with self.assertRaisesRegex(ValueError,'Identical source copies'):
            self.confirmation_sources(copied=True)
        self.assertEqual(self.con.execute('SELECT count(*) FROM source_relations').fetchone()[0],0)

    def test_changed_confirmation_source_hash_is_rejected(self):
        from evidence_confirmation import confirm
        self.confirmation_sources()
        (self.run/'sheet').write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError,'hash changed'):
            confirm(self.run)
        self.assertEqual(self.con.execute('SELECT count(*) FROM fact_confirmations').fetchone()[0],0)

    def test_half_run_schema_change_is_blocked_before_writes(self):
        from db import set_meta
        from run_compatibility import execution_contract, assert_compatible
        from unittest.mock import patch
        root=Path(__file__).resolve().parents[2]
        original=execution_contract(root)
        self.con.commit();set_meta(self.run,'execution_contract',original)
        changed=dict(original,sha256='new-schema')
        with patch('run_compatibility.execution_contract',return_value=changed):
            with self.assertRaisesRegex(ValueError,'Incompatible run contract'):
                assert_compatible(self.run,root)
        self.assertEqual(self.con.execute('SELECT count(*) FROM model_receipts').fetchone()[0],0)

    def test_unrelated_readme_edit_does_not_change_execution_contract(self):
        from run_compatibility import execution_contract
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'scripts').mkdir();(root/'config').mkdir()
            (root/'scripts/main.py').write_text('x=1')
            before=execution_contract(root)
            (root/'README.md').write_text('new explanation')
            self.assertEqual(before,execution_contract(root))

    def test_stale_dispatched_packet_rejects_result_without_attempt_write(self):
        from run_compatibility import pin_dispatch
        from task_queue import _add_task
        from record_results import record_task_result
        root=Path(__file__).resolve().parents[2]
        tid=_add_task(self.con,'PREPARE','semantic_extraction','document_classification',{},document_id='d');self.con.commit()
        context=self.run/'context.json';context.write_text(json.dumps({'task':{'task_id':tid}}))
        pin_dispatch(self.run,{'task_id':tid},context,root)
        context.write_text(json.dumps({'task':{'task_id':'other'}}))
        with self.assertRaisesRegex(ValueError,'Stale dispatch'):
            record_task_result(self.run,tid,{'document_role':'support'},model_name='fixture',reasoning_effort='high',input_tokens=0,output_tokens=0)
        self.assertEqual(self.con.execute('SELECT attempts FROM task_queue WHERE task_id=?',[tid]).fetchone()[0],0)

    def test_future_migration_refuses_to_stamp_current_schema(self):
        self.con.execute("UPDATE run_meta SET value='99.0.0' WHERE key='schema_version'");self.con.commit()
        with self.assertRaisesRegex(RuntimeError,'Unsupported database schema'):
            init_db(self.run)
        self.assertEqual(self.con.execute("SELECT value FROM run_meta WHERE key='schema_version'").fetchone()[0],'99.0.0')

    def test_supported_old_schema_gains_checked_columns(self):
        self.con.execute("UPDATE run_meta SET value='5.0.5' WHERE key='schema_version'");self.con.commit()
        init_db(self.run)
        self.assertIn('cost_role',{r[1] for r in self.con.execute("PRAGMA table_info('scope_items')").fetchall()})
        self.assertEqual(self.con.execute("SELECT value FROM run_meta WHERE key='schema_version'").fetchone()[0],'5.0.18')

    def test_unreadable_cache_is_retried_after_environment_recovers(self):
        from ingest import _parse_from_cache,_cache_key
        cached={'parser_name':'recoverable','status':'unreadable','units':[],'notes':['dependency missing']}
        self.con.execute('INSERT INTO cache_index(cache_key,source_sha256,parser_name,parser_version,schema_version,result_json) VALUES (?,?,?,?,?,?)',[_cache_key('source','xlsx'),'source','recoverable','5.0.15','5.0.18',json_text(cached)])
        self.con.commit()
        self.assertIsNone(_parse_from_cache(self.run,'source','xlsx'))

    def test_included_scope_independent_calculation_does_not_double_count(self):
        from independent_recompute import _recompute_cost
        self.add_scope('included_in_price',110000)
        cost=self.cost()
        calc=dict(zip(['inputs_json','result_json'],self.con.execute("SELECT inputs_json,result_json FROM calculations WHERE offer_id='o'").fetchone()))
        independent,_=_recompute_cost(self.con,calc)
        self.assertEqual(independent['acquisition_cost_basis'],cost['acquisition_cost_basis'])
        self.assertEqual(float(independent['acquisition_cost_basis']),110000)
