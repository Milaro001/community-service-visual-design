"""Meaningful bridge regressions; temporary files and a fake Label Studio API only."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib
from contextlib import redirect_stdout


SCRIPT = Path(__file__).resolve().parents[1] / "visual_review.py"
SPEC = importlib.util.spec_from_file_location("visual_review", SCRIPT)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def png(red):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes([0, red, 100, 150, 255])))
            + chunk(b"IEND", b""))


def result(name, key, value):
    return {"from_name": name, "value": {key: value}}


def annotation(identifier=10, author=7, selected="candidate-1", stamp="2026-10-13T09:00:00Z", **kwargs):
    results = [] if selected is None else [result("stage_selection", "choices", [selected])]
    return dict({"id": identifier, "completed_by": author, "updated_at": stamp,
                 "was_cancelled": False, "result": results}, **kwargs)


class FakeClient:
    def __init__(self):
        self.tasks = {}
        self.next_id = 100
        self.requests = []
        self.omit_export = False
        self.export_error = None
        self.detail_error = None
        self.import_ids = True

    def project_tasks(self, project_id):
        self.requests.append(("list", project_id))
        return copy.deepcopy([task for task in self.tasks.values() if task["project"] == project_id])

    def exported_tasks(self, project_id):
        self.requests.append(("export", project_id))
        if self.export_error:
            raise self.export_error
        return [] if self.omit_export else self.project_tasks(project_id)

    def request(self, method, route, payload=None):
        self.requests.append((method, route))
        if method == "POST" and route.endswith("/import"):
            project_id = int(route.split("/")[-2])
            identifier = self.next_id
            self.next_id += 1
            self.tasks[identifier] = dict(copy.deepcopy(payload[0]), id=identifier, project=project_id, annotations=[])
            return {"task_ids": [identifier]} if self.import_ids else {"task_count": 1}
        if method == "GET" and route.startswith("/api/tasks/"):
            if self.detail_error:
                raise self.detail_error
            identifier = int(route.split("/")[-2])
            if identifier not in self.tasks:
                raise bridge.APIError("任务不存在", 404)
            return copy.deepcopy(self.tasks[identifier])
        raise AssertionError((method, route))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="community-review-test-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        for index in range(1, 7):
            (self.source / f"image-{index}.png").write_bytes(png(index * 20))
        private = self.root / "private" / "connection.json"
        bridge.atomic_json(private, {"api_key": "SECRET-NEVER-IN-PUBLIC-JSON", "reviewer_id": 7})
        self.config = self.root / "runtime.json"
        bridge.atomic_json(self.config, {
            "base_url": "http://127.0.0.1:8877", "private_config": str(private),
            "media_root": str(self.root / "media"), "jobs_root": str(self.root / "jobs"),
            "memory_root": str(self.root / "memory"), "templates_root": str(self.root / "templates"),
            "project_ids": {"background": 1, "background_3": 8, "type_pair": 9, "title": 2, "body": 3, "layout": 4,
                            "layout_3": 4, "layout_4": 6, "layout_5": 7, "color": 5},
        })
        self.runtime = bridge.Runtime(str(self.config))
        self.client = FakeClient()
        self.manifest_path = self.root / "manifest.json"
        self.manifest = {
            "job_id": "job-one", "stage": "background", "language": "ZH", "version": "v1",
            "is_demo": False, "context": {"theme": "社区环保", "audience": "居民"},
            "overview": str(self.source / "image-6.png"),
            "candidates": [{"candidate_id": f"candidate-{index}", "label": chr(64 + index),
                            "path": str(self.source / f"image-{index}.png"),
                            "asset_version": "v1", "description": "布局参考"} for index in range(1, 6)],
            "internal_review": {"status": "unknown", "hard_checks": "unknown"},
        }
        self.review_path = None
        self.task_id = None

    def tearDown(self):
        self.temporary.cleanup()

    def export(self, submit=True):
        bridge.atomic_json(self.manifest_path, self.manifest)
        result = bridge.export_manifest(self.runtime, self.manifest_path, submit, self.client)
        self.review_path = Path(result["review_record"])
        self.task_id = result["task_id"]
        return result

    def sync(self, annotations=None):
        if annotations is not None:
            self.client.tasks[self.task_id]["annotations"] = annotations
        result = bridge.sync_reviews(self.runtime, "job-one", self.client)
        self.assertEqual(result["errors"], [])
        return result["synced"][0]

    def record(self):
        return bridge.read_json(self.review_path)

    def memory(self):
        return bridge.read_json(self.runtime.memory_root / "feedback.json")["records"]

    def profile(self):
        return bridge.read_json(self.runtime.memory_root / "profile.json")

    def preference_annotation(self, **kwargs):
        item = annotation(**kwargs)
        item["result"] += [result("persist_preference", "choices", [bridge.PERSIST_CHOICE]),
                            result("preference_statement", "text", ["同类环保海报优先把主体置于左侧"])]
        return item

    def test_export_copies_real_images_and_keeps_credentials_private(self):
        output = self.export()
        record = self.record()
        self.assertEqual(record["project_id"], 1)
        self.assertEqual(record["manifest"]["internal_review"], self.manifest["internal_review"])
        metadata = record["task"]["data"]["review_metadata"]
        self.assertEqual(metadata["display_mapping"]["E"], "candidate-5")
        for image in metadata["candidate_mapping"].values():
            self.assertEqual(bridge.sha256(image["copied_path"]), image["sha256"])
            self.assertTrue(image["url"].startswith("http://127.0.0.1:8877/data/local-files/?d="))
            self.assertIn(image["sha256"], Path(image["copied_path"]).name)
        self.assertNotIn("SECRET-", json.dumps(output) + self.review_path.read_text(encoding="utf-8"))
        self.assertEqual(record["selection"]["status"], "pending")
        self.assertEqual(output["task_url"], "http://127.0.0.1:8877/projects/1/data/?task=100")
        self.assertEqual(output["review_url"], "http://127.0.0.1:8877/projects/1/data/?task=100")
        self.assertNotIn("labeling=1", output["review_url"])
        self.assertIn("底图选择 · 中文", record["task"]["data"]["review_context"])

    def test_html_descriptions_are_escaped(self):
        self.manifest["candidates"][0]["description"] = '<script>alert("x")</script>'
        self.export()
        option = self.record()["task"]["data"]["selection_options"][0]
        self.assertNotIn("<script>", option["html"])
        self.assertIn("&lt;script&gt;", option["html"])

    def test_second_submit_is_idempotent_and_import_recovers_missing_ids(self):
        self.client.import_ids = False
        self.export()
        first_id = self.task_id
        self.export()
        self.assertEqual(self.task_id, first_id)
        self.assertEqual(sum(item[0] == "POST" for item in self.client.requests), 1)

    def test_export_without_submit_leaves_import_json(self):
        output = self.export(False)
        self.assertIsNone(output["task_id"])
        self.assertFalse(output["submitted"])
        self.assertIsNone(output["review_url"])
        self.assertEqual(len(bridge.read_json(output["task_file"])), 1)
        self.assertEqual(self.sync()["status"], "not_submitted")

    def test_repeated_sync_reads_task_detail_without_generating_server_exports(self):
        self.export()
        self.client.requests.clear()
        self.sync([annotation()])
        self.sync()
        self.assertEqual(self.client.requests, [("GET", "/api/tasks/100/"), ("GET", "/api/tasks/100/")])
        self.assertEqual(len(self.memory()), 1)

    def test_manually_imported_local_task_is_discovered_without_export_api(self):
        self.export(False)
        data = copy.deepcopy(self.record()["task"]["data"])
        self.client.tasks[200] = {"id": 200, "project": 1, "data": data, "annotations": [annotation()]}
        self.client.requests.clear()
        self.sync()
        self.assertEqual(self.record()["task_id"], 200)
        self.assertEqual(self.record()["selection"]["candidate_id"], "candidate-1")
        self.assertEqual(self.client.requests, [("list", 1)])

    def test_same_version_cannot_silently_change_asset(self):
        self.export()
        (self.source / "image-1.png").write_bytes(png(220))
        with self.assertRaisesRegex(bridge.BridgeError, "新的 version"):
            self.export()

    def test_directory_traversal_is_rejected(self):
        self.manifest["job_id"] = "../escape"
        with self.assertRaises(bridge.BridgeError):
            self.export()
        self.assertFalse((self.root / "escape").exists())

    def test_media_symlink_cannot_escape_root(self):
        self.runtime.media_root.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.runtime.media_root / "job-one").symlink_to(outside, target_is_directory=True)
        except OSError as exc:  # Windows without symlink privilege
            self.skipTest(f"symlink unavailable: {exc}")
        with self.assertRaisesRegex(bridge.BridgeError, "超出"):
            self.export()

    def test_nested_media_urls_are_relative_to_local_files_document_root(self):
        config = bridge.read_json(self.config)
        config["local_files_document_root"] = str(self.root / "media")
        config["media_root"] = str(self.root / "media" / "assets")
        bridge.atomic_json(self.config, config)
        self.runtime = bridge.Runtime(self.config)
        self.export()
        metadata = self.record()["task"]["data"]["review_metadata"]
        for asset in list(metadata["candidate_mapping"].values()) + [metadata["overview_asset"]]:
            self.assertIn("/data/local-files/?d=assets/job-one/", asset["url"])
            self.assertTrue(Path(asset["copied_path"]).is_relative_to(self.runtime.media_root))
            self.assertEqual(bridge.sha256(asset["copied_path"]), asset["sha256"])

    def test_media_root_outside_local_document_root_is_rejected(self):
        config = bridge.read_json(self.config)
        config["local_files_document_root"] = str(self.root / "other-root")
        bridge.atomic_json(self.config, config)
        with self.assertRaisesRegex(bridge.BridgeError, "media_root 必须位于"):
            bridge.Runtime(self.config)

    def test_invalid_image_header_is_rejected(self):
        (self.source / "image-1.png").write_text("not an image")
        with self.assertRaisesRegex(bridge.BridgeError, "真实 PNG"):
            self.export()

    def test_three_backgrounds_use_new_project_and_title_still_needs_five(self):
        self.manifest["candidates"] = self.manifest["candidates"][:3]
        self.assertEqual(self.export()["project_id"], 8)
        self.manifest["version"] = "v2"
        self.manifest["stage"] = "title"
        with self.assertRaisesRegex(bridge.BridgeError, "五个"):
            self.export()

    def test_type_pair_is_single_preview_with_explicit_approval(self):
        self.manifest["stage"] = "type_pair"
        self.manifest["candidates"] = self.manifest["candidates"][:1]
        output = self.export()
        self.assertEqual(output["project_id"], 9)
        self.assertEqual(len(self.record()["task"]["data"]["review_metadata"]["candidate_mapping"]), 1)
        self.assertEqual(self.sync([annotation(selected=None)])["selection"]["status"], "pending")
        self.assertNotEqual(self.sync([annotation(selected="__revise__")])["selection"]["status"], "selected")
        approved = self.sync([annotation(selected="candidate-1")])
        self.assertEqual(approved["selection"]["status"], "selected")
        self.manifest["version"] = "v2"
        self.manifest["candidates"] *= 3
        with self.assertRaisesRegex(bridge.BridgeError, "一张"):
            self.export()

    def test_layout_counts_choose_their_own_projects(self):
        self.manifest["stage"] = "layout"
        for count, project in ((3, 4), (4, 6), (5, 7)):
            with self.subTest(count=count):
                value = copy.deepcopy(self.manifest)
                value["candidates"] = value["candidates"][:count]
                record = bridge.prepared_record(self.runtime, bridge.valid_manifest(value))
                self.assertEqual(record["project_id"], project)
                self.assertEqual(len(record["task"]["data"]["review_metadata"]["display_mapping"]), count)

    def test_selection_requires_local_reviewer_and_explicit_full_group_choice(self):
        self.export()
        foreign = annotation(author=8)
        output = self.sync([foreign])
        self.assertEqual(output["selection"]["status"], "pending")
        self.assertEqual(len(self.record()["feedback"]), 1)
        self.assertEqual(self.memory(), {})
        output = self.sync([foreign, annotation(identifier=11, author={"id": 7}, selected="candidate-4")])
        self.assertEqual(output["selection"]["candidate_id"], "candidate-4")
        self.assertEqual(self.record()["manifest"]["internal_review"], self.manifest["internal_review"])

    def test_pair_winner_is_advice_and_does_not_select_whole_group(self):
        self.manifest["stage"] = "color"
        self.manifest["candidates"] = self.manifest["candidates"][:2]
        self.manifest["pair"] = ["candidate-2", "candidate-1"]
        self.export()
        item = annotation(selected=None)
        item["result"] = [result("pair_preference", "choices", ["左图A更好"]),
                          result("a_composition", "rating", 5)]
        output = self.sync([item])
        self.assertEqual(output["selection"]["status"], "pending")
        feedback = next(iter(self.memory().values()))
        self.assertEqual(feedback["ratings"]["candidate-2"]["composition"], 5)
        self.assertEqual(feedback["display_mapping"], {"left": "candidate-2", "right": "candidate-1"})

    def test_all_candidate_ratings_and_zero_normalization(self):
        self.export()
        item = annotation()
        item["result"] += [result("a_composition", "rating", 0), result("b_typography", "rating", None),
                            result("c_color", "rating", 4), result("d_hierarchy", "rating", True),
                            result("e_style_fit", "rating", 5)]
        self.sync([item])
        feedback = next(iter(self.memory().values()))
        self.assertIsNone(feedback["ratings"]["candidate-1"]["composition"])
        self.assertIsNone(feedback["ratings"]["candidate-2"]["typography"])
        self.assertEqual(feedback["ratings"]["candidate-3"]["color"], 4)
        self.assertIsNone(feedback["ratings"]["candidate-4"]["hierarchy"])
        self.assertEqual(feedback["ratings"]["candidate-5"]["style_fit"], 5)

    def test_repeated_sync_deduplicates_and_updates_same_annotation(self):
        self.export()
        self.sync([annotation()])
        self.sync()
        self.assertEqual(len(self.memory()), 1)
        updated = annotation(selected="candidate-5", stamp="2026-10-13T10:00:00Z")
        updated["result"].append(result("likes", "text", ["已修改反馈"]))
        self.sync([updated])
        self.assertEqual(len(self.memory()), 1)
        self.assertEqual(next(iter(self.memory().values()))["likes"], "已修改反馈")
        self.assertEqual(self.record()["selection"]["candidate_id"], "candidate-5")

    def test_cancel_and_delete_clear_selection_and_confirmed_preference(self):
        self.export()
        item = self.preference_annotation()
        self.sync([item])
        self.assertEqual(len(self.profile()["confirmed_preferences"]), 1)
        item["was_cancelled"] = True
        self.sync([item])
        self.assertEqual(self.record()["selection"]["status"], "pending")
        self.assertEqual(self.profile()["confirmed_preferences"], [])
        self.sync([])
        self.assertEqual(self.record()["selection"]["status"], "pending")
        self.assertFalse(next(iter(self.memory().values()))["active"])

    def test_change_to_undecided_or_remove_choice_does_not_leave_old_selection(self):
        self.export()
        self.sync([annotation()])
        for selected in ("__undecided__", None):
            with self.subTest(selected=selected):
                self.sync([annotation(selected=selected, stamp="2026-10-13T10:00:00Z")])
                self.assertEqual(self.record()["selection"]["status"], "pending")
                self.assertIsNone(self.record()["selection"]["candidate_id"])

    def test_revise_and_reject_are_separate_states(self):
        self.export()
        for selected, status in (("__revise__", "revision_requested"), ("__reject__", "rejected")):
            self.sync([annotation(selected=selected)])
            self.assertEqual(self.record()["selection"]["status"], status)
            self.assertIsNone(self.record()["selection"]["candidate_id"])

    def test_deleted_newer_annotation_does_not_resurrect_old_selection(self):
        self.export()
        old = annotation(identifier=10)
        newer = annotation(identifier=11, selected="candidate-2", stamp="2026-10-13T10:00:00Z")
        self.sync([old, newer])
        self.sync([old])
        self.assertEqual(self.record()["selection"]["status"], "pending")
        self.assertEqual(self.record()["selection"]["reason"], "latest_review_deleted")

    def test_export_omission_fetches_complete_task_and_deleted_task_revokes(self):
        self.export()
        self.sync([annotation()])
        self.client.omit_export = True
        self.sync([])
        self.assertEqual(self.record()["selection"]["status"], "pending")
        self.assertTrue(any(item[0] == "GET" and "/api/tasks/" in str(item[1]) for item in self.client.requests))
        del self.client.tasks[self.task_id]
        self.sync()
        self.assertEqual(self.record()["selection"]["reason"], "task_missing")

    def test_temporary_api_failure_does_not_destroy_existing_state(self):
        self.export()
        self.sync([annotation()])
        original = self.record()
        self.client.omit_export = True
        self.client.detail_error = bridge.APIError("temporary failure", 503)
        result = bridge.sync_reviews(self.runtime, "job-one", self.client)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(self.record(), original)

    def test_source_change_prevents_selection_and_preference_update(self):
        self.export()
        self.sync([self.preference_annotation()])
        (self.source / "image-1.png").write_bytes(png(220))
        output = self.sync()
        self.assertEqual(output["selection"]["status"], "pending")
        self.assertFalse(output["integrity"]["assets_valid"])
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_copied_image_change_prevents_selection(self):
        self.export()
        asset = self.record()["task"]["data"]["review_metadata"]["candidate_mapping"]["candidate-5"]
        Path(asset["copied_path"]).write_bytes(png(220))
        output = self.sync([annotation()])
        self.assertEqual(output["selection"]["status"], "pending")
        self.assertFalse(output["integrity"]["assets_valid"])

    def test_server_image_or_metadata_change_invalidates_evaluation(self):
        self.export()
        self.sync([self.preference_annotation()])
        self.client.tasks[self.task_id]["data"]["image_a"] = "http://attacker.invalid/image.png"
        output = self.sync()
        self.assertEqual(output["selection"]["reason"], "server_task_data_changed")
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_demo_reviews_stay_in_job_and_do_not_touch_real_memory(self):
        self.manifest["is_demo"] = True
        self.export()
        self.sync([self.preference_annotation()])
        self.assertEqual(self.record()["selection"]["candidate_id"], "candidate-1")
        self.assertEqual(len(self.record()["feedback"]), 1)
        self.assertFalse(self.runtime.memory_root.exists())

    def test_predictions_cannot_select_or_teach_preferences(self):
        self.export()
        self.sync([self.preference_annotation(is_prediction=True)])
        self.assertEqual(self.record()["selection"]["status"], "pending")
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_high_ratings_and_likes_do_not_create_confirmed_preferences(self):
        self.export()
        item = annotation()
        item["result"] += [result("a_style_fit", "rating", 5), result("likes", "text", ["很喜欢"])]
        self.sync([item])
        self.assertEqual(len(self.profile()["observations"]), 1)
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_confirmed_preferences_are_scoped_and_empty_context_matches_nothing(self):
        self.export()
        self.sync([self.preference_annotation()])
        self.assertEqual(len(bridge.matching_preferences(self.runtime, self.manifest["context"])["preferences"]), 1)
        self.assertEqual(bridge.matching_preferences(self.runtime, {})["preferences"], [])
        self.assertEqual(bridge.matching_preferences(self.runtime, {"theme": "消防", "audience": "居民"})["preferences"], [])

    def test_explicit_conversational_confirmation_is_idempotent_and_retractable(self):
        self.export()
        self.sync([annotation()])
        evidence = next(iter(self.memory()))
        for _ in range(2):
            bridge.confirm_preference(self.runtime, "同类图优先主体居中", self.manifest["context"], evidence)
        self.assertEqual(len(self.profile()["confirmed_preferences"]), 1)
        self.sync([])
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_empty_context_or_foreign_evidence_cannot_be_confirmed(self):
        self.export()
        self.sync([annotation(author=8)])
        with self.assertRaises(bridge.BridgeError):
            bridge.confirm_preference(self.runtime, "居中", {}, "fake")
        with self.assertRaises(bridge.BridgeError):
            bridge.confirm_preference(self.runtime, "居中", self.manifest["context"], "ls:1:100:10")

    def test_duplicate_selection_results_do_not_silently_accept_last_value(self):
        self.export()
        item = annotation()
        item["result"].append(result("stage_selection", "choices", ["candidate-2"]))
        self.sync([item])
        self.assertEqual(self.record()["selection"]["status"], "pending")

    def test_private_key_is_not_accepted_in_public_config(self):
        value = bridge.read_json(self.config)
        value["api_key"] = "SECRET-"
        bridge.atomic_json(self.config, value)
        with self.assertRaisesRegex(bridge.BridgeError, "私有文件"):
            bridge.Runtime(str(self.config))

    def test_opposite_preference_requires_explicit_replace_or_append(self):
        self.export()
        self.sync([annotation()])
        evidence = next(iter(self.memory()))
        first = bridge.confirm_preference(self.runtime, "主体居左", self.manifest["context"], evidence)
        with self.assertRaisesRegex(bridge.BridgeError, "--replace"):
            bridge.confirm_preference(self.runtime, "主体居右", self.manifest["context"], evidence)
        identifier = first["confirmed_preference"]["preference_id"]
        bridge.confirm_preference(self.runtime, "主体居右", self.manifest["context"], evidence, replace=identifier)
        self.assertEqual([item["statement"] for item in self.profile()["confirmed_preferences"]], ["主体居右"])
        self.assertEqual(self.profile()["preference_history"][0]["status"], "superseded")
        self.sync()
        self.assertEqual([item["statement"] for item in self.profile()["confirmed_preferences"]], ["主体居右"])

    def test_different_dimension_append_is_explicit_and_keeps_original(self):
        self.export()
        self.sync([annotation()])
        evidence = next(iter(self.memory()))
        bridge.confirm_preference(self.runtime, "主体居左", self.manifest["context"], evidence)
        with self.assertRaises(bridge.BridgeError):
            bridge.confirm_preference(self.runtime, "配色偏绿", self.manifest["context"], evidence)
        bridge.confirm_preference(self.runtime, "配色偏绿", self.manifest["context"], evidence, append=True)
        self.assertEqual({item["statement"] for item in self.profile()["confirmed_preferences"]}, {"主体居左", "配色偏绿"})

    def test_replaced_web_preference_is_not_recreated_on_repeated_sync(self):
        self.export()
        self.sync([self.preference_annotation()])
        evidence = next(iter(self.memory()))
        identifier = self.profile()["confirmed_preferences"][0]["preference_id"]
        bridge.confirm_preference(self.runtime, "主体居右", self.manifest["context"], evidence, replace=identifier)
        self.sync()
        self.sync()
        self.assertEqual([item["statement"] for item in self.profile()["confirmed_preferences"]], ["主体居右"])
        self.assertEqual(len(self.profile()["preference_history"]), 1)

    def test_annotation_edit_invalidates_manual_preference_and_archives_old_feedback_once(self):
        self.export()
        self.sync([annotation()])
        evidence = next(iter(self.memory()))
        bridge.confirm_preference(self.runtime, "主体居左", self.manifest["context"], evidence)
        edited = annotation(selected="candidate-5", stamp="2026-10-13T10:00:00Z")
        self.sync([edited])
        self.assertEqual(self.profile()["confirmed_preferences"], [])
        self.assertEqual(self.profile()["preference_history"][0]["status"], "inactive")
        saved = self.record()["feedback"][evidence]
        self.assertEqual(len(saved["history"]), 1)
        self.assertEqual(saved["history"][0]["feedback"]["stage_selection"], "candidate-1")
        self.sync()
        self.assertEqual(len(self.record()["feedback"][evidence]["history"]), 1)
        self.assertEqual(len(self.profile()["preference_history"]), 1)

    def test_web_preference_edit_archives_previous_statement(self):
        self.export()
        item = self.preference_annotation()
        self.sync([item])
        item["result"][-1] = result("preference_statement", "text", ["以后改为主体居右"])
        self.sync([item])
        self.assertEqual([old["statement"] for old in self.profile()["confirmed_preferences"]], ["以后改为主体居右"])
        self.assertIn("左侧", self.profile()["preference_history"][0]["statement"])
        self.assertEqual(len(next(iter(self.memory().values()))["history"]), 1)
        self.sync()
        self.assertEqual(len(self.profile()["preference_history"]), 1)

    def test_timestamp_only_change_does_not_invalidate_or_grow_history(self):
        self.export()
        self.sync([annotation()])
        evidence = next(iter(self.memory()))
        bridge.confirm_preference(self.runtime, "主体居左", self.manifest["context"], evidence)
        self.sync([annotation(stamp="2026-10-13T10:00:00Z")])
        self.assertEqual(len(self.profile()["confirmed_preferences"]), 1)
        self.assertEqual(self.record()["feedback"][evidence]["history"], [])

    def test_noop_sync_keeps_review_feedback_and_profile_files_untouched(self):
        self.export()
        self.sync([self.preference_annotation()])
        paths = [self.review_path, self.runtime.memory_root / "feedback.json",
                 self.runtime.memory_root / "profile.json"]
        before = [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths]
        with mock.patch.object(bridge, "now", return_value="2099-01-01T00:00:00+00:00"), \
                mock.patch.object(bridge, "rebuild_profile", wraps=bridge.rebuild_profile) as rebuild:
            output = self.sync()
        self.assertFalse(output["changed"])
        self.assertFalse(output["memory"]["updated"])
        self.assertEqual(rebuild.call_count, 0)
        self.assertEqual(before, [(path.read_bytes(), path.stat().st_mtime_ns) for path in paths])

    def export_extra(self, job_id, version="v1", stamp="2026-10-14T10:00:00+00:00"):
        manifest = copy.deepcopy(self.manifest)
        manifest.update({"job_id": job_id, "version": version})
        path = self.root / (job_id + "-" + version + "-manifest.json")
        bridge.atomic_json(path, manifest)
        with mock.patch.object(bridge, "now", return_value=stamp):
            return bridge.export_manifest(self.runtime, path, True, self.client)

    def test_many_tasks_merge_memory_and_build_profile_once_per_sync(self):
        self.export()
        extra = self.export_extra("job-two")
        self.client.tasks[self.task_id]["annotations"] = [self.preference_annotation()]
        self.client.tasks[extra["task_id"]]["annotations"] = [annotation(identifier=20)]
        with mock.patch.object(bridge, "atomic_json", wraps=bridge.atomic_json) as writes, \
                mock.patch.object(bridge, "rebuild_profile", wraps=bridge.rebuild_profile) as rebuild:
            output = bridge.sync_reviews(self.runtime, client=self.client)
        self.assertEqual(output["errors"], [])
        self.assertEqual(len(self.memory()), 2)
        self.assertEqual(rebuild.call_count, 1)
        self.assertEqual(sum(Path(call.args[0]).name == "feedback.json" for call in writes.call_args_list), 1)
        self.assertEqual(sum(Path(call.args[0]).name == "profile.json" for call in writes.call_args_list), 1)

    def test_profile_interrupted_after_feedback_write_repairs_on_next_noop(self):
        self.export()
        self.client.tasks[self.task_id]["annotations"] = [self.preference_annotation()]
        original = bridge.atomic_json
        def fail_profile(path, value):
            if Path(path).name == "profile.json":
                raise bridge.BridgeError("synthetic profile write interruption")
            return original(path, value)
        with mock.patch.object(bridge, "atomic_json", side_effect=fail_profile):
            failed = bridge.sync_reviews(self.runtime, "job-one", self.client)
        self.assertEqual(failed["errors"][0]["scope"], "memory_batch")
        self.assertTrue((self.runtime.memory_root / "feedback.json").exists())
        repaired = self.sync()
        self.assertFalse(repaired["changed"])
        self.assertTrue(repaired["memory"]["profile_updated"])
        self.assertEqual(len(self.profile()["confirmed_preferences"]), 1)

    def test_background_prioritizes_latest_unselected_version_and_sweeps_history(self):
        with mock.patch.object(bridge, "now", return_value="2026-10-14T09:00:00+00:00"):
            self.export()
        old_task = self.task_id
        current = self.export_extra("job-one", "v2")
        other = self.export_extra("older-job", stamp="2026-10-14T08:00:00+00:00")
        bridge.activate_job(self.runtime, "job-one")
        self.client.requests.clear()
        bridge.sync_reviews(self.runtime, client=self.client, background=True)
        self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{current['task_id']}/")])
        self.client.requests.clear()
        bridge.sync_reviews(self.runtime, client=self.client, background=True, include_history=True)
        gets = [request[1] for request in self.client.requests if request[0] == "GET"]
        self.assertEqual(gets[0], f"/api/tasks/{current['task_id']}/")
        self.assertEqual(set(gets), {f"/api/tasks/{identifier}/" for identifier in (old_task, current['task_id'], other['task_id'])})

    def test_selected_moves_to_history_but_explicit_job_sync_recovers_edits_and_deletion(self):
        self.export()
        self.sync([self.preference_annotation()])
        self.client.tasks[self.task_id]["annotations"] = [annotation(selected="candidate-5")]
        self.client.requests.clear()
        skipped = bridge.sync_reviews(self.runtime, client=self.client, background=True)
        self.assertEqual(skipped["synced"], [])
        self.assertEqual(self.client.requests, [])
        self.assertEqual(self.sync()["selection"]["candidate_id"], "candidate-5")
        self.client.tasks[self.task_id]["annotations"] = []
        self.client.requests.clear()
        swept = bridge.sync_reviews(self.runtime, client=self.client, background=True, include_history=True)
        self.assertEqual(swept["synced"][0]["selection"]["status"], "pending")
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_explicit_sync_hashes_content_even_when_file_timestamp_is_restored(self):
        self.export()
        self.sync([self.preference_annotation()])
        path = self.source / "image-1.png"
        stat = path.stat()
        path.write_bytes(png(220))
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        output = self.sync()
        self.assertFalse(output["integrity"]["assets_valid"])
        self.assertEqual(output["selection"]["status"], "pending")
        self.assertEqual(self.profile()["confirmed_preferences"], [])

    def test_batch_rereads_newer_review_committed_during_other_task_fetch(self):
        self.export()
        extra = self.export_extra("job-two")
        self.client.tasks[self.task_id]["annotations"] = [annotation()]
        original = self.client.request
        def request(method, route, payload=None):
            task = original(method, route, payload)
            if route == f"/api/tasks/{extra['task_id']}/":
                concurrent = self.record()
                updated = copy.deepcopy(self.client.tasks[self.task_id])
                updated["annotations"] = [annotation(selected="candidate-5", stamp="2026-10-14T11:00:00Z")]
                with bridge.locked(self.review_path.parent / ".lock"):
                    bridge.atomic_json(self.review_path, bridge.apply_snapshot(self.runtime, concurrent, updated, 7))
            return task
        with mock.patch.object(self.client, "request", side_effect=request):
            output = bridge.sync_reviews(self.runtime, client=self.client)
        self.assertEqual(output["errors"], [])
        evidence = f"ls:1:{self.task_id}:10"
        self.assertEqual(self.memory()[evidence]["stage_selection"], "candidate-5")

    def test_explicit_resume_activates_older_job_without_rewriting_same_pointer(self):
        self.export()
        self.export_extra("newer-job", stamp="2099-01-01T00:00:00+00:00")
        self.sync()
        marker = bridge.active_job_path(self.runtime)
        self.assertEqual(bridge.read_json(marker)["job_id"], "job-one")
        before = marker.stat().st_mtime_ns
        self.sync()
        self.assertEqual(marker.stat().st_mtime_ns, before)
        self.client.requests.clear()
        bridge.sync_reviews(self.runtime, client=self.client, background=True)
        self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{self.task_id}/")])
        bridge.sync_reviews(self.runtime, "nonexistent-job", self.client)
        self.assertEqual(bridge.read_json(marker)["job_id"], "job-one")

    def test_corrupt_or_missing_activity_pointer_falls_back_to_newest_job(self):
        self.export()
        newer = self.export_extra("newer-job", stamp="2099-01-01T00:00:00+00:00")
        marker = bridge.active_job_path(self.runtime)
        for bad in (None, "broken json", {"job_id": "../bad"}, {"job_id": "missing-job"}):
            with self.subTest(bad=bad):
                if bad is None:
                    marker.unlink(missing_ok=True)
                elif isinstance(bad, str):
                    marker.write_text(bad)
                else:
                    bridge.atomic_json(marker, bad)
                self.client.requests.clear()
                output = bridge.sync_reviews(self.runtime, client=self.client, background=True)
                self.assertEqual(output["active_job_id"], "newer-job")
                self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{newer['task_id']}/")])

    def test_same_second_arbitrary_version_names_still_choose_last_export(self):
        with mock.patch.object(bridge, "now", return_value="2026-10-14T09:00:00+00:00"):
            self.manifest["version"] = "v9"
            self.export()
            latest = self.export_extra("job-one", "v10", stamp="2026-10-14T09:00:00+00:00")
        self.client.requests.clear()
        bridge.sync_reviews(self.runtime, client=self.client, background=True)
        self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{latest['task_id']}/")])

    def test_failed_explicit_sync_preserves_previous_active_job(self):
        self.export()
        self.export_extra("newer-job")
        self.client.detail_error = bridge.APIError("temporary failure", 503)
        output = bridge.sync_reviews(self.runtime, "job-one", self.client)
        self.assertTrue(output["errors"])
        self.assertEqual(bridge.read_json(bridge.active_job_path(self.runtime))["job_id"], "newer-job")

    def test_current_selected_job_does_not_activate_old_pending_job(self):
        self.export()
        self.export_extra("newer-job", stamp="2099-01-01T00:00:00+00:00")
        self.sync([annotation()])
        output = bridge.sync_reviews(self.runtime, client=self.client, background=True)
        self.assertEqual(output["active_job_id"], "job-one")
        self.assertEqual(output["active_count"], 0)
        self.assertEqual(output["synced"], [])

    def test_legacy_numeric_versions_same_second_use_natural_tiebreak(self):
        with mock.patch.object(bridge, "now", return_value="2026-10-14T09:00:00+00:00"):
            self.manifest["version"] = "v9"
            self.export()
            latest = self.export_extra("job-one", "v10", stamp="2026-10-14T09:00:00+00:00")
        for path in bridge.review_records(self.runtime):
            record = bridge.read_json(path)
            record.pop("creation_sequence")
            bridge.atomic_json(path, record)
        self.client.requests.clear()
        bridge.sync_reviews(self.runtime, client=self.client, background=True)
        self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{latest['task_id']}/")])

    def test_bad_history_record_cannot_starve_current_background_task(self):
        self.export()
        old_path = self.review_path
        extra = self.export_extra("newer-job", stamp="2099-01-01T00:00:00+00:00")
        broken = "{invalid historical json"
        old_path.write_text(broken)
        self.client.requests.clear()
        output = bridge.sync_reviews(self.runtime, client=self.client, background=True, include_history=True)
        self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{extra['task_id']}/")])
        self.assertEqual(len(output["errors"]), 1)
        self.assertEqual(output["errors"][0]["scope"], "record_validation")
        self.assertEqual(Path(output["errors"][0]["review_record"]), old_path)
        self.assertEqual(old_path.read_text(), broken)
        with self.assertRaises(bridge.BridgeError):
            bridge.sync_reviews(self.runtime, "job-one", self.client)

    def test_malformed_complete_task_snapshot_does_not_revoke_existing_feedback(self):
        self.export()
        self.sync([self.preference_annotation()])
        original_record = self.record()
        original_memory = self.memory()
        for malformed in (["annotations"], {"annotations": None}):
            with self.subTest(malformed=malformed), mock.patch.object(self.client, "request", return_value=malformed):
                output = bridge.sync_reviews(self.runtime, "job-one", self.client)
            self.assertTrue(output["errors"])
            self.assertEqual(self.record(), original_record)
            self.assertEqual(self.memory(), original_memory)

    def test_duplicate_resolved_review_paths_do_not_reacquire_same_lock(self):
        self.export()
        self.client.requests.clear()
        with mock.patch.object(bridge, "review_records", return_value=[self.review_path, self.review_path]):
            output = bridge.sync_reviews(self.runtime, "job-one", self.client)
        self.assertEqual(output["errors"], [])
        self.assertEqual(len(output["synced"]), 1)
        self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{self.task_id}/")])

    def test_new_export_sequence_beats_frozen_or_backward_clock_and_arbitrary_names(self):
        self.manifest["version"] = "z-older"
        with mock.patch.object(bridge, "now", return_value="2099-01-01T00:00:00+00:00"):
            self.export()
        old_sequence = self.record()["creation_sequence"]
        for stamp, version in (("2099-01-01T00:00:00+00:00", "a-frozen"),
                               ("2000-01-01T00:00:00+00:00", "b-backward")):
            latest = self.export_extra("job-one", version, stamp=stamp)
            latest_record = bridge.read_json(latest["review_record"])
            self.assertGreater(latest_record["creation_sequence"], old_sequence)
            self.client.requests.clear()
            bridge.sync_reviews(self.runtime, client=self.client, background=True)
            self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{latest['task_id']}/")])
            old_sequence = latest_record["creation_sequence"]
        # Retrying this same record does not allocate a new creation identity.
        repeated = bridge.export_manifest(self.runtime, self.root / "job-one-b-backward-manifest.json", True, self.client)
        self.assertEqual(bridge.read_json(repeated["review_record"])["creation_sequence"], old_sequence)

    def test_creation_sequence_counter_recovers_from_missing_and_corrupt_file(self):
        self.export()
        first = self.record()["creation_sequence"]
        counter = self.runtime.jobs_root / ".review-sequence.json"
        counter.write_text("bad json")
        second = self.export_extra("job-one", "v2")
        second_sequence = bridge.read_json(second["review_record"])["creation_sequence"]
        self.assertGreater(second_sequence, first)
        counter.unlink()
        third = self.export_extra("job-one", "v3")
        self.assertGreater(bridge.read_json(third["review_record"])["creation_sequence"], second_sequence)

    def test_semantically_bad_history_is_isolated_and_explicit_reports_bridge_error(self):
        self.export()
        old_path = self.review_path
        original = self.record()
        extra = self.export_extra("newer-job")
        for mutate in (lambda value: value.pop("project_id"),
                       lambda value: value.update(selection=[]),
                       lambda value: value.update(feedback=[]),
                       lambda value: value.update(task={"data": {}})):
            with self.subTest(mutate=mutate):
                broken = copy.deepcopy(original)
                mutate(broken)
                bridge.atomic_json(old_path, broken)
                self.client.tasks[extra["task_id"]]["annotations"] = [annotation(identifier=20, selected="candidate-5")]
                self.client.requests.clear()
                output = bridge.sync_reviews(self.runtime, client=self.client, background=True, include_history=True)
                self.assertEqual(len(output["errors"]), 1)
                self.assertEqual(output["errors"][0]["scope"], "record_validation")
                self.assertEqual(self.client.requests, [("GET", f"/api/tasks/{extra['task_id']}/")])
                self.assertEqual(self.memory()[f"ls:1:{extra['task_id']}:20"]["stage_selection"], "candidate-5")
                self.assertEqual(bridge.read_json(old_path), broken)
                with self.assertRaises(bridge.BridgeError):
                    bridge.sync_reviews(self.runtime, "job-one", self.client)

    def test_relative_cli_context_and_config_paths(self):
        bridge.atomic_json(self.root / "context.json", self.manifest["context"])
        original = Path.cwd()
        try:
            os.chdir(self.root)
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = bridge.main(["--config", "runtime.json", "preferences", "--context", "context.json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(buffer.getvalue())["context"], self.manifest["context"])
        finally:
            os.chdir(original)

    def test_project_task_lookup_handles_empty_and_full_pagination(self):
        class PaginatedClient(bridge.Client):
            def __init__(self, pages):
                self.pages = pages
                self.routes = []
            def request(self, method, route, payload=None):
                self.routes.append(route)
                return self.pages[len(self.routes) - 1]
        client = PaginatedClient([{"total": 0, "tasks": []}])
        self.assertEqual(client.project_tasks(2), [])
        client = PaginatedClient([{"total": 3, "tasks": [{"id": 1}, {"id": 2}]},
                                  {"total": 3, "tasks": [{"id": 3}]}])
        self.assertEqual([task["id"] for task in client.project_tasks(2)], [1, 2, 3])
        self.assertIn("page=2", client.routes[-1])
        self.assertTrue(all(route.startswith("/api/tasks/?project=2") for route in client.routes))

    def test_partial_or_repeated_project_pagination_is_rejected(self):
        class PaginatedClient(bridge.Client):
            def __init__(self):
                self.count = 0
            def request(self, method, route, payload=None):
                self.count += 1
                return {"total": 2, "tasks": [{"id": 1}]}
        with self.assertRaisesRegex(bridge.APIError, "重复 ID"):
            PaginatedClient().project_tasks(2)


if __name__ == "__main__":
    unittest.main()
