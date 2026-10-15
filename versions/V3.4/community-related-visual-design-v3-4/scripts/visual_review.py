#!/usr/bin/env python3
"""Bridge real poster candidates to a local Label Studio review and scoped memory.

Only the Python standard library is required. Credentials remain in a separate,
private connection file. Review text is stored as data; it is never executed.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA_VERSION = 1
CONFIG_VERSION = "community-stage-1"
STAGES = {"background", "title", "body", "type_pair", "layout", "color"}
SPECIAL_CHOICES = {
    "__revise__": "合并或调整",
    "__reject__": "全部重做",
    "__undecided__": "暂不采用",
}
RATING_DIMENSIONS = ("composition", "typography", "color", "hierarchy", "style_fit")
PERSIST_CHOICE = "同类任务以后沿用"
NON_CONTEXT_KEYS = {"job_id", "candidate_id", "version", "asset_version", "is_demo"}
STAGE_LABELS = {"background": "底图选择", "title": "主题字选择", "body": "正文方向选择",
                "type_pair": "主题字与正文满意确认", "layout": "完整排版选择", "color": "精修配色选择"}
CONTEXT_LABELS = {"theme": "主题", "topic": "主题", "audience": "受众", "language": "语言",
                  "copy_density": "文案密度", "medium": "用途", "style_family": "风格"}


class BridgeError(Exception):
    """A safe, user-facing validation or connectivity failure."""


class APIError(BridgeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path):
    try:
        with Path(path).open(encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise BridgeError(f"无法读取 JSON 文件：{path}（{type(exc).__name__}）") from None


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".review-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        if fcntl:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        else:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def absolute_path(value, field):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise BridgeError(f"{field} 必须是绝对路径")
    return Path(value).resolve()


def component(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", value):
        raise BridgeError(f"{field} 必须是 ASCII 标识，允许字母、数字、点、横线和下划线")
    if value in {".", ".."}:
        raise BridgeError(f"{field} 含非法目录标识")
    return value


def within(root, *parts):
    root = Path(root).resolve()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise BridgeError("目标路径超出配置目录，已停止") from None
    return candidate


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_extension(path):
    try:
        with Path(path).open("rb") as handle:
            signature = handle.read(32)
    except OSError:
        raise BridgeError(f"图片不可读取：{path}") from None
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if signature.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if signature.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
        return ".webp"
    if signature.startswith(b"BM"):
        return ".bmp"
    raise BridgeError(f"候选文件必须是真实 PNG/JPEG/WebP/GIF/BMP 图片：{path}")


class Runtime:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        value = read_json(self.path)
        if not isinstance(value, dict):
            raise BridgeError("运行配置必须是 JSON 对象")
        if "api_key" in value:
            raise BridgeError("API 密钥必须放在 private_config 指向的私有文件中")
        self.base_url = str(value.get("base_url", "")).rstrip("/")
        parsed = urlparse(self.base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise BridgeError("当前桥接仅接受本机 HTTP Label Studio 地址")
        self.private_config = absolute_path(value.get("private_config"), "private_config")
        self.media_root = absolute_path(value.get("media_root"), "media_root")
        self.local_files_document_root = absolute_path(
            value.get("local_files_document_root", str(self.media_root)), "local_files_document_root")
        try:
            self.media_root.relative_to(self.local_files_document_root)
        except ValueError:
            raise BridgeError("media_root 必须位于 local_files_document_root 内") from None
        self.jobs_root = absolute_path(value.get("jobs_root"), "jobs_root")
        self.memory_root = absolute_path(value.get("memory_root"), "memory_root")
        self.templates_root = absolute_path(value.get("templates_root"), "templates_root")
        self.project_ids = value.get("project_ids", {})
        if not isinstance(self.project_ids, dict):
            raise BridgeError("project_ids 必须是对象")
        self._connection = None

    def connection(self):
        if self._connection is None:
            value = read_json(self.private_config)
            if not isinstance(value, dict) or not isinstance(value.get("api_key"), str) or not value["api_key"]:
                raise BridgeError("私有连接配置缺少 API 密钥")
            reviewer = value.get("reviewer_id")
            if isinstance(reviewer, bool) or not isinstance(reviewer, int) or reviewer <= 0:
                raise BridgeError("私有连接配置缺少有效 reviewer_id")
            if value.get("auth_scheme", "Token") != "Token":
                raise BridgeError("此本地配置需要 legacy Token 认证")
            self._connection = value
        return self._connection

    def project_id(self, stage, candidate_count=None):
        key = f"layout_{candidate_count}" if stage == "layout" and candidate_count is not None else stage
        if stage == "background" and candidate_count == 3:
            key = "background_3"
        identifier = self.project_ids.get(key)
        if identifier is None and key == "layout_3":
            identifier = self.project_ids.get("layout")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
            raise BridgeError(f"阶段 {key} 尚未配置 Label Studio 项目")
        return identifier


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, runtime):
        self.runtime = runtime
        self.opener = build_opener(NoRedirect())

    def request(self, method, route, payload=None):
        if not isinstance(route, str) or not route.startswith("/api/"):
            raise BridgeError("非法 API 路径")
        connection = self.runtime.connection()
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        request = Request(self.runtime.base_url + route, body, method=method, headers={
            "Authorization": "Token " + connection["api_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as exc:
            # Do not echo response bodies or request headers: either may contain secrets.
            raise APIError(f"Label Studio API 请求失败（HTTP {exc.code}）", exc.code) from None
        except (URLError, TimeoutError, OSError):
            raise APIError("无法连接本机 Label Studio，请检查服务是否运行") from None
        except (UnicodeError, ValueError):
            raise APIError("Label Studio API 返回了无法解析的 JSON") from None

    def exported_tasks(self, project_id):
        value = self.request("GET", f"/api/projects/{project_id}/export?exportType=JSON")
        if isinstance(value, list):
            return value
        if isinstance(value, dict) and isinstance(value.get("tasks"), list):
            return value["tasks"]
        raise APIError("Label Studio 导出结果不是任务数组")

    def project_tasks(self, project_id):
        # The project-specific listing in 1.23.2 returns 404 for an empty page.
        # Global task listing supports empty projects and reports a complete total.
        tasks = []
        seen = set()
        page = 1
        while True:
            value = self.request("GET", f"/api/tasks/?project={project_id}&page_size=1000&page={page}")
            if isinstance(value, list):
                if page != 1:
                    raise APIError("任务分页格式发生变化，已停止导入以避免重复")
                return value
            if not isinstance(value, dict):
                raise APIError("Label Studio 任务列表格式无法识别")
            rows = value.get("tasks", value.get("results"))
            total = value.get("total", value.get("count"))
            if (not isinstance(rows, list) or isinstance(total, bool)
                    or not isinstance(total, int) or total < 0):
                raise APIError("任务列表缺少完整分页信息，已停止导入以避免重复")
            for row in rows:
                identifier = row.get("id") if isinstance(row, dict) else None
                if not isinstance(identifier, int) or isinstance(identifier, bool) or identifier in seen:
                    raise APIError("任务分页含无效或重复 ID，已停止导入以避免重复")
                seen.add(identifier)
                tasks.append(row)
            if len(tasks) == total:
                return tasks
            if not rows or len(tasks) > total or page >= 10000:
                raise APIError("任务分页不完整或在读取期间变化，请重试")
            page += 1


def valid_manifest(raw):
    if not isinstance(raw, dict):
        raise BridgeError("manifest 必须是 JSON 对象")
    value = copy.deepcopy(raw)
    for field in ("job_id", "language", "version"):
        component(value.get(field), field)
    if value.get("stage") not in STAGES:
        raise BridgeError("stage 必须是 background/title/type_pair/layout/color；body仅兼容历史")
    value.setdefault("is_demo", False)
    if not isinstance(value["is_demo"], bool):
        raise BridgeError("is_demo 必须是布尔值")
    value.setdefault("context", {})
    value.setdefault("internal_review", {"status": "unknown"})
    if not isinstance(value["context"], dict) or not isinstance(value["internal_review"], dict):
        raise BridgeError("context 和 internal_review 必须是对象")
    overview = absolute_path(value.get("overview"), "overview")
    image_extension(overview)
    value["overview"] = str(overview)
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 5:
        raise BridgeError("candidates 必须包含 1 至 5 个真实候选")
    if value["stage"] == "title" and len(candidates) != 5:
        raise BridgeError("主题字阶段需要完整的五个候选")
    if value["stage"] == "background" and len(candidates) not in {3, 5}:
        raise BridgeError("底图阶段默认三个候选；五个仅用于既有记录/明确覆盖的兼容")
    if value["stage"] == "type_pair" and len(candidates) != 1:
        raise BridgeError("标题正文确认需要一张完整同图合览，不是三方向选稿")
    if value["stage"] == "color" and len(candidates) != 2:
        raise BridgeError("配色比较需要两个候选")
    if value["stage"] == "body" and len(candidates) != 3:
        raise BridgeError("正文方向阶段需要三个候选")
    if value["stage"] == "layout" and not 3 <= len(candidates) <= 5:
        raise BridgeError("完整排版阶段需要三个至五个候选")
    identifiers = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise BridgeError("每个候选必须是 JSON 对象")
        identifier = candidate.get("candidate_id")
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 200:
            raise BridgeError("候选缺少有效 candidate_id")
        if identifier in identifiers or identifier in SPECIAL_CHOICES:
            raise BridgeError("candidate_id 重复或使用了保留值")
        identifiers.add(identifier)
        for field in ("label", "asset_version"):
            if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                raise BridgeError(f"候选缺少 {field}")
        if "description" in candidate and not isinstance(candidate["description"], str):
            raise BridgeError("候选 description 必须是文字")
        source = absolute_path(candidate.get("path"), "candidate.path")
        image_extension(source)
        candidate["path"] = str(source)
    pair = value.get("pair")
    if pair is not None:
        if (not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]
                or any(identifier not in identifiers for identifier in pair)):
            raise BridgeError("pair 必须指向两个不同的有效 candidate_id")
        if value["stage"] != "color":
            raise BridgeError("仅配色阶段支持 pair；全组选稿请使用 stage_selection")
    return value


def location(runtime, manifest):
    parts = [manifest[field] for field in ("job_id", "stage", "language", "version")]
    return within(runtime.jobs_root, *parts, "review"), within(runtime.media_root, *parts)


def copy_image(runtime, source, destination):
    source = Path(source)
    extension = image_extension(source)
    digest = sha256(source)
    target = within(destination, digest + extension)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256(target) != digest:
            raise BridgeError("媒体目录已有同名但内容不同的文件，已停止")
    else:
        descriptor, temporary = tempfile.mkstemp(prefix=".image-", dir=target.parent)
        os.close(descriptor)
        try:
            shutil.copyfile(source, temporary)
            if sha256(temporary) != digest or sha256(source) != digest:
                raise BridgeError("复制期间源图片发生变化，请重新导出")
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    relative = target.relative_to(runtime.local_files_document_root).as_posix()
    return {
        "source_path": str(source), "copied_path": str(target), "sha256": digest,
        "url": runtime.base_url + "/data/local-files/?d=" + quote(relative, safe="/"),
    }


def pending(reason="awaiting_review"):
    return {"status": "pending", "candidate_id": None, "reason": reason,
            "selection_scope": "stage_candidate_selection"}


def prepared_record(runtime, manifest):
    review_dir, media_dir = location(runtime, manifest)
    mapping = {}
    for candidate in manifest["candidates"]:
        asset = copy_image(runtime, candidate["path"], media_dir)
        asset.update({"candidate_id": candidate["candidate_id"], "label": candidate["label"],
                      "asset_version": candidate["asset_version"],
                      "description": candidate.get("description", "")})
        mapping[candidate["candidate_id"]] = asset
    overview = copy_image(runtime, manifest["overview"], media_dir)
    ordering = manifest.get("pair") or [candidate["candidate_id"] for candidate in manifest["candidates"]]
    display = ({"left": ordering[0], "right": ordering[1]} if manifest["stage"] == "color"
               else {chr(65 + index): identifier for index, identifier in enumerate(ordering)})
    metadata = {
        "job_id": manifest["job_id"], "stage": manifest["stage"], "language": manifest["language"],
        "version": manifest["version"], "is_demo": manifest["is_demo"],
        "context": manifest["context"], "candidate_mapping": mapping,
        "display_mapping": display, "overview_asset": overview,
        "config_version": CONFIG_VERSION, "selection_scope": "stage_candidate_selection",
    }
    language = {"ZH": "中文", "EN": "英文", "zh": "中文", "en": "英文"}.get(manifest["language"], manifest["language"])
    context_lines = [f"{CONTEXT_LABELS.get(key, key)}："
                     + (value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
                     for key, value in manifest["context"].items() if key not in NON_CONTEXT_KEYS]
    summary = (f"{STAGE_LABELS[manifest['stage']]} · {language}\n当前版本：{manifest['version']}\n"
               + ("这是演示任务，不写入真实偏好。\n" if manifest["is_demo"] else "")
               + "\n".join(context_lines) + f"\n任务编号：{manifest['job_id']}")
    options = [{"value": identifier,
                "html": html.escape(mapping[identifier]["label"])
                        + (" · " + html.escape(mapping[identifier]["description"])
                           if mapping[identifier]["description"] else "")}
               for identifier in ordering]
    options.extend({"value": identifier, "html": label} for identifier, label in SPECIAL_CHOICES.items())
    if manifest["stage"] == "type_pair":
        options = [{"value": ordering[0], "html": "满意，可以进入排版"},
                   {"value": "__revise__", "html": "不满意，修改后再看"},
                   {"value": "__reject__", "html": "不满意，重新设计"},
                   {"value": "__undecided__", "html": "暂不进入排版"}]
    data = {"review_context": summary, "overview_image": overview["url"],
            "selection_options": options, "review_metadata": metadata}
    for index, identifier in enumerate(ordering):
        letter = chr(97 + index)
        data["image_" + letter] = mapping[identifier]["url"]
        data["label_" + letter] = mapping[identifier]["label"]
    return {
        "schema_version": SCHEMA_VERSION, "manifest": manifest,
        "project_id": runtime.project_id(manifest["stage"], len(manifest["candidates"])), "task_id": None,
        "task": {"data": data}, "selection": pending(), "feedback": {},
        "created_at": now(), "updated_at": now(),
    }


def task_data_matches(record, task):
    data = task.get("data") if isinstance(task, dict) else None
    if not isinstance(data, dict):
        return False
    expected = record["task"]["data"]
    return all(data.get(key) == value for key, value in expected.items())


def task_id_from_import(response):
    if isinstance(response, dict):
        ids = response.get("task_ids", [])
        if isinstance(ids, list) and len(ids) == 1:
            item = ids[0]
            identifier = item.get("id") if isinstance(item, dict) else item
            if isinstance(identifier, int) and not isinstance(identifier, bool) and identifier > 0:
                return identifier
    return None


def export_manifest(runtime, manifest_path, submit=False, client=None):
    manifest = valid_manifest(read_json(manifest_path))
    review_dir, _ = location(runtime, manifest)
    review_path = within(review_dir, "review.json")
    task_path = within(review_dir, "task.json")
    with locked(within(review_dir, ".lock")):
        fresh = prepared_record(runtime, manifest)
        if review_path.exists():
            record = read_json(review_path)
            if record.get("manifest") != manifest or record.get("task") != fresh["task"]:
                raise BridgeError("该任务阶段版本已导出且资产或说明已改变；请使用新的 version")
        else:
            record = fresh
            record["creation_sequence"] = next_creation_sequence(runtime)
            atomic_json(review_path, record)
            atomic_json(task_path, [record["task"]])
        if submit and record.get("task_id") is None:
            client = client or Client(runtime)
            # A previous import may have succeeded before the local process stopped.
            existing = [task for task in client.project_tasks(record["project_id"])
                        if task_data_matches(record, task)]
            if len(existing) > 1:
                raise BridgeError("网页存在重复任务，请保留一份后再次同步")
            if existing:
                identifier = existing[0].get("id")
            else:
                response = client.request("POST", f"/api/projects/{record['project_id']}/import", [record["task"]])
                identifier = task_id_from_import(response)
                if identifier is None:
                    matches = [task for task in client.project_tasks(record["project_id"])
                               if task_data_matches(record, task)]
                    if len(matches) != 1:
                        raise BridgeError("已发送导入请求但未得到唯一 task_id；本地任务已保留，请检查网页后同步")
                    identifier = matches[0].get("id")
            if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
                raise BridgeError("服务器未返回有效 task_id")
            record["task_id"] = identifier
            record["submitted_at"] = now()
            record["updated_at"] = now()
            atomic_json(review_path, record)
    activate_job(runtime, manifest["job_id"])
    project_url = runtime.base_url + f"/projects/{record['project_id']}/data/"
    task_url = project_url + f"?task={record['task_id']}" if record.get("task_id") is not None else None
    return {"job_id": manifest["job_id"], "stage": manifest["stage"],
            "project_id": record["project_id"], "task_id": record.get("task_id"),
            "review_record": str(review_path), "task_file": str(task_path),
            "selection": record["selection"], "submitted": record.get("task_id") is not None,
            # Label Studio 1.23.2's labeling=1 queue can ignore task=ID. Use the
            # exact task link so a reviewer cannot accidentally judge another version.
            "project_url": project_url, "task_url": task_url, "review_url": task_url}


def integrity_errors(runtime, record):
    errors = []
    metadata = record["task"]["data"]["review_metadata"]
    assets = list(metadata["candidate_mapping"].values()) + [metadata["overview_asset"]]
    for asset in assets:
        for field in ("source_path", "copied_path"):
            try:
                path = absolute_path(asset[field], field)
                if field == "copied_path":
                    path.relative_to(runtime.media_root)
                if not path.is_file() or sha256(path) != asset["sha256"]:
                    errors.append({"asset": asset.get("candidate_id", "overview"), "file": field,
                                   "reason": "missing_or_changed"})
            except (BridgeError, OSError, ValueError, KeyError):
                errors.append({"asset": asset.get("candidate_id", "overview"), "file": field,
                               "reason": "missing_or_outside_media_root"})
    return errors


def author_id(annotation):
    author = annotation.get("completed_by")
    if isinstance(author, dict):
        author = author.get("id")
    return author if isinstance(author, int) and not isinstance(author, bool) else None


def cancelled(annotation):
    return any(annotation.get(field) is True for field in ("was_cancelled", "cancelled", "is_deleted"))


def result_fields(annotation):
    result = annotation.get("result", [])
    if not isinstance(result, list):
        return {}
    # Duplicate control results are ambiguous and must not silently choose the last one.
    fields = {}
    duplicates = set()
    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get("from_name"), str):
            continue
        name = item["from_name"]
        if name in fields:
            duplicates.add(name)
        else:
            fields[name] = item.get("value", {})
    for name in duplicates:
        fields[name] = {}
    return fields


def choice(fields, name):
    value = fields.get(name, {})
    values = value.get("choices", []) if isinstance(value, dict) else []
    return values[0] if isinstance(values, list) and len(values) == 1 and isinstance(values[0], str) else None


def text_field(fields, name):
    value = fields.get(name, {})
    values = value.get("text", []) if isinstance(value, dict) else []
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        return ""
    return "\n".join(values).strip()[:10000]


def rating(fields, name):
    value = fields.get(name, {})
    number = value.get("rating") if isinstance(value, dict) else None
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        return None
    return number if math.isfinite(number) and 1 <= number <= 5 else None


def event_sort(annotation):
    stamp = annotation.get("updated_at") or annotation.get("created_at") or ""
    try:
        instant = dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=dt.timezone.utc)
        time_value = instant.timestamp()
    except (ValueError, TypeError, OverflowError):
        time_value = 0
    identifier = annotation.get("id", 0)
    return [time_value, identifier if isinstance(identifier, int) and not isinstance(identifier, bool) else 0]


def feedback_id(record, annotation):
    return f"ls:{record['project_id']}:{record['task_id']}:{annotation['id']}"


def normalize_feedback(record, annotation, reviewer_id, trusted=True, assets_valid=True):
    fields = result_fields(annotation)
    meta = record["task"]["data"]["review_metadata"]
    display = meta["display_mapping"]
    ordering = ([display["left"], display["right"]] if "left" in display
                else [display[key] for key in sorted(display)])
    scores = {}
    for index, identifier in enumerate(ordering):
        prefix = chr(97 + index) + "_"
        scores[identifier] = {dimension: rating(fields, prefix + dimension) for dimension in RATING_DIMENSIONS}
    reviewer = author_id(annotation) == reviewer_id
    is_cancelled = cancelled(annotation)
    is_prediction = annotation.get("is_prediction") is True or annotation.get("prediction") is True
    active = not is_cancelled and not is_prediction
    return {
        "feedback_id": feedback_id(record, annotation), "annotation_id": annotation["id"],
        "project_id": record["project_id"], "task_id": record["task_id"],
        "job_id": meta["job_id"], "stage": meta["stage"], "language": meta["language"],
        "version": meta["version"], "is_demo": meta["is_demo"], "context": meta["context"],
        "candidate_mapping": copy.deepcopy(meta["candidate_mapping"]),
        "display_mapping": copy.deepcopy(display), "completed_by": author_id(annotation),
        "is_local_reviewer": reviewer, "active": active, "cancelled": is_cancelled,
        "is_prediction": is_prediction, "task_integrity_valid": trusted,
        "asset_integrity_valid": assets_valid, "stage_selection": choice(fields, "stage_selection"),
        "pair_preference": choice(fields, "pair_preference"), "ratings": scores,
        "likes": text_field(fields, "likes"), "changes": text_field(fields, "changes"),
        "persist_preference": choice(fields, "persist_preference"),
        "preference_statement": text_field(fields, "preference_statement"),
        "annotation_updated_at": annotation.get("updated_at") or annotation.get("created_at"),
        "source": "label_studio_human_review", "instruction_text_is_data": True,
    }


def selection_from_feedback(feedback, record):
    if not feedback["active"]:
        return pending("review_cancelled_or_prediction")
    selected = feedback["stage_selection"]
    mapping = record["task"]["data"]["review_metadata"]["candidate_mapping"]
    if selected in mapping:
        state = {"status": "selected", "candidate_id": selected, "reason": "explicit_stage_selection"}
    elif selected == "__revise__":
        state = {"status": "revision_requested", "candidate_id": None, "reason": "explicit_revision_request"}
    elif selected == "__reject__":
        state = {"status": "rejected", "candidate_id": None, "reason": "explicit_rejection"}
    else:
        state = pending("explicit_undecided" if selected == "__undecided__" else "no_explicit_stage_selection")
    state.update({"selection_scope": "stage_candidate_selection", "feedback_id": feedback["feedback_id"],
                  "annotation_id": feedback["annotation_id"]})
    return state


def scope_context(context):
    if not isinstance(context, dict):
        return {}
    return {key: value for key, value in context.items()
            if key not in NON_CONTEXT_KEYS and value not in (None, "", [], {})}


def eligible_feedback(feedback):
    return (feedback.get("active") is True and feedback.get("is_local_reviewer") is True
            and feedback.get("is_demo") is False and feedback.get("task_integrity_valid") is True
            and feedback.get("asset_integrity_valid") is True and not feedback.get("is_prediction"))


def feedback_fingerprint(feedback):
    # A server timestamp changing by itself is not a new human opinion. History is
    # excluded so preserving old revisions cannot alter the current evidence hash.
    content = {key: value for key, value in feedback.items()
               if key not in {"history", "annotation_updated_at"}}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def with_feedback_history(old, fresh):
    fresh = copy.deepcopy(fresh)
    history = copy.deepcopy(old.get("history", [])) if old else []
    if old:
        old_fingerprint = feedback_fingerprint(old)
        if old_fingerprint != feedback_fingerprint(fresh):
            snapshot = {key: value for key, value in old.items() if key != "history"}
            history.append({"archived_at": now(), "fingerprint": old_fingerprint, "feedback": snapshot})
    fresh["history"] = history
    return fresh


def archived_preference(preference, status, reason):
    value = copy.deepcopy(preference)
    value.update({"status": status, "reason": reason, "archived_at": now()})
    return value


def evidence_fingerprints(evidence, records):
    return {identifier: feedback_fingerprint(records[identifier]) for identifier in evidence if identifier in records}


def valid_preference_evidence(preference, records):
    evidence = preference.get("evidence", [])
    expected = preference.get("evidence_fingerprints", {})
    return (bool(evidence) and all(identifier in records and eligible_feedback(records[identifier])
                                  and expected.get(identifier) == feedback_fingerprint(records[identifier])
                                  for identifier in evidence))


def memory_paths(runtime):
    return (within(runtime.memory_root, "feedback.json"), within(runtime.memory_root, "profile.json"),
            within(runtime.memory_root, ".lock"))


def memory_digest(records):
    # Timestamps and history remain in the saved feedback; this digest also lets
    # the next sync repair a profile write interrupted after feedback was saved.
    return hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def rebuild_profile(memory, previous, feedback_digest=None):
    records = memory["records"]
    preferences = []
    observations = []
    history = copy.deepcopy(previous.get("preference_history", []))
    previous_active = {preference["preference_id"]: preference
                       for preference in previous.get("confirmed_preferences", [])}
    for feedback in sorted(records.values(), key=lambda value: value["feedback_id"]):
        if not eligible_feedback(feedback):
            continue
        observations.append({"feedback_id": feedback["feedback_id"], "context": feedback["context"],
                             "likes": feedback["likes"], "changes": feedback["changes"],
                             "ratings": feedback["ratings"], "stage_selection": feedback["stage_selection"],
                             "status": "observation_only"})
        scope = scope_context(feedback["context"])
        if (feedback.get("persist_preference") == PERSIST_CHOICE
                and feedback.get("preference_statement") and scope):
            proposed = {
                "preference_id": "feedback:" + feedback["feedback_id"],
                "statement": feedback["preference_statement"], "scope": scope,
                "evidence": [feedback["feedback_id"]], "confirmed_via": "explicit_review_preference",
                "evidence_fingerprints": evidence_fingerprints([feedback["feedback_id"]], records),
                "status": "active", "instruction_text_is_data": True,
            }
            # An explicit replacement suppresses only the exact superseded evidence
            # revision, so a subsequent edited web review can express a new preference.
            suppressed = any(old.get("status") == "superseded"
                             and old.get("preference_id") == proposed["preference_id"]
                             and old.get("evidence_fingerprints") == proposed["evidence_fingerprints"]
                             for old in history)
            if not suppressed:
                preferences.append(proposed)
    # Explicit conversational confirmations remain tied to active, unchanged evidence.
    for preference in previous.get("confirmed_preferences", []):
        if preference.get("confirmed_via") != "explicit_user_instruction":
            continue
        if valid_preference_evidence(preference, records):
            preferences.append(preference)
    active = {preference["preference_id"]: preference for preference in preferences}
    for identifier, old in previous_active.items():
        new = active.get(identifier)
        if new is None or old.get("evidence_fingerprints") != new.get("evidence_fingerprints"):
            # Move invalidated evidence to history once; it is absent from the next
            # active set, so repeated sync cannot grow this history indefinitely.
            history.append(archived_preference(old, "inactive", "evidence_changed_or_withdrawn"))
    return {"schema_version": SCHEMA_VERSION, "confirmed_preferences": preferences,
            "preference_history": history,
            "observations": observations, "updated_at": now(), "instruction_text_is_data": True,
            "feedback_digest": feedback_digest or memory_digest(records)}


def update_memory_batch(runtime, batch):
    """Merge complete successful snapshots once, preserving deletions and revisions."""
    real = [record for record in batch if not record["manifest"]["is_demo"]]
    if not real:
        return {"updated": False, "reason": "demo_excluded"}
    feedback_path, profile_path, lock_path = memory_paths(runtime)
    with locked(lock_path):
        memory = read_json(feedback_path) if feedback_path.exists() else {"schema_version": SCHEMA_VERSION, "records": {}}
        previous = read_json(profile_path) if profile_path.exists() else {"confirmed_preferences": []}
        records = memory["records"]
        original = copy.deepcopy(records)
        for record in real:
            local = {identifier: feedback for identifier, feedback in record["feedback"].items()
                     if feedback.get("is_local_reviewer") is True}
            # A complete task snapshot supersedes old entries, including deleted
            # annotations and an annotation whose reviewer has changed.
            for identifier, feedback in list(records.items()):
                if feedback.get("project_id") == record["project_id"] and feedback.get("task_id") == record["task_id"]:
                    if identifier not in local:
                        removed = copy.deepcopy(feedback)
                        removed.update({"active": False, "removed": True})
                        records[identifier] = with_feedback_history(feedback, removed)
            for identifier, feedback in local.items():
                records[identifier] = copy.deepcopy(feedback)
        changed = records != original or not feedback_path.exists()
        digest = memory_digest(records)
        profile_changed = previous.get("feedback_digest") != digest
        if changed:
            memory["updated_at"] = now()
            atomic_json(feedback_path, memory)
        if profile_changed:
            atomic_json(profile_path, rebuild_profile(memory, previous, digest))
    return {"updated": changed or profile_changed, "feedback_updated": changed,
            "profile_updated": profile_changed,
            "feedback_file": str(feedback_path), "profile_file": str(profile_path)}


def update_memory(runtime, record):
    # Retain the existing helper for direct callers.
    return update_memory_batch(runtime, [record])


def apply_snapshot(runtime, record, task, reviewer_id):
    old_feedback = record.get("feedback", {})
    trusted = task is not None and task_data_matches(record, task)
    asset_errors = integrity_errors(runtime, record)
    assets_valid = not asset_errors
    annotations = task.get("annotations", []) if isinstance(task, dict) else []
    if not isinstance(annotations, list):
        raise BridgeError("任务 annotations 不是完整数组，已停止回读该任务")
    annotations = [annotation for annotation in annotations
                   if isinstance(annotation, dict) and isinstance(annotation.get("id"), int)
                   and not isinstance(annotation.get("id"), bool) and annotation["id"] > 0]
    live_ids = {feedback_id(record, annotation) for annotation in annotations}
    feedbacks = {}
    for identifier, old in old_feedback.items():
        if identifier not in live_ids:
            removed = copy.deepcopy(old)
            removed["active"] = False
            removed["removed"] = True
            removed["task_integrity_valid"] = trusted
            removed["asset_integrity_valid"] = assets_valid
            feedbacks[identifier] = with_feedback_history(old, removed)
    for annotation in annotations:
        item = normalize_feedback(record, annotation, reviewer_id, trusted, assets_valid)
        feedbacks[item["feedback_id"]] = with_feedback_history(old_feedback.get(item["feedback_id"]), item)
    record["feedback"] = feedbacks
    events = [annotation for annotation in annotations if author_id(annotation) == reviewer_id
              and annotation.get("is_prediction") is not True and annotation.get("prediction") is not True]
    events.sort(key=event_sort)
    prior = record.get("last_reviewer_event")
    newest = events[-1] if events else None
    if not trusted:
        record["selection"] = pending("task_missing" if task is None else "server_task_data_changed")
    elif not assets_valid:
        record["selection"] = pending("asset_missing_or_changed")
    elif newest is None:
        record["selection"] = pending("review_deleted" if prior else "awaiting_local_reviewer")
    else:
        identifier = feedback_id(record, newest)
        # Deleting the active annotation must not resurrect an older selection.
        old_active_removed = prior and prior["feedback_id"] not in live_ids
        older_only = old_active_removed and event_sort(newest) <= prior.get("sort_key", [0, 0])
        if older_only:
            record["selection"] = pending("latest_review_deleted")
        else:
            record["selection"] = selection_from_feedback(feedbacks[identifier], record)
            record["last_reviewer_event"] = {"feedback_id": identifier, "annotation_id": newest["id"],
                                              "sort_key": event_sort(newest)}
    record["integrity"] = {"task_data_valid": trusted, "assets_valid": assets_valid, "asset_errors": asset_errors}
    record["synced_at"] = now()
    record["updated_at"] = now()
    return record


def validate_review_record(record):
    if not isinstance(record, dict) or not isinstance(record.get("manifest"), dict):
        raise BridgeError("本地评审记录及 manifest 必须是对象")
    manifest = record["manifest"]
    for field in ("job_id", "language", "version"):
        component(manifest.get(field), field)
    if manifest.get("stage") not in STAGES:
        raise BridgeError("本地评审记录含非法阶段")
    identifier = record.get("project_id")
    task_id = record.get("task_id")
    if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
        raise BridgeError("本地评审记录缺少有效 project_id")
    if task_id is not None and (isinstance(task_id, bool) or not isinstance(task_id, int) or task_id <= 0):
        raise BridgeError("本地评审记录含无效 task_id")
    task = record.get("task")
    data = task.get("data") if isinstance(task, dict) else None
    meta = data.get("review_metadata") if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        raise BridgeError("本地评审记录缺少完整 task.data.review_metadata")
    if (not isinstance(record.get("selection"), dict) or not isinstance(record.get("feedback"), dict)
            or any(not isinstance(feedback, dict) or not isinstance(feedback.get("history", []), list)
                   for feedback in record["feedback"].values())):
        raise BridgeError("本地评审记录 selection/feedback 格式异常")
    mapping = meta.get("candidate_mapping")
    if (not isinstance(mapping, dict) or not mapping
            or any(not isinstance(asset, dict) for asset in mapping.values())
            or not isinstance(meta.get("overview_asset"), dict)
            or not isinstance(meta.get("display_mapping"), dict)):
        raise BridgeError("本地评审记录缺少完整候选与总览映射")
    for field in ("job_id", "stage", "language", "version", "is_demo", "context"):
        if field not in manifest or field not in meta or meta[field] != manifest[field]:
            raise BridgeError("本地评审记录元数据与 manifest 不一致")
    prior = record.get("last_reviewer_event")
    if prior is not None and (not isinstance(prior, dict) or not isinstance(prior.get("feedback_id"), str)
                              or not isinstance(prior.get("sort_key"), list)
                              or len(prior["sort_key"]) != 2
                              or any(isinstance(value, bool) or not isinstance(value, (int, float))
                                     or not math.isfinite(value) for value in prior["sort_key"])):
        raise BridgeError("本地评审记录 last_reviewer_event 格式异常")
    return manifest


def review_records(runtime, job_id=None, errors=None):
    root = runtime.jobs_root
    if job_id is not None:
        component(job_id, "--job-id")
        root = within(root, job_id)
    if not root.exists():
        return []
    result = []
    for path in sorted(root.glob("**/review/review.json")):
        try:
            resolved = path.resolve()
            try:
                resolved.relative_to(runtime.jobs_root)
            except ValueError:
                raise BridgeError("任务目录存在越界符号链接，已停止") from None
            record = read_json(resolved)
            manifest = validate_review_record(record)
            expected, _ = location(runtime, manifest)
            if resolved != within(expected, "review.json"):
                raise BridgeError("评审记录路径与任务标识不一致")
            result.append(resolved)
        except BridgeError as exc:
            if errors is None:
                raise
            # Background discovery isolates a bad historical record, retains an
            # explicit per-path error, and leaves that record/evidence untouched.
            errors.append({"review_record": str(path), "scope": "record_validation", "error": str(exc)})
    return result


def next_creation_sequence(runtime):
    path = within(runtime.jobs_root, ".review-sequence.json")
    with locked(within(runtime.jobs_root, ".activity.lock")):
        highest = 0
        try:
            value = read_json(path) if path.exists() else {}
            last = value.get("last") if isinstance(value, dict) else None
            if isinstance(last, int) and not isinstance(last, bool) and last > 0:
                highest = last
        except BridgeError:
            pass
        # Recover a missing/corrupt/stale counter from existing records. This
        # metadata-only scan happens once per new export, never on a fast poll.
        for existing in runtime.jobs_root.glob("**/review/review.json"):
            try:
                existing.resolve().relative_to(runtime.jobs_root)
                value = read_json(existing)
                sequence = value.get("creation_sequence") if isinstance(value, dict) else None
                if isinstance(sequence, int) and not isinstance(sequence, bool) and sequence > highest:
                    highest = sequence
            except (BridgeError, ValueError):
                continue
        sequence = highest + 1
        atomic_json(path, {"last": sequence})
        return sequence


def active_job_path(runtime):
    return within(runtime.jobs_root, ".active-job.json")


def activate_job(runtime, job_id):
    component(job_id, "job_id")
    path = active_job_path(runtime)
    with locked(within(runtime.jobs_root, ".activity.lock")):
        try:
            previous = read_json(path) if path.exists() else {}
        except BridgeError:
            previous = {}
        if not isinstance(previous, dict) or previous.get("job_id") != job_id:
            atomic_json(path, {"job_id": job_id})


def background_records(runtime, paths, include_history=False, errors=None):
    """Prioritize the newest job's latest unselected stage/language versions.

    Discovery reads only review JSON metadata. Every selected record still gets
    a fresh task snapshot and full SHA verification; no stat-based asset cache.
    """
    items = []
    for path in paths:
        try:
            items.append((path, read_json(path)))
        except BridgeError as exc:
            if errors is None:
                raise
            errors.append({"review_record": str(path), "scope": "record_validation", "error": str(exc)})
    paths = [item[0] for item in items]
    if not items:
        return [], {"active_job_id": None, "active_count": 0, "history_count": 0}
    def rank(item):
        path, record = item
        sequence = record.get("creation_sequence", 0)
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
            sequence = 0
        version = str(record["manifest"]["version"])
        natural_version = tuple((1, int(part)) if part.isdigit() else (0, part.lower())
                                for part in re.split(r"(\d+)", version) if part)
        # New exports use an atomic monotonic sequence, independent of wall-clock
        # jumps and arbitrary version names. Only legacy records fall back to time.
        return (bool(sequence), sequence, event_sort({"created_at": record.get("created_at")})[0],
                natural_version, str(path))
    active_job = max(items, key=rank)[1]["manifest"]["job_id"]
    try:
        marker = read_json(active_job_path(runtime)) if active_job_path(runtime).exists() else {}
        marked = component(marker.get("job_id"), "active_job") if isinstance(marker, dict) else None
        if marked in {item[1]["manifest"]["job_id"] for item in items}:
            active_job = marked
    except BridgeError:
        # This pointer affects scheduling only. Missing/corrupt markers recover
        # from existing records without altering review or evidence content.
        pass
    latest = {}
    for item in items:
        manifest = item[1]["manifest"]
        if manifest["job_id"] != active_job:
            continue
        key = (manifest["stage"], manifest["language"])
        if key not in latest or rank(item) > rank(latest[key]):
            latest[key] = item
    active = sorted((item[0] for item in latest.values()
                     if item[1].get("selection", {}).get("status") != "selected"), key=str)
    active_set = set(active)
    history = [path for path in paths if path not in active_set]
    return active + (history if include_history else []), {
        "active_job_id": active_job, "active_count": len(active), "history_count": len(history)}


def record_content(record):
    # These fields describe the last persisted content change. A fresh check is
    # reported in the sync result instead of rewriting every review JSON.
    return {key: value for key, value in record.items() if key not in {"synced_at", "updated_at"}}


def sync_reviews(runtime, job_id=None, client=None, background=False, include_history=False):
    client = client or Client(runtime)
    if background and job_id is not None:
        raise BridgeError("--background 与 --job-id 不能同时使用")
    if include_history and not background:
        raise BridgeError("--include-history 仅供 --background 使用")
    errors = []
    paths = list(dict.fromkeys(review_records(runtime, job_id, errors if background else None)))
    schedule = {"active_count": len(paths), "history_count": 0}
    if background:
        paths, schedule = background_records(runtime, paths, include_history, errors)
    reviewer_id = runtime.connection()["reviewer_id"] if paths else None
    listings = {}
    results = []
    successful = []
    for path in paths:
        try:
            with locked(path.parent / ".lock"):
                record = read_json(path)
                validate_review_record(record)
                before = copy.deepcopy(record)
                project_id = record["project_id"]
                task_id = record.get("task_id")
                if task_id is None:
                    # Full project listings are needed only to discover a task
                    # manually imported after a local, unsubmitted export.
                    if project_id not in listings:
                        listings[project_id] = client.project_tasks(project_id)
                    tasks = listings[project_id]
                    matches = [task for task in tasks if task_data_matches(record, task)]
                    if len(matches) > 1:
                        raise BridgeError("网页有重复任务，无法确定哪一份评价属于当前版本")
                    if not matches:
                        results.append({"review_record": str(path), "status": "not_submitted", "selection": record["selection"]})
                        continue
                    task = matches[0]
                    record["task_id"] = task["id"]
                else:
                    # GET a complete current snapshot. The export endpoint writes
                    # persistent files on every request and must not be polled.
                    try:
                        task = client.request("GET", f"/api/tasks/{task_id}/")
                    except APIError as exc:
                        if exc.status == 404:
                            task = None
                        else:
                            raise
                if task is not None and not isinstance(task, dict):
                    raise BridgeError("服务器任务不是完整对象，旧评价状态已保留")
                if task is not None and "annotations" not in task:
                    task = client.request("GET", f"/api/tasks/{record['task_id']}/")
                    if not isinstance(task, dict) or "annotations" not in task:
                        raise BridgeError("服务器未返回完整标注快照，旧评价状态已保留")
                record = apply_snapshot(runtime, record, task, reviewer_id)
                changed = record_content(before) != record_content(record)
                # Save changed state first; the batch commit rereads it under locks.
                if changed:
                    atomic_json(path, record)
                successful.append(path)
                results.append({"review_record": str(path), "job_id": record["manifest"]["job_id"],
                                "stage": record["manifest"]["stage"], "task_id": record.get("task_id"),
                                "selection": record["selection"], "integrity": record["integrity"],
                                "feedback_count": len(record["feedback"]), "changed": changed,
                                "is_demo": record["manifest"]["is_demo"]})
        except BridgeError as exc:
            errors.append({"review_record": str(path), "error": str(exc)})
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            message = f"本地评审记录或服务器快照格式异常（{type(exc).__name__}），旧状态已保留"
            if not background:
                raise BridgeError(message) from None
            errors.append({"review_record": str(path), "scope": "record_validation", "error": message})
    if successful:
        try:
            # All code acquires task locks before the memory lock. Acquire task
            # locks in fixed order and reread their latest atomic snapshots so a
            # concurrent explicit sync cannot be overwritten by our earlier read.
            with ExitStack() as stack:
                ordered = sorted(set(successful), key=str)
                for path in ordered:
                    stack.enter_context(locked(path.parent / ".lock"))
                memory = update_memory_batch(runtime, [read_json(path) for path in ordered])
            for result in results:
                if "is_demo" in result:
                    is_demo = result.pop("is_demo")
                    result["memory"] = ({"updated": False, "reason": "demo_excluded"}
                                        if is_demo else memory)
        except BridgeError as exc:
            errors.append({"scope": "memory_batch", "error": str(exc)})
    if job_id is not None and results and not errors:
        activate_job(runtime, job_id)
    return {"synced": results, "errors": errors, "checked_at": now(),
            "changed_count": sum(result.get("changed", False) for result in results),
            "scope": "background" if background else "explicit",
            "history_included": include_history if background else True, **schedule}


def context_matches(scope, context):
    scope = scope_context(scope)
    context = scope_context(context)
    return bool(scope) and bool(context) and all(key in context and context[key] == value for key, value in scope.items())


def matching_preferences(runtime, context):
    if not isinstance(context, dict):
        raise BridgeError("context 必须是 JSON 对象")
    _, profile_path, lock_path = memory_paths(runtime)
    with locked(lock_path):
        profile = read_json(profile_path) if profile_path.exists() else {"confirmed_preferences": []}
    selected = [preference for preference in profile.get("confirmed_preferences", [])
                if context_matches(preference.get("scope", {}), context)]
    return {"context": context, "preferences": selected, "instruction_text_is_data": True,
            "observations_excluded": True}


def confirm_preference(runtime, statement, context, evidence, replace=None, append=False):
    if not isinstance(statement, str) or not statement.strip() or len(statement) > 10000:
        raise BridgeError("长期偏好需要有效的明确文字说明")
    scope = scope_context(context)
    if not scope:
        raise BridgeError("长期偏好必须限定适用情境，不能使用空 context")
    if replace and append:
        raise BridgeError("--replace 和 --append 不能同时使用")
    feedback_path, profile_path, lock_path = memory_paths(runtime)
    with locked(lock_path):
        memory = read_json(feedback_path) if feedback_path.exists() else {"records": {}}
        item = memory["records"].get(evidence)
        if not item or not eligible_feedback(item):
            raise BridgeError("evidence 必须指向本机评审者对真实、当前且未撤销资产的有效评价")
        if not context_matches(scope, item["context"]):
            raise BridgeError("偏好适用情境必须与证据情境相符")
        profile = read_json(profile_path) if profile_path.exists() else {"confirmed_preferences": []}
        profile = rebuild_profile(memory, profile)
        active = profile["confirmed_preferences"]
        if replace:
            target = next((old for old in active if old["preference_id"] == replace), None)
            if target is None:
                raise BridgeError("--replace 必须指向当前有效的 preference_id")
            profile["preference_history"].append(archived_preference(target, "superseded", "explicit_user_replacement"))
            active = [old for old in active if old["preference_id"] != replace]
        elif not append:
            existing = [old for old in active if old.get("scope") == scope and old.get("evidence") == [evidence]]
            identical = next((old for old in existing if old.get("statement") == statement.strip()), None)
            if identical is not None:
                return {"confirmed_preference": identical, "profile_file": str(profile_path), "already_confirmed": True}
            if existing:
                identifiers = ", ".join(old["preference_id"] for old in existing)
                raise BridgeError(f"同一情境和证据已有有效偏好（{identifiers}）；明确更正请用 --replace PREFERENCE_ID，独立追加请用 --append")
        digest = hashlib.sha256(json.dumps([statement.strip(), scope, evidence], ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]
        preference = {"preference_id": "user:" + digest, "statement": statement.strip(), "scope": scope,
                      "evidence": [evidence], "confirmed_via": "explicit_user_instruction",
                      "evidence_fingerprints": evidence_fingerprints([evidence], memory["records"]),
                      "status": "active",
                      "instruction_text_is_data": True}
        profile["confirmed_preferences"] = [old for old in active
                                            if old["preference_id"] != preference["preference_id"]] + [preference]
        atomic_json(profile_path, profile)
    return {"confirmed_preference": preference, "profile_file": str(profile_path),
            "replaced_preference_id": replace, "explicit_append": append}


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--config", required=True, help="本机 service/runtime.json 绝对路径")
    operations = command.add_subparsers(dest="operation", required=True)
    export = operations.add_parser("export", help="导出真实候选并可提交到网页")
    export.add_argument("--manifest", required=True)
    export.add_argument("--submit", action="store_true")
    sync = operations.add_parser("sync", help="回读评价与明确选稿状态")
    sync.add_argument("--job-id")
    sync.add_argument("--background", action="store_true", help="后台优先回读当前未选任务")
    sync.add_argument("--include-history", action="store_true", help="后台周期性完整回读历史")
    preferences = operations.add_parser("preferences", help="读取已确认且符合当前情境的偏好")
    preferences.add_argument("--context", required=True)
    confirm = operations.add_parser("confirm-preference", help="仅在用户明确提出长期要求后记录偏好")
    confirm.add_argument("--statement", required=True)
    confirm.add_argument("--context", required=True)
    confirm.add_argument("--evidence", required=True)
    changes = confirm.add_mutually_exclusive_group()
    changes.add_argument("--replace", metavar="PREFERENCE_ID", help="用户明确更正时替换一条当前有效偏好")
    changes.add_argument("--append", action="store_true", help="用户明确要求保留原有偏好并独立追加")
    return command


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        runtime = Runtime(arguments.config)
        if arguments.operation == "export":
            result = export_manifest(runtime, Path(arguments.manifest).expanduser().resolve(), arguments.submit)
        elif arguments.operation == "sync":
            result = sync_reviews(runtime, arguments.job_id, background=arguments.background,
                                  include_history=arguments.include_history)
        elif arguments.operation == "preferences":
            result = matching_preferences(runtime, read_json(Path(arguments.context).expanduser().resolve()))
        else:
            result = confirm_preference(runtime, arguments.statement,
                                        read_json(Path(arguments.context).expanduser().resolve()), arguments.evidence,
                                        arguments.replace, arguments.append)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 1 if result.get("errors") else 0
    except BridgeError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError, ValueError) as exc:
        # Never include arbitrary exception text from an auth or JSON payload.
        print(json.dumps({"error": f"评审数据或本地文件异常（{type(exc).__name__}），已停止"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
