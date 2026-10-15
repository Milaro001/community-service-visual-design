"""Full-library coverage and stale-preview boundaries, independent of search limits."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts/find_reference.py'
spec=importlib.util.spec_from_file_location('layout_lookup',SCRIPT)
lookup=importlib.util.module_from_spec(spec);spec.loader.exec_module(lookup)

class LayoutCatalogTests(unittest.TestCase):
    def fixture(self, root):
        sources=[]
        for library,directory,identifiers in [('layout','layout-priority-references',['P01','P02']),('posters','reference-posters',['A-R01_D01'])]:
            entries=[]
            for identifier in identifiers:
                p=root/'assets'/directory/(identifier+'.png');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(identifier.encode())
                digest=hashlib.sha256(p.read_bytes()).hexdigest();relative=str(p.relative_to(root))
                entries.append({'id':identifier,'path':relative,'sha256':digest,'file_sha256':digest})
                sources.append({'id':identifier,'library':library,'path':relative,'sha256':digest})
            if library=='posters':
                entries.append(dict(entries[0],id='A-R16_D05',canonical_id='A-R01_D01'))
                entries.append({'id':'overview','path':'assets/reference-posters/overview.png','collection':'overview'})
            (root/'assets'/directory/'index.json').write_text(json.dumps({'files':entries}))
        for library,directory,name in [('typography','typography-references','T01_test'),('wireframes','wireframes','D01_S1_01')]:
            p=root/'assets'/directory/(name+'.png');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode())
            sources.append({'id':name.split('_')[0] if library=='typography' else name,'library':library,'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        preview=root/'assets/layout-atlas/preview.jpg';preview.parent.mkdir(parents=True);preview.write_bytes(b'synthetic preview')
        manifest={'source_count':len(sources),'sources':sources,'previews':[{'path':str(preview.relative_to(root)),'sha256':hashlib.sha256(preview.read_bytes()).hexdigest(),'source_ids':[row['id'] for row in sources]}]}
        (preview.parent/'index.json').write_text(json.dumps(manifest));return manifest

    def test_real_catalog_covers_all_sources_without_three_limit(self):
        result=lookup.layout_catalog(ROOT)
        self.assertEqual(result['source_count'],195)
        self.assertEqual(result['source_counts'],{'layout':23,'posters':123,'typography':4,'wireframes':45})
        self.assertTrue(result['catalog_current']);self.assertTrue(result['preview_coverage_complete'])
        self.assertEqual(len(result['catalog']),195);self.assertEqual(len(result['preview_paths']),23)
        self.assertEqual(len({row['path'] for row in result['catalog']}),195)

    def test_alias_and_overview_are_not_extra_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);r=lookup.layout_catalog(root)
        self.assertTrue(r['catalog_current']);self.assertEqual(r['source_count'],5)
        self.assertEqual(r['source_counts']['posters'],1)

    def test_changed_source_disables_preview_and_old_observation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=self.fixture(root);(root/m['sources'][0]['path']).write_bytes(b'replaced')
            r=lookup.layout_catalog(root)
        self.assertFalse(r['catalog_current']);self.assertEqual(r['preview_paths'],[])
        self.assertFalse(r['catalog'][0]['source_current'])

    def test_new_inventory_source_invalidates_old_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);(root/'assets/wireframes/D02_S1_01.png').write_bytes(b'new')
            r=lookup.layout_catalog(root)
        self.assertFalse(r['inventory_matches']);self.assertFalse(r['catalog_current'])
        self.assertEqual(r['source_count'],6);self.assertEqual(r['preview_paths'],[])

    def test_incomplete_preview_mapping_cannot_claim_all_readable(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=self.fixture(root);m['previews'][0]['source_ids'].pop()
            (root/'assets/layout-atlas/index.json').write_text(json.dumps(m));r=lookup.layout_catalog(root)
        self.assertFalse(r['preview_coverage_complete']);self.assertEqual(r['preview_paths'],[])

    def test_altered_preview_is_not_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);m=self.fixture(root);(root/m['previews'][0]['path']).write_bytes(b'wrong image')
            r=lookup.layout_catalog(root)
        self.assertFalse(r['catalog_current']);self.assertEqual(r['preview_paths'],[])

    def test_full_catalog_flag_cannot_silently_filter(self):
        r=subprocess.run([sys.executable,str(SCRIPT),'--catalog-layout','--library','layout'],capture_output=True,text=True)
        self.assertEqual(r.returncode,2)
        r=subprocess.run([sys.executable,str(SCRIPT),'--catalog-layout'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(len(json.loads(r.stdout)['catalog']),195)

if __name__=='__main__':unittest.main()
