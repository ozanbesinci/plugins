"""Synthetic counterparties and amounts only. Model packets describe the actual canonical IDs and assertion paths."""
import tempfile
import unittest
import os
from pathlib import Path
from test_engine_support import sqlite_modes

from context_packet import decision_packet, task_packet
from db import connect, init_db, set_meta
from task_queue import _add_task


class PacketContractTests(unittest.TestCase):
    def test_partial_scope_is_visible_to_model_before_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';init_db(run,Path(__file__).resolve().parents[2])
            set_meta(run,'decision_status','SUFFICIENT')
            set_meta(run,'comparability_contract',{'ranking_allowed':True})
            set_meta(run,'scope_ledger',{'status':'PARTIAL','blocking_gaps':[]})
            packet=decision_packet(run,100000)['decision_context']
            self.assertEqual(packet['meta']['decision_status'],'PRELIMINARY_ONLY')
            self.assertEqual(packet['pre_output']['deterministic_decision_status'],'SUFFICIENT')
            self.assertEqual(packet['pre_output']['preliminary_reasons'],['scope ledger is PARTIAL'])
            self.assertTrue(packet['pre_output']['recommendation_must_be_null'])

    def test_decision_packet_points_into_result_and_keeps_missing_source_as_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run'
            init_db(run,Path(__file__).resolve().parents[2])
            packet=decision_packet(run,100000)
            contract=packet['decision_context']['claim_contract']
            self.assertEqual(contract['assertion_example']['path'],'comparable_total')
            self.assertIn('result.comparable_total',contract['assertion_path_semantics'])
            self.assertIn('recommendation:null',contract['recommendations'])
            self.assertIn('exact bound assertions',contract['calculated_claims'])

    def test_offer_packet_links_questions_and_quantity_to_own_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run'
            init_db(run,Path(__file__).resolve().parents[2])
            con=connect(run)
            try:
                con.execute("INSERT INTO suppliers(supplier_id,display_name) VALUES ('S','Supplier')")
                con.execute("INSERT INTO offers(offer_id,supplier_id,status) VALUES ('O','S','active')")
                task_id=_add_task(con,'EXTRACT','semantic_extraction','offer_semantic_fields',
                                  {'offer_id':'O','fields':['quantity','scope_signature']},offer_id='O')
                con.commit()
            finally: con.close()
            packet=task_packet(run,task_id,40,100000)
            contract=packet['fact_contract']
            self.assertEqual(contract['allowed_offer_field_keys'],['quantity','scope_signature'])
            self.assertIn('<offer_id>/field/<field_key>',contract['question_fact_scope'])
            self.assertIn('scope_signature',contract['scope_cost_question'])
            self.assertIn('evidence_client_id',contract['aggregate_quantity_evidence'])
            schema=packet['result_schema']
            issue=schema['properties']['open_issues']['items']['$ref']
            self.assertEqual(issue,'#/$defs/open_issue')
            self.assertEqual(packet['documents'],[])

    def test_calculation_names_follow_offer_identity_not_array_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';init_db(run,Path(__file__).resolve().parents[2])
            con=connect(run)
            try:
                for supplier,offer,name,cost in [('S0','Z','Sentetik Tedarikçi Alfa','10100'),('S1','A','Sentetik Tedarikçi Beta','11200')]:
                    con.execute('INSERT INTO suppliers(supplier_id,display_name) VALUES (?,?)',[supplier,name])
                    con.execute("INSERT INTO offers(offer_id,supplier_id,display_name,status) VALUES (?,?,?,'active')",[offer,supplier,name])
                    con.execute("INSERT INTO calculations(calculation_id,offer_id,calculation_type,inputs_json,result_json,calculation_version,input_hash,status,updated_at) VALUES (?,?,'cost_summary','{}',?,'test','hash','complete','now')",['calc-'+offer,offer,'{"comparable_total":"'+cost+'"}'])
                con.commit()
            finally:con.close()
            packet=decision_packet(run,100000)['decision_context']
            self.assertEqual([x['offer_id'] for x in packet['offers']],['Z','A'])
            self.assertEqual([x['offer_id'] for x in packet['calculations']],['A','Z'])
            identity={x['offer_id']:(x['display_name'],x['result']['comparable_total']) for x in packet['calculations']}
            self.assertEqual(identity,{'Z':('Sentetik Tedarikçi Alfa','10100'),'A':('Sentetik Tedarikçi Beta','11200')})

    def test_quantity_search_keeps_specific_price_row_without_generic_header(self):
        for sqlite in sqlite_modes():
            with self.subTest(sqlite=sqlite), tempfile.TemporaryDirectory() as tmp:
                old=os.environ.get('TEKLIF_TEST_SQLITE')
                if sqlite: os.environ['TEKLIF_TEST_SQLITE']='1'
                else: os.environ.pop('TEKLIF_TEST_SQLITE',None)
                try:
                    run=Path(tmp)/'run'; init_db(run,Path(__file__).resolve().parents[2])
                    con=connect(run)
                    try:
                        con.execute("INSERT INTO suppliers(supplier_id,display_name) VALUES ('S','Supplier')")
                        con.execute("INSERT INTO offers(offer_id,supplier_id,status) VALUES ('O','S','active')")
                        con.execute("INSERT INTO documents(document_id,relative_path,filename,format_family,document_role,supplier_id,offer_id,sha256,size_bytes,parse_status,active) VALUES ('D','offer.xlsx','offer.xlsx','xlsx','offer','S','O','hash',10,'read',true)")
                        for i,value in enumerate(('Fiyat Teklifi','İlgisiz açıklama 0','İlgisiz açıklama 1',
                                'Birim fiyat: 10 TL','Miktar: 5 adet','Satır tutarı: 50 TL'),start=1):
                            con.execute("INSERT INTO document_units(unit_id,document_id,unit_type,unit_index,locator_json,text_content,structured_json,content_sha256) VALUES (?, 'D','xlsx_sheet',?,'{}',?,'{}','hash')",[f'U{i}',i,value])
                        task_id=_add_task(con,'EXTRACT','semantic_extraction','offer_semantic_fields',
                            {'offer_id':'O','fields':['quantity'],'document_ids':['D']},offer_id='O')
                        con.commit()
                    finally: con.close()
                    packet=task_packet(run,task_id,6,100000)
                    text=' '.join(row['text_content'] for row in packet['documents'][0]['units'])
                    self.assertIn('Birim fiyat: 10 TL',text)
                    self.assertIn('Miktar: 5 adet',text)
                    self.assertIn('Satır tutarı: 50 TL',text)
                    self.assertNotIn('Fiyat Teklifi',text)
                    self.assertNotIn('İlgisiz açıklama 0',text)
                finally:
                    if old is None: os.environ.pop('TEKLIF_TEST_SQLITE',None)
                    else: os.environ['TEKLIF_TEST_SQLITE']=old


if __name__=='__main__':
    unittest.main()
