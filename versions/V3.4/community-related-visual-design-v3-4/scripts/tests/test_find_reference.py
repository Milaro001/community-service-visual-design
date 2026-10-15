"""Reference discovery and bounded-output checks against the bundled indexes."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/find_reference.py"
spec = importlib.util.spec_from_file_location("find_reference", SCRIPT)
lookup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lookup)


class ReferenceLookupTests(unittest.TestCase):
    def test_every_index_id_is_discoverable_and_points_to_existing_image(self):
        for library, directory in lookup.LIBRARIES.items():
            entries = json.loads((ROOT / "assets" / directory / "index.json").read_text(encoding="utf-8-sig"))["files"]
            for entry in entries:
                with self.subTest(library=library, identifier=entry["id"]):
                    found = lookup.search(ROOT, library, identifier=entry["id"])["results"]
                    self.assertEqual(len(found), 1)
                    self.assertEqual(found[0]["id"], entry["id"])
                    self.assertTrue(found[0]["file_exists"])

    def test_compound_screenshot_subimage_can_be_selected_exactly(self):
        found = lookup.search(ROOT, "layout", identifier="P12-R1C2")["results"][0]
        self.assertEqual(found["id"], "P12")
        self.assertEqual([part["id"] for part in found["layout_units"]], ["P12-R1C2"])
        self.assertIn("右侧", found["layout_units"][0]["location"])
        self.assertIn("excluded_regions", found)

    def test_chinese_glyph_anchor_is_searchable(self):
        found = lookup.search(ROOT, "type", query="有猫青年")["results"][0]
        self.assertEqual(found["id"], "TG04")
        self.assertEqual(found["glyph_samples"][0]["anchor"], "有猫青年")
        self.assertIn("body_simplification", found)

    def test_duplicate_original_alias_keeps_its_domain_and_canonical_path(self):
        found = lookup.search(ROOT, "posters", identifier="R16")["results"][0]
        self.assertEqual(found["id"], "A-R16_D05")
        self.assertEqual(found["canonical_id"], "A-R01_D01")
        self.assertEqual(found["domain_id"], "D05")
        self.assertEqual(found["domain_label_role"], "adaptation")
        self.assertEqual(Path(found["path"]).name, "R01_D01.png")
        self.assertEqual({row["domain_id"] for row in found["aliases"]}, {"D01", "D05", "D10"})

    def test_broad_query_deduplicates_paths_and_obeys_limit(self):
        result = lookup.search(ROOT, "posters", query="实例海报", limit=10)
        self.assertGreater(result["matched_entries"], result["matched_images"])
        self.assertEqual(result["shown"], 10)
        self.assertEqual(len({row["path"] for row in result["results"]}), 10)

    def test_skeleton_is_labeled_as_retrieval_hint(self):
        result = lookup.search(ROOT, "layout", skeleton="S6")
        self.assertGreater(result["shown"], 0)
        self.assertLessEqual(result["shown"], 3)
        self.assertIn("关键词提示", result["note"])

    def test_absolute_invocation_works_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            process = subprocess.run([sys.executable, str(SCRIPT), "--id", "TG57"],
                                     cwd=directory, text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["results"][0]["id"], "TG57")

    def test_bad_limit_and_empty_search_are_rejected(self):
        for arguments in (["--id", "TG01", "--limit", "11"], ["--id", "TG01", "--limit", "0"], []):
            with self.subTest(arguments=arguments):
                process = subprocess.run([sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True)
                self.assertEqual(process.returncode, 2)

    def test_index_path_cannot_escape_skill_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "assets/type-generation-references/index.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps({"files": [{"id": "X", "path": "../outside.png"}]}))
            with self.assertRaisesRegex(ValueError, "越出"):
                lookup.search(root, "type", identifier="X")

    def test_domain_id_mistake_suggests_a_working_query_without_selecting(self):
        result = lookup.search(ROOT, identifier="D11")
        self.assertEqual(result["shown"], 0)
        self.assertEqual(result["results"], [])
        arguments = result["suggestions"][0]["retry_args"]
        process = subprocess.run([sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertGreater(json.loads(process.stdout)["shown"], 0)

    def test_extra_filters_remain_and_and_only_suggest_explicit_retry(self):
        result = lookup.search(ROOT, "type", query="不存在的字例", identifier="TG04")
        self.assertEqual(result["shown"], 0)
        self.assertEqual(result["results"], [])
        arguments = result["suggestions"][0]["retry_args"]
        process = subprocess.run([sys.executable, str(SCRIPT), *arguments], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["results"][0]["id"], "TG04")

    def synthetic_index(self, root, entries):
        for directory in lookup.LIBRARIES.values():
            index = root / "assets" / directory / "index.json"
            index.parent.mkdir(parents=True)
            index.write_text(json.dumps({"files": entries if directory == lookup.LIBRARIES["posters"] else []}))
        for entry in entries:
            image = root / entry["path"]
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"synthetic test image")

    def labeled_entry(self, identifier, structure, path=None):
        digest = hashlib.sha256(b"synthetic test image").hexdigest()
        return {"id": identifier, "path": path or f"assets/reference-posters/{identifier}.png",
                "file_sha256": digest, "observed_structure": structure,
                "visual_review": {"status": "observed", "method": "actual_image",
                                  "image_sha256": digest, "reviewed_at": "2026-10-14"}}

    def test_missing_poster_structure_tags_are_explained_not_invented(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [{"id": "X", "path": "assets/reference-posters/X.png"}])
            result = lookup.search(root, "posters", query="分栏 日期")
        self.assertEqual(result["shown"], 0)
        self.assertTrue(any("未充分标注" in item["reason"] for item in result["suggestions"]))

    def test_reviewed_structure_ranks_before_repeated_file_name(self):
        entries = [{"id": "path-only", "path": "assets/reference-posters/日期日期日期.png"},
                   self.labeled_entry("observed", {"features": ["日期"]})]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, entries)
            result = lookup.search(root, "posters", query="日期")
        self.assertEqual(result["results"][0]["id"], "observed")
        self.assertEqual(result["matched_images"], 2)

    def test_structure_filters_require_all_conditions_and_observed_evidence(self):
        entries = [self.labeled_entry("fit", {"text_density": "high", "body_columns": 2,
                                               "subject_positions": ["left"], "features": ["日期"]}),
                   self.labeled_entry("wrong-column", {"text_density": "high", "body_columns": 1,
                                                        "subject_positions": ["left"]}),
                   self.labeled_entry("wrong-density", {"text_density": "low", "body_columns": 2,
                                                         "subject_positions": ["left"]}),
                   {"id": "no-review", "path": "assets/reference-posters/no-review.png",
                    "observed_structure": {"text_density": "high", "body_columns": 2,
                                           "subject_positions": ["left"]}}]
        filters = {"text_density": "high", "body_columns": 2, "subject_positions": "left"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, entries)
            result = lookup.search(root, "posters", query="日期", structure=filters)
            process = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), "--library", "posters",
                                      "--density", "high", "--columns", "2", "--subject-position", "left"],
                                     text=True, capture_output=True)
        self.assertEqual([entry["id"] for entry in result["results"]], ["fit"])
        self.assertEqual(result["results"][0]["matched_structure_filters"], filters)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual([entry["id"] for entry in json.loads(process.stdout)["results"]], ["fit"])

    def test_structure_labels_bound_to_other_revision_are_not_used(self):
        entry = self.labeled_entry("stale", {"features": ["分栏"], "body_columns": 2})
        entry["visual_review"]["image_sha256"] = "other-revision"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry])
            self.assertEqual(lookup.search(root, "posters", query="分栏")["shown"], 0)
            self.assertEqual(lookup.search(root, "posters", structure={"body_columns": 2})["shown"], 0)
            self.assertNotIn("observed_structure", lookup.search(root, "posters", identifier="stale")["results"][0])

    def test_actual_image_replacement_removes_structure_but_keeps_exact_id(self):
        entry = self.labeled_entry("changed", {"features": ["日期"], "body_columns": 2})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry])
            (root / entry["path"]).write_bytes(b"new image revision")
            self.assertEqual(lookup.search(root, "posters", query="日期")["shown"], 0)
            self.assertEqual(lookup.search(root, "posters", structure={"body_columns": 2})["shown"], 0)
            found = lookup.search(root, "posters", identifier="changed")["results"][0]
            self.assertNotIn("observed_structure", found)
            self.assertTrue(found["file_exists"])

    def test_aliases_hash_each_potential_image_only_once_per_call(self):
        entry = self.labeled_entry("canonical", {"features": ["日期"]})
        alias = dict(entry, id="alias")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry, alias])
            with mock.patch.object(lookup, "image_sha256", wraps=lookup.image_sha256) as hashing:
                result = lookup.search(root, "posters", query="日期")
            self.assertEqual(hashing.call_count, 1)
        self.assertEqual(result["matched_entries"], 2)
        self.assertEqual(result["matched_images"], 1)

    def test_column_filter_can_find_seven_column_source(self):
        entry = self.labeled_entry("seven", {"body_columns": 7})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry])
            process = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root),
                                      "--library", "posters", "--columns", "7"], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["results"][0]["id"], "seven")

    def test_caveats_do_not_turn_negative_observations_into_search_tags(self):
        entry = self.labeled_entry("negative", {"features": ["条目"], "caveats": ["没有日期，没有分栏"]})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry])
            self.assertEqual(lookup.search(root, "posters", query="日期")["shown"], 0)
            self.assertEqual(lookup.search(root, "posters", query="条目")["shown"], 1)

    def test_unknown_structure_does_not_satisfy_requested_column_count(self):
        entry = self.labeled_entry("mixed", {"body_columns": None, "features": ["多面板"]})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry])
            result = lookup.search(root, "posters", structure={"body_columns": 2})
        self.assertEqual(result["shown"], 0)
        self.assertTrue(any("结构条件" in item["reason"] for item in result["suggestions"]))

    def test_boolean_metadata_is_not_a_zero_column_observation(self):
        entry = self.labeled_entry("bad-column", {"body_columns": False})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.synthetic_index(root, [entry])
            self.assertEqual(lookup.search(root, "posters", structure={"body_columns": 0})["shown"], 0)

    def test_invalid_structure_filters_are_rejected(self):
        for filters in ({"body_columns": -1}, {"body_columns": True}, {"subject_positions": "guess"}, {"invented": "x"}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                lookup.search(ROOT, "posters", structure=filters)


if __name__ == "__main__":
    unittest.main()
