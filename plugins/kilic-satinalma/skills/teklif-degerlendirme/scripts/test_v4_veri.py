"""Business invariants: missing information, eligibility, provenance and corrections."""
import copy
import unittest
from veri_kontrol import CRITICAL_FIELDS, apply_corrections, compare, digest, validate
from teklif_motoru import cost_summary, price_line


def fixture():
    inv={'entries':[{'source_id':'src','sha256':'a'*64}]}
    data={'schema':'teklif-data/v4','analysis_date':'2026-09-26','project':'Synthetic only',
          'offers':[{'id':'a','supplier_id':'a','name':'Sentetik A'}], 'facts':[], 'rfi':[], 'costs':{}, 'requirements':[]}
    values={'total':'100','currency':'TRY','vat':'0.20','quantity':'1','quote_date':'2026-09-20','validity':'2026-10-20','delivery':'2026-10-01','payment':'2026-10-01','incoterms':'DAP','warranty':'24 ay'}
    for field in CRITICAL_FIELDS:
        data['facts'].append({'fact_id':'a/field/'+field,'value':values[field], 'critical':True,
                             'evidence_status':'verified','source_id':'src','source_sha256':'a'*64,'location':'s.1','quote':'Sentetik dayanak '+field})
    data['costs']['a']={'base_date':'2026-09-26','annual_rates':{'TRY':'0.3'},'base_currency':'TRY','fx_rates':{'TRY':{'forex_selling':'1','unit':'1'}},
                       'assumption_sources':'Sentetik kontrollü test parametreleri',
                       'events':[{'event_id':'price','known':True,'owner':'supplier','amount':'100','currency':'TRY','payment_date':'2026-10-01',
                                  'bindings':{'amount':'a/field/total','currency':'a/field/currency','payment_date':'a/field/payment'}}]}
    return data,inv


class DataTests(unittest.TestCase):
    def test_complete_fixture_has_no_open_critical_issue(self):
        d,i=fixture(); result=validate(d,i)
        self.assertEqual(result['status'],'PASS'); self.assertEqual(result['open_issues'],[])

    def test_each_required_field_cannot_disappear(self):
        for key in CRITICAL_FIELDS:
            d,i=fixture(); d['facts']=[f for f in d['facts'] if f['fact_id']!='a/field/'+key]
            self.assertEqual(validate(d,i)['status'],'FAIL',key)

    def test_missing_is_not_zero_and_needs_rfi(self):
        d,i=fixture(); f=d['facts'][0]; f.update(value=None,evidence_status='missing',open_issue='Tutar yok')
        self.assertEqual(validate(d,i)['status'],'FAIL')
        d['rfi']=[{'fact_ids':[f['fact_id']],'owner':'Tedarikçi','question':'Fiyatı teyit edin'}]
        e=d['costs']['a']['events'][0]; e.update(known=False,fact_ids=[f['fact_id']],amount=None,payment_date=None)
        result=validate(d,i)
        self.assertEqual(result['status'],'PASS'); self.assertTrue(result['open_issues'])
        self.assertIsNone(result['costs']['a']['known_present_value_in_base_currency'])

    def test_verified_null_is_rejected(self):
        d,i=fixture(); d['facts'][2]['value']=None
        self.assertEqual(validate(d,i)['status'],'FAIL')

    def test_wrong_source_hash_and_unbound_cost_rejected(self):
        d,i=fixture(); d['facts'][0]['source_sha256']='b'*64
        self.assertEqual(validate(d,i)['status'],'FAIL')
        d,i=fixture(); d['costs']['a']['events'][0]['amount']='1'
        self.assertEqual(validate(d,i)['status'],'FAIL')

    def test_quote_age_and_expiry_both_controlled(self):
        for field,value in [('quote_date','2025-01-01'),('validity','2026-09-01'),('quote_date','2027-01-01')]:
            d,i=fixture(); next(f for f in d['facts'] if f['fact_id']=='a/field/'+field)['value']=value
            self.assertTrue(validate(d,i)['open_issues'])

    def test_spec_requires_matrix_for_each_offer(self):
        d,i=fixture(); d['requirements']=[{'id':'r1','category':'mandatory'}]
        self.assertEqual(validate(d,i)['status'],'FAIL')

    def test_one_supplier_alternatives_cannot_be_scored(self):
        d,i=fixture(); d['scoring']={'suppliers':[], 'criteria':[]}
        self.assertIn('Tek bağımsız', ' '.join(validate(d,i)['failures']))

    def test_fact_correction_updates_bound_cost(self):
        d,i=fixture(); independent=copy.deepcopy(d); independent['facts'][0]['value']='120'
        diff=compare(d,independent)
        verdict={'data_sha256':digest(d),'diff_sha256':digest(diff),'decisions':[{'difference_id':'a/field/total','decision':'independent','reason':'Özgün tutar120', 'replacement':independent['facts'][0]}]}
        corrected=apply_corrections(d,verdict,diff,{'src':'a'*64})
        self.assertEqual(corrected['costs']['a']['events'][0]['amount'],'120')
        self.assertEqual(validate(corrected,i)['status'],'PASS')
        self.assertEqual(d['costs']['a']['events'][0]['amount'],'100')

    def test_independent_cannot_be_accepted_without_applying_fact(self):
        d,_=fixture(); other=copy.deepcopy(d); other['facts'][0]['value']='120'; diff=compare(d,other)
        verdict={'data_sha256':digest(d),'diff_sha256':digest(diff),'decisions':[{'difference_id':'a/field/total','decision':'independent','reason':'Confirmed'}]}
        with self.assertRaises(ValueError): apply_corrections(d,verdict,diff,{'src':'a'*64})

    def test_open_adjudication_cannot_be_final(self):
        d,i=fixture(); other=copy.deepcopy(d); other['free_notes']=['Eksik ek']
        diff=compare(d,other); verdict={'data_sha256':digest(d),'diff_sha256':digest(diff),'decisions':[{'difference_id':'free/0','decision':'open','reason':'RFI bekliyor'}]}
        self.assertTrue(validate(apply_corrections(d,verdict,diff,{'src':'a'*64}),i)['open_issues'])

    def test_stale_verdict_rejected(self):
        d,_=fixture(); diff=compare(d,d)
        with self.assertRaises(ValueError): apply_corrections(d,{'data_sha256':'old','diff_sha256':digest(diff)},diff,{})

    def test_cost_correction_recalculates_scoring_winner(self):
        d,i=fixture()
        second=copy.deepcopy(d['offers'][0]); second.update(id='b',supplier_id='b',name='Sentetik B'); d['offers'].append(second)
        for f in copy.deepcopy(d['facts']):
            f['fact_id']=f['fact_id'].replace('a/','b/',1)
            if f['fact_id']=='b/field/total': f['value']='200'
            d['facts'].append(f)
        d['costs']['a']['annual_rates']['TRY']='0'
        d['costs']['b']=copy.deepcopy(d['costs']['a']); e=d['costs']['b']['events'][0]; e['amount']='200'; e['bindings']={k:v.replace('a/','b/',1) for k,v in e['bindings'].items()}
        d['scoring']={'suppliers':[{'supplier_id':s,'eligible':True} for s in ('a','b')],
                      'criteria':[{'criterion_id':'cost','weight':'100','direction':'lower','values':{'a':'100','b':'200'},
                                   'bindings':{s:{'kind':'cost','offer_id':s,'metric':'known_present_value_in_base_currency'} for s in ('a','b')}}]}
        self.assertEqual(validate(d,i)['status'],'PASS')
        independent=copy.deepcopy(d); independent['facts'][0]['value']='300'; diff=compare(d,independent)
        verdict={'data_sha256':digest(d),'diff_sha256':digest(diff),'decisions':[{'difference_id':'a/field/total','decision':'independent','reason':'Confirmed300','replacement':independent['facts'][0]}]}
        corrected=apply_corrections(d,verdict,diff,{'src':'a'*64}); result=validate(corrected,i)
        self.assertEqual(result['status'],'PASS'); self.assertEqual(result['scoring']['top_tied_supplier_ids'],['b'])
        corrected['scoring']['criteria'][0]['values']['a']='100'
        self.assertEqual(validate(corrected,i)['status'],'FAIL')
        d['costs']['b']['base_currency']='USD'
        self.assertEqual(validate(d,i)['status'],'FAIL')
        d['costs']['b']['base_currency']='TRY'; d['costs']['b']['base_date']='2026-09-25'
        self.assertEqual(validate(d,i)['status'],'FAIL')

    def test_free_item_allowed_and_unknown_event_has_no_fake_date(self):
        result=price_line({'quantity':'1','unit_price':'0','price_unit':'1','vat_rate':'0.2'})
        self.assertEqual(result['total_including_vat'],0)
        d,_=fixture(); p=d['costs']['a']; p['events'].append({'event_id':'unknown','owner':'buyer','known':False,'amount':None,'currency':None,'payment_date':None})
        result=cost_summary(p)
        self.assertEqual(result['status'],'known_subtotal_not_final'); self.assertEqual(result['known_nominal_by_currency']['TRY'],100)


if __name__=='__main__': unittest.main()
