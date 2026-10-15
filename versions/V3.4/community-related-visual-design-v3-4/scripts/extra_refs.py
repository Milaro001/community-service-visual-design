#!/usr/bin/env python3
"""Contact sheets for the unscreened extra reference pool (one-shot mode only).

The pool is a plain folder of images (default `assets/reference-extra/`, or
`extra_reference_dir` in agents/local-resources.json, or --dir). Sheets are cached
in `<pool>/_atlas/` and rebuilt only when the file list changes, so the model skims
~10 numbered sheets instead of opening 200+ files one by one.

  extra_refs.py                 # build/reuse sheets, print sheet paths
  extra_refs.py --domain D03 --grade A   # only one theme / grade (needs a registry CSV)
  extra_refs.py --id X037       # print the original file behind number X037

If the pool has a registry CSV with columns reference_id, delivered_file, domain_id,
domain_name, quality_grade, asset_type, its IDs and labels are used instead of X001...
"""
import csv
import argparse
import hashlib
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = None

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
PER_SHEET = 24
COLS = 6
CELL = (320, 380)
FONT_CANDIDATES = ["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/PingFang.ttc",
                   "C:/Windows/Fonts/msyh.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]


def pool_dir(explicit=None):
    if explicit:
        return Path(explicit).expanduser()
    config = ROOT / "agents/local-resources.json"
    if config.is_file():
        value = json.loads(config.read_text(encoding="utf-8-sig")).get("extra_reference_dir")
        if value:
            return Path(value).expanduser()
    return ROOT / "assets/reference-extra"


def list_images(folder):
    return sorted(p for p in folder.rglob("*")
                  if p.suffix.lower() in SUFFIXES and "_atlas" not in p.parts and not p.name.startswith("."))


def signature(files, folder, extra=""):
    text = "\n".join(f"{p.relative_to(folder)}|{p.stat().st_size}" for p in files) + extra
    return hashlib.sha256(text.encode()).hexdigest()[:16]


REGISTRY_COLUMNS = {"reference_id", "delivered_file", "domain_id"}


def load_registry(folder):
    """Rows of the first CSV in the pool root that looks like a reference registry."""
    for path in sorted(folder.glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if rows and REGISTRY_COLUMNS <= set(rows[0]):
            return rows
    return None


def select(folder, domain=None, grade=None):
    """(ident, path, label) for every image in scope, registry-aware."""
    registry = load_registry(folder)
    if registry:
        chosen = []
        for row in registry:
            if domain and row["domain_id"].upper() != domain.upper():
                continue
            if grade and row.get("quality_grade", "").upper() != grade.upper():
                continue
            path = folder / row["delivered_file"]
            if path.is_file():
                label = f"{row['reference_id']} {row.get('quality_grade', '')} {row.get('asset_type', '')}".strip()
                chosen.append((row["reference_id"], path, label, row))
        return chosen
    if domain or grade:
        return []
    return [(f"X{i + 1:03d}", path, None, None) for i, path in enumerate(list_images(folder))]


def load_font(size):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def build(folder, domain=None, grade=None):
    items = select(folder, domain, grade)
    scope = "_".join(filter(None, [domain and domain.upper(), grade and grade.upper()])) or "all"
    atlas = folder / "_atlas" / scope
    manifest_path = atlas / "manifest.json"
    sig = signature([path for _, path, _, _ in items], folder, scope)
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("signature") == sig and all((atlas / s).is_file() for s in manifest["sheets"]):
            return manifest, atlas, True
    atlas.mkdir(parents=True, exist_ok=True)
    for old in atlas.glob("sheet-*.jpg"):
        old.unlink()
    font = load_font(22)
    entries, sheets, skipped, numbered = {}, [], [], []
    for ident, path, label, row in items:
        try:
            with Image.open(path) as image:
                image.seek(0)
                thumb = image.convert("RGB")
                size = thumb.size
                thumb.thumbnail((CELL[0] - 10, CELL[1] - 50))
        except Exception:
            skipped.append(str(path.relative_to(folder)))
            continue
        entry = {"file": str(path.relative_to(folder)), "px": list(size)}
        if row:
            entry.update({key: row[key] for key in ("domain_id", "domain_name", "group_title", "quality_grade", "asset_type")
                          if row.get(key)})
        entries[ident] = entry
        numbered.append((label or ident, thumb, size))
    for start in range(0, len(numbered), PER_SHEET):
        chunk = numbered[start:start + PER_SHEET]
        rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * CELL[0], rows * CELL[1]), "white")
        draw = ImageDraw.Draw(sheet)
        for i, (label, thumb, size) in enumerate(chunk):
            x, y = (i % COLS) * CELL[0], (i // COLS) * CELL[1]
            sheet.paste(thumb, (x + (CELL[0] - thumb.width) // 2, y + 5))
            orient = "横" if size[0] > size[1] * 1.15 else "竖" if size[1] > size[0] * 1.15 else "方"
            draw.text((x + 8, y + CELL[1] - 40), f"{label} {orient}", fill="red", font=font)
        name = f"sheet-{start // PER_SHEET + 1:02d}.jpg"
        sheet.save(atlas / name, quality=82)
        sheets.append(name)
    manifest = {"signature": sig, "scope": scope, "count": len(entries), "sheets": sheets, "entries": entries,
                "skipped": skipped,
                "note": "参考池：只借风格、配色、字图关系和构图，不借文字、品牌、人物、号码；B级（应用/信息展示、系列拼图）降低权重。"}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest, atlas, False


def find_entry(folder, ident):
    for manifest_path in (folder / "_atlas").rglob("manifest.json"):
        entry = json.loads(manifest_path.read_text(encoding="utf-8"))["entries"].get(ident)
        if entry:
            return entry
    for row_ident, path, _, row in select(folder):
        if row_ident.upper() == ident:
            return {"file": str(path.relative_to(folder))}
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="未筛选参考池的编号巡览页（仅一键出图使用）。")
    parser.add_argument("--dir", help="参考池文件夹；默认读 agents/local-resources.json 的 extra_reference_dir，再退回 assets/reference-extra/")
    parser.add_argument("--domain", help="只看某一类，如 D03（需要池里有登记表CSV）")
    parser.add_argument("--grade", help="只看某一质量级，如 A")
    parser.add_argument("--id", help="查编号对应的原图路径，如 D03_05 或 X037")
    args = parser.parse_args(argv)
    folder = pool_dir(args.dir)
    if not folder.is_dir() or not list_images(folder):
        print(json.dumps({"status": "empty", "dir": str(folder), "note": "参考池不存在或没有图片，跳过这一步"}, ensure_ascii=False))
        return 0
    if args.id:
        ident = args.id.upper()
        entry = find_entry(folder, ident)
        print(json.dumps({"id": ident, "path": str(folder / entry["file"]) if entry else None,
                          **(entry or {"error": "编号不存在"})}, ensure_ascii=False))
        return 0 if entry else 1
    if Image is None:
        print(json.dumps({"error": "需要 Pillow：用已安装 Pillow 的解释器运行"}, ensure_ascii=False))
        return 2
    manifest, atlas, cached = build(folder, args.domain, args.grade)
    registry = load_registry(folder)
    domains = sorted({(r["domain_id"], r.get("domain_name", "")) for r in registry}) if registry else []
    print(json.dumps({"dir": str(folder), "scope": manifest["scope"], "count": manifest["count"], "cached": cached,
                      "sheets": [str(atlas / s) for s in manifest["sheets"]], "skipped": manifest["skipped"],
                      "domains": [f"{d} {n}" for d, n in domains], "note": manifest["note"]}, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    sys.exit(main())
