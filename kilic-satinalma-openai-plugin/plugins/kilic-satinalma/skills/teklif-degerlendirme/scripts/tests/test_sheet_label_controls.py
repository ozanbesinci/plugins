"""Long work descriptions cannot impersonate worksheet field labels."""
import json
import unittest

from field_extract import _has_material_conflict, _sheet_candidates


def sheet(*pairs):
    cells = [{'cell': address, 'formula_or_value': value} for address, value in pairs]
    return {'document_id': 'doc', 'unit_id': 'sheet', 'structured_json': json.dumps(
        {'title': 'ICMAL', 'cells': cells}, ensure_ascii=False)}


class SheetLabelControlsTests(unittest.TestCase):
    def test_technical_description_does_not_turn_category_or_unit_into_delivery_or_scope(self):
        description = ('Çelik hasır bağlantıları tamamlanmış temele beton dökülecektir. '
                       'Malzeme temini, nakliye ve işin teslim edilmesi dahildir.')
        unit = sheet(('B7', description), ('C7', 'BETON'), ('D7', 'M3'),
                     ('B35', 'Teslim Süresi'), ('C35', '15 gün'))
        candidates = _sheet_candidates(unit)
        self.assertEqual([c['value_text'] for c in candidates['delivery']], ['15 gün'])
        self.assertEqual(candidates['scope_signature'], [])
        self.assertFalse(_has_material_conflict('delivery', candidates['delivery']))

    def test_real_short_labels_still_produce_conflicting_peers(self):
        unit = sheet(('A1', 'Teslim'), ('B1', '15 gün'),
                     ('A2', 'Teslim Süresi'), ('B2', '30 gün'),
                     ('A3', 'Malzeme'), ('B3', 'Pompa'))
        candidates = _sheet_candidates(unit)
        self.assertEqual(len(candidates['delivery']), 2)
        self.assertTrue(_has_material_conflict('delivery', candidates['delivery']))
        self.assertEqual([c['value_text'] for c in candidates['scope_signature']], ['Pompa'])


if __name__ == '__main__':
    unittest.main()
