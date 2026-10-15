#!/usr/bin/env python3
"""Draw 5 style options from the 15-style pool for the one-shot style question.

At least 2 options suit the topic keywords; the rest are random, and no style
family appears more than twice, so the five options always span a wide range.

  pick_styles.py --topic "重阳 敬老 讲座"
  pick_styles.py --topic "反诈" --exclude S02,S03   # skip styles shown last time
  pick_styles.py --id S06                           # full preset for one style
"""
import argparse
import json
import random
import sys
from pathlib import Path

STYLES = Path(__file__).resolve().parents[1] / "assets/oneshot-styles.json"
SHOW = 5
MIN_FIT = 2
MAX_PER_FAMILY = 2


def load():
    return json.loads(STYLES.read_text(encoding="utf-8-sig"))


def fit(style, topic):
    return sum(1 for word in style["suits"] if word in topic)


def pick(styles, topic="", exclude=(), seed=None, show=SHOW):
    rng = random.Random(seed)
    pool = [s for s in styles if s["id"] not in exclude] or list(styles)
    rng.shuffle(pool)
    suited = [s for s in pool if fit(s, topic)]  # pool is shuffled, so suited picks vary too
    chosen, families = [], {}

    def take(style):
        if style in chosen or families.get(style["family"], 0) >= MAX_PER_FAMILY:
            return False
        chosen.append(style)
        families[style["family"]] = families.get(style["family"], 0) + 1
        return True

    for style in suited:
        if sum(1 for s in chosen if fit(s, topic)) >= MIN_FIT:
            break
        take(style)
    for style in pool:
        if len(chosen) >= show:
            break
        take(style)
    for style in pool:  # family cap left gaps (tiny pool after exclusions)
        if len(chosen) >= show:
            break
        if style not in chosen:
            chosen.append(style)
    rng.shuffle(chosen)
    return chosen


def main(argv=None):
    parser = argparse.ArgumentParser(description="从风格库随机抽5种给用户选（至少2种贴合主题，跨度大）。")
    parser.add_argument("--topic", default="", help="主题关键词，如“重阳 敬老”")
    parser.add_argument("--exclude", default="", help="上次已展示的风格编号，逗号分隔")
    parser.add_argument("--count", type=int, default=SHOW, help="抽几种，选择题工具最多4项时用4")
    parser.add_argument("--seed", type=int, help="固定随机数（测试用）")
    parser.add_argument("--id", help="查看某一种风格的完整预设")
    args = parser.parse_args(argv)
    styles = load()
    if args.id:
        found = [s for s in styles if s["id"] == args.id.upper()]
        print(json.dumps(found[0] if found else {"error": "编号不存在"}, ensure_ascii=False, indent=1))
        return 0 if found else 1
    exclude = {x.strip().upper() for x in args.exclude.split(",") if x.strip()}
    chosen = pick(styles, args.topic, exclude, args.seed, max(2, args.count))
    lines = [f"{n}. **{s['name']}**——{s['pitch']}" for n, s in enumerate(chosen, 1)]
    print(json.dumps({"ask_with": "用选择题工具（AskUserQuestion / request_user_input）让用户点选；label=name，description=pitch",
                      "options": [{"no": n, "id": s["id"], "name": s["name"], "pitch": s["pitch"]}
                                  for n, s in enumerate(chosen, 1)],
                      "message": "\n".join(lines)}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
