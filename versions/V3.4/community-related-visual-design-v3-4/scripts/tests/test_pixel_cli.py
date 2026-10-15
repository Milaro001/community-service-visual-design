"""Optional pixel dependencies must not break discovery or create false audit files."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'audit_poster_readability.py'

class PixelCliTests(unittest.TestCase):
    def test_help_works_without_site_packages(self):
        r=subprocess.run([sys.executable,'-S',str(SCRIPT),'--help'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertIn('--out-dir',r.stdout)

    def test_missing_dependencies_return_unknown_without_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'audit'
            r=subprocess.run([sys.executable,'-S',str(SCRIPT),'unused.json','--out-dir',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2,r.stderr);self.assertFalse(out.exists())
        result=json.loads(r.stdout)
        self.assertEqual(result['audit_status'],'unknown')
        self.assertEqual(result['pixel_contrast_status'],'unknown');self.assertIn('Pillow',result['error'])
        self.assertNotIn('Traceback',r.stderr)

if __name__=='__main__':unittest.main()
