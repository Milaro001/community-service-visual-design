#!/usr/bin/env python3
"""Count on-poster copy from the master copy in state.md and recommend a mode.

Master copy rows look like `ID｜语言｜采用文案｜来源`. IDs starting with T are
treated as the main title; everything else is body copy.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ONESHOT_LIMIT = 100
TWO_STEP_LIMIT = 160
CJK = re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ가-힯]")
ALNUM = re.compile(r"[0-9A-Za-z０-９Ａ-Ｚａ-ｚ]")
ROW = re.compile(r"^\s*\|?\s*([A-Za-z]+[\w.-]*)\s*[｜|]\s*([^｜|]+?)\s*[｜|]\s*([^｜|]+?)\s*(?:[｜|].*)?$")


def weight(text):
    """CJK characters count 1 each; every 2 Latin letters or digits count 1."""
    cjk = len(CJK.findall(text))
    alnum = len(ALNUM.findall(text))
    return cjk + math.ceil(alnum / 2)


def parse_rows(text):
    rows = []
    for line in text.splitlines():
        match = ROW.match(line)
        if not match:
            continue
        identifier, language, copy = match.groups()
        if identifier.upper() == "ID" or set(copy) <= set("-: "):
            continue
        rows.append({"id": identifier, "language": language.strip(), "copy": copy.strip()})
    return rows


def recommend(total):
    if total <= ONESHOT_LIMIT:
        return "oneshot"
    if total <= TWO_STEP_LIMIT:
        return "oneshot-two-step"
    return "ask"


def summarize(rows, body_only=False):
    languages = {}
    for row in rows:
        is_title = row["id"].upper().startswith("T")
        entry = languages.setdefault(row["language"], {"title": 0, "body": 0, "rows": 0})
        entry["title" if is_title else "body"] += weight(row["copy"])
        entry["rows"] += 1
    for entry in languages.values():
        entry["total"] = entry["title"] + entry["body"]
    key = "body" if body_only else "total"
    largest = max((entry[key] for entry in languages.values()), default=0)
    return {"languages": languages, "counted": key, "max_count": largest,
            "recommended_mode": recommend(largest),
            "thresholds": {"oneshot": ONESHOT_LIMIT, "oneshot_two_step": TWO_STEP_LIMIT},
            "rule": "汉字每字1；数字和拉丁字母每2个算1；标点和空格不计"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="数上图文案字数并推荐模式（一键/一键分两步/询问）。")
    parser.add_argument("state", nargs="?", type=Path, help="state.md，母本行格式 ID｜语言｜采用文案｜来源；主标题ID用T开头")
    parser.add_argument("--text", help="直接给一段上图文案（不区分标题和正文）")
    parser.add_argument("--body-only", action="store_true", help="只数正文（ID不以T开头的行）")
    args = parser.parse_args(argv)
    if args.text is not None:
        rows = [{"id": "B1", "language": "text", "copy": args.text}]
    elif args.state:
        rows = parse_rows(args.state.read_text(encoding="utf-8-sig"))
        if not rows:
            print(json.dumps({"error": "没有找到母本行（ID｜语言｜采用文案｜来源）"}, ensure_ascii=False))
            return 2
    else:
        parser.error("需要 state.md 路径或 --text")
    print(json.dumps(summarize(rows, args.body_only), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
