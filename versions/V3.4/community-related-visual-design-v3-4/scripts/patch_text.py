#!/usr/bin/env python3
"""Patch text onto a poster with a real font, only where the user approved it.

Single patch:  patch_text.py in.png out.png --box X Y W H --text "正确文字" --color "#D9452B"
Batch:         patch_text.py in.png out.png --spec patches.json
Each patch can cover the old text with the surrounding colour first (cover=true,
default) or write into an already clean reserved area (cover=false).
"""
import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover - reported to the user instead
    Image = None

FONT_DIRS = [
    Path.home() / "Library/Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"), Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts", Path("/usr/share/fonts"),
    Path.home() / ".local/share/fonts", Path.home() / ".fonts",
]
FALLBACK_KEYWORDS = ["SourceHanSans", "SourceHanSerif", "NotoSansCJK", "NotoSansSC", "NotoSerifCJK",
                     "AlibabaPuHuiTi", "PingFang", "STHeiti", "Songti", "msyh", "simhei", "wqy"]
FONT_SUFFIXES = (".ttf", ".otf", ".ttc")


def find_font(name=None):
    """Return a font path: an explicit path, a file-name keyword, or the first CJK fallback."""
    if name and Path(name).is_file():
        return Path(name)
    keywords = [name] if name else FALLBACK_KEYWORDS
    for keyword in keywords:
        needle = keyword.lower().replace(" ", "").replace("-", "")
        for directory in FONT_DIRS:
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*")):
                if path.suffix.lower() in FONT_SUFFIXES and needle in path.name.lower().replace(" ", "").replace("-", ""):
                    return path
    return None


def hex_color(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def border_color(image, box, margin=6):
    """Median colour of a thin ring just outside the box: the surface the old text sat on."""
    x, y, w, h = box
    rgb = image.convert("RGB")
    left, top = max(0, x - margin), max(0, y - margin)
    right, bottom = min(rgb.width, x + w + margin), min(rgb.height, y + h + margin)
    pixels = []
    for px in range(left, right):
        for py in (top, bottom - 1):
            pixels.append(rgb.getpixel((px, py)))
    for py in range(top, bottom):
        for px in (left, right - 1):
            pixels.append(rgb.getpixel((px, py)))
    channels = list(zip(*pixels))
    return tuple(sorted(channel)[len(channel) // 2] for channel in channels)


def cover(image, box, feather=4):
    """Paint the box with the surrounding colour, feathered so no hard rectangle shows."""
    x, y, w, h = box
    colour = border_color(image, box)
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rectangle([x, y, x + w, y + h], fill=255)
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    layer = Image.new(image.mode, image.size, colour + ((255,) if image.mode == "RGBA" else ()))
    image.paste(layer, (0, 0), mask)
    return colour


def fit_font(font_path, lines, box, size, line_spacing, index):
    """Largest size ≤ requested that fits every line inside the box."""
    _, _, w, h = box
    size = size or h
    while size > 6:
        font = ImageFont.truetype(str(font_path), size, index=index)
        widths = [font.getbbox(line)[2] - font.getbbox(line)[0] for line in lines]
        height = size * (1 + line_spacing * (len(lines) - 1))
        if max(widths) <= w and height <= h:
            return font, size
        size -= 1
    return ImageFont.truetype(str(font_path), 6, index=index), 6


def apply_patch(image, patch):
    box = [int(v) for v in patch["box"]]
    font_path = find_font(patch.get("font"))
    if not font_path:
        raise SystemExit(f"找不到字体：{patch.get('font') or '中文后备字体'}；用 --font 指定字体文件路径")
    if patch.get("cover", True):
        cover(image, box, patch.get("feather", 4))
    lines = str(patch["text"]).split("\n")
    spacing = float(patch.get("line_spacing", 0.3))
    font, size = fit_font(font_path, lines, box, patch.get("size"), spacing, int(patch.get("font_index", 0)))
    draw = ImageDraw.Draw(image)
    x, y, w, h = box
    total = size * (1 + spacing * (len(lines) - 1)) if len(lines) > 1 else size
    top = y + (h - total) / 2
    for number, line in enumerate(lines):
        left_edge, _, right_edge, _ = font.getbbox(line)
        width = right_edge - left_edge
        align = patch.get("align", "left")
        lx = x + (w - width) / 2 if align == "center" else x + w - width if align == "right" else x
        draw.text((lx - left_edge, top + number * size * (1 + spacing)), line, font=font,
                  fill=hex_color(patch.get("color", "#2B2B2B")),
                  stroke_width=int(patch.get("stroke", 0)),
                  stroke_fill=hex_color(patch.get("stroke_color", "#FFFFFF")))
    return {"box": box, "font": str(font_path), "size": size, "text": patch["text"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description="用真实字体贴补错字或排入正文区（需用户同意）。")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--spec", type=Path, help="JSON 列表：[{box:[x,y,w,h], text, font, color, size, align, cover, line_spacing, stroke}]")
    parser.add_argument("--box", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--text")
    parser.add_argument("--font", help="字体文件路径或文件名关键词，如 SourceHanSerif、AlibabaPuHuiTi")
    parser.add_argument("--color", default="#2B2B2B")
    parser.add_argument("--size", type=int, help="最大字号（像素），默认按框高自动适配")
    parser.add_argument("--align", choices=("left", "center", "right"), default="left")
    parser.add_argument("--no-cover", action="store_true", help="目标区域已干净，不先盖掉原字")
    args = parser.parse_args(argv)
    if Image is None:
        print(json.dumps({"error": "需要 Pillow：用已安装 Pillow 的解释器以 python -P 运行"}, ensure_ascii=False))
        return 2
    if args.spec:
        patches = json.loads(args.spec.read_text(encoding="utf-8-sig"))
        if args.no_cover:
            for patch in patches:
                patch.setdefault("cover", False)
    elif args.box and args.text is not None:
        patches = [{"box": args.box, "text": args.text.replace("\\n", "\n"), "font": args.font, "color": args.color,
                    "size": args.size, "align": args.align, "cover": not args.no_cover}]
    else:
        parser.error("需要 --spec，或 --box 加 --text")
    image = Image.open(args.input)
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    report = [apply_patch(image, patch) for patch in patches]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(json.dumps({"output": str(args.output), "patches": report}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
