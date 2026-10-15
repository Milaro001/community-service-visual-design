#!/usr/bin/env python3
"""Screen the entire type library, then return a varied semantic shortlist."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

CUES = (
    ("关怀 温暖 陪伴 邻里 养老 友好 暖心", "生活关怀 陪伴 友好 圆润 柔和 亲和"),
    ("运动 行动 活力 成长 青年 挑战 启程", "运动 行动 成长 青年 斜体 动态 启程"),
    ("文化 阅读 诗意 怀旧 街区 人文 展览", "文化 阅读 人文 衬线 书写 复古 展览 街区"),
    ("自然 花卉 春日 户外 露营 探索 漫步", "自然 花卉 春日 户外 探索 书写"),
    ("亲子 儿童 趣味 快乐 泡泡 柔软", "亲子 趣味 手写 圆润 轻松 柔软"),
    ("科技 数字 智能 未来", "科技 棱角 几何 匀线"),
    ("安全 警示 紧急 风险", "清楚 稳定 粗黑 几何"),
    ("敬老 重阳 老人 长辈 孝亲 养老 节日 传统 国风 中秋 春节", "敬老 重阳 传统节日 书法 书写 国风 陪伴"),
)
LAYOUTS = {"horizontal": "横排", "vertical": "竖排", "stacked": "叠排", "staggered": "错落",
           "interleaved": "穿插填隙", "side-caption": "侧组", "curved": "弧形", "grid": "网格", "mixed": "混合合集"}
NON_FORM_FAMILIES = {"摄影搭配", "错落组块", "趣味组块", "弧形辅助字", "横向组块", "竖向组块",
                     "品牌字组", "数字层级", "生活图形", "装饰切口", "装饰轮廓", "轻字重", "亲和强调", "彩色分组"}
FORM_ALIASES = {
    "圆润匀线": {"圆润"}, "圆润粗字": {"圆润"}, "圆润手写": {"圆润", "手写"},
    "书写衬线": {"衬线人文"},
    **{name: {"手写"} for name in ("英文手写", "粗手写", "柔和手写", "趣味手写", "柔软书写")},
    **{name: {"书写"} for name in ("书写书法", "粗书写", "柔和书写", "复古书写", "书写匀线", "动态书写")},
}


def form_families(row):
    result = set()
    for family in row["families"]:
        if family not in NON_FORM_FAMILIES:
            result.update(FORM_ALIASES.get(family, {family}))
    return result


def form_overlap(forms, selected_forms):
    # Missing form observations are not evidence of a new visual direction.
    if not forms:
        return 1.0 if selected_forms else 0.0
    return max((len(forms & prior) / len(forms | prior)
                for prior in selected_forms if prior), default=0.0)


def flatten(value):
    if isinstance(value, str): return value
    if isinstance(value, list): return " ".join(flatten(item) for item in value)
    if isinstance(value, dict): return " ".join(flatten(item) for item in value.values())
    return ""


def load_catalog(root):
    root = Path(root).resolve()
    data = json.loads((root / "assets/type-generation-references/index.json").read_text(encoding="utf-8-sig"))
    rows = []
    for entry in data["files"]:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root): raise ValueError("字体参考路径越出技能目录")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        layout = entry.get("type_layout", {})
        current = actual == entry.get("sha256") == layout.get("source_sha256")
        rows.append({"id": entry["id"], "path": str(path), "features": entry.get("features", ""),
                     "families": entry.get("type_families", []), "context_tags": entry.get("context_tags", []),
                     "layout": layout if current else {}, "glyph_samples": entry.get("glyph_samples", []),
                     "body_simplification": entry.get("body_simplification", ""), "source_current": current})
    return data, rows


def select(root, semantics="", query="", layout=None, limit=8, catalog=False):
    data, rows = load_catalog(root)
    if catalog:
        compact = [{key: row[key] for key in ("id", "path", "features", "families", "context_tags", "layout", "source_current")} for row in rows]
        version_data = [{key: value for key, value in row.items() if key != "path"} for row in compact]
        version = hashlib.sha256(json.dumps(version_data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        catalog_result = {"scanned_sources": len(rows), "catalog_version": version, "catalog": compact,
                "preview_paths": [str((Path(root) / path).resolve()) for path in data.get("catalog_preview", {}).get("paths", [])]
                if all(row["source_current"] for row in rows) else [],
                "note": "全库缩略巡览后筛选；具体字例需再开原图，源图已变时先更新观察及总览。"}
        if not (semantics.strip() or query.strip() or layout):
            return catalog_result
    literal = semantics.casefold().split()
    expanded = set()
    for triggers, aliases in CUES:
        if any(word in semantics for word in triggers.split()): expanded.update(aliases.split())
    terms = query.casefold().split()
    matches = []
    for row in rows:
        if not row["source_current"]: continue
        mode = row["layout"].get("modes", [])
        if layout and layout not in mode: continue
        # IDs, filenames, example text and warning caveats are not semantic evidence.
        text = flatten([row["features"], row["families"], row["context_tags"],
                        row["layout"].get("semantic_device_observed", ""),
                        [LAYOUTS.get(item, item) for item in mode]]).casefold()
        if not all(term in text for term in terms): continue
        hits = sorted({word for word in literal if word in text})
        cue_hits = sorted({word for word in expanded if word in text})
        score = 12 * len(hits) + 3 * len(cue_hits) + 2 * len(terms)
        if semantics.strip() and score == 0: continue
        tie = hashlib.sha256((semantics + "|" + query + "|" + str(layout) + "|" + row["id"]).encode()).hexdigest()
        matches.append((score, tie, dict(row, semantic_matches=hits, affinity_matches=cue_hits)))
    matches.sort(key=lambda item: (-item[0], item[1]))
    selected = []
    selected_forms = []
    while matches and len(selected) < limit:
        # A bounded soft penalty favors distinct core forms among nearby semantic fits.
        overlaps = [form_overlap(form_families(item[2]), selected_forms) for item in matches]
        best = max(range(len(matches)), key=lambda i: (matches[i][0] - 6 * overlaps[i], -overlaps[i], -i))
        _, _, row = matches.pop(best)
        forms = form_families(row)
        row["form_families"] = sorted(forms)
        selected.append(row)
        selected_forms.append(forms)
    form_counts = {}
    for forms in selected_forms:
        for family in sorted(forms):
            form_counts[family] = form_counts.get(family, 0) + 1
    shortlist = {"scanned_sources": len(rows), "eligible_sources": len(matches) + len(selected),
            "results": selected, "form_family_counts": form_counts,
            "note": "先全库筛选再返回短名单；核心笔形只作轻度去重，语义线索不锁定风格。须看具体字例并写入当前主题方案；集中结果不是最终风格配额。",
            "suggestion": "无合适结果时显式放宽组合条件，或返回全库巡览；不按编号补前几张。" if not selected else ""}
    return dict(catalog_result, shortlist=shortlist) if catalog else shortlist


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--catalog", action="store_true", help="完整65项目录与总览；可同时带语义/组合条件，一次扫描附短名单")
    parser.add_argument("--semantics", default="", help="主题关键词、情绪、行动与受众")
    parser.add_argument("--query", default="", help="笔形/组合关键词，全部需命中")
    parser.add_argument("--layout", choices=LAYOUTS)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.limit <= 12 or not (args.catalog or args.semantics.strip() or args.query.strip() or args.layout):
        parser.error("需提供全库巡览或语义/笔形/组合条件，limit为1–12")
    try:
        print(json.dumps(select(args.root, args.semantics, args.query, args.layout, args.limit, args.catalog), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
