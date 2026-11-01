#!/usr/bin/env python3
"""Regenerate the traditional-Chinese support for the Chinese lists. Developer tool; not shipped.

Run after any change to ZH_WORDS, ZH_PHRASES, ZH_MILD, ZH_PATTERNS or ZH_CONTRAST:

    pip install opencc-python-reimplemented
    python3 -I build/zh_traditional.py

It converts every list item with OpenCC (s2t, s2tw, s2hk, s2twp) and then:
  1. rewrites the ZH_T2S table in voice_check.py from scratch, so every traditional character
     in the s2t, s2tw and s2hk conversions maps back to the simplified character the list uses;
  2. rewrites ZH_TRAD_PHRASES with the few Taiwan word forms (s2twp) that differ from the list
     after that mapping, written in the simplified characters the matcher sees;
  3. writes test/fixtures/zh-list-traditional.json, which the tests use to check that every
     list item, in every conversion, is still caught. A list item added without re-running
     this script fails that test.
The checker itself never needs OpenCC.
"""
import json
import os
import re
import sys

try:
    from opencc import OpenCC
    import opencc
except ImportError:
    sys.exit("Needs OpenCC: pip install opencc-python-reimplemented")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VC = os.path.join(ROOT, "plugin", "skills", "geodequill", "scripts", "voice_check.py")
FIXTURE = os.path.join(ROOT, "test", "fixtures", "zh-list-traditional.json")
CONFIGS = ("s2t", "s2tw", "s2hk", "s2twp")

# One sample sentence per regex, so the patterns can be converted and checked too.
PATTERN_SAMPLES = {
    "negative parallelism (不仅是…更是)": "它不仅是一个工具更是一个伙伴",
    "stacked hedge": "这也许可能是对的",
    "grand opener (随着…的发展 / 在…时代背景下)": "随着科技的不断发展，在数字化的时代背景下",
    "inflated significance (标志着…新时代)": "这标志着一个新时代",
}
CONTRAST_SAMPLES = ["这不是结束，而是开始。", "这并非偶然，而是必然。", "这并不是问题，而是机会。"]


def load_module():
    sys.path.insert(0, os.path.dirname(VC))
    import voice_check
    return voice_check


def main():
    vc = load_module()
    items = {
        "words": vc.ZH_WORDS.pattern.split("|"),
        "phrases": list(vc.ZH_PHRASES),
        "mild": list(vc.ZH_MILD),
        "patterns": [PATTERN_SAMPLES[label] for label, _rx in vc.ZH_PATTERNS],
        "contrast": CONTRAST_SAMPLES,
    }
    converters = {c: OpenCC(c) for c in CONFIGS}
    table = {}
    fixture = {"generated_with": f"OpenCC {', '.join(CONFIGS)} (opencc-python-reimplemented "
                                 f"{getattr(opencc, '__version__', '')})".replace(" )", ")"),
               "items": {}}
    extra = []
    for kind, lst in items.items():
        rows = []
        for item in lst:
            forms = []
            for c in CONFIGS:
                trad = converters[c].convert(item)
                if trad not in forms and trad != item:
                    forms.append(trad)
                # Character pairs come only from the character conversions. s2twp also swaps
                # whole words (人工智能 -> 人工智慧); those become ZH_TRAD_PHRASES instead.
                if c != "s2twp" and len(trad) == len(item):
                    for t, s in zip(trad, item):
                        if t != s:
                            if table.get(t, s) != s:
                                sys.exit(f"conflict: {t} maps to {table[t]} and {s}")
                            table[t] = s
            rows.append([item, forms])
        fixture["items"][kind] = rows
    # Every Chinese character written inside the regexes, so alternatives the samples do not use
    # (飞速, 阶段, 纪元, 不单 ...) are covered too.
    regex_src = "".join([vc.ZH_WORDS.pattern, vc.ZH_CONTRAST.pattern] + [rx.pattern for _l, rx in vc.ZH_PATTERNS])
    for ch in sorted(set(re.findall(r"[\u4e00-\u9fff]", regex_src))):
        for c in CONFIGS[:3]:
            t = converters[c].convert(ch)
            if len(t) == 1 and t != ch:
                if table.get(t, ch) != ch:
                    sys.exit(f"conflict: {t} maps to {table[t]} and {ch}")
                table[t] = ch
    trans = str.maketrans(table)
    for kind in ("phrases",):
        for item, forms in fixture["items"][kind]:
            for f in forms:
                back = f.translate(trans).lower()
                if back != item and back not in extra:
                    extra.append(back)
    keys = "".join(sorted(table))
    vals = "".join(table[k] for k in keys)
    src = open(VC, encoding="utf-8").read()
    src = re.sub(r'ZH_T2S = str\.maketrans\(\s*"[^"]*",\s*"[^"]*"\)',
                 lambda _m: f'ZH_T2S = str.maketrans(\n    "{keys}",\n    "{vals}")', src, count=1)
    src = re.sub(r"ZH_TRAD_PHRASES = \[[^\]]*\]",
                 lambda _m: "ZH_TRAD_PHRASES = [" + ", ".join(json.dumps(e, ensure_ascii=False) for e in extra) + "]",
                 src, count=1)
    with open(VC, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    with open(FIXTURE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"ZH_T2S: {len(table)} characters. Taiwan word forms: {len(extra)}. Fixture: "
          f"{sum(len(v) for v in fixture['items'].values())} items.")


if __name__ == "__main__":
    main()
