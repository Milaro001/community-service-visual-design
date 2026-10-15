import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pick_styles = load("pick_styles")


class PickStylesTests(unittest.TestCase):
    def setUp(self):
        self.styles = pick_styles.load()

    def test_library_has_15_complete_styles(self):
        self.assertEqual(len(self.styles), 12)
        for style in self.styles:
            self.assertTrue({"id", "name", "family", "pitch", "keywords", "type", "palette", "suits"} <= set(style))
        self.assertEqual(len({s["id"] for s in self.styles}), len(self.styles))

    def test_five_options_two_suited_family_capped(self):
        for seed in range(30):
            chosen = pick_styles.pick(self.styles, "重阳 敬老", seed=seed)
            self.assertEqual(len({s["id"] for s in chosen}), 5)
            self.assertGreaterEqual(sum(1 for s in chosen if pick_styles.fit(s, "重阳 敬老")), 2)
            families = [s["family"] for s in chosen]
            self.assertLessEqual(max(families.count(f) for f in families), 2)

    def test_draws_vary_and_exclude_works(self):
        draws = {tuple(sorted(s["id"] for s in pick_styles.pick(self.styles, "敬老", seed=i))) for i in range(20)}
        self.assertGreater(len(draws), 5)
        excluded = {"S01", "S02", "S03", "S04", "S05"}
        chosen = pick_styles.pick(self.styles, "", exclude=excluded, seed=1)
        self.assertFalse(excluded & {s["id"] for s in chosen})

    def test_count_four_for_option_tools(self):
        self.assertEqual(len(pick_styles.pick(self.styles, "敬老", seed=2, show=4)), 4)

    def test_cli_message(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(pick_styles.main(["--topic", "反诈", "--seed", "3"]), 0)
        self.assertEqual(json.loads(buffer.getvalue())["message"].count("\n"), 4)



if __name__ == "__main__":
    unittest.main()
