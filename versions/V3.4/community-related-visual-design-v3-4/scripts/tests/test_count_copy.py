import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "count_copy.py"
spec = importlib.util.spec_from_file_location("count_copy", SCRIPT)
count_copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(count_copy)


class CountCopyTests(unittest.TestCase):
    def test_weight_counts_cjk_and_halves_digits(self):
        self.assertEqual(count_copy.weight("银龄手机课堂"), 6)
        self.assertEqual(count_copy.weight("8888-1234"), 4)
        self.assertEqual(count_copy.weight("上午9:30—11:00"), 2 + 4)
        self.assertEqual(count_copy.weight("，。！ "), 0)

    def test_state_rows_split_title_and_body(self):
        state = "\n".join([
            "| ID｜语言｜采用文案｜来源 |",
            "T1｜zh｜银龄手机课堂｜原文",
            "B1｜zh｜课堂免费，不推销手机和套餐｜原文",
            "B2｜zh｜电话 8888-1234｜原文",
            "随便一行说明",
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.md"
            path.write_text(state, encoding="utf-8")
            rows = count_copy.parse_rows(path.read_text(encoding="utf-8"))
        result = count_copy.summarize(rows)
        zh = result["languages"]["zh"]
        self.assertEqual(zh["title"], 6)
        self.assertEqual(zh["body"], 12 + 2 + 4)
        self.assertEqual(result["recommended_mode"], "oneshot")
        self.assertEqual(count_copy.summarize(rows, body_only=True)["max_count"], 18)

    def test_thresholds(self):
        self.assertEqual(count_copy.recommend(100), "oneshot")
        self.assertEqual(count_copy.recommend(101), "oneshot-two-step")
        self.assertEqual(count_copy.recommend(161), "ask")

    def test_largest_language_decides(self):
        rows = [{"id": "B1", "language": "zh", "copy": "短"},
                {"id": "B1", "language": "en", "copy": "x" * 400}]
        self.assertEqual(count_copy.summarize(rows)["recommended_mode"], "ask")

    def test_cli_text_mode(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(count_copy.main(["--text", "社区"]), 0)


if __name__ == "__main__":
    unittest.main()
