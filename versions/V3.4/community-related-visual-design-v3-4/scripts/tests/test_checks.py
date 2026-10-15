"""Behavioral regression checks for evidence boundaries and defect detection.

Run from skill root: python3 -m unittest discover -s scripts/tests -v
Pixel cases require scripts/requirements-pixel-audit.txt.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_layout
import check_linebreaks
import verify_copy
import quick_validate

try:
    import audit_poster_readability
    from PIL import Image
except ImportError:
    audit_poster_readability = None


class LinebreakChecks(unittest.TestCase):
    def record(self):
        return {'asset_version': 'test-v1', 'expected_group_ids': ['body'], 'groups': [{
            'id': 'body', 'measurement': 'rendered', 'master_text': '请保持通道畅通。',
            'unbreakable_units': ['通道畅通'], 'available_bounds': [0, 0, 500, 200], 'min_line_gap': 10,
            'lines': [{'text': '请保持', 'join_after': '', 'bounds': [10, 10, 250, 60]},
                      {'text': '通道畅通。', 'join_after': '', 'bounds': [10, 90, 330, 60]}]}]}

    def test_valid_current_record(self):
        self.assertEqual(check_linebreaks.evaluate(self.record())['status'], 'pass')

    def test_estimate_does_not_pass(self):
        d = self.record(); d['groups'][0]['measurement'] = 'estimate'
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'unknown')

    def test_lost_negation_fails(self):
        d = self.record(); d['groups'][0]['master_text'] = '请勿保持通道畅通。'
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_punctuation_at_start_fails(self):
        d = self.record(); g = d['groups'][0]
        g['master_text'] = '请保持，通道畅通。'; g['lines'][1]['text'] = '，通道畅通。'
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_split_number_fails(self):
        d = self.record(); g = d['groups'][0]
        g['master_text'] = '120'; g['unbreakable_units'] = ['120']
        g['lines'][0]['text'] = '1'; g['lines'][1]['text'] = '20'
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_each_occurrence_of_unit_checked(self):
        d = self.record(); g = d['groups'][0]
        g['master_text'] = '120及120'; g['unbreakable_units'] = ['120']
        g['lines'][0]['text'] = '120及1'; g['lines'][1]['text'] = '20'
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_original_english_space_preserved(self):
        d = self.record(); g = d['groups'][0]
        g['master_text'] = 'Keep the path clear.'; g['unbreakable_units'] = []
        g['lines'][0].update(text='Keep the', join_after=' '); g['lines'][1]['text'] = 'path clear.'
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'pass')
        g['lines'][0]['join_after'] = ''
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_clipped_line_fails(self):
        d = self.record(); d['groups'][0]['lines'][1]['bounds'][2] = 510
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_overlap_fails(self):
        d = self.record(); d['groups'][0]['lines'][1]['bounds'][1] = 65
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'fail')

    def test_missing_inventory_does_not_pass(self):
        d = self.record(); del d['expected_group_ids']
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'unknown')

    def test_missing_unit_list_does_not_pass(self):
        d = self.record(); del d['groups'][0]['unbreakable_units']
        self.assertEqual(check_linebreaks.evaluate(d)['status'], 'unknown')

    def test_short_last_line_is_hint_not_failure(self):
        d = self.record(); d['groups'][0]['lines'][1]['bounds'][2] = 30
        result = check_linebreaks.evaluate(d)
        self.assertEqual(result['status'], 'pass'); self.assertTrue(result['review_hints'])

    def test_nonfinite_geometry_invalid(self):
        d = self.record(); d['groups'][0]['lines'][0]['bounds'][0] = float('nan')
        with self.assertRaises(ValueError): check_linebreaks.evaluate(d)

    def test_embedded_newline_invalid(self):
        d = self.record(); d['groups'][0]['lines'][0]['text'] = '请\n保持'
        with self.assertRaises(ValueError): check_linebreaks.evaluate(d)


class ExistingChecks(unittest.TestCase):
    def test_canvas_object_required(self):
        with self.assertRaises(ValueError): check_layout.evaluate({'asset_version': 'test', 'canvas': []})

    def test_geometry_estimates_unknown(self):
        result = check_layout.evaluate({'asset_version': 'test', 'canvas': {'width': 100, 'height': 100, 'unit': 'px'}, 'groups': []})
        self.assertEqual(result['status'], 'unknown')

    def test_copy_keeps_spaces_and_punctuation(self):
        self.assertTrue(verify_copy.compare({('en', 'body'): 'Call 120.'}, {('en', 'body'): 'Call120.'}))

    def test_copy_missing_group_fails(self):
        self.assertEqual(verify_copy.compare({('zh', 'body'): '原文'}, {})[0]['error'], 'missing')

    def test_copy_legitimate_pending_status_is_only_a_hint(self):
        data = {('zh', 'body'): '提交后请在待确认列表查看进度。'}
        self.assertEqual(verify_copy.compare(data, data), [])
        self.assertEqual(verify_copy.review_hints(data)[0]['hint'], 'possible_placeholder_language')

    def test_copy_explicit_placeholder_still_fails(self):
        data = {('zh', 'body'): '请前往{{地点}}。'}
        self.assertEqual(verify_copy.compare(data, data)[0]['error'], 'unresolved_placeholder')

    def test_copy_reads_bom_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.json'
            path.write_text(json.dumps([{'id': 'body', 'language': 'zh', 'text': '保持通道畅通。'}]), encoding='utf-8-sig')
            self.assertEqual(verify_copy.read(path), {('zh', 'body'): '保持通道畅通。'})


class SkillMetadataChecks(unittest.TestCase):
    def validate(self, name='sample-skill', description='A focused skill.'):
        with tempfile.TemporaryDirectory() as directory:
            content = '---\nname: '+json.dumps(name)+'\ndescription: '+json.dumps(description)+'\n---\nUseful instructions.\n'
            (Path(directory) / 'SKILL.md').write_text(content, encoding='utf-8-sig')
            return quick_validate.validate_skill(directory)[0]

    def test_valid_bom_skill(self):
        self.assertTrue(self.validate())

    def test_empty_and_whitespace_name_rejected(self):
        for value in ('', '   '):
            with self.subTest(value=value): self.assertFalse(self.validate(name=value))

    def test_empty_and_whitespace_description_rejected(self):
        for value in ('', '   '):
            with self.subTest(value=value): self.assertFalse(self.validate(description=value))


@unittest.skipIf(audit_poster_readability is None, 'Pillow/NumPy unavailable; pixel checks not verified')
class PixelChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        bg = Image.new('RGB', (40, 40), 'white'); bg.save(self.root / 'bg.png')
        self.asset = Image.new('RGBA', (10, 10), 'black'); self.asset.save(self.root / 'asset.png')
        poster = bg.copy(); poster.paste(self.asset, (10, 10), self.asset); poster.save(self.root / 'poster.png')
        self.manifest = {'poster': 'poster.png', 'background': 'bg.png', 'expected_group_ids': ['body'],
                         'groups': [{'id': 'body', 'bbox': [10, 10, 20, 20], 'placed_asset': 'asset.png'}]}

    def tearDown(self):
        self.temp.cleanup()

    def audit(self, encoding='utf-8'):
        path = self.root / 'manifest.json'; path.write_text(json.dumps(self.manifest), encoding=encoding)
        return audit_poster_readability.audit(path, self.root / 'review')

    def test_registered_high_contrast(self):
        result = self.audit()
        self.assertEqual(result['audit_status'], 'pass'); self.assertAlmostEqual(result['groups'][0]['contrast_min'], 21)

    def test_bom_manifest_preserves_contrast_and_inventory_check(self):
        self.assertEqual(self.audit(encoding='utf-8-sig')['audit_status'], 'pass')

    def test_transparent_poster_cannot_pass(self):
        Image.new('RGBA', (40, 40), (255, 255, 255, 0)).save(self.root / 'poster.png')
        with self.assertRaisesRegex(ValueError, 'Poster must be fully opaque'):
            self.audit()

    def test_transparent_background_cannot_pass(self):
        Image.new('RGBA', (40, 40), (255, 255, 255, 0)).save(self.root / 'bg.png')
        with self.assertRaisesRegex(ValueError, 'Background must be fully opaque'):
            self.audit()

    def test_palette_transparency_cannot_bypass_check(self):
        background = Image.new('P', (40, 40), 0)
        background.putpalette([255, 255, 255] + [0, 0, 0] * 255)
        background.save(self.root / 'bg.png', transparency=0)
        with self.assertRaisesRegex(ValueError, 'Background must be fully opaque'):
            self.audit()

    def test_unmeasured_group_cannot_pass_inventory(self):
        self.manifest['expected_group_ids'].append('unmeasured')
        result = self.audit()
        self.assertEqual(result['pixel_contrast_status'], 'pass'); self.assertEqual(result['audit_status'], 'fail')

    def test_no_inventory_unknown(self):
        del self.manifest['expected_group_ids']
        self.assertEqual(self.audit()['audit_status'], 'unknown')

    def test_stale_export_unknown(self):
        Image.new('RGB', (40, 40), 'white').save(self.root / 'poster.png')
        self.assertEqual(self.audit()['audit_status'], 'unknown')

    def test_low_contrast_failure(self):
        self.asset = Image.new('RGBA', (10, 10), '#eeeeee'); self.asset.save(self.root / 'asset.png')
        poster = Image.open(self.root / 'bg.png'); poster.paste(self.asset, (10, 10), self.asset); poster.save(self.root / 'poster.png')
        self.assertEqual(self.audit()['audit_status'], 'fail')

    def test_boolean_coordinate_rejected(self):
        self.manifest['groups'][0]['bbox'] = [True, 10, 20, 20]
        self.assertEqual(self.audit()['audit_status'], 'fail')


if __name__ == '__main__':
    unittest.main()
