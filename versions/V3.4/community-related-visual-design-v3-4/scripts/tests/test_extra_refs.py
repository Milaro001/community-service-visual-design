import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "extra_refs.py"
spec = importlib.util.spec_from_file_location("extra_refs", SCRIPT)
extra_refs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extra_refs)


def run(args):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = extra_refs.main(args)
    return code, json.loads(buffer.getvalue())


class ExtraRefsTests(unittest.TestCase):
    def test_empty_pool_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            code, result = run(["--dir", directory])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "empty")

    @unittest.skipIf(extra_refs.Image is None, "Pillow not installed")
    def test_sheets_are_numbered_cached_and_rebuilt(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "sub").mkdir()
            for i, size in enumerate([(300, 200), (200, 300), (250, 250)]):
                extra_refs.Image.new("RGB", size, (i * 80, 100, 150)).save(folder / ("sub" if i else ".") / f"p{i}.png")
            (folder / "broken.jpg").write_text("not an image")
            code, first = run(["--dir", directory])
            self.assertEqual((code, first["count"], first["cached"]), (0, 3, False))
            self.assertEqual(first["skipped"], ["broken.jpg"])
            self.assertEqual(run(["--dir", directory])[1]["cached"], True)
            code, found = run(["--dir", directory, "--id", "x002"])
            self.assertTrue(Path(found["path"]).is_file())
            extra_refs.Image.new("RGB", (100, 100)).save(folder / "p9.png")
            self.assertEqual(run(["--dir", directory])[1]["count"], 4)


if __name__ == "__main__":
    unittest.main()
