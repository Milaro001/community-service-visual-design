import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("type_selector", ROOT / "scripts/select_type_references.py")
selector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selector)


class TypeSelectionTests(unittest.TestCase):
    def test_catalog_covers_every_source_and_preview(self):
        result = selector.select(ROOT, catalog=True)
        self.assertEqual(result["scanned_sources"], 65)
        self.assertEqual({row["id"] for row in result["catalog"]}, {f"TG{i:02}" for i in range(1, 66)})
        self.assertEqual(len(result["preview_paths"]), 8)
        self.assertTrue(all(Path(path).is_file() for path in result["preview_paths"]))

    def test_late_specific_semantic_source_is_not_hidden_by_prefix(self):
        result = selector.select(ROOT, semantics="亲子 泡泡", limit=3)
        self.assertEqual(result["scanned_sources"], 65)
        self.assertEqual(result["results"][0]["id"], "TG54")
        self.assertIn("泡泡", result["results"][0]["semantic_matches"])

    def test_different_topics_change_the_shortlist(self):
        care = selector.select(ROOT, semantics="邻里 陪伴 温暖", limit=5)["results"]
        sport = selector.select(ROOT, semantics="成长 运动 挑战", limit=5)["results"]
        self.assertNotEqual([row["id"] for row in care], [row["id"] for row in sport])
        self.assertTrue(all(row["semantic_matches"] or row["affinity_matches"] for row in care + sport))

    def test_layout_is_a_strict_observed_constraint(self):
        result = selector.select(ROOT, semantics="文化 阅读", layout="grid")
        self.assertGreater(len(result["results"]), 0)
        self.assertTrue(all("grid" in row["layout"]["modes"] for row in result["results"]))
        self.assertEqual(selector.select(ROOT, query="不存在的笔形", layout="grid")["results"], [])

    def fixture(self, root, reverse=False):
        folder = root / "assets/type-generation-references"
        folder.mkdir(parents=True, exist_ok=True)
        entries = []
        for identifier in ("TG01", "TG50", "TG57"):
            path = folder / (identifier + ".png")
            path.write_bytes(identifier.encode())
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            entries.append({"id": identifier, "path": str(path.relative_to(root)), "sha256": digest,
                            "features": "圆润清楚", "context_tags": ["温暖"], "type_families": [identifier],
                            "type_layout": {"modes": ["horizontal"], "source_sha256": digest}})
        (folder / "index.json").write_text(json.dumps({"files": entries[::-1] if reverse else entries}))
        return entries

    def test_equal_score_order_does_not_depend_on_index_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            first = [row["id"] for row in selector.select(root, semantics="温暖")["results"]]
            self.fixture(root, reverse=True)
            second = [row["id"] for row in selector.select(root, semantics="温暖")["results"]]
        self.assertEqual(first, second)

    def test_changed_source_cannot_reuse_old_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = self.fixture(root)
            (root / entries[0]["path"]).write_bytes(b"replacement")
            result = selector.select(root, semantics="温暖")
        self.assertNotIn("TG01", [row["id"] for row in result["results"]])

    def test_no_semantic_match_does_not_fill_from_start(self):
        self.assertEqual(selector.select(ROOT, semantics="绝无对应主题XYZ")["results"], [])


    def test_combined_catalog_and_shortlist_use_one_source_scan(self):
        with mock.patch.object(selector,"load_catalog",wraps=selector.load_catalog) as load:
            result=selector.select(ROOT,semantics="亲子 春日",catalog=True,limit=5)
        self.assertEqual(load.call_count,1)
        self.assertEqual(len(result["catalog"]),65)
        self.assertEqual(result["shortlist"],selector.select(ROOT,semantics="亲子 春日",limit=5))

    def test_combined_mode_respects_layout_and_no_match(self):
        r=selector.select(ROOT,semantics="春日 自然",layout="vertical",catalog=True)
        self.assertTrue(r["shortlist"]["results"])
        self.assertTrue(all("vertical" in row["layout"]["modes"] for row in r["shortlist"]["results"]))
        r=selector.select(ROOT,semantics="绝无对应主题XYZ",catalog=True)
        self.assertEqual(r["shortlist"]["results"],[])

    def select_profiles(self, profiles, semantics="需求", limit=2):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entries = self.fixture(root)
            for entry in entries:
                entry["features"], entry["type_families"] = profiles[entry["id"]]
                entry["context_tags"] = []
            (root / "assets/type-generation-references/index.json").write_text(json.dumps({"files": entries}))
            return selector.select(root, semantics=semantics, limit=limit)

    def test_same_core_form_with_different_layout_tags_is_not_new_direction(self):
        result = self.select_profiles({
            "TG57": ("需求", ["粗黑几何", "摄影搭配"]),
            "TG01": ("需求", ["粗黑几何", "横向组块"]),
            "TG50": ("需求", ["衬线人文", "摄影搭配"]),
        })
        self.assertEqual([row["id"] for row in result["results"]], ["TG57", "TG50"])
        self.assertEqual(result["form_family_counts"], {"粗黑几何": 1, "衬线人文": 1})

    def test_nearby_round_forms_allow_relevant_serif_alternative(self):
        result = self.select_profiles({
            "TG57": ("需求", ["圆润匀线"]),
            "TG01": ("需求", ["圆润粗字"]),
            "TG50": ("需求", ["书写衬线"]),
        })
        self.assertEqual({row["id"] for row in result["results"]}, {"TG57", "TG50"})

    def test_strong_topic_fit_is_not_replaced_for_a_style_quota(self):
        result = self.select_profiles({
            "TG57": ("需求 明确", ["粗黑几何", "摄影搭配"]),
            "TG01": ("需求 明确", ["粗黑几何", "横向组块"]),
            "TG50": ("需求", ["衬线人文"]),
        }, semantics="需求 明确")
        self.assertEqual({row["id"] for row in result["results"]}, {"TG57", "TG01"})

    def test_unobserved_form_is_not_promoted_as_distinct(self):
        result = self.select_profiles({
            "TG57": ("需求", ["粗黑几何"]),
            "TG01": ("需求", []),
            "TG50": ("需求", ["衬线人文"]),
        })
        self.assertEqual({row["id"] for row in result["results"]}, {"TG57", "TG50"})

if __name__ == "__main__":
    unittest.main()
