#!/usr/bin/env python3
"""voice_check.py - measure writing habits and scan text for machine-writing tells.

Usage:
  python3 -I voice_check.py stats FILE [FILE ...] [--each] [--targets] [--lang CODE]
                                                         -> JSON of writing habits;
     --each lists each file; --targets suggests ranges from how the writer's
     pieces vary (long files are cut into ~500-word windows first)
  python3 -I voice_check.py habits FILE [FILE ...] [--lang CODE]
                                                         -> common words, sentence openers,
                                                            paragraph and sentence-length habits
  python3 -I voice_check.py scan FILE [--profile P.md] [--register written|spoken] [--tone NAME]
                                [--lang CODE] [--before ORIGINAL]
                                                         -> plain-text report; --before names the
     text a rewrite started from and adds its reading level before and after
  python3 -I voice_check.py languages                    -> which languages get which checks

Any language and script can be measured. The language is read from the script
(Chinese characters, kana, Hangul, Cyrillic and so on) and, for the Latin script,
from its most common small words; the report says which it found and how.
--lang CODE (en, zh, es, fr, ja ...) sets it instead. Chinese, Japanese and Thai
have no spaces between words, so their lengths are counted in characters.
Reading level (reading_lix) is LIX: words per sentence plus the percentage of
words longer than six letters. It is measured for Latin-script text only.
  python3 -I voice_check.py tones [--json]               -> tones to choose from: the built-in
     list plus your own in ~/.geodequill/tones; scan --tone NAME loosens the voice's
     ranges in that tone's direction
  python3 -I voice_check.py voices [FOLDER ...] [--json] -> saved voices to choose from: the
     project's voice-profiles folder, then the personal folder ~/.geodequill/voices
     (or $GEODEQUILL_HOME/voices), which every AI tool on this computer can share,
     then the built-in voices of public-domain authors; your own voice of the same
     name hides a built-in one

Standard library only. It reports habits it can count. It does NOT predict
what any AI detector will say and never prints an AI-probability score.
Exit codes: 0 done, 1 a file could not be read or scan found no words, 2 wrong usage.
"""
import json
import os
import re
import statistics
import sys
import unicodedata
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
]

COMMON_PATTERNS = [
    ("bold-lead bullet",
     re.compile(r"^\s*(?:(?:[-*•]|\d+\.)\s+|\d+、\s*)\*\*[^*\n]{1,40}(?:[:：]\*\*|\*\*\s*[:：\-–—])")),
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

CONTRACTIONS_EN = re.compile(
    r"\b\w+(?:n't|'re|'ve|'ll|'d|'m)\b|\b(?:it|that|he|she|there|what|let|who|here)'s\b", re.I)

ZH_WORDS = re.compile(
    r"赋能|至关重要|深入探讨|无缝|闭环|助力|抓手|底层逻辑|颗粒度|全方位|多维度|不可或缺|举足轻重|"
    r"日新月异|蓬勃发展|璀璨|瑰宝|交织|织锦|画卷|焕发|无与伦比|独特魅力|深远影响")

ZH_PHRASES = [
    "希望这对你有帮助", "希望这对您有帮助", "希望对你有所帮助", "希望对您有所帮助",
    "希望以上内容对你有帮助", "希望以上内容对您有帮助", "如果你还有其他问题", "如果您还有其他问题",
    "这是一个很好的问题", "好问题！", "稳稳地接住", "被稳稳接住", "你问到了问题的核心", "一句话总结",
    "要不要我帮你", "要不要我为你", "如果你愿意，我可以", "如果你愿意,我可以",
    "作为一个人工智能", "作为一个ai", "作为ai语言模型", "作为人工智能语言模型",
    "在当今社会", "在这个瞬息万变的", "在这个快速发展的", "在当今快节奏",
    "让我们深入", "接下来让我们", "让我们一起来探讨",
    "彰显了", "彰显出", "具有里程碑意义", "开启了新篇章", "谱写了新篇章",
    "留下了深刻的印记", "不可磨灭的印记",
    "发挥着至关重要的作用", "起着至关重要的作用", "发挥着关键作用", "扮演着重要的角色",
    "扮演着关键的角色", "扮演着至关重要的角色",
    "一些专家认为", "有专家指出",
    "让我们拭目以待", "未来可期", "值得我们深思",
]

ZH_MILD = [
    "此外，", "此外,", "与此同时，", "与此同时,", "值得注意的是", "值得一提的是", "总的来说", "换句话说",
    "首先，", "首先,", "其次，", "其次,", "最后，", "最后,", "另一方面", "不仅如此", "总而言之", "综上所述",
    "如有任何疑问", "请随时告诉我", "欢迎随时提问", "充分体现了",
]

ZH_PATTERNS = [
    ("negative parallelism (不仅是…更是)",
     re.compile(r"(?:不仅仅|不仅|不只|不单)是[^。！？\n]{1,30}?更是")),
    ("stacked hedge",
     re.compile(r"(?:也许|或许|大概|可能)(?:可能|也许|或许)")),
    ("grand opener (随着…的发展 / 在…时代背景下)",
     re.compile(r"随着[^。！？\n]{1,20}的(?:不断|快速|飞速|迅猛|日益)(?:发展|进步)|在[^。！？\n]{1,15}的?时代背景下")),
    ("inflated significance (标志着…新时代)",
     re.compile(r"标志着[^。！？\n]{0,15}新(?:时代|纪元|篇章|阶段|里程碑)")),
]

# Traditional to simplified, for the characters in the Chinese lists. Generated by
# build/zh_traditional.py from OpenCC (Apache-2.0); re-run it after changing any Chinese list.
ZH_T2S = str.maketrans(
    "並來個們倫僅內問啓啟單夥寫寶專對層幫後換揮數斷時會標機歡滅為無煥爲獨現環畫異當發穩節紀結綜維縫總織義與舉萬著裏裡討記許訴話誌認語說説請譜變讓賦輕輯這進遠還邏錦鍵閉開關階隨響顆題願顯飛體",
    "并来个们伦仅内问启启单伙写宝专对层帮后换挥数断时会标机欢灭为无焕为独现环画异当发稳节纪结综维缝总织义与举万着里里讨记许诉话志认语说说请谱变让赋轻辑这进远还逻锦键闭开关阶随响颗题愿显飞体")

# Generated by build/zh_traditional.py from OpenCC (Apache-2.0). Do not edit by hand: re-run it.
ZH_TRAD_PHRASES = ["作为一个人工智慧", "作为人工智慧语言模型"]

ZH_CONTRAST = re.compile(r"(?:不是|并非|并不是)[^。！？\n]{1,40}?而是")

ES_WORDS = re.compile(
    r"\b(?:sumerg(?:e|en|ir|irse|irnos)|adentr(?:a|an|arse|arnos)|fomenta(?:r|n)?|primordial(?:es)?|"
    r"robust[oa]s?|hol[ií]stic[oa]s?|sinergias?|multifac[eé]tic[oa]s?|vibrantes?|meticulos[oa]s?|"
    r"transformador(?:a|es|as)?|empodera(?:r|n|miento)?|desbloquea(?:r|n)?|vanguardia|tapiz|"
    r"potenciar|optimizar)\b", re.I)

ES_PHRASES = [
    "en la era digital", "en el mundo actual", "en el vertiginoso", "en el mundo de hoy",
    "cabe destacar que", "cabe señalar que", "cabe mencionar que", "cabe resaltar que",
    "es importante destacar", "es importante señalar", "es importante tener en cuenta",
    "es importante mencionar", "vale la pena mencionar", "vale la pena destacar",
    "juega un papel crucial", "juega un papel fundamental", "juega un papel clave",
    "desempeña un papel crucial", "desempeña un papel fundamental", "desempeña un papel clave",
    "rico tapiz", "se erige como", "embárcate en", "sumérgete en",
    "en el vasto mundo de", "llevar al siguiente nivel", "no busques más",
    "espero que esto te ayude", "espero que esto le ayude", "espero que te sea útil",
    "no dudes en", "si tienes alguna otra pregunta", "si tiene alguna otra pregunta",
    "excelente pregunta", "buena pregunta!", "como modelo de lenguaje",
]

ES_MILD = [
    "además,", "asimismo,", "en resumen", "en conclusión", "por otro lado", "en definitiva",
    "por último,", "en primer lugar", "sin lugar a dudas", "en el ámbito de", "no solo",
    "un testimonio de",
]

ES_PATTERNS = [
    ("negative parallelism (no se trata solo de)",
     re.compile(r"\bno se trata (?:solo|sólo|solamente|únicamente) de\b", re.I)),
    ("tacked-on gerund clause",
     re.compile(r",\s+(?:destacando|subrayando|resaltando|garantizando|fomentando|"
                r"consolidando|evidenciando|reflejando)\b", re.I)),
    ("vague attribution",
     re.compile(r"\b(?:los expertos|los especialistas|diversos estudios|los estudios|las investigaciones)\s+"
                r"(?:dicen|afirman|sugieren|creen|señalan|indican|muestran|demuestran)\b", re.I)),
    ("stacked hedge",
     re.compile(r"\b(?:podría|puede|podrían|pueden)\s+(?:potencialmente|posiblemente|quizás|quizá|tal vez)\b", re.I)),
]

FIRST_PERSON_EN = re.compile(r"\b(?:I|I'm|I've|I'll|I'd|my|me)\b")

LANGS = {
    "en": {"name": "English", "words": STRONG_WORDS, "phrases": STRONG_PHRASES, "mild": MILD_PHRASES,
           "patterns": PATTERNS, "fillers": FILLERS, "contractions": CONTRACTIONS_EN,
           "first_person": FIRST_PERSON_EN, "i_led": re.compile(r"[\"'(]*I\b")},
    "zh": {"name": "Chinese", "words": ZH_WORDS, "phrases": ZH_PHRASES + ZH_TRAD_PHRASES, "mild": ZH_MILD,
           "patterns": ZH_PATTERNS, "first_person": re.compile(r"我(?![们們])"),
           "i_led": re.compile(r"[“「『\"'(（]*我(?![们們])")},
    "es": {"name": "Spanish", "words": ES_WORDS, "phrases": ES_PHRASES, "mild": ES_MILD,
           "patterns": ES_PATTERNS,
           "first_person": re.compile(r"\b(?:yo|me|mi|mis|mí|conmigo)\b", re.I)},
}

LANG_NAMES = {
    "lo": "Lao", "bo": "Tibetan", "my": "Burmese", "km": "Khmer",
    "en": "English", "zh": "Chinese", "es": "Spanish", "ja": "Japanese", "ko": "Korean",
    "fr": "French", "de": "German", "pt": "Portuguese", "it": "Italian", "nl": "Dutch",
    "ru": "Russian", "uk": "Ukrainian", "ar": "Arabic", "fa": "Persian", "he": "Hebrew",
    "hi": "Hindi", "bn": "Bengali", "th": "Thai", "vi": "Vietnamese", "tr": "Turkish",
    "pl": "Polish", "el": "Greek", "id": "Indonesian or Malay", "sv": "Swedish", "da": "Danish",
    "no": "Norwegian", "sw": "Swahili", "cs": "Czech", "ro": "Romanian", "hu": "Hungarian",
    "fi": "Finnish", "tl": "Tagalog", "ca": "Catalan", "hr": "Croatian, Bosnian or Serbian",
    "af": "Afrikaans", "ms": "Malay",
    "lt": "Lithuanian", "lv": "Latvian", "et": "Estonian", "sl": "Slovenian", "sk": "Slovak",
    "is": "Icelandic", "ga": "Irish", "cy": "Welsh", "eu": "Basque", "gl": "Galician", "sq": "Albanian",
    "mk": "Macedonian", "bg": "Bulgarian", "ka": "Georgian", "hy": "Armenian", "az": "Azerbaijani",
    "kk": "Kazakh", "uz": "Uzbek", "mn": "Mongolian", "ne": "Nepali", "mr": "Marathi", "ta": "Tamil",
    "te": "Telugu", "kn": "Kannada", "ml": "Malayalam", "gu": "Gujarati", "pa": "Punjabi", "ur": "Urdu",
    "si": "Sinhala", "am": "Amharic", "ha": "Hausa", "yo": "Yoruba", "ig": "Igbo", "zu": "Zulu",
    "xh": "Xhosa", "so": "Somali", "mt": "Maltese", "lb": "Luxembourgish", "eo": "Esperanto",
}

STOPWORDS = {
    "en": "the and of to a in is that it was for on with as i you he be at by this have are but not they "
          "his from had she which or we an were her been their has would will",
    "es": "de la que el en y los se del las un por con no una su para es al lo como más pero sus le ya o "
          "este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos "
          "durante todos uno les ni contra otros ese eso ante ellos esto mí antes algunos qué unos yo otro "
          "otras otra él",
    "fr": "le la les de des du et est un une pour dans qui que pas au sur avec ce il elle je nous vous "
          "sont mais ou aux cette ces ne se en par plus",
    "pt": "o os a as de do da dos das e em um uma não no na ao com para se que mais mas foi ele ela eu "
          "você também muito isso por pelo pela",
    "it": "il di che è e la per un una del della non sono con gli le ma anche questo come più alla nel "
          "ho mi lo si da",
    "de": "der die und das ist nicht ein eine zu den von mit sich des auf für im dem auch es an als nach "
          "wie aber ich sie wir",
    "nl": "de het een en van is dat op te niet zijn voor met ook die maar er aan bij ik je wat",
    "da": "og i at er det en til af på de med for den som ikke har jeg vi var et men så om fra kan skal "
          "sig han hun der vores dette eller",
    "no": "og i er det en til av på de med for den som ikke har jeg vi var et men så om fra kan skal seg "
          "han hun der vår dette eller",
    "sv": "och i att är det en till av på de med för den som inte har jag vi var ett men så om från kan "
          "ska sig han hon där vår detta eller",
    "id": "yang dan di ini itu dengan untuk dari dalam tidak akan pada juga ke ada adalah saya kami kita "
          "mereka atau bisa sudah karena oleh telah",
    "sw": "na ya wa kwa ni katika la za kuwa hii hiyo lakini pia kama au si sana yake wake hayo zaidi",
    "pl": "i w nie na się z do że to jest jak o co ale tak po od jego za przez są dla czy już tylko może "
          "być",
    "cs": "a v se na je že to s z do o ale jak jsem jsou by k pro tak po jeho za od který které také už",
    "tr": "ve bir bu da de için ile çok daha olarak gibi ama en ne var değil ki o şey her olan sonra kadar",
    "vi": "và của là có không những các được trong cho một với này người đã để khi thì như cũng",
    "ro": "și în de la a cu nu pe o că este un care se din pentru sunt mai dar ca acest",
    "hu": "a az és hogy nem is egy meg van de ez csak már el mint ha vagy volt még",
    "fi": "ja on ei se että oli hän ovat mutta kun niin kuin jos myös tai olla ole minä me",
    "tl": "ang ng sa na at mga ay ko ito hindi siya para kung may si ka ako niya",
    "ca": "el la de que i a els les en del es per amb no un una és com al però més són",
    "hr": "i u je da se na za su od s ne to ali kao što iz bi sam smo ili",
    "af": "die en van is in het dat nie op te vir met wat ek as was sy hy ook om",
}
STOPWORDS = {code: set(words.split()) for code, words in STOPWORDS.items()}

CHAR_LANGS = {"zh", "ja", "th", "lo", "km", "my", "bo"}

CHAR_UNIT = ("々〇぀-ヿㇰ-ㇿ㐀-䶿一-鿿豈-﫿"
             "ｦ-ﾝ\U00020000-\U0002fa1f฀-໿ༀ-࿿က-႟ក-៿")
MARKS = ("̀-ͯ҃-҉֑-ׇؐ-ًؚ-ٰٟۖ-ۭ"
         "ऀ-ॣ०-෿᪰-᫿᷀-᷿⃐-⃿︠-︯")
_WCH = rf"(?:(?![{CHAR_UNIT}])[^\W_]|[{MARKS}])"
WORD = re.compile(rf"{_WCH}+(?:['-]{_WCH}+)*")
CHAR_RX = re.compile(f"[{CHAR_UNIT}]")
WINDOW_BY_LANG = {"zh": 750, "ja": 1200}


def norm(s):
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return (unicodedata.normalize("NFC", s).replace("’", "'").replace("‘", "'")
             .replace("“", '"').replace("”", '"'))


DECODE_NOTES = {}


def read_text(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if data[:4] in (b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff"):
        return data.decode("utf-32", errors="replace")
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8-sig", errors="replace")
        DECODE_NOTES[path] = (f"{os.path.basename(path)} is not saved as UTF-8 ({text.count(chr(0xFFFD))} "
                              "characters could not be read; it may be GBK, Big5, Shift-JIS or Windows-1252). "
                              "Save it as UTF-8 and run again: the numbers below are unreliable.")
        return text


def prose_only(text):
    text = norm(text)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"^\s*#{1,6}\s+.*$", " ", text, flags=re.M)
    text = re.sub(r"^\s*(?:[-*•]|\d+\.)\s+", "", text, flags=re.M)
    return re.sub(r"[*_`>]", "", text)


def split_sentences(prose):
    guarded = ABBREV.sub(lambda m: m.group(0).replace(".", "\x00"), prose)
    parts = re.split(
        r"(?<=[.!?।॥؟۔։።፧])\s+|(?<=[။។])\s*|(?<=[.!?][\"')\]])\s+|(?<=[.!?][\"')\]]{2})\s+|\n{2,}"
        r"|(?<=[.!?])(?=[\u3400-\u9fff\u3040-\u30ff])"
        r"|(?<=[。！？｡‼⁇⁈⁉])(?![\"')\]”’」』）〕】》])\s*"
        r"|(?<=[。！？｡‼⁇⁈⁉][\"')\]”’」』）〕】》])(?![\"')\]”’」』）〕】》])\s*"
        r"|(?<=[。！？｡‼⁇⁈⁉][\"')\]”’」』）〕】》]{2})\s*",
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


def char_units(s):
    if not CHAR_RX.search(s):
        return 0
    return sum(1 for c in CHAR_RX.findall(s) if not unicodedata.category(c).startswith("M"))


def wc(s):
    return len(WORD.findall(s)) + char_units(s)


def script_of(ch):
    name = unicodedata.name(ch, "")
    first = name.split(" ")[0] if name else "OTHER"
    if first in ("CJK", "IDEOGRAPHIC"):
        return "HAN"
    if first in ("HALFWIDTH", "FULLWIDTH"):
        for s in ("KATAKANA", "HANGUL", "LATIN"):
            if s in name:
                return s
    return first


SCRIPT_LABELS = {"HAN": "Chinese characters", "HIRAGANA": "hiragana", "KATAKANA": "katakana",
                 "HANGUL": "Hangul", "LATIN": "Latin", "CYRILLIC": "Cyrillic", "GREEK": "Greek",
                 "ARABIC": "Arabic", "HEBREW": "Hebrew", "DEVANAGARI": "Devanagari", "THAI": "Thai"}


def script_shares(text, limit=200000):
    text = text[:limit]
    counts = Counter()
    for tok in WORD.findall(text):
        for ch in tok:
            if ch.isalpha():
                counts[script_of(ch)] += 1
                break
    for ch in CHAR_RX.findall(text):
        if ch.isalpha():
            counts[script_of(ch)] += 1
    total = sum(counts.values())
    return [(s, n / total) for s, n in counts.most_common()] if total else []


def latin_guess(text):
    toks = [t.lower() for t in WORD.findall(text)]
    shares = {code: sum(1 for t in toks if t in words) / len(toks) for code, words in STOPWORDS.items()} if toks else {}
    ranked = sorted(shares.items(), key=lambda kv: -kv[1])
    if len(toks) < 20 and (not ranked or ranked[0][1] == 0):
        return "en?", shares, len(toks)
    if len(ranked) < 2 or ranked[0][1] == 0:
        return None, shares, len(toks)
    (best, top), (runner, second) = ranked[0], ranked[1]
    if len(toks) >= 20 and best in LANGS and top >= LATIN_MIN_SHARE and top >= second * LATIN_CLEAR_MARGIN:
        return best, shares, len(toks)
    if len(toks) >= 20 and top >= (LATIN_MIN_LISTED if best in LANGS else LATIN_MIN_SHARE):
        if top >= second * LATIN_MARGIN:
            return best, shares, len(toks)
        own = sum(1 for t in toks if t in STOPWORDS[best] and t not in STOPWORDS[runner])
        theirs = sum(1 for t in toks if t in STOPWORDS[runner] and t not in STOPWORDS[best])
        if own >= 5 and own >= 3 * theirs:
            return best, shares, len(toks)
    if best == "en" and len(toks) < 20 and top >= second * LATIN_SHORT_MARGIN:
        return "en?", shares, len(toks)
    return None, shares, len(toks)


LATIN_MIN_SHARE = 0.10
LATIN_MIN_LISTED = 0.18
LATIN_CLEAR_MARGIN = 2.0
LATIN_MARGIN = 1.3
LATIN_SHORT_MARGIN = 1.5


def resolve_language(text, requested=None):
    text = re.sub(r"https?://\S+|www\.\S+|(?<!\S)[^\s@]+@[^\s@]+\.\S+", " ", prose_only(text))
    shares = script_shares(text)
    info = {"scripts": [(s, round(p, 3)) for s, p in shares]}
    main = shares[0][0] if shares else None
    unread = requested if requested and not normalize_lang(requested) else None
    if requested and normalize_lang(requested):
        code = normalize_lang(requested)
        how = "chosen with --lang"
    elif not shares:
        code, how = "en", "no letters found; English assumed"
    elif main in ("HAN", "HIRAGANA", "KATAKANA"):
        cjk = sum(p for s, p in shares if s in ("HAN", "HIRAGANA", "KATAKANA"))
        kana = sum(p for s, p in shares if s in ("HIRAGANA", "KATAKANA"))
        if kana >= 0.05 * cjk:
            code, how = "ja", "read from the script: kana among the Chinese characters"
        elif len(CHAR_RX.findall(text)) < 20:
            code, how = "zh", "Chinese characters with no kana, but too short to rule out Japanese (use --lang ja if it is)"
        else:
            code, how = "zh", "read from the script: Chinese characters with no Japanese kana"
    elif main == "HANGUL":
        code, how = "ko", "read from the script: Hangul"
    elif main == "THAI":
        code, how = "th", "read from the script: Thai"
    elif main == "LAO":
        code, how = "lo", "read from the script: Lao"
    elif main == "TIBETAN":
        code, how = "bo", "read from the script: Tibetan"
    elif main == "LATIN":
        guess, ls, ntok = latin_guess(text)
        ranked = [c for c, v in sorted(ls.items(), key=lambda kv: -kv[1]) if v > 0][:2]
        if guess == "en?":
            code, how = "en", ("Latin script; too short to tell the language, so English is assumed "
                               "(use --lang to choose)")
        elif guess:
            pct = round(100 * ls[guess])
            code, how = guess, f"Latin script; {pct}% of words are common {LANG_NAMES[guess]} words"
        else:
            looks = " or ".join(LANG_NAMES[c] for c in ranked)
            code, how = None, ("Latin script; the language could not be told" +
                               (f" (it looks most like {looks})" if looks else "") +
                               " (use --lang to name it)")
    else:
        code, how = None, f"{SCRIPT_LABELS.get(main, main.title())} script; language not identified (use --lang to name it)"
    if code and code in CHAR_LANGS:
        unit = "characters"
    elif code:
        unit = "words"
    else:
        unit = "characters" if sum(p for s, p in shares if s in ("HAN", "HIRAGANA", "KATAKANA", "THAI", "LAO", "KHMER", "MYANMAR", "TIBETAN")) >= 0.5 else "words"
    tag = code or ("und-" + main.lower() if main else "und")
    if unread:
        how = f"--lang {unread} was not understood, so the language was read from the text: " + how
    info.update(code=code, tag=tag, how=how, unit=unit, lists=code in LANGS,
                name=LANG_NAMES.get(code, code or "unidentified"))
    return info


IDENTIFIABLE = set(STOPWORDS) | {"zh", "ja", "ko", "th", "lo", "bo"}
LANG_SCRIPT = {"ar": "arabic", "fa": "arabic", "ur": "arabic", "he": "hebrew", "hi": "devanagari",
               "mr": "devanagari", "ne": "devanagari", "bn": "bengali", "ru": "cyrillic", "uk": "cyrillic",
               "bg": "cyrillic", "mk": "cyrillic", "kk": "cyrillic", "mn": "cyrillic", "el": "greek",
               "my": "myanmar", "km": "khmer", "ka": "georgian", "hy": "armenian", "ta": "tamil",
               "te": "telugu", "kn": "kannada", "ml": "malayalam", "gu": "gujarati", "pa": "gurmukhi",
               "si": "sinhala", "am": "ethiopic"}


def same_language(plang, info):
    """True when the voice and the text are the same language, including when one side is a
    language the checker could not name but the scripts agree."""
    if plang == info["tag"]:
        return True
    main = info["scripts"][0][0].lower() if info["scripts"] else ""
    if plang.startswith("und-"):
        return plang[4:] == main
    if info["code"] is None and plang not in IDENTIFIABLE:
        # The checker cannot name the voice's language, so an unnamed text in its script may be it.
        return LANG_SCRIPT.get(plang, "latin") == main
    return False


OWN_SCRIPTS = {"zh": {"HAN"}, "ja": {"HAN", "HIRAGANA", "KATAKANA"}, "ko": {"HANGUL", "HAN"}}
NO_SENTENCE_MARKS = {"th", "lo", "bo"}


def language_label(tag):
    if tag.startswith("und"):
        script = tag[4:]
        label = SCRIPT_LABELS.get(script.upper(), script.title())
        return ("a language not identified, in " + label + ("" if label.endswith("characters") else " script")
                if script else "a language not identified")
    return LANG_NAMES.get(tag, tag)


def per(n, words, scale):
    return round(n * scale / words, 2) if words else 0.0


LANG_NEUTRAL = ("sentence_cv", "paragraph_cv", "bullet_line_share")

LATIN_LETTER = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]")
ANY_LETTER = re.compile(r"[^\W\d_]")
LIX_BANDS = ((30, "very easy"), (40, "easy"), (50, "standard"), (60, "hard"))


def lix(prose, sents):
    tokens = WORD.findall(prose)
    if not tokens or not sents:
        return None
    letters = len(ANY_LETTER.findall(prose))
    if not letters or len(LATIN_LETTER.findall(prose)) < letters / 2:
        return None
    long_words = sum(1 for t in tokens if sum(c.isalpha() for c in t) > 6)
    return round(len(tokens) / len(sents) + 100 * long_words / len(tokens), 1)


def reading_level(score):
    for top, name in LIX_BANDS:
        if score < top:
            return name
    return "very hard"


def metrics(raw, lang="en", unit=None):
    spec = LANGS.get(lang, {})
    unit = unit or ("characters" if lang in CHAR_LANGS else "words")
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
    bullets = sum(1 for l in lines if re.match(r"\s*(?:(?:[-*•]|\d+\.)\s+|\d+、)", l))
    dash_rx = r"—+|―+|\s–\s|\s--\s|(?<=\w)--(?=\w)" if unit == "characters" else r"—|\s–\s|\s--\s|(?<=\w)--(?=\w)"
    if lang in NO_SENTENCE_MARKS:
        out = {"words": words, "sentences": 0}
    else:
        out = {
            "words": words,
            "sentences": len(sents),
            "avg_sentence_words": round(mean, 1),
            "sentence_cv": round(sd / mean, 2) if mean else 0.0,
        }
    if unit == "words" and lang not in NO_SENTENCE_MARKS:
        score = lix(prose, sents)
        if score is not None:
            out["reading_lix"] = score
        out["short_sentence_share"] = round(sum(1 for n in lens if n <= 8) / len(lens), 2)
        out["long_sentence_share"] = round(sum(1 for n in lens if n >= 25) / len(lens), 2)
    out.update({
        "paragraphs": len(paras),
        "avg_paragraph_words": round(pmean, 1),
        "paragraph_cv": round(psd / pmean, 2) if pmean else 0.0,
    })
    if spec.get("contractions"):
        out["contractions_per_100w"] = per(len(spec["contractions"].findall(prose)), words, 100)
    out.update({
        "em_dashes_per_1000w": per(len(re.findall(dash_rx, prose)), words, 1000),
        "semicolons_per_1000w": per(sum(prose.count(c) for c in ";；؛"), words, 1000),
        "exclamations_per_1000w": per(sum(prose.count(c) for c in "!！"), words, 1000),
        "questions_per_1000w": per(sum(prose.count(c) for c in "?？؟"), words, 1000),
    })
    if spec.get("fillers"):
        out["fillers_per_1000w"] = per(len(spec["fillers"].findall(prose)), words, 1000)
    if spec.get("first_person"):
        out["first_person_per_100w"] = per(len(spec["first_person"].findall(prose)), words, 100)
    if spec.get("i_led"):
        out["i_led_sentence_pct"] = round(100 * sum(1 for x in sents if spec["i_led"].match(x)) / len(sents), 1) if sents else 0.0
    out["bullet_line_share"] = round(bullets / len(lines), 2) if lines else 0.0
    return out


def find_tells(raw, lang="en"):
    spec = LANGS.get(lang)
    hits = []
    mild = {}
    in_code = False
    for no, line in enumerate(norm(raw).splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        src = line.translate(ZH_T2S) if lang == "zh" else line
        low = src.lower()
        spans = []
        for ph in (spec["phrases"] if spec else ()):
            i = low.find(ph)
            while i != -1:
                spans.append((i, i + len(ph)))
                hits.append((no, "stock phrase", line[i:i + len(ph)] if lang == "zh" else ph, line))
                i = low.find(ph, i + len(ph))
        if spec:
            for m in spec["words"].finditer(src):
                if not any(a <= m.start() < b for a, b in spans):
                    hits.append((no, "stock word", line[m.start():m.end()], line))
        for ph in (spec["mild"] if spec else ()):
            if ph in low:
                mild[ph] = mild.get(ph, 0) + low.count(ph)
        if lang == "en":
            triples = len(re.findall(r"\b[A-Za-z-]+, [A-Za-z-]+,? (?:and|or) [A-Za-z-]+\b", line))
            if triples:
                mild["three-item lists"] = mild.get("three-item lists", 0) + triples
        for label, rx in (spec["patterns"] if spec else []) + COMMON_PATTERNS:
            for m in rx.finditer(src):
                hits.append((no, label, line[m.start():m.end()].strip(), line))
        hm = re.match(r"\s*#{1,6}\s+(.*)$", line) if lang == "en" else None
        if hm:
            ws = hm.group(1).split()
            body = [w for w in ws if w.lower() not in SMALL_WORDS]
            if len(ws) >= 3 and body and all(w[0].isupper() for w in body if w[0].isalpha()):
                hits.append((no, "Title Case heading", hm.group(1), line))
    if lang == "zh":
        text = norm(raw).translate(ZH_T2S)
        found = [m for m in ZH_CONTRAST.finditer(text)]
        units = max(wc(prose_only(raw)), 1)
        if len(found) >= 2 and len(found) * 1000 / units >= 5:
            no = text.count("\n", 0, found[0].start()) + 1
            hits.append((no, f"contrast pile-up (不是…而是…), {len(found)} in this piece", found[0].group(0), ""))
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


SPREAD_NEEDS = {"paragraph_cv": ("paragraphs", 3), "sentence_cv": ("sentences", 3)}


ISO3 = {"eng": "en", "spa": "es", "zho": "zh", "chi": "zh", "cmn": "zh", "yue": "zh", "jpn": "ja",
        "kor": "ko", "fra": "fr", "fre": "fr", "deu": "de", "ger": "de", "por": "pt", "ita": "it",
        "nld": "nl", "dut": "nl", "rus": "ru", "ukr": "uk", "ara": "ar", "hin": "hi", "vie": "vi",
        "tur": "tr", "pol": "pl", "ind": "id", "tha": "th", "swe": "sv", "dan": "da", "nob": "no"}


def normalize_lang(value):
    value = (value or "").strip().strip("\"'`").strip().lower()
    if not value:
        return None
    if re.fullmatch(r"und(?:-[a-z]{2,20})?", value):
        return value
    first = re.split(r"[-_\s(,.#;]", value)[0]
    if first in ISO3:
        return ISO3[first]
    if first in LANG_NAMES and re.fullmatch(r"[a-z]{2,3}(?:[-_][a-z0-9]{2,8})*", value):
        return first
    if (first in LANG_NAMES or first in ISO3) and re.fullmatch(r"[a-z]{2,3}(?:[-_][a-z0-9]{2,8})*\s*[(,.#;].*", value):
        return ISO3.get(first, first)  # a code with a note after it: "zh (simplified)", "es (Spain)"
    words = re.findall(r"[a-z]+", value)
    for c, name in LANG_NAMES.items():
        if any(n.strip().lower() in words for n in name.replace(",", " or ").split(" or ")):
            return c
    for native, c in NATIVE_NAMES.items():
        if native in value:
            return c
    return value if re.fullmatch(r"[a-z]{2,3}", value) else None


NATIVE_NAMES = {"中文": "zh", "汉语": "zh", "漢語": "zh", "简体": "zh", "繁體": "zh", "日本語": "ja",
                "한국어": "ko", "español": "es", "castellano": "es", "français": "fr", "deutsch": "de",
                "português": "pt", "italiano": "it", "русский": "ru", "العربية": "ar", "हिन्दी": "hi",
                "tiếng việt": "vi", "türkçe": "tr", "polski": "pl", "ไทย": "th"}


def profile_language(ptxt):
    m = re.search(r"^[ \t]*language[ \t]*:[ \t]*(.*?)[ \t]*$", ptxt or "", re.M | re.I)
    return (normalize_lang(m.group(1)) if m else None) or "en"


def language_lines(info):
    name = info["name"] if info["code"] else "not identified"
    out = ["== Language ==", f"Checked as: {name} ({info['how']})."]
    if info["unit"] == "characters":
        out.append("Lengths are counted in characters, because this script has no spaces between words.")
    if info["code"] in NO_SENTENCE_MARKS:
        out.append("This script does not mark where sentences end, so sentence measures were not taken.")
    if info["lists"]:
        missing = [label for key, label in (("contractions", "contractions"), ("fillers", "spoken fillers"),
                                            ("first_person", "first person"), ("i_led", "sentences that start with I"))
                   if not LANGS[info["code"]].get(key)]
        out.append(f"Machine-writing habit lists: {LANGS[info['code']]['name']}.")
        if missing:
            out.append("Not measured for this language: " + ", ".join(missing) + ".")
    else:
        out.append("Machine-writing habit lists: none for this language yet, so phrases and stock words "
                   "were NOT checked. " + ("Paragraph rhythm, punctuation and layout were."
                                           if info["code"] in NO_SENTENCE_MARKS else
                                           "Rhythm, punctuation and layout were."))
    own = OWN_SCRIPTS.get(info["code"], set()) | {info["scripts"][0][0] if info["scripts"] else ""}
    others = [f"{SCRIPT_LABELS.get(s, s.title())} {round(100 * p)}%" for s, p in info["scripts"] if p >= 0.05 and s not in own]
    if others:
        out.append("Other scripts in the text, not checked against any list: " + ", ".join(others) + ".")
    return out


MAX_LISTED = 200


EMPTY_MESSAGE = "Nothing to check: the text has no words."


def has_words(raw):
    """True when the text holds at least one letter in any script."""
    return any(ch.isalpha() for ch in prose_only(raw or ""))


LANG_WARN_MIN_TOKENS = 20     # Latin texts shorter than this cannot be told apart reliably
LANG_WARN_MIN_SHARE = 0.25    # share of the other language's common words before warning
LANG_WARN_MIN_SCRIPT = 0.6    # share of letters in another script before warning


def expected_script(code):
    if code in ("zh",):
        return {"HAN"}
    if code == "ja":
        return {"HAN", "HIRAGANA", "KATAKANA"}
    if code == "ko":
        return {"HANGUL"}
    if code in ("th", "lo", "bo"):
        return {{"th": "THAI", "lo": "LAO", "bo": "TIBETAN"}[code]}
    if code in LANG_SCRIPT:
        return {LANG_SCRIPT[code].upper()}
    if code in STOPWORDS:
        return {"LATIN"}
    return None


def language_mismatch(raw, requested):
    """A warning when --lang names one language and the text plainly reads as another, or None.
    Narrow on purpose: it fires only on a clear signal, so short notes and Vietnamese typed
    without accent marks are not flagged (both are read too weakly to judge)."""
    code = normalize_lang(requested) if requested else None
    if not code:
        return None
    text = re.sub(r"https?://\S+|www\.\S+", " ", prose_only(raw))
    shares = script_shares(text)
    if not shares:
        return None
    main, part = shares[0]
    want = expected_script(code)
    letters = sum(1 for ch in text if ch.isalpha())
    if want and main not in want and part >= LANG_WARN_MIN_SCRIPT and letters >= 20:
        label = SCRIPT_LABELS.get(main, main.title())
        label = label if "characters" in label else label + " script"
        return (f"Warning: --lang {requested} was given, but most of the text is written in "
                f"{label}. If the draft should be in "
                f"{LANG_NAMES.get(code, code)}, it is not.")
    if main == "LATIN" and (not want or "LATIN" in want):
        guess, ls, ntok = latin_guess(text)
        if (guess and guess not in ("en?", code) and ntok >= LANG_WARN_MIN_TOKENS
                and ls.get(guess, 0) >= LANG_WARN_MIN_SHARE):
            pct = round(100 * ls[guess])
            return (f"Warning: --lang {requested} was given, but the text reads as {LANG_NAMES[guess]} "
                    f"({pct}% of its words are common {LANG_NAMES[guess]} words). If the draft should "
                    f"be in {LANG_NAMES.get(code, code)}, it is not.")
    return None


def before_line(before, m, lang):
    old = {}
    if has_words(before):
        info = resolve_language(before, lang)
        old = metrics(before, info["code"], info["unit"])
    was = (f"before {old['reading_lix']} ({reading_level(old['reading_lix'])})" if "reading_lix" in old
           else "before not measured for this language")
    now = (f"after {m['reading_lix']} ({reading_level(m['reading_lix'])})" if "reading_lix" in m
           else "after not measured for this language")
    return f"reading level: {was}, {now}"


def scan_report(raw, ptxt=None, profile=None, register="written", tone=None, lang=None, before=None):
    if not has_words(raw):
        return EMPTY_MESSAGE
    info = resolve_language(raw, lang)
    hits, mild = find_tells(raw, info["code"])
    m = metrics(raw, info["code"], info["unit"])
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
    out = language_lines(info)
    mismatch = language_mismatch(raw, lang)
    if mismatch:
        out.append(mismatch)
    out += ["", "== Machine-writing tells =="]
    if hits:
        for no, kind, found, _line in hits[:MAX_LISTED]:
            out.append(f"line {no}: {kind}: \"{found}\"")
        if len(hits) > MAX_LISTED:
            out.append(f"... and {len(hits) - MAX_LISTED} more (counted in the summary)")
    elif info["lists"]:
        out.append("none found")
    else:
        out.append("none found among layout marks; phrases and words not checked for this language")
    mild_rate = sum(mild.values()) * 1000 / max(m["words"], 1)
    if sum(mild.values()) >= 3 and mild_rate >= 5:
        out.append("mild connectors, worth thinning: " +
                   ", ".join(f"{k} x{v}" for k, v in mild.items()))
    out.append("")
    out.append("== Habits ==" + (" (lengths and rates per character)" if info["unit"] == "characters" else ""))
    for k in ("words", "avg_sentence_words", "reading_lix", "sentence_cv", "paragraph_cv",
              "contractions_per_100w", "em_dashes_per_1000w",
              "questions_per_1000w", "fillers_per_1000w",
              "first_person_per_100w", "i_led_sentence_pct"):
        if k in m:
            out.append(f"{k}: {m[k]}" + (f" ({reading_level(m[k])})" if k == "reading_lix" else ""))
    if before is not None:
        out.append(before_line(before, m, lang))
    out.append("")
    plang = profile_language(ptxt) if ptxt else None
    short = window_for(info["code"], info["unit"]) // 2
    off = []
    if targets:
        if note:
            out.append(note)
        if tone_note:
            out.append(tone_note)
        out.append(f"== Versus the voice profile ({label}) ==")
        same_lang = same_language(plang, info)
        if not same_lang:
            out.append(f"(the voice was measured in {language_label(plang)} and this text is "
                       f"{language_label(info['tag'])}: only the measures that do not depend on language are judged)")
        for k, (lo, hi) in targets.items():
            if k not in m:
                out.append(f"{k}: not measured for this language")
                continue
            if not same_lang and k not in LANG_NEUTRAL:
                out.append(f"{k}: {m[k]} (profile {lo} to {hi}) not judged: different language")
                continue
            need = SPREAD_NEEDS.get(k)
            if need and m.get(need[0], 0) < need[1]:
                out.append(f"{k}: {m[k]} (profile {lo} to {hi}) not judged: needs {need[1]} or more {need[0]}")
                continue
            state = "ok" if lo <= m[k] <= hi else (
                "OUTSIDE (short text, a hint only)" if m["words"] < short else "OUTSIDE")
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
               f"{fmt} formatting marks (weak alone; real writers use them), {len(off)} habits off."
               + ("" if info["lists"] else " Phrases and stock words were not checked for this language.")
               + (" English was assumed, not identified: if the text is not English, its phrases and stock "
                  "words were not checked." if info["lists"] and "assumed" in info["how"] else ""))
    return "\n".join(out)


def cmd_scan(path, profile, register="written", tone=None, lang=None, before=None):
    raw = read_text(path)
    if raw is None:
        print(f"Cannot read {path}.")
        return 1
    old = None
    if before is not None:
        old = read_text(before)
        if old is None:
            print(f"Cannot read {before}.")
            return 1
    ptxt = read_text(profile) if profile else None
    for f in (path, before):
        if f in DECODE_NOTES:
            print("WARNING: " + DECODE_NOTES[f] + "\n")
    report = scan_report(raw, ptxt, profile, register, tone, lang, old)
    print(report)
    return 1 if report == EMPTY_MESSAGE else 0


TARGET_KEYS = ("avg_sentence_words", "sentence_cv", "paragraph_cv",
               "contractions_per_100w", "em_dashes_per_1000w",
               "semicolons_per_1000w", "exclamations_per_1000w",
               "questions_per_1000w", "fillers_per_1000w",
               "first_person_per_100w", "i_led_sentence_pct",
               "bullet_line_share", "reading_lix")

def window_for(lang, unit):
    return 500 if unit == "words" else WINDOW_BY_LANG.get(lang, WINDOW_BY_LANG["zh"])

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


def suggest_targets(texts, lang="en", unit="words"):
    size = window_for(lang, unit)
    ms = [m for m in (metrics(p, lang, unit) for t in texts for p in pieces(t, size)) if m["words"] > 0]
    if not ms:
        return {"targets": {}, "based_on_pieces": 0}
    usable = [m for m in ms if m["words"] >= size * 3 // 10] or ms
    targets = {}
    for k in TARGET_KEYS:
        if k not in usable[0]:
            continue
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


def stats_result(texts, names=None, each=False, targets=False, lang=None):
    joined = "\n\n".join(texts)
    info = resolve_language(joined, lang)
    code, unit = info["code"], info["unit"]
    m = metrics(joined, code, unit)
    m["files"] = len(texts)
    if each:
        labels = [str(n) for n in (names or range(1, len(texts) + 1))]
        m["per_file"] = {n: {k: pm[k] for k in ("words",) + TARGET_KEYS if k in pm}
                         for n, pm in zip(labels, (metrics(t, code, unit) for t in texts))}
    if targets:
        m["suggested"] = suggest_targets(texts, code, unit)
    if "reading_lix" in m:
        m["reading_level"] = reading_level(m["reading_lix"])
    m["language"] = info["tag"]
    m["language_how"] = info["how"]
    m["counted_in"] = unit
    return m


def cmd_stats(paths, each=False, targets=False, lang=None):
    texts, err = load_all(paths)
    if err:
        print(err)
        return 1
    result = stats_result(texts, paths, each, targets, lang)
    if any(p in DECODE_NOTES for p in paths):
        result["warnings"] = [DECODE_NOTES[p] for p in paths if p in DECODE_NOTES]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


COMMON = set("""that this with have from they were been their there would which what when your
them then than will into some more other about could should only also such these those very much
just over said says like upon and the for are but not you all any can had her his him she its our
out who how why where while being does did done has make made even here after before again never
every still must may might shall each both through under between because against""".split())


def habits_result(texts, lang=None):
    joined = "\n\n".join(texts)
    info = resolve_language(joined, lang)
    code = info["code"]
    prose = prose_only(joined)
    sents = split_sentences(prose)
    ns = len(sents) or 1
    paras = [p for p in re.split(r"\n\s*\n", prose) if re.search(r"\w", p)]
    psents = [len(split_sentences(p)) for p in paras] or [0]
    if code == "en":
        words = re.findall(r"[A-Za-z][a-z']+", prose)
        total = len(words) or 1
        cnt = Counter(w.lower() for w in words if len(w) >= 4 and w.lower() not in COMMON)
        openers = Counter(m.group(0).lower() for m in (re.search(r"[A-Za-z']+", s) for s in sents) if m)
    elif info["unit"] == "characters":
        total = wc(prose) or 1
        cnt = Counter()
        openers = Counter(s.lstrip("\"'(（「『“")[:2] for s in sents if s.strip())
    else:
        words = [w.lower() for w in WORD.findall(prose)]
        total = len(words) or 1
        stop = STOPWORDS.get(code, set())
        cnt = Counter(w for w in words if len(w) >= 4 and w not in stop and not w.isdigit())
        openers = Counter(f[0].lower() for f in (WORD.findall(s) for s in sents) if f)
    out = {
        "words": total,
        "common_words_per_10k": {w: round(n * 10000 / total) for w, n in cnt.most_common(30) if n >= 2},
        "sentence_openers_pct": {w: round(n * 100 / ns, 1) for w, n in openers.most_common(12)},
        "one_sentence_paragraph_pct": round(100 * sum(1 for n in psents if n == 1) / len(psents)),
        "avg_sentences_per_paragraph": round(sum(psents) / len(psents), 1),
    }
    if info["unit"] == "words":
        out["sentences_6_words_or_fewer_pct"] = round(100 * sum(1 for s in sents if wc(s) <= 6) / ns)
    if code == "en":
        out["I_per_10k_words"] = round(len(re.findall(r"\bI\b", prose)) * 10000 / total)
    if info["unit"] == "characters":
        out["common_words_per_10k"] = "not measured: no spaces between words in this script"
    out["language"] = info["tag"]
    out["language_how"] = info["how"]
    out["counted_in"] = info["unit"]
    return out


def cmd_languages():
    print("Every language and script: paragraph rhythm, punctuation and layout marks, and sentence rhythm")
    print("wherever the script marks sentence ends (Thai, Lao and Tibetan do not, so there it is skipped).")
    print("Lengths in Chinese, Japanese, Thai, Lao, Khmer, Burmese and Tibetan are counted in characters.")
    print("Machine-writing phrase and word lists:")
    for code, spec in LANGS.items():
        gaps = [label for key, label in (("contractions", "contractions"), ("fillers", "spoken fillers"),
                                         ("first_person", "first person"), ("i_led", "sentences that start with I"))
                if not spec.get(key)]
        print(f"  {code}  {spec['name']}" + (f" (not measured: {', '.join(gaps)})" if gaps else ""))
    print("The Chinese lists match simplified and traditional characters.")
    print("Any other language: no lists yet; the report says so instead of reporting a clean result.")
    return 0


def cmd_habits(paths, lang=None):
    texts, err = load_all(paths)
    if err:
        print(err)
        return 1
    result = habits_result(texts, lang)
    if any(p in DECODE_NOTES for p in paths):
        result["warnings"] = [DECODE_NOTES[p] for p in paths if p in DECODE_NOTES]
    print(json.dumps(result, indent=2, ensure_ascii=False))
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
    return {"name": name, "summary": summary, "built": built, "registers": registers,
            "language": profile_language(text), "file": path}


BUILT_IN_VOICES = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "voices"))


def voice_files(d):
    if not os.path.isdir(d):
        return []
    return [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.lower().endswith(".md")]


def find_voices(extra=()):
    dirs = voice_dirs(extra)
    found = []
    for d in dirs:
        for path in voice_files(d):
            found.append(dict(describe_voice(path), built_in=False))
    taken = set()
    for v in found:
        taken.add(v["name"].lower())
        taken.add(os.path.splitext(os.path.basename(v["file"]))[0].lower())
    for path in voice_files(BUILT_IN_VOICES):
        v = describe_voice(path)
        if v["name"].lower() not in taken and os.path.splitext(os.path.basename(path))[0].lower() not in taken:
            found.append(dict(v, built_in=True))
    return dirs + [BUILT_IN_VOICES], found


def voice_key(name):
    return re.sub(r"[\s_-]+", "-", (name or "").strip().lower()).strip("-")


def find_voice(name, extra=()):
    key = voice_key(name)
    if not key:
        return None
    for v in find_voices(extra)[1]:
        stem = os.path.splitext(os.path.basename(v["file"]))[0]
        if key in (voice_key(v["name"]), voice_key(stem)):
            return v["file"]
    return None


def cmd_voices(args):
    as_json = "--json" in args
    dirs, found = find_voices([a for a in args if not a.startswith("--")])
    if as_json:
        print(json.dumps({"searched": dirs, "voices": found}, indent=2))
        return 0
    if not any(not v["built_in"] for v in found):
        print("No voices of your own saved yet. Looked in:")
        for d in dirs[:-1]:
            print("  " + d)
    for i, v in enumerate(found, 1):
        regs = " and ".join(v["registers"]) or "no measured habits"
        if v["language"] != "en":
            regs += ", in " + LANG_NAMES.get(v["language"], v["language"])
        tag = " (built in)" if v["built_in"] else ""
        print(f"{i}. {v['name']}{tag}: {v['summary'] or 'no description'} ({regs})")
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
    "reading level": ("reading_lix",),
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
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if len(argv) >= 2 and argv[1] == "voices":
        return cmd_voices(argv[2:])
    if len(argv) >= 2 and argv[1] == "tones":
        return cmd_tones(argv[2:])
    if len(argv) >= 2 and argv[1] == "languages":
        return cmd_languages()
    if len(argv) < 3 or argv[1] not in ("stats", "scan", "habits"):
        print(__doc__)
        return 2
    args = argv[2:]
    lang = None
    if "--lang" in args:
        i = args.index("--lang")
        lang = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
        if not normalize_lang(lang):
            print("--lang needs a language code or name, such as en, zh, es or Chinese")
            return 2
    if argv[1] == "stats":
        flags = [a for a in args if a.startswith("--")]
        files = [a for a in args if not a.startswith("--")]
        return cmd_stats(files, each="--each" in flags, targets="--targets" in flags, lang=lang)
    if argv[1] == "habits":
        return cmd_habits(args, lang)
    profile, register = None, "written"
    if "--profile" in args:
        i = args.index("--profile")
        profile = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    tone = None
    if "--tone" in args:
        i = args.index("--tone")
        tone = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    before = None
    if "--before" in args:
        i = args.index("--before")
        before = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
        if not before:
            print("--before needs the file the rewrite started from")
            return 2
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
    return cmd_scan(args[0], profile, register, tone, lang, before)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
