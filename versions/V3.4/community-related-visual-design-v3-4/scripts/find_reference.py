#!/usr/bin/env python3
"""Return a small selection from the existing visual-reference indexes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

LIBRARIES = {
    "layout": "layout-priority-references",
    "type": "type-generation-references",
    "posters": "reference-posters",
}
# These are retrieval hints, not asserted classifications of the source images.
SKELETON_HINTS = {
    "S1": ("时间", "地点", "日期", "公告", "通知"),
    "S2": ("步骤", "流程", "行动", "办理"),
    "S3": ("清单", "条目", "编号", "并列", "服务信息"),
    "S4": ("分类", "对比", "分栏", "双栏", "双项"),
    "S5": ("警示", "禁止", "安全", "风险", "应急"),
    "S6": ("招募", "邀约", "报名", "活动", "志愿"),
    "S7": ("数据", "公示", "数字", "统计"),
    "S8": ("空间", "导视", "地图", "点位", "分区"),
    "S9": ("求助", "联络", "号码", "电话", "联系方式"),
}
SEARCH_FIELDS = (
    "id", "path", "display_name", "features", "suitable_content",
    "adaptation", "type_families", "context_tags", "uses", "body_simplification",
    "observed_palette", "domain_id", "domain_name", "asset_role",
)
STRUCTURE_CHOICES = {
    "text_density": ("low", "medium", "high"),
    "subject_positions": ("left", "center", "right", "top", "bottom", "distributed", "none"),
    "text_zones": ("left", "center", "right", "top", "bottom", "throughout"),
    "reading_route": ("top-to-bottom", "left-to-right", "vertical", "modular"),
    "title_anchor": ("top-left", "top-center", "top-right", "middle-left", "middle-center",
                     "middle-right", "bottom-left", "bottom-center", "bottom-right",
                     "vertical-left", "vertical-right", "mixed", "unknown"),
}
STRUCTURE_WORDS = {
    "text_density": {"low": "低密度 短文案 少量文字", "medium": "中密度 中等文案",
                     "high": "高密度 长文案 密集信息"},
    "subject_positions": {"left": "主体偏左", "center": "主体居中", "right": "主体偏右",
                          "top": "主体偏上", "bottom": "主体偏下",
                          "distributed": "主体分散", "none": "无主体"},
    "text_zones": {"left": "文字区左侧", "center": "文字区中部", "right": "文字区右侧",
                   "top": "文字区上方", "bottom": "文字区下方", "throughout": "文字满版"},
    "reading_route": {"top-to-bottom": "从上到下", "left-to-right": "从左到右",
                      "vertical": "竖向阅读", "modular": "模块阅读"},
    "title_anchor": {"top-left": "标题左上", "top-center": "标题上方居中", "top-right": "标题右上",
                     "middle-left": "标题左中", "middle-center": "标题中部居中", "middle-right": "标题右中",
                     "bottom-left": "标题左下", "bottom-center": "标题下方居中", "bottom-right": "标题右下",
                     "vertical-left": "标题左侧竖排", "vertical-right": "标题右侧竖排"},
}


def observed_structure(entry):
    """Only use visual labels bound to the same indexed source revision."""
    review = entry.get("visual_review", {})
    structure = entry.get("observed_structure", {})
    if (isinstance(review, dict) and isinstance(structure, dict)
            and review.get("status") == "observed" and review.get("method") == "actual_image"
            and entry.get("file_sha256")
            and review.get("image_sha256") == entry["file_sha256"]):
        return structure
    return {}


def structure_text(entry):
    structure = observed_structure(entry)
    if not structure:
        return ""
    # Caveats are shown to the caller, but negative statements are not search tags.
    words = [text_values(structure.get("features", []))]
    for field, aliases in STRUCTURE_WORDS.items():
        value = structure.get(field, [])
        values = value if isinstance(value, list) else [value]
        words.extend(aliases.get(item, "") for item in values)
    columns = structure.get("body_columns")
    if type(columns) is int:
        words.append({0: "无正文栏", 1: "单栏", 2: "双栏 两栏 分栏",
                      3: "三栏 分栏", 4: "四栏 分栏"}.get(columns, "多栏 分栏"))
    return " ".join(words).casefold()


def validate_structure_filters(filters):
    for field, value in filters.items():
        if field == "body_columns":
            if type(value) is not int or value < 0:
                raise ValueError("正文栏数必须为非负整数")
        elif field not in STRUCTURE_CHOICES or value not in STRUCTURE_CHOICES[field]:
            raise ValueError(f"无效结构过滤条件：{field}")


def matches_structure(entry, filters):
    structure = observed_structure(entry)
    for field, expected in filters.items():
        actual = structure.get(field)
        if field == "body_columns" and type(actual) is not int:
            return False
        matches = expected in actual if isinstance(actual, list) else actual == expected
        if not matches:
            return False
    return True


def image_sha256(path):
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def relevance(entry, terms, hints):
    """Count each fact once; file-name repetition is not visual relevance."""
    visual = structure_text(entry)
    domain = text_values([entry.get("domain_id"), entry.get("domain_name")]).casefold()
    curated = " ".join(text_values(entry.get(key)) for key in SEARCH_FIELDS
                       if key not in ("path", "id", "domain_id", "domain_name")).casefold()
    units = text_values(parts(entry)).casefold()
    score = sum(max(8 if term in visual else 0, 6 if term in domain else 0,
                    5 if term in curated else 0, 4 if term in units else 0) for term in terms)
    score += sum(3 if hint in visual else 1 if hint in curated or hint in units else 0
                 for hint in hints)
    return score


def text_values(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(text_values(part) for part in value)
    if isinstance(value, dict):
        return " ".join(text_values(part) for part in value.values())
    return ""


def parts(entry):
    return entry.get("layout_units", []) + entry.get("glyph_samples", [])


def searchable(entry):
    return " ".join(text_values(entry.get(key)) for key in SEARCH_FIELDS).casefold() + " " + structure_text(entry)


def id_matches(entry, identifier):
    if entry["id"].casefold() == identifier.casefold():
        return True
    # R01 is a convenient alias for the index's A-R01_D01-style ID.
    return bool(re.fullmatch(r"R\d{2}", identifier, re.I)
                and re.match(r"A-" + re.escape(identifier) + r"_D\d{2}$", entry["id"], re.I))


def safe_path(root, value):
    if not isinstance(value, str) or not value:
        raise ValueError("索引条目缺少图片路径")
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("索引图片路径越出技能目录")
    return path


def compact_part(part, entry):
    keys = ("id", "location", "bounds_normalized_xyxy", "anchor", "position",
            "features", "body_simplification")
    return {key: part[key] for key in keys if key in part and
            (key not in ("features", "body_simplification") or part[key] != entry.get(key))}


def empty_search_suggestions(library, query, identifier, skeleton, filters=None, labels_available=False):
    suggestions = []
    if identifier and re.fullmatch(r"D\d{2}", identifier, re.I):
        suggestions.append({"reason": "D编号是领域，不是图片ID；用领域关键词搜索。",
                            "retry_args": ["--library", "posters", "--query", identifier.upper()]})
    if identifier and (query.strip() or skeleton):
        suggestions.append({"reason": "编号与其他过滤条件按AND组合；可先只定位该编号，再实际看图判断适配。",
                            "retry_args": ["--library", library, "--id", identifier]})
    if filters:
        suggestions.append({"reason": "结构条件须同时满足且有对应源图的看图记录；可减少条件或先定位编号后看图，不自动放宽。"})
    if library == "posters" and (query.strip() or skeleton) and not labels_available:
        suggestions.append({"reason": "A/B实例索引主要记录编号和领域，未充分标注分栏、日期等结构；先按领域检索并实际看图，骨架标签不能代替结构判断。"})
    if len(query.split()) > 1:
        suggestions.append({"reason": "多个关键词必须全部命中；可减少关键词后重试。",
                            "retry_args": ["--library", library, "--query", query.split()[0]]})
    return suggestions or [{"reason": "核对图片编号，或换更短关键词；不自动放宽过滤条件。"}]


def search(root, library="all", query="", identifier=None, skeleton=None, limit=3, structure=None):
    root = Path(root).resolve()
    terms = query.casefold().split()
    hints = SKELETON_HINTS.get(skeleton, ())
    structure = structure or {}
    validate_structure_filters(structure)
    matches = []
    entries_by_path = {}
    checked_images = {}
    labels_available = False
    for name in LIBRARIES if library == "all" else (library,):
        path = root / "assets" / LIBRARIES[name] / "index.json"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("files"), list):
            raise ValueError(f"无效参考索引：{path}")
        for entry in data["files"]:
            labels_available = labels_available or bool(observed_structure(entry))
            image_path = str(safe_path(root, entry["path"]))
            entries_by_path.setdefault(image_path, []).append(entry)
            units = parts(entry)
            unit_hits = [part for part in units if identifier and
                         str(part.get("id", "")).casefold() == identifier.casefold()]
            if identifier and not id_matches(entry, identifier) and not unit_hits:
                continue
            if not matches_structure(entry, structure):
                continue
            base = searchable(entry)
            combined = base + " " + text_values(units).casefold()
            if not all(term in combined for term in terms):
                continue
            if hints and not any(hint in combined for hint in hints):
                continue
            if observed_structure(entry):
                # Verify only potential matches, once per physical image per call.
                if image_path not in checked_images:
                    checked_images[image_path] = image_sha256(image_path)
                if checked_images[image_path] != entry["file_sha256"]:
                    entry = {key: value for key, value in entry.items()
                             if key not in ("observed_structure", "visual_review")}
                    base = searchable(entry)
                    combined = base + " " + text_values(units).casefold()
                    if (not matches_structure(entry, structure)
                            or not all(term in combined for term in terms)
                            or hints and not any(hint in combined for hint in hints)):
                        continue
            score = relevance(entry, terms, hints)
            chosen = unit_hits or sorted(units, key=lambda part: -sum(
                term in text_values(part).casefold() for term in terms))[:3]
            match = {"library": name, "id": entry["id"],
                     "path": image_path}
            if identifier:
                match["requested_id"] = identifier
            for key in ("canonical_id", "domain_id", "domain_name", "features",
                        "suitable_content", "adaptation", "body_simplification",
                        "observed_palette", "same_layout_family_as", "excluded_regions"):
                if entry.get(key):
                    match[key] = entry[key]
            if name == "posters" and entry.get("domain_id"):
                match["domain_label_role"] = "adaptation"
            if observed_structure(entry):
                match["observed_structure"] = observed_structure(entry)
                match["structure_evidence"] = {key: entry["visual_review"][key]
                                               for key in ("status", "method", "reviewed_at")
                                               if key in entry["visual_review"]}
            if structure:
                match["matched_structure_filters"] = structure
            if chosen:
                match["layout_units" if name == "layout" else "glyph_samples"] = [
                    compact_part(part, entry) for part in chosen]
                if len(units) > len(chosen):
                    match["other_units"] = len(units) - len(chosen)
            matches.append((score, match))
    matches.sort(key=lambda result: -result[0])
    unique = {}
    for _, match in matches:
        if match["path"] in unique:
            representative = unique[match["path"]]
            representative.setdefault("matched_aliases", [representative["id"]]).append(match["id"])
        else:
            match["file_exists"] = Path(match["path"]).is_file()
            unique[match["path"]] = match
    results = list(unique.values())[:limit]
    for result in results:
        aliases = entries_by_path[result["path"]]
        if len(aliases) > 1:
            result["aliases"] = [{key: entry[key] for key in ("id", "domain_id", "domain_name")
                                  if key in entry} for entry in aliases]
    response = {"matched_entries": len(matches), "matched_images": len(unique),
                "shown": len(results), "results": results,
                "note": "检索描述不代替实际开图；子图矩形仅用于粗略定位。" +
                        ("骨架参数为关键词提示，需按当前内容复核。" if skeleton else "") +
                        ("领域为社区服务适配标签，不等于原图真实主题。" if library in ("all", "posters") else "")}
    if not results:
        response["suggestions"] = empty_search_suggestions(library, query, identifier, skeleton,
                                                           structure, labels_available)
    return response


def layout_inventory(root):
    """Enumerate all layout sources; aliases and overview collages are not extra works."""
    root = Path(root).resolve()
    rows = {}
    for library in ("layout", "posters"):
        data = json.loads((root / "assets" / LIBRARIES[library] / "index.json").read_text(encoding="utf-8-sig"))
        for entry in data["files"]:
            if library == "posters" and (entry.get("collection") == "overview" or entry.get("asset_role") == "总览"):
                continue
            path = safe_path(root, entry["path"])
            relative = str(path.relative_to(root))
            if relative in rows:
                rows[relative].setdefault("aliases", []).append(entry["id"])
                continue
            row = {"id": entry.get("canonical_id", entry["id"]), "library": library,
                   "path": relative, "indexed_sha256": entry.get("file_sha256", entry.get("sha256")),
                   "features": entry.get("features", "")}
            if observed_structure(entry): row["observed_structure"] = observed_structure(entry)
            rows[relative] = row
    for library, directory in (("typography", "typography-references"), ("wireframes", "wireframes")):
        for path in sorted((root / "assets" / directory).glob("*")):
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"): continue
            path = safe_path(root, str(path.relative_to(root)))
            relative = str(path.relative_to(root))
            rows[relative] = {"id": path.stem.split("_")[0] if library == "typography" else path.stem,
                              "library": library, "path": relative}
    return list(rows.values())


def layout_catalog(root):
    """Return the full library and only previews bound to the current source bytes."""
    root = Path(root).resolve()
    data = json.loads((root / "assets/layout-atlas/index.json").read_text(encoding="utf-8-sig"))
    expected = {str(safe_path(root, row["path"]).relative_to(root)): row for row in data["sources"]}
    rows = layout_inventory(root)
    inventory_matches = len(expected) == len(data["sources"]) == data["source_count"] and set(expected) == {row["path"] for row in rows}
    previews = []
    for row in rows:
        actual = image_sha256(root / row["path"])
        recorded = expected.get(row["path"], {})
        row["source_current"] = bool(actual and actual == recorded.get("sha256") and
                                     (not row.get("indexed_sha256") or actual == row["indexed_sha256"]))
        row["actual_sha256"] = actual
        row["display_id"] = recorded.get("display_id", row["id"])
        if not row["source_current"]: row.pop("observed_structure", None)
    preview_current = bool(data.get("previews"))
    for preview in data.get("previews", []):
        path = safe_path(root, preview["path"])
        preview_current = preview_current and image_sha256(path) == preview.get("sha256")
        previews.append(str(path))
    covered = [identifier for page in data.get("previews", []) for identifier in page.get("source_ids", [])]
    preview_coverage = len(covered) == len(rows) and set(covered) == {row["id"] for row in rows}
    current = inventory_matches and preview_current and preview_coverage and all(row["source_current"] for row in rows)
    version = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    counts = {library: sum(row["library"] == library for row in rows)
              for library in ("layout", "posters", "typography", "wireframes")}
    return {"source_count": len(rows), "source_counts": counts, "catalog_version": version,
            "catalog_current": current, "inventory_matches": inventory_matches, "preview_coverage_complete": preview_coverage,
            "preview_paths": previews if current else [],
            "catalog": [dict(row, path=str(root / row["path"])) for row in rows],
            "note": "先实际巡览所有布局参考，再筛入选原图/子图；默认3条仅是短名单，不是阅读范围。"
                    if current else "源图、目录或总览已变化；先补看原图并更新总览，不能复用旧巡览。"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="检索参考图，默认最多输出 3 张不同原图。")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--catalog-layout", action="store_true", help="完整布局库目录、版本与全库巡览图，不受默认3条截断")
    parser.add_argument("--library", choices=("all", *LIBRARIES), default="all")
    parser.add_argument("--query", default="", help="空格分隔关键词；所有词都需命中，支持中文")
    parser.add_argument("--id", dest="identifier", help="主编号或 P 子图编号，例如 TG04、R16、P12-R1C2")
    parser.add_argument("--skeleton", type=str.upper, choices=SKELETON_HINTS)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--density", choices=STRUCTURE_CHOICES["text_density"])
    parser.add_argument("--columns", type=int, help="主要信息区列数（含图标条目），非负整数；0指无成组正文/条目")
    parser.add_argument("--subject-position", choices=STRUCTURE_CHOICES["subject_positions"])
    parser.add_argument("--text-zone", choices=STRUCTURE_CHOICES["text_zones"])
    parser.add_argument("--reading-route", choices=STRUCTURE_CHOICES["reading_route"])
    parser.add_argument("--title-anchor", choices=STRUCTURE_CHOICES["title_anchor"])
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 10:
        parser.error("--limit 必须为 1–10")
    structure = {field: value for field, value in {
        "text_density": args.density, "body_columns": args.columns,
        "subject_positions": args.subject_position, "text_zones": args.text_zone,
        "reading_route": args.reading_route, "title_anchor": args.title_anchor,
    }.items() if value is not None}
    if args.catalog_layout and (args.query.strip() or args.identifier or args.skeleton or structure or args.library != "all"):
        parser.error("--catalog-layout须读取完整布局库，不与筛选条件混用")
    if not args.catalog_layout and not (args.query.strip() or args.identifier or args.skeleton or structure):
        parser.error("至少提供关键词、编号、骨架提示或结构条件之一")
    try:
        result = (layout_catalog(args.root) if args.catalog_layout else
                  search(args.root, args.library, args.query, args.identifier, args.skeleton, args.limit, structure))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
