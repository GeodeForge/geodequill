#!/usr/bin/env python3
"""voice_check.py - measure writing habits and scan text for machine-writing tells.

Usage:
  python3 -I voice_check.py stats FILE [FILE ...] [--each] [--targets]
                                                         -> JSON of writing habits;
     --each lists each file; --targets suggests ranges from how the writer's
     pieces vary (long files are cut into ~500-word windows first)
  python3 -I voice_check.py habits FILE [FILE ...]       -> common words, sentence openers,
                                                            paragraph and sentence-length habits
  python3 -I voice_check.py scan FILE [--profile P.md] [--register written|spoken] [--tone NAME]
                                                         -> plain-text report
  python3 -I voice_check.py tones [--json]               -> tones to choose from: the built-in
     list plus your own in ~/.geodequill/tones; scan --tone NAME loosens the voice's
     ranges in that tone's direction
  python3 -I voice_check.py voices [FOLDER ...] [--json] -> saved voices to choose from: the
     project's voice-profiles folder, then the personal folder ~/.geodequill/voices
     (or $GEODEQUILL_HOME/voices), which every AI tool on this computer can share

Standard library only. It reports habits it can count. It does NOT predict
what any AI detector will say and never prints an AI-probability score.
Exit codes: 0 done, 1 a file could not be read, 2 wrong usage.
"""
import json
import os
import re
import statistics
import sys
from collections import Counter


STRONG_WORDS = re.compile(
    r"\b(delv(?:e|es|ed|ing)|tapestry|testament|pivotal|vibrant|intricate|"
    r"intricacies|underscor(?:e|es|ed|ing)|showcas(?:e|es|ed|ing)|"
    r"foster(?:s|ed|ing)?|garner(?:s|ed|ing)?|multifaceted|"
    r"leverag(?:e|es|ed|ing)|robust|seamless(?:ly)?|elevat(?:e|es|ing)|"
    r"holistic|cutting-edge|game-changer|groundbreaking|transformative|"
    r"meticulous(?:ly)?|commendable|noteworthy|invaluable|bustling|nestled|"
    r"boasts)\b",
    re.I,
)

STRONG_PHRASES = [
    "in today's fast-paced", "in today's digital", "ever-evolving",
    "it's important to note", "it is important to note", "it's worth noting",
    "it is worth noting", "it's worth mentioning", "let's dive",
    "hope this helps", "let me know if",
    "great question", "absolutely!", "certainly!", "stands as a",
    "serves as a", "plays a pivotal", "plays a crucial", "plays a vital",
    "plays a key role", "a testament to", "rich tapestry",
    "navigate the complexities", "unlock the potential",
    "unlock the power", "at the end of the day", "in the realm of",
    "evolving landscape", "shed light on", "pave the way",
    "paving the way", "take it to the next level", "look no further",
    "whether you're a", "here's the kicker",
]

MILD_PHRASES = [
    "overall,", "ultimately,", "moreover,", "furthermore,", "additionally,",
    "in addition,", "when it comes to", "a wide range of", "a variety of",
    "in order to", "due to the fact that", "not only",
    "in conclusion", "in summary", "to sum up", "that being said",
    "having said that", "dive into", "deep dive", "navigating the",
    "the landscape of", "feel free to",
]

FORMAT_KINDS = {"Title Case heading", "bold-lead bullet", "emoji"}

PATTERNS = [
    ("negative parallelism (not just X, but Y)",
     re.compile(r"\b(?:not|isn't|aren't|wasn't|weren't|doesn't|don't|didn't)\s+(?:just|only|merely|simply)\b[^.!?\n]{0,80}?[,;—-]\s*(?:it'?s|it is|that'?s|this is|they'?re|rather)\b", re.I)),
    ("tacked-on -ing clause",
     re.compile(r",\s+(?:highlighting|underscoring|showcasing|ensuring|reflecting|emphasizing|demonstrating|fostering|contributing to|cementing|solidifying)\b", re.I)),
    ("vague attribution",
     re.compile(r"\b(?:experts|studies|research|critics|observers|analysts)\s+(?:say|says|suggest|suggests|believe|argue|argues|indicate|indicates|have found|has shown|have shown|show|shows)\b", re.I)),
    ("stacked hedge",
     re.compile(r"\b(?:may|might|could|can)\s+(?:potentially|possibly|perhaps)\b", re.I)),
    ("rhetorical question then answer",
     re.compile(r"\bthe (?:result|catch|kicker|problem|truth|upshot|answer|reality|bottom line)\?\s", re.I)),
    ("colon reveal",
     re.compile(r"\bhere's (?:the thing|why|what|how)\b\s*[:,]|\bthe (?:truth|reality) is\s*:", re.I)),
    ("bold-lead bullet",
     re.compile(r"^\s*(?:[-*•]|\d+\.)\s+\*\*[^*\n]{1,40}(?::\*\*|\*\*\s*[:\-–—])")),
    ("emoji",
     re.compile("[\U0001F300-\U0001FAFF✅❌✨⚡⭐❤➡]")),
]

SMALL_WORDS = {"a", "an", "the", "of", "and", "or", "in", "on", "to", "for",
               "with", "at", "by", "from", "vs", "as", "is"}

FILLERS = re.compile(
    r"\byou know,|,\s*you know\b|\bI mean,|\bmind you\b"
    r"|(?:^|(?<=[.!?\"]\s))(?:Well|Now|Why|Oh|So|Look),",
    re.M | re.I)

ABBREV = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|vs|e\.g|i\.e|a\.m|p\.m|U\.S)\.")


def norm(s):
    return (s.replace("’", "'").replace("‘", "'")
             .replace("“", '"').replace("”", '"'))


def read_text(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def prose_only(text):
    text = norm(text)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^\s*#{1,6}\s+.*$", " ", text, flags=re.M)
    text = re.sub(r"^\s*(?:[-*•]|\d+\.)\s+", "", text, flags=re.M)
    return re.sub(r"[*_`>]", "", text)


def split_sentences(prose):
    guarded = ABBREV.sub(lambda m: m.group(0).replace(".", "\x00"), prose)
    parts = re.split(
        r"(?<=[.!?])\s+|(?<=[.!?][\"')\]])\s+|(?<=[.!?][\"')\]]{2})\s+|\n{2,}",
        guarded)
    out = []
    for p in parts:
        p = p.replace("\x00", ".").strip()
        if not re.search(r"\w", p):
            continue
        if out and re.search(r"[!?][\"')\]]+$", out[-1]) and p[0].islower():
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def wc(s):
    return len(re.findall(r"[A-Za-z0-9À-ɏ]+(?:['-][A-Za-z0-9À-ɏ]+)*", s))


def per(n, words, scale):
    return round(n * scale / words, 2) if words else 0.0


def metrics(raw):
    prose = prose_only(raw)
    words = wc(prose)
    sents = split_sentences(prose)
    lens = [wc(s) for s in sents] or [0]
    mean = statistics.mean(lens)
    sd = statistics.pstdev(lens) if len(lens) > 1 else 0.0
    paras = [p for p in re.split(r"\n\s*\n", prose) if re.search(r"\w", p)]
    plens = [wc(p) for p in paras] or [0]
    pmean = statistics.mean(plens)
    psd = statistics.pstdev(plens) if len(plens) > 1 else 0.0
    lines = [l for l in norm(raw).splitlines() if l.strip()]
    bullets = sum(1 for l in lines if re.match(r"\s*(?:[-*•]|\d+\.)\s+", l))
    contractions = len(re.findall(
        r"\b\w+(?:n't|'re|'ve|'ll|'d|'m)\b|\b(?:it|that|he|she|there|what|let|who|here)'s\b",
        prose, re.I))
    return {
        "words": words,
        "sentences": len(sents),
        "avg_sentence_words": round(mean, 1),
        "sentence_cv": round(sd / mean, 2) if mean else 0.0,
        "short_sentence_share": round(sum(1 for n in lens if n <= 8) / len(lens), 2),
        "long_sentence_share": round(sum(1 for n in lens if n >= 25) / len(lens), 2),
        "paragraphs": len(paras),
        "avg_paragraph_words": round(pmean, 1),
        "paragraph_cv": round(psd / pmean, 2) if pmean else 0.0,
        "contractions_per_100w": per(contractions, words, 100),
        "em_dashes_per_1000w": per(len(re.findall(r"—|\s–\s|\s--\s|(?<=\w)--(?=\w)", prose)), words, 1000),
        "semicolons_per_1000w": per(prose.count(";"), words, 1000),
        "exclamations_per_1000w": per(prose.count("!"), words, 1000),
        "questions_per_1000w": per(prose.count("?"), words, 1000),
        "fillers_per_1000w": per(len(FILLERS.findall(prose)), words, 1000),
        "first_person_per_100w": per(len(re.findall(r"\b(?:I|I'm|I've|I'll|I'd|my|me)\b", prose)), words, 100),
        "i_led_sentence_pct": round(100 * sum(1 for x in sents if re.match(r"[\"'(]*I\b", x)) / len(sents), 1) if sents else 0.0,
        "bullet_line_share": round(bullets / len(lines), 2) if lines else 0.0,
    }


def find_tells(raw):
    hits = []
    mild = {}
    in_code = False
    for no, line in enumerate(norm(raw).splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        low = line.lower()
        spans = []
        for ph in STRONG_PHRASES:
            i = low.find(ph)
            while i != -1:
                spans.append((i, i + len(ph)))
                hits.append((no, "stock phrase", ph, line))
                i = low.find(ph, i + len(ph))
        for m in STRONG_WORDS.finditer(line):
            if not any(a <= m.start() < b for a, b in spans):
                hits.append((no, "stock word", m.group(0), line))
        for ph in MILD_PHRASES:
            if ph in low:
                mild[ph] = mild.get(ph, 0) + low.count(ph)
        triples = len(re.findall(r"\b[A-Za-z-]+, [A-Za-z-]+,? (?:and|or) [A-Za-z-]+\b", line))
        if triples:
            mild["three-item lists"] = mild.get("three-item lists", 0) + triples
        for label, rx in PATTERNS:
            for m in rx.finditer(line):
                hits.append((no, label, m.group(0).strip(), line))
        hm = re.match(r"\s*#{1,6}\s+(.*)$", line)
        if hm:
            ws = hm.group(1).split()
            body = [w for w in ws if w.lower() not in SMALL_WORDS]
            if len(ws) >= 3 and body and all(w[0].isupper() for w in body if w[0].isalpha()):
                hits.append((no, "Title Case heading", hm.group(1), line))
    return hits, mild


def parse_targets(text, key="targets"):
    for m in re.finditer(r"```json\s*(\{.*?\})\s*```", text, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        raw = data.get(key) if isinstance(data, dict) else None
        if not isinstance(raw, dict):
            continue
        good = {}
        for k, rng in raw.items():
            if (isinstance(rng, list) and len(rng) == 2
                    and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in rng)
                    and rng[0] <= rng[1]):
                good[k] = rng
        if good:
            return good
    return None


def default_flags(m):
    flags = []
    if m["sentences"] >= 6 and m["sentence_cv"] < 0.5:
        flags.append(f"sentence lengths are very even (variation {m['sentence_cv']}); mix short and long")
    if m["paragraphs"] >= 4 and m["paragraph_cv"] < 0.3:
        flags.append("paragraphs are all about the same size")
    return flags


def scan_report(raw, ptxt=None, profile=None, register="written", tone=None):
    hits, mild = find_tells(raw)
    m = metrics(raw)
    targets, note, label = None, None, "written"
    if profile:
        if ptxt is None:
            note = f"(profile not found: {profile}; using general checks)"
        else:
            if register == "spoken":
                targets = parse_targets(ptxt, "targets_spoken")
                if targets:
                    label = "spoken"
                else:
                    note = "(profile has no spoken targets; comparing with written)"
            if not targets:
                targets = parse_targets(ptxt)
            if not targets:
                note = "(profile has no readable targets block; using general checks)"
    tone_note = None
    if tone:
        t = lookup_tone(tone)
        if not t:
            tone_note = f"(tone not found: {tone}; ranges unchanged)"
        elif targets:
            targets, loosened = apply_tone(targets, t["moves"])
            tone_note = f"(tone: {t['name']}; loosened in its direction: {', '.join(loosened) or 'nothing in this profile'})"
        else:
            tone_note = f"(tone: {t['name']}; no profile ranges to adjust)"
    out = ["== Machine-writing tells =="]
    if hits:
        for no, kind, found, _line in hits:
            out.append(f"line {no}: {kind}: \"{found}\"")
    else:
        out.append("none found")
    mild_rate = sum(mild.values()) * 1000 / max(m["words"], 1)
    if sum(mild.values()) >= 3 and mild_rate >= 5:
        out.append("mild connectors, worth thinning: " +
                   ", ".join(f"{k} x{v}" for k, v in mild.items()))
    out.append("")
    out.append("== Habits ==")
    for k in ("words", "avg_sentence_words", "sentence_cv", "paragraph_cv",
              "contractions_per_100w", "em_dashes_per_1000w",
              "questions_per_1000w", "fillers_per_1000w",
              "first_person_per_100w", "i_led_sentence_pct"):
        out.append(f"{k}: {m[k]}")
    out.append("")
    off = []
    if targets:
        if note:
            out.append(note)
        if tone_note:
            out.append(tone_note)
        out.append(f"== Versus the voice profile ({label}) ==")
        for k, (lo, hi) in targets.items():
            if k in m:
                state = "ok" if lo <= m[k] <= hi else (
                    "OUTSIDE (short text, a hint only)" if m["words"] < 250 else "OUTSIDE")
                if state != "ok":
                    off.append(k)
                out.append(f"{k}: {m[k]} (profile {lo} to {hi}) {state}")
    else:
        if note:
            out.append(note)
        if tone_note:
            out.append(tone_note)
        flags = default_flags(m)
        out.append("== General checks ==")
        out.extend(flags or ["nothing flagged"])
        off = flags
    out.append("")
    weak = sum(1 for h in hits if h[1] == "stock word")
    fmt = sum(1 for h in hits if h[1] in FORMAT_KINDS)
    out.append(f"Summary: {len(hits) - weak - fmt} strong tells, {weak} stock words and "
               f"{fmt} formatting marks (weak alone; real writers use them), {len(off)} habits off.")
    return "\n".join(out)


def cmd_scan(path, profile, register="written", tone=None):
    raw = read_text(path)
    if raw is None:
        print(f"Cannot read {path}.")
        return 1
    ptxt = read_text(profile) if profile else None
    print(scan_report(raw, ptxt, profile, register, tone))
    return 0


TARGET_KEYS = ("avg_sentence_words", "sentence_cv", "paragraph_cv",
               "contractions_per_100w", "em_dashes_per_1000w",
               "semicolons_per_1000w", "exclamations_per_1000w",
               "questions_per_1000w", "fillers_per_1000w",
               "first_person_per_100w", "i_led_sentence_pct",
               "bullet_line_share")

HI_FLOOR = {"em_dashes_per_1000w": 2.0, "semicolons_per_1000w": 2.0,
            "exclamations_per_1000w": 2.0, "questions_per_1000w": 2.0,
            "fillers_per_1000w": 2.0, "contractions_per_100w": 1.0,
            "first_person_per_100w": 1.0, "i_led_sentence_pct": 10.0,
            "bullet_line_share": 0.05}


def pieces(text, size=500):
    if wc(text) < size * 2:
        return [text]
    units = []
    for p in re.split(r"\n\s*\n", text):
        if wc(p) > size:
            units.extend((s, "\n\n" if j == 0 else " ")
                         for j, s in enumerate(split_sentences(norm(p))))
        else:
            units.append((p, "\n\n"))
    out, cur, n = [], "", 0
    for u, sep in units:
        cur = u if not cur else cur + sep + u
        n += wc(u)
        if n >= size:
            out.append(cur)
            cur, n = "", 0
    if cur and n >= size // 2:
        out.append(cur)
    return out


def pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, round(q * (len(s) - 1))))]


def suggest_targets(texts):
    ms = [m for m in (metrics(p) for t in texts for p in pieces(t)) if m["words"] > 0]
    if not ms:
        return {"targets": {}, "based_on_pieces": 0}
    usable = [m for m in ms if m["words"] >= 150] or ms
    targets = {}
    for k in TARGET_KEYS:
        vals = [m[k] for m in usable]
        if len(vals) >= 10:
            lo, hi = pct(vals, 0.1), pct(vals, 0.9)
        else:
            lo, hi = min(vals), max(vals)
        pad = max((hi - lo) * 0.1, abs(hi) * 0.05, 0.05)
        if len(vals) < 3:
            pad = max(pad, abs(hi) * 0.25)
        targets[k] = [round(max(lo - pad, 0), 2),
                      round(max(hi + pad, HI_FLOOR.get(k, 0)), 2)]
    return {"targets": targets, "based_on_pieces": len(usable)}


def load_all(paths):
    if not paths:
        return None, "Give at least one file."
    texts = [read_text(p) for p in paths]
    bad = [p for p, t in zip(paths, texts) if t is None]
    if bad:
        return None, "Cannot read: " + ", ".join(bad)
    return texts, None


def stats_result(texts, names=None, each=False, targets=False):
    m = metrics("\n\n".join(texts))
    m["files"] = len(texts)
    if each:
        labels = [str(n) for n in (names or range(1, len(texts) + 1))]
        m["per_file"] = {n: {k: pm[k] for k in ("words",) + TARGET_KEYS}
                         for n, pm in zip(labels, (metrics(t) for t in texts))}
    if targets:
        m["suggested"] = suggest_targets(texts)
    return m


def cmd_stats(paths, each=False, targets=False):
    texts, err = load_all(paths)
    if err:
        print(err)
        return 1
    print(json.dumps(stats_result(texts, paths, each, targets), indent=2))
    return 0


COMMON = set("""that this with have from they were been their there would which what when your
them then than will into some more other about could should only also such these those very much
just over said says like upon and the for are but not you all any can had her his him she its our
out who how why where while being does did done has make made even here after before again never
every still must may might shall each both through under between because against""".split())


def habits_result(texts):
    prose = prose_only("\n\n".join(texts))
    words = re.findall(r"[A-Za-z][a-z']+", prose)
    total = len(words) or 1
    cnt = Counter(w.lower() for w in words if len(w) >= 4 and w.lower() not in COMMON)
    sents = split_sentences(prose)
    ns = len(sents) or 1
    openers = Counter(m.group(0).lower() for m in (re.search(r"[A-Za-z']+", s) for s in sents) if m)
    paras = [p for p in re.split(r"\n\s*\n", prose) if re.search(r"\w", p)]
    psents = [len(split_sentences(p)) for p in paras] or [0]
    return {
        "words": total,
        "common_words_per_10k": {w: round(n * 10000 / total) for w, n in cnt.most_common(30) if n >= 2},
        "sentence_openers_pct": {w: round(n * 100 / ns, 1) for w, n in openers.most_common(12)},
        "one_sentence_paragraph_pct": round(100 * sum(1 for n in psents if n == 1) / len(psents)),
        "avg_sentences_per_paragraph": round(sum(psents) / len(psents), 1),
        "sentences_6_words_or_fewer_pct": round(100 * sum(1 for s in sents if wc(s) <= 6) / ns),
        "I_per_10k_words": round(len(re.findall(r"\bI\b", prose)) * 10000 / total),
    }


def cmd_habits(paths):
    texts, err = load_all(paths)
    if err:
        print(err)
        return 1
    print(json.dumps(habits_result(texts), indent=2))
    return 0


def geodequill_home():
    return os.environ.get("GEODEQUILL_HOME") or os.path.join(os.path.expanduser("~"), ".geodequill")


def voice_dirs(extra=()):
    home = geodequill_home()
    out = []
    for d in list(extra) + [os.path.join(os.getcwd(), "voice-profiles"), os.path.join(home, "voices")]:
        a = os.path.abspath(d)
        if a not in out:
            out.append(a)
    return out


def describe_voice(path):
    text = read_text(path) or ""
    name = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r"^voice:\s*(.+?)\s*$", text, re.M)
    if m:
        name = m.group(1)
    m = re.search(r"^## In one line[ \t]*\n+[ \t]*(\S.*?)\s*$", text, re.M)
    summary = m.group(1) if m else ""
    m = re.search(r"^built:\s*(.+?)\s*$", text, re.M)
    built = m.group(1) if m else ""
    registers = [r for r, k in (("written", "targets"), ("spoken", "targets_spoken")) if parse_targets(text, k)]
    return {"name": name, "summary": summary, "built": built, "registers": registers, "file": path}


def find_voices(extra=()):
    dirs = voice_dirs(extra)
    found = []
    for d in dirs:
        if os.path.isdir(d):
            for n in sorted(os.listdir(d)):
                if n.lower().endswith(".md"):
                    found.append(describe_voice(os.path.join(d, n)))
    return dirs, found


def cmd_voices(args):
    as_json = "--json" in args
    dirs, found = find_voices([a for a in args if not a.startswith("--")])
    if as_json:
        print(json.dumps({"searched": dirs, "voices": found}, indent=2))
        return 0
    if not found:
        print("No saved voices. Looked in:")
        for d in dirs:
            print("  " + d)
        return 0
    for i, v in enumerate(found, 1):
        regs = " and ".join(v["registers"]) or "no measured habits"
        print(f"{i}. {v['name']}: {v['summary'] or 'no description'} ({regs})")
        print(f"   {v['file']}")
    return 0


TONE_MEASURES = {
    "contractions": ("contractions_per_100w",),
    "fillers": ("fillers_per_1000w",),
    "exclamations": ("exclamations_per_1000w",),
    "questions": ("questions_per_1000w",),
    "first person": ("first_person_per_100w", "i_led_sentence_pct"),
    "sentence length": ("avg_sentence_words",),
    "dashes": ("em_dashes_per_1000w",),
    "semicolons": ("semicolons_per_1000w",),
}


def parse_tone_blocks(text, default_name=""):
    parts = re.split(r"^##[ \t]+(.+?)[ \t]*$", text, flags=re.M)
    blocks = [(parts[i].strip().lower(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]
    if not blocks and default_name:
        blocks = [(default_name, text)]
    tones = []
    for name, body in blocks:
        m = re.search(r"^In one line:[ \t]*(.+?)[ \t]*$", body, re.M)
        if not m:
            continue
        moves = []
        mv = re.search(r"^Moves:[ \t]*(.+?)[ \t]*$", body, re.M)
        for tok in (mv.group(1).split(",") if mv else []):
            words = tok.strip().lower().split()
            if len(words) >= 2 and words[-1] in ("up", "down") and " ".join(words[:-1]) in TONE_MEASURES:
                moves.append((" ".join(words[:-1]), words[-1]))
        tones.append({"name": name, "summary": m.group(1), "moves": moves})
    return tones


def find_tones():
    builtin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "tones.md")
    found = []
    for t in parse_tone_blocks(read_text(builtin) or ""):
        t["source"] = "built in"
        found.append(t)
    custom = os.path.join(geodequill_home(), "tones")
    if os.path.isdir(custom):
        for n in sorted(os.listdir(custom)):
            if n.lower().endswith(".md"):
                path = os.path.join(custom, n)
                for t in parse_tone_blocks(read_text(path) or "", os.path.splitext(n)[0].lower()):
                    t["source"] = path
                    found.append(t)
    return found


def lookup_tone(name):
    key = (name or "").strip().lower()
    hits = [t for t in find_tones() if t["name"] == key]
    custom = [t for t in hits if t["source"] != "built in"]
    return (custom or hits or [None])[0]


def apply_tone(targets, moves):
    out = {k: list(v) for k, v in targets.items()}
    loosened = []
    for measure, way in moves:
        for key in TONE_MEASURES[measure]:
            if key in out:
                lo, hi = out[key]
                if way == "down":
                    out[key] = [0, hi]
                else:
                    out[key] = [lo, round(max(hi * 2, hi + HI_FLOOR.get(key, 1.0)), 2)]
                loosened.append(key)
    return out, loosened


def cmd_tones(args):
    found = find_tones()
    if "--json" in args:
        print(json.dumps({"tones": found, "custom_folder": os.path.join(geodequill_home(), "tones")}, indent=2))
        return 0
    for i, t in enumerate(found, 1):
        where = "" if t["source"] == "built in" else f" (yours: {t['source']})"
        print(f"{i}. {t['name']}: {t['summary']}{where}")
    return 0


def main(argv):
    if len(argv) >= 2 and argv[1] == "voices":
        return cmd_voices(argv[2:])
    if len(argv) >= 2 and argv[1] == "tones":
        return cmd_tones(argv[2:])
    if len(argv) < 3 or argv[1] not in ("stats", "scan", "habits"):
        print(__doc__)
        return 2
    if argv[1] == "stats":
        flags = [a for a in argv[2:] if a.startswith("--")]
        files = [a for a in argv[2:] if not a.startswith("--")]
        return cmd_stats(files, each="--each" in flags, targets="--targets" in flags)
    if argv[1] == "habits":
        return cmd_habits(argv[2:])
    profile, register = None, "written"
    args = argv[2:]
    if "--profile" in args:
        i = args.index("--profile")
        profile = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    tone = None
    if "--tone" in args:
        i = args.index("--tone")
        tone = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    if "--register" in args:
        i = args.index("--register")
        register = args[i + 1] if i + 1 < len(args) else "written"
        args = args[:i] + args[i + 2:]
        if register not in ("written", "spoken"):
            print("--register must be written or spoken")
            return 2
    if not args:
        print(__doc__)
        return 2
    return cmd_scan(args[0], profile, register, tone)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
