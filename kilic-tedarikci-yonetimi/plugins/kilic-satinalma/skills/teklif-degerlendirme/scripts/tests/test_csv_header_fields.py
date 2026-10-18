"""Regression from real Work: CSV headers are not verified commercial values."""
import json
from pathlib import Path
import tempfile
import unittest

from db import connect
from field_extract import CRITICAL_FIELDS, _tabular_candidates, extract
from ingest import ingest_source


HEADER = ['firma', 'teklif_no', 'tarih', 'gecerlilik_sonu', 'urun', 'miktar', 'birim',
          'birim_fiyat', 'para_birimi', 'fiyat_kdv_durumu', 'kdv_yuzde', 'iskonto_1_yuzde',
          'iskonto_2_yuzde', 'net_toplam_kdv_haric', 'kdv_tutari', 'toplam_kdv_dahil',
          'teslim_gun', 'teslim_baslangici', 'odeme', 'garanti_ay', 'nakliye', 'paketleme']
DATA = ['SENTETIK ALFA', 'A-001', '2026-10-17', '2026-11-17', 'TEST POMPASI STP-01',
        '10', 'ADET', '1000', 'TRY', 'HARIC', '20', '10', '5', '8550', '1710', '10260',
        '20', 'SIPARIS TARIHI', 'TESLIM VE FATURA GUNUNDE PESIN', '24', 'DAHIL', 'DAHIL']


def unit(rows):
    return {'unit_id': 'fixture-unit', 'document_id': 'fixture-doc', 'unit_type': 'csv_chunk',
            'structured_json': json.dumps({'rows': rows}), 'locator_json': '{}'}


class CsvHeaderFieldTests(unittest.TestCase):
    def test_acceptance_header_and_data_never_become_key_value_facts(self):
        result = _tabular_candidates(unit([HEADER, DATA]))
        self.assertEqual({k: v for k, v in result.items() if v}, {})

    def test_adjacent_named_columns_are_not_each_others_values(self):
        for row in (['Ödeme', 'Garanti'], ['Ürün', 'Miktar', 'Birim'],
                    ['Teslim Gün', 'Teslim Başlangıcı', 'Ödeme']):
            with self.subTest(row=row):
                self.assertFalse(any(_tabular_candidates(unit([row])).values()))

    def test_description_substrings_cannot_become_field_labels(self):
        for text in ('Teslim pompası', 'Garanti uzatma paketi', 'Ödeme kontrol ünitesi', 'Malzeme transfer hattı'):
            with self.subTest(text=text):
                self.assertFalse(any(_tabular_candidates(unit([[text, '5000']])).values()))

    def test_existing_label_value_csv_remains_deterministic(self):
        rows = [['Genel Toplam', '8550'], ['Para Birimi', 'TRY'], ['KDV', 'hariç'],
                ['Teklif Tarihi', '17.10.2026'], ['Geçerlilik', '30 gün'], ['Teslim', '20 gün'],
                ['Ödeme', 'Peşin'], ['Garanti', '24 ay'], ['Ürün', 'Test pompası'], ['Miktar', '10', 'ADET']]
        result = _tabular_candidates(unit(rows))
        self.assertEqual(result['total'][0]['value_number'], 8550)
        self.assertEqual(result['payment'][0]['value_text'], 'Peşin')
        self.assertEqual(result['quantity'][0]['fact_unit'], 'adet')
        self.assertEqual(result['delivery'][0]['value_text'], '20 gün')
        self.assertEqual(result['quote_date'][0]['value_date'], '2026-10-17')

    def test_unlabelled_horizontal_data_does_not_infer_scope_from_filename(self):
        result = _tabular_candidates(unit([DATA]))
        self.assertTrue(all(not result[field] for field in CRITICAL_FIELDS))

    def fixture_run(self, root, text):
        source = root / 'source'; source.mkdir()
        (source / 'Alpha_teklif.csv').write_text(text, encoding='utf-8')
        run = root / 'run'
        ingest_source(source, run)
        con = connect(run)
        try:
            offer = con.execute('SELECT offer_id,supplier_id FROM offers LIMIT 1').fetchone()
            self.assertIsNotNone(offer)
            return run, offer
        finally:
            con.close()

    def test_reextract_preserves_semantic_delivery_instead_of_header_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            run, (offer, supplier) = self.fixture_run(Path(temp), ','.join(HEADER)+'\n'+','.join(DATA)+'\n')
            extract(run)
            con = connect(run)
            try:
                self.assertEqual(con.execute("SELECT count(*) FROM facts WHERE evidence_status='verified'").fetchone()[0], 0)
                # Synthetic unit fixture for an already accepted semantic result;
                # no real model call or production acceptance is claimed.
                con.execute("UPDATE facts SET value_text=?,evidence_status='verified',extraction_path='semantic_llm' WHERE fact_id=?",
                            ['20 gün; sipariş tarihinden', offer+'/field/delivery'])
                con.commit()
            finally:
                con.close()
            extract(run)
            con = connect(run)
            try:
                self.assertEqual(con.execute('SELECT value_text,evidence_status FROM facts WHERE fact_id=?', [offer+'/field/delivery']).fetchone(),
                                 ('20 gün; sipariş tarihinden', 'verified'))
            finally:
                con.close()

    def test_real_conflicting_delivery_pairs_still_require_review(self):
        with tempfile.TemporaryDirectory() as temp:
            run, (offer, _) = self.fixture_run(Path(temp), 'Fiyat Teklifi;Alpha Ltd.\nTeslim;20 gün\nTeslim;30 gün\n')
            extract(run)
            con = connect(run)
            try:
                self.assertEqual(con.execute('SELECT evidence_status FROM facts WHERE fact_id=?', [offer+'/field/delivery']).fetchone()[0], 'conflicting')
            finally:
                con.close()


if __name__ == '__main__':
    unittest.main()
