"""Negative/golden regression first executed before the product fix."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
scripts=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(scripts),str(scripts/'tests')]
import test_buyer_costs as fixtures
from common import json_text
from report_model import build_preliminary
from report_delivery import export_preliminary
from openpyxl import load_workbook
import fitz

class PendingBuyerReportTests(unittest.TestCase):
 setUp=fixtures.BuyerCostTests.setUp;tearDown=fixtures.BuyerCostTests.tearDown
 _row=fixtures.BuyerCostTests._row;_install=fixtures.BuyerCostTests._install
 def declarations(self):
  base={k:v for k,v in self._row(26,'q26').items() if k not in {'source_row','quantity_item_id','quantity','unit'}}
  return [self._row(26,'q26'),self._row(27,'q27'),
          {**base,'kind':'validity_date','date_status':'known','value':'2026-10-30'},
          {**base,'kind':'quote_date','date_status':'unknown','value':None}]
 def model(self):
  self._install(self.declarations());return build_preliminary(self.run,'Eksik diğer maliyet; karar verilemedi')
 def test_pending_report_preserves_authoritative_dates_without_verifying_source(self):
  m=self.model();r=m['buyer_declarations']
  self.assertEqual(next(x['value']for x in r if x['kind']=='validity_date'),'2026-10-30')
  self.assertEqual(next(x['value']for x in r if x['kind']=='quote_date'),'Bilinmiyor (kullanıcı yanıtı)')
  self.assertEqual(m['recommendation'],None);self.assertEqual(m['ranking'],[])
  self.assertEqual(self.con.execute('SELECT COUNT(*) FROM calculations').fetchone()[0],0)
 def test_quantity_reference_subtotal_is_separate_from_source_and_tco(self):
  m=self.model();a=m['buyer_quantity_totals'][0]
  self.assertEqual(float(a['source_total']),2547640);self.assertEqual(float(a['quantity_adjusted_total']),2011640)
  self.assertEqual(a['currency'],'TRY');self.assertEqual(a['assurance'],'BUYER_QUANTITY_REFERENCE_ONLY')
  self.assertEqual(self.con.execute("SELECT value_number FROM facts WHERE fact_id='TEZ/total'").fetchone()[0],2547640)
  self.assertEqual(m['calculations'],[])
 def test_all_profiles_show_pending_user_inputs_in_both_reports(self):
  self._install(self.declarations())
  for profile in ('hizli','standart','yuksek_guvence'):
   self.con.execute("INSERT OR REPLACE INTO run_meta VALUES ('profile',?)",[profile]);self.con.commit()
   d=export_preliminary(self.run,'Diğer giderler bilinmiyor')
   self.assertEqual(d['delivery_status'],'READY',d)
   w=load_workbook(d['xlsx']);self.assertTrue(w['Alici Beyanlari'].protection.sheet)
   text='\n'.join(str(c.value)for s in w for row in s for c in row if c.value is not None);w.close()
   self.assertIn('2026-10-30',text);self.assertIn('2011640',text)
   with fitz.open(d['pdf'])as pdf:pdftext='\n'.join(p.get_text()for p in pdf)
   self.assertIn('2026-10-30',pdftext);self.assertIn('2011640',pdftext)
   self.assertEqual(d['decision_assurance'],'NO_DECISION')
 def test_fallback_retains_user_dates_and_quantity_subtotal(self):
  self._install(self.declarations())
  with patch('report_delivery.render_pdf',side_effect=OSError('Primary unavailable')):
   d=export_preliminary(self.run,'Eksik maliyet')
  self.assertEqual(d['delivery_status'],'READY',d)
  with fitz.open(d['pdf'])as pdf:text='\n'.join(p.get_text()for p in pdf).replace('\u2010','-')
  self.assertIn('2026-10-30',text);self.assertIn('2011640',text)
 def test_changed_response_cannot_leak_pending_user_values(self):
  self._install(self.declarations());(self.run/'response.json').write_text('{}',encoding='utf-8')
  m=build_preliminary(self.run,'Yanıt değişti')
  self.assertEqual(m['decision_assurance'],'BLOCKED_INTEGRITY')
  self.assertEqual(m.get('buyer_declarations'),[]);self.assertEqual(m.get('buyer_quantity_totals'),[])
 def test_foreign_quantity_row_cannot_become_pending_amount(self):
  items=self.declarations();items[0]['source_row']['quantity_cell']='E28';self._install(items)
  m=build_preliminary(self.run,'Yabancı satır')
  self.assertEqual(m['decision_assurance'],'BLOCKED_INTEGRITY')
  self.assertEqual(m.get('buyer_quantity_totals'),[])
 def test_changed_source_clears_already_collected_user_values(self):
  self._install(self.declarations());(self.run/'sources/tez.xlsx').write_bytes(b'changed')
  m=build_preliminary(self.run,'Kaynak değişti')
  self.assertEqual(m['decision_assurance'],'BLOCKED_INTEGRITY')
  self.assertEqual(m.get('buyer_declarations'),[]);self.assertEqual(m.get('buyer_quantity_totals'),[])
 def test_unknown_currency_does_not_become_a_zero_or_foreign_money_total(self):
  self.con.execute("DELETE FROM facts WHERE field_key='currency'");self.con.commit()
  m=self.model();self.assertEqual(m['buyer_quantity_totals'],[])
  self.assertEqual(len(m['buyer_declarations']),4)
 def test_missing_source_total_does_not_become_zero(self):
  self.con.execute("DELETE FROM facts WHERE fact_id='TEZ/total'");self.con.commit()
  m=self.model();self.assertEqual(m['buyer_quantity_totals'],[])
  self.assertEqual(len(m['buyer_declarations']),4)
 def test_foreign_offer_declaration_cannot_enter_report(self):
  items=self.declarations();items[0]['offer_id']='FOREIGN';self._install(items)
  m=build_preliminary(self.run,'Yabancı teklif')
  self.assertEqual(m['decision_assurance'],'BLOCKED_INTEGRITY');self.assertEqual(m['buyer_declarations'],[])
if __name__=='__main__':unittest.main(verbosity=2)
