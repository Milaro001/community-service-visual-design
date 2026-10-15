#!/usr/bin/env python3
"""Turn a generated poster into a print file without cropping any content.

The image is scaled to fit the trim size, the leftover margin is filled by
extending the edge colours (never by cropping), then optional bleed is added.
"""
import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    Image = None

PAPER_MM = {"A3": (297, 420), "A4": (210, 297), "A2": (420, 594), "A1": (594, 841)}
MM_PER_INCH = 25.4
EXTEND_WARN = 0.05
UPSCALE_WARN = 2.5


def mm_to_px(mm, dpi):
    return round(mm / MM_PER_INCH * dpi)


def target_size(size, orientation, source, dpi):
    if size.upper() in PAPER_MM:
        w_mm, h_mm = PAPER_MM[size.upper()]
    else:
        w_mm, h_mm = (float(v) for v in size.lower().split("x"))
    landscape = orientation == "landscape" or (orientation == "auto" and source[0] > source[1])
    if landscape != (w_mm > h_mm):
        w_mm, h_mm = h_mm, w_mm
    return (w_mm, h_mm), (mm_to_px(w_mm, dpi), mm_to_px(h_mm, dpi))


def extend_to(image, size):
    """Centre `image` on `size`, filling the margin by stretching a blurred copy of its edges."""
    canvas = ImageOps.fit(image, size, method=Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    edge = image.resize((max(1, image.width // 64), max(1, image.height // 64)), Image.BILINEAR)
    canvas = Image.blend(canvas, edge.resize(size, Image.BILINEAR), 0.5)
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def export(source_path, output, size="A3", dpi=300, bleed_mm=0.0, orientation="auto", pdf=False):
    image = Image.open(source_path).convert("RGB")
    trim_mm, trim_px = target_size(size, orientation, image.size, dpi)
    scale = min(trim_px[0] / image.width, trim_px[1] / image.height)
    fitted = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    if scale > 1.2:
        fitted = fitted.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    filled_ratio = 1 - (fitted.width * fitted.height) / (trim_px[0] * trim_px[1])
    page = extend_to(fitted, trim_px) if fitted.size != trim_px else fitted
    bleed_px = mm_to_px(bleed_mm, dpi) if bleed_mm else 0
    if bleed_px:
        page = extend_to(page, (page.width + 2 * bleed_px, page.height + 2 * bleed_px))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    page.save(output, dpi=(dpi, dpi))
    warnings = []
    if filled_ratio > EXTEND_WARN:
        warnings.append(f"比例差异较大，扩边面积约{filled_ratio:.0%}，请看边缘是否自然；更好的做法是按目标比例重生")
    if scale > UPSCALE_WARN:
        warnings.append(f"放大了{scale:.1f}倍，文字边缘可能发虚；建议用高清放大工具或以更高原生尺寸重生")
    report = {"output": str(output), "trim_mm": trim_mm, "trim_px": trim_px, "bleed_mm": bleed_mm,
              "final_px": page.size, "dpi": dpi, "upscale": round(scale, 2),
              "extended_area": round(filled_ratio, 3), "warnings": warnings}
    if pdf:
        pdf_path = output.with_suffix(".pdf")
        page.save(pdf_path, "PDF", resolution=dpi)
        report["pdf"] = str(pdf_path)
        report["pdf_note"] = "PDF为整页图片；未写入TrimBox/BleedBox，印厂需要时请在排版软件中设置"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="成品图转印刷尺寸：等比放入、扩边适配、可加出血。")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="默认 <输入名>_print.png")
    parser.add_argument("--size", default="A3", help="A1/A2/A3/A4 或 宽x高 毫米，如 600x900")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--bleed", type=float, default=0.0, help="每边出血毫米数，常用3")
    parser.add_argument("--orientation", choices=("auto", "portrait", "landscape"), default="auto")
    parser.add_argument("--pdf", action="store_true", help="同时输出整页PDF")
    args = parser.parse_args(argv)
    if Image is None:
        print(json.dumps({"error": "需要 Pillow：用已安装 Pillow 的解释器以 python -P 运行"}, ensure_ascii=False))
        return 2
    output = args.output or args.input.with_name(args.input.stem + ("_print_bleed" if args.bleed else "_print") + ".png")
    print(json.dumps(export(args.input, output, args.size, args.dpi, args.bleed, args.orientation, args.pdf),
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
