#!/usr/bin/env python3
"""Build an editable SVG: a text-free background image plus real text layers.

layers.json:
{
  "canvas": [2480, 3508],
  "background": "poster_notext.png",
  "embed": true,
  "layers": [
    {"type": "text", "text": "活动时间", "x": 200, "y": 1400, "size": 96,
     "font_family": "Source Han Sans SC", "font_weight": 700, "fill": "#E8642C",
     "anchor": "start", "line_height": 1.3, "letter_spacing": 0},
    {"type": "image", "href": "title.png", "x": 180, "y": 200, "w": 2100, "h": 900}
  ]
}
Multi-line text uses "\n". Positions are the text baseline of the first line.
"""
import argparse
import base64
import json
import mimetypes
import sys
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

DEFAULT_FAMILY = "Source Han Sans SC, Noto Sans CJK SC, Alibaba PuHuiTi, PingFang SC, Microsoft YaHei, sans-serif"


def href_for(path, base, embed):
    path = (base / path).resolve() if not Path(path).is_absolute() else Path(path)
    if not embed:
        return path.as_uri()
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def text_element(layer, index):
    lines = str(layer["text"]).split("\n")
    size = float(layer["size"])
    step = size * float(layer.get("line_height", 1.3))
    attrs = {
        "id": layer.get("id", f"text-{index + 1}"),
        "x": layer["x"], "y": layer["y"],
        "font-family": layer.get("font_family", DEFAULT_FAMILY),
        "font-size": size,
        "font-weight": layer.get("font_weight", 400),
        "fill": layer.get("fill", "#2B2B2B"),
        "text-anchor": layer.get("anchor", "start"),
    }
    if layer.get("letter_spacing"):
        attrs["letter-spacing"] = layer["letter_spacing"]
    if layer.get("stroke"):
        attrs.update({"stroke": layer["stroke"], "stroke-width": layer.get("stroke_width", 4), "paint-order": "stroke"})
    if layer.get("rotate"):
        attrs["transform"] = f"rotate({layer['rotate']} {layer['x']} {layer['y']})"
    opening = "<text " + " ".join(f"{key}={quoteattr(str(value))}" for key, value in attrs.items()) + ">"
    spans = "".join(f'<tspan x={quoteattr(str(layer["x"]))} dy="{0 if n == 0 else step}">{escape(line)}</tspan>'
                    for n, line in enumerate(lines))
    return opening + spans + "</text>"


def build(spec, base, embed_default=True):
    width, height = spec["canvas"]
    embed = spec.get("embed", embed_default)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    if spec.get("background"):
        parts.append(f'<g id="background"><image width="{width}" height="{height}" '
                     f'href={quoteattr(href_for(spec["background"], base, embed))}/></g>')
    parts.append('<g id="layers">')
    for index, layer in enumerate(spec.get("layers", [])):
        if layer.get("type", "text") == "image":
            parts.append(f'<image id={quoteattr(layer.get("id", f"image-{index + 1}"))} x="{layer["x"]}" y="{layer["y"]}" '
                         f'width="{layer["w"]}" height="{layer["h"]}" href={quoteattr(href_for(layer["href"], base, embed))}/>')
        else:
            parts.append(text_element(layer, index))
    parts.append("</g></svg>")
    return "\n".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="无字底图＋文字层描述 → 文字可编辑的 SVG。")
    parser.add_argument("layers", type=Path, help="layers.json")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--link", action="store_true", help="图片以链接引用而不是内嵌（文件更小，但需随附图片）")
    args = parser.parse_args(argv)
    spec = json.loads(args.layers.read_text(encoding="utf-8-sig"))
    svg = build(spec, args.layers.parent, embed_default=not args.link)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg, encoding="utf-8")
    texts = sum(1 for layer in spec.get("layers", []) if layer.get("type", "text") == "text")
    print(json.dumps({"output": str(args.output), "text_layers": texts,
                      "note": "用 Illustrator/Inkscape/Figma 打开即可改字；本机缺字体时会显示替代字体"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
