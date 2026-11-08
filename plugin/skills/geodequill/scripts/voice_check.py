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
                                [--lang CODE] [--before ORIGINAL] [--keep WORDS ...]
                                                         -> plain-text report; --before names the
     text a rewrite started from and adds its reading level before and after and how
     much of its wording changed; --keep (repeatable) names words or phrases that must
     appear exactly, and the report lists any that are missing or altered. Your saved
     protected words (see keep) are judged too whenever --before is given.
  python3 -I voice_check.py learn EDITED [EDITED ...] --profile P.md|NAME [--register written|spoken]
                                [--draft DRAFT] [--lang CODE] [--write]
                                                         -> adds your own edited text to a voice as
     a sample and re-measures its ranges; --draft is the AI's draft you edited (text
     that is mostly the draft unchanged is refused); without --write it only shows
     what would change
  python3 -I voice_check.py keep [--add WORDS ...] [--remove WORDS ...]
                                                         -> your protected words, kept in
     ~/.geodequill/keep.md (or $GEODEQUILL_HOME/keep.md): words and phrases a rewrite
     must never change
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
     (or $GEODEQUILL_HOME/voices), which every AI app with GeodeQuill on this computer can share,
     then the built-in voices of public-domain authors; your own voice of the same
     name hides a built-in one

Standard library only. It reports habits it can count. It does NOT predict
what any AI detector will say and never prints an AI-probability score.
Exit codes: 0 done, 1 a file could not be read or scan found no words, 2 wrong usage,
3 learn changed nothing (the message says why).
"""
import difflib
import json
import math
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

# Japanese, Korean, Turkish, German, Russian and Finnish (0.6.5). Drawn from published lists (see
# LICENSE.txt) and cut down on human writing dated before November 2022: novels and stories, the
# translated Python documentation and Pro Git, Wikipedia and Wikisource. An entry that fired on
# that writing more than 0.05 times per 10,000 words was dropped or moved to the mild list.
# These languages are matched on folded lower-case text (see fold_tr, fold_ru), so the lists are
# written in lower case.


def fold_lower(s):
    return s.lower()


def fold_tr(s):
    """Turkish lower case: I is dotless ı and İ is i. Keeps every character in place."""
    return s.replace("İ", "i").replace("I", "ı").lower()


def fold_ru(s):
    """Russian lower case with ё read as е, as most Russian is typed."""
    return s.lower().replace("ё", "е")


def _rx(*parts):
    return re.compile("|".join(parts))


JA_WORDS = _rx(
    "多面的な", "包括的な", "画期的な", "計り知れない", "パラダイムシフト", "新たな地平", "唯一無二の",
    "他に類を見ない", "シナジー", "ソリューション", "インサイト", "レジリエンス",
    # density phrases from patina's Japanese lexicon: weak alone, by that lexicon's own note
    "本記事では", "この記事では", "ぜひ参考にしてください", "現代社会において", "デジタル時代において",
    "欠かせない存在", "重要な鍵とな", "持続可能な成長", "より良い未来", "新たな選択肢", "未来を切り拓く",
    "可能性を広げる", "価値を最大化", "最大限に引き出す", "これからの時代に求められる")
JA_PHRASES = [
    "浮き彫りにしており", "今後の展開が注目", "今後の展開に注目", "と言えるでしょう", "重要な示唆を与え",
    "重要な役割を果た", "素晴らしいご質問", "素晴らしい質問", "良いご指摘ですね", "鋭いご指摘ですね",
    "が注目を集めています", "今後ますます重要に", "さらなる発展が期待", "今後の発展が期待",
    "急速に変化する現代社会", "と言っても過言ではない", "お役に立てれば幸い", "ご不明な点がございましたら",
    "さらに詳しい情報が必要な場合", "お気軽にお尋ねください", "最新の情報と異なる場合があります",
    "周知の通り", "注目すべきは", "特筆すべきは", "と言えるかもしれない", "大きな可能性を秘めて",
    "無限の可能性", "新たな章の幕開け", "誰も教えてくれない", "について理解しておく必要があります",
]
JA_MILD = [
    "しかしながら", "加えて", "とりわけ", "このように", "これにより", "これを踏まえ", "まとめると", "結論として",
    "総じて", "以上のことから", "を示しており", "を物語っています", "いただけますと幸いです",
    "注目に値する", "重要なのは", "見ていきましょう", "することが重要です", "言うまでもなく",
]
JA_PATTERNS = [
    ("negative parallelism (単なる…ではなく)", re.compile(r"単なる[^。\n]{1,40}?ではなく")),
    ("template opener (ここでは…について解説します)", re.compile(r"ここでは[^。\n]{0,40}?について解説します")),
    ("template opener (近年、…急速に進展)", re.compile(r"近年[、,][^。\n]{0,40}?急速に進展")),
    ("vague attribution (専門家によると)", re.compile(r"(?:業界の)?専門家によると|業界関係者によると|多くの企業が指摘しているように")),
    ("stacked hedge (おそらく…かもしれない)", re.compile(r"おそらく[^。\n]{0,40}?かもしれない|ある程度[^。\n]{0,40}?可能性がある")),
    ("template ending (…が期待されます。)", re.compile(r"が期待され(?:ます|る)。?\s*$")),
]

KO_WORDS = _rx(
    "가시화", "자리매김", "일환", "차별화", "혁신적인", "획기적인", "괄목할 만한", "무궁무진한", "고무적인",
    "시너지", "솔루션", "인사이트", "패러다임", "심층적인", "선도적인", "극대화")
KO_PHRASES = [
    # "중요한 역할을", "필요가 있습니다", "있습니다. 또한,", "영향을 미칩니다." and "새로운 가능성을" were in
    # patina's lexicon; all ran above the line in Korean Wikipedia or the Korean Python docs.
    "있으며, 이는", "라고 할 수 있습니다", "시사점을 제공", "과언이 아니", "귀추가 주목", "밝은 미래", "빠르게 변화하는",
    "새로운 패러다임", "중요한 시사점", "에 그치지 않고", "도움이 되셨기를", "도움이 되셨으면 좋겠습니다",
    "물론입니다", "좋은 질문", "궁금한 점이 있으시면", "에 대해 알아보겠습니다", "더 자세한 내용이 필요하시면",
    "최신 정보와 다를 수 있습니다", re.compile(r"새로운 지평을 열\w*"), re.compile(r"토대를 마련\w*"),
    re.compile(r"위상을 드높\w*"), "패러다임의 전환",
    "이러한 과제에도 불구하고", "밝은 전망이 기대", "4차 산업혁명 시대를 맞이하여", "에 박차를 가하고 있",
    "앞으로의 행보가 기대", "향후 추이를 지켜볼 필요가 있다", "흥미진진한 여정", "아무도 말해주지 않는",
    "아무도 알려주지 않는", "주목할 만한 점은", "라는 점에서 의미가 있습니다", "현대 사회에서 그 중요성이",
    "정확하게 말하자면", re.compile(r"가능성이 큽니다\."),
]
KO_MILD = [
    "결론적으로", "궁극적으로", "이를 통해", "더 나아가", "한편으로는", "요약하자면", "아울러", "이러한 맥락에서",
    "이처럼", "이렇듯", "뿐만 아니라", "종합하면", "종합해 보면", "종합해보면", "요컨대",
]
KO_PATTERNS = [
    ("double passive (되어지다, 보여지다)", re.compile(r"되어[지진질졌짐]|보여[지진질졌짐]")),
    ("beyond merely (단순히 …를 넘어)", re.compile(r"단순히 .{0,12}[을를] 넘어")),
    ("not merely (비단 … 뿐 아니라)", re.compile(r"비단 .{0,40}뿐(?:만)? 아니라")),
    ("vague attribution (전문가들은…)", re.compile(r"전문가들은|업계 관계자에 따르면|관련 연구에 따르면")),
    ("pivotal role (핵심적인 역할)", re.compile(r"(?:핵심적|중추적|획기적)인 역할")),
    ("era opener (최근 들어 … 급격히 변화하고 있다)", re.compile(r"최근 들어 .{0,20}[이가] 급격히 변화하고 있다")),
]

TR_WORDS = re.compile(
    r"\beşsiz\w*|\bbenzersiz\w*|\bpaha biçilmez\w*|\bzengin bir mozai\w*|\bçok ?boyutlu\w*|\bhayat[iî]\b")
TR_PHRASES = [
    re.compile(r"kritik bir rol oyna\w*"), re.compile(r"hayat[iî] bir önem taşı\w*"),
    re.compile(r"önemli bir rol üstlen\w*"), re.compile(r"vazgeçilmez bir h[aâ]le gel\w*"),
    "değil, aynı zamanda", re.compile(r"niteliğini de taşı\w*"), "boyutu göz ardı edilmemeli",
    "değil, yalnızca", "değil, sadece", "değil, sırf", re.compile(r"bir soru ısrarla bekle\w*"),
    "şu soru gündemde",
]
TR_MILD = [
    "bu bağlamda", "öte yandan", "bunun yanı sıra", "bu doğrultuda", "bu çerçevede",
    ("tam da", re.compile(r"\btam da\b")), "tam anlamıyla", ("gerçekten de", re.compile(r"\bgerçekten de\b")),
    ("aslında da", re.compile(r"\baslında da\b")), ("esasen", re.compile(r"\besasen\b")),
    ("nihayetinde", re.compile(r"\bnihayetinde\b")), ("bir bakıma", re.compile(r"\bbir bakıma\b")),
    "gerçek anlamda", "sonuç olarak",
]
# The source's punctuation and grammar signals (semicolons, dashes, a comma before "ama", -mektedir,
# a sentence opened by "ama" or "işte", "şudur:") all ran far above the line on human Turkish.
TR_PATTERNS = []

DE_WORDS = re.compile(
    r"\bbeleucht(?!ung|er)\w*|\beintauch(?!ung)\w*|\bunterstreich(?!ung)\w*|\bspannend\w*|"
    r"\bma(?:ß|ss)geblich\w*|\bnahtlos\w*|\bvielschichtig\w*|\bfacettenreich\w*|\bganzheitlich\w*|"
    r"\bma(?:ß|ss)geschneidert\w*|\bdigitalen?\s+landschaft\w*|\bzusammenspiel\w*|\bentfessel\w*|"
    r"\brevolutionier\w*|\bessen[zt]iell\w*|\bmeilenstein\w*|\bspannungsfeld\w*|\batemberaubend\w*|"
    r"\bfaszinierend\w*|\bgame-?changer\b|\bzweifellos\b")
DE_PHRASES = [
    "steht als zeugnis für", "ist ein beweis für", "das ändert alles", "es ist wichtig zu bemerken",
    "es kann nicht ignoriert werden", "keine diskussion wäre vollständig ohne", "es sollte hervorgehoben werden",
    "es ist erwähnenswert", re.compile(r"es ist wichtig,? zu beachten"), "zu beachten ist, dass",
    re.compile(r"branchenberichte (?:zeigen|belegen)"), "manche argumentieren", "mehrere studien deuten darauf hin",
    "experten sind sich einig", "ich hoffe, das hilft", re.compile(r"(?:du hast|sie haben) völlig recht"),
    "was für eine großartige frage", "lassen sie mich wissen", "ich helfe ihnen gerne", "lassen sie uns eintauchen",
    "bis zu meinem letzten update", re.compile(r"als ki-(?:sprach)?modell"), "als ki kann ich nicht",
    "das liegt außerhalb meiner fähigkeiten", "die eigentliche frage ist", "was wirklich zählt",
    "worauf es wirklich ankommt", "letztlich geht es um", "lassen sie uns erkunden",
    "hier ist, was sie wissen müssen", "ohne weitere umschweife", re.compile(r"tauchen wir .{0,20}ein\b"),
    re.compile(r"ha(?:ben sie|st du) (?:dich |sich )?jemals gefragt"), "seit anbeginn der zivilisation",
    "in einer zunehmend vernetzten welt", "im zeitalter der digitalisierung", "in der heutigen schnelllebigen",
    "angesichts der rasanten entwicklung", "die möglichkeiten sind grenzenlos",
    "an der schwelle zu einer neuen ära", "mit zuversicht in die zukunft", "das potenzial ist enorm",
    "am ende des tages", "unterstreicht die bedeutung", re.compile(r"\bgute frage\b"),
]
DE_MILD = [
    "darüber hinaus", ("zudem", re.compile(r"\bzudem\b")), ("ferner", re.compile(r"\bferner\b")),
    "des weiteren", ("überdies", re.compile(r"\büberdies\b")), "zusammenfassend", "abschließend",
    "im wesentlichen", ("fungiert als", re.compile(r"\bfungier\w* als\b")),
    ("erweist sich als", re.compile(r"\berweis\w* sich als\b")), "in vielerlei hinsicht",
    ("schauen wir uns … an", re.compile(r"schauen wir uns .{0,30}an\b")),
]
DE_PATTERNS = [
    ("plays a key role (spielt eine wichtige Rolle)",
     re.compile(r"\bspiel\w*\s+eine\s+(?:wichtige|entscheidende|zentrale|bedeutende)\s+rolle\b")),
    ("dash punchline (es geht nicht um … – es geht um)",
     re.compile(r"\bes\s+geht\s+nicht\s+um\b[^.!?]{1,60}\s[–—-]\s*es\s+geht\s+um\b")),
    ("tacked-on significance (, was … unterstreicht)",
     re.compile(r",\s*was\s+(?:[\wäöüß-]+\s+){0,6}(?:unterstreicht|verdeutlicht)\b")),
    ("stacked hedge", re.compile(r"\b(?:scheint|könnte|dürfte)\s+(?:möglicherweise|eventuell|vielleicht|unter\s+umständen)\b")),
    ("grand opener (in der heutigen … Welt)", re.compile(r"\bin\s+der\s+heutigen\s+\w+\s+(?:welt|gesellschaft)\b")),
    ("calque (Potenzial freischalten, Veränderung umarmen)",
     re.compile(r"\bpotenzial\w*\s+(?:zu\s+)?frei(?:zu)?schalt\w*|\bpotenzial\w*\s+freigeschaltet|\bveränderungen?\s+(?:zu\s+)?umarm\w*")),
    ("vague attribution (Experten sagen)",
     re.compile(r"\b(?:experten|studien|forscher|beobachter|kritiker)\s+(?:sagen|zeigen|meinen|betonen|erwarten|warnen)\b")),
]

RU_WORDS = re.compile(
    r"\bбесшовн\w*|\bвызов(?:ы|ов|ами|ам|ах)\b|\bэкосистем\w*|\bинсайт\w*|\bуникальн\w*|\bнеотъемлем\w*|"
    r"\bвпечатляющ\w*|\bинновационн\w*|\bсинерги\w*|"
    r"\bпоистине\b|\bпо-настоящему\b")
RU_PHRASES = [
    "конечно! вот", "отличный вопрос", "надеюсь, это поможет", "надеюсь, было полезно",
    re.compile(r"если хотите, (?:я )?могу"), re.compile(r"на момент моего (?:обучения|последнего обновления)"),
    "стоит отметить", "следует отметить", "стоит подчеркнуть", "важно понимать", "давайте разберемся",
    "в современном мире", "в эпоху цифровизации", "не секрет, что",
    "в рамках данной статьи", "в этой статье мы", "ключевую роль", re.compile(r"нов(?:ый|ом|ого|ому) уров(?:ень|н\w*)"),
    re.compile(r"безграничн\w+ возможност\w*"), re.compile(r"раскры\w+ (?:свой |ваш |весь )?потенциал"),
    re.compile(r"комплексн\w+ подход"), "что свидетельствует о", "можно с уверенностью сказать", "рады сообщить",
    re.compile(r"широк\w+ спектр"), "ряд преимуществ", "на ежедневной основе", re.compile(r"погруз(?:иться|имся) в"),
    "подводя итог", "будущее уже здесь", "мало кто знает", "секрет прост",
    "у каждого свой подход", "скажу честно",
]
RU_MILD = [
    "кроме того", "более того", "помимо этого", "таким образом", "в заключение", "резюмируя", "иными словами",
    "в конечном итоге", ("по сути", re.compile(r"\bпо сути\b")), "как известно", "в целях", "важно отметить",
    "на сегодняшний день",
]
RU_PATTERNS = [
    ("not about X, about Y (это не про)", re.compile(r"\bэто\s+не\s+про\b|\bречь\s+не\s+(?:о|об|про)\b")),
    ("false contrast (не просто …, а)", re.compile(r"\bне\s+просто\b[^.!?\n]{0,80}?,\s*(?:а|это)\b")),
    ("challenges then optimism (несмотря на … трудности)",
     re.compile(r"\bнесмотря на\b[^.!?\n]{0,120}?(?:сталкива|вызов|трудност)")),
    # "символизирует" and "неизгладимое впечатление" were in the source's pattern: both ordinary Russian.
    ("inflated symbolism", re.compile(r"служит напоминанием|поворотн(?:ый|ым|ого) момент")),
    ("tacked-on gerund", re.compile(r",\s+(?:подчеркивая|демонстрируя|отражая|свидетельствуя|способствуя|содействуя)\b")),
    ("promotional place", re.compile(r"в самом сердце|может похвастаться|богат(?:ое|ым|ой)\s+(?:культурн\w+\s+)?наследи")),
    ("vague attribution (эксперты отмечают)",
     re.compile(r"(?:эксперты|специалисты)\s+(?:отмечают|считают|рекомендуют)|исследования\s+показывают|по\s+словам\s+экспертов")),
    ("opens new possibilities", re.compile(r"открыва\w*\s+(?:перед\s+\w+\s+)?(?:новые|огромные)\s+(?:возможности|перспективы)")),
    ("calque (адресовать проблему)", re.compile(r"адрес(?:овать|ует|уют|овал\w*)\s+(?:\w+\s+)?(?:проблем\w*|бол\w*)")),
    ("stacked hedge", re.compile(r"\bмо(?:жет|гут)\s+потенциально\b")),
    ("asks and answers (Почему …? Потому что)", re.compile(r"\b(?:почему|зачем)\b[^?\n]{0,60}\?\s+(?:потому что|чтобы)\b")),
    ("teaser (Результат? …)", re.compile(r"\bрезультат\?\s")),
]

FI_WORDS = re.compile(
    r"\bratkaisev\w*|\bolennai\w+|\belintärke\w+|\bkriitti\w+|\bainutlaatui\w+|"
    r"\buraauurtav\w*|\bvallankumoukselli\w+|\binnovatiivi\w*|\bkäyttäjäystävälli\w*")
FI_PHRASES = [
    "vertaansa vailla", "olisin erittäin kiitollinen", "voisitte ystävällisesti", "harkita mahdollisuutta",
    "haluaisin nöyrästi", "hyvä kysymys!", "erinomainen huomio!", "ehdottomasti!", "voitaneen todeta",
    "lienee perusteltua", "saattaisi olla mahdollista", "on syytä huomata", "tässä yhteydessä on tärkeää",
    "on huomattava, että", "tulevaisuus näyttää valoisalta", "asiantuntijoiden mukaan", "tutkimukset osoittavat",
    "haasteista huolimatta", re.compile(r"viimeisimpien tietoj\w*"), "saatavilla olevien tietojen perusteella",
    "on tärkeää huomioida se tosiasia", "se tosiasia, että", re.compile(r"\bme näemme, että"),
    re.compile(r"\bme uskomme, että"), "muodostaa perustan", "monipuolisia mahdollisuuksia",
]
FI_MILD = [
    "tämän lisäksi,", "tapaa, jolla", ("mikäli", re.compile(r"\bmikäli\b")), "voidaan todeta",
    "kyse on kuitenkin siitä, että", "tässä yhteydessä", "edellä mainit", "kuten aiemmin mainit",
]
FI_PATTERNS = [
    ("doubled significance (merkittävä ja keskeinen)",
     re.compile(r"\b(?:merkittäv|keskei|tärke|olennai|ratkaisev|elintärke|kriitti)\w*\s+ja\s+"
                r"(?:merkittäv|keskei|tärke|olennai|ratkaisev|elintärke|kriitti)\w*")),
    ("stacked hedge", re.compile(r"\b(?:saattai\w*|saattaa|voisi\w*|voi(?:t|mme|tte|vat)?|ehkä(?:pä)?)\s+"
                                 r"(?:\w+\s+){0,2}(?:mahdollisesti|potentiaalisesti)\b")),
    ("opens new possibilities (avaa uusia mahdollisuuksia)",
     re.compile(r"\bava(?:a|avat|ten|si|sivat)\s+uusia(?:,?\s+\w+)?\s+mahdollisuuksia\b")),
    ("continues its development (jatkaa kehitystään)",
     re.compile(r"\bjatka(?:a|vat|en|i|ivat)\s+(?:vahvaa\s+)?kehit(?:tymis|ys)tään\b")),
    ("vague attribution (alan johtavat toimijat)", re.compile(r"\balan\s+johtav\w*\s+toimij\w+")),
    ("English cleft (se on tämä X, joka)", re.compile(r"\bse on (?:juuri )?(?:tämä|tuo|se) \w+, joka\b")),
]

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
    "ja": {"name": "Japanese", "words": JA_WORDS, "phrases": JA_PHRASES, "mild": JA_MILD,
           "patterns": JA_PATTERNS, "fold": fold_lower},
    "ko": {"name": "Korean", "words": KO_WORDS, "phrases": KO_PHRASES, "mild": KO_MILD,
           "patterns": KO_PATTERNS, "fold": fold_lower},
    "tr": {"name": "Turkish", "words": TR_WORDS, "phrases": TR_PHRASES, "mild": TR_MILD,
           "patterns": TR_PATTERNS, "fold": fold_tr},
    "de": {"name": "German", "words": DE_WORDS, "phrases": DE_PHRASES, "mild": DE_MILD,
           "patterns": DE_PATTERNS, "fold": fold_lower,
           "first_person": re.compile(r"\b(?:ich|mich|mir|mein|meine|meinen|meinem|meiner|meines)\b", re.I)},
    "ru": {"name": "Russian", "words": RU_WORDS, "phrases": RU_PHRASES, "mild": RU_MILD,
           "patterns": RU_PATTERNS, "fold": fold_ru,
           "first_person": re.compile(r"\b(?:я|меня|мне|мной|мой|моя|моё|мое|мои|моего|моей|моих)\b", re.I)},
    "fi": {"name": "Finnish", "words": FI_WORDS, "phrases": FI_PHRASES, "mild": FI_MILD,
           "patterns": FI_PATTERNS, "fold": fold_lower},
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
    "af": "Afrikaans", "ms": "Malay", "be": "Belarusian", "sr": "Serbian",
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

# Cyrillic-script languages, told apart the same way (ё is read as е). Russian has the lists;
# the others are here so that Ukrainian, Bulgarian and the rest are never given Russian lists.
# Short words these languages share (в, и, на, за ...) swamp the difference in encyclopedic text,
# so any word in two tables is dropped from both and only each language's own words are counted.
CYRILLIC_STOPWORDS = {
    "ru": "что это как он она его ее они был была были было году года также который которая которые "
          "которых после при или их может между только еще уже чтобы когда если даже нет есть него этого "
          "всех время является один одна свой своей во со же бы вот",
    "uk": "що це як він вона його її вони був була були було році року також який яка які яких після "
          "при або їх може між тільки ще вже щоб коли якщо навіть немає є та й із від до про всіх час "
          "один одна свій своєї у",
    "be": "што гэта як ён яна яго яе яны быў была былі было годзе года таксама які якая якія пасля пры "
          "або іх можа паміж толькі яшчэ ўжо каб калі нават няма ёсць ад да пра ўсіх час адзін адна ў і",
    "bg": "че това като той тя неговата беше които която който след през година също са ще може между "
          "само още вече когато ако дори няма има от за е да се ли със във един една своя",
    "sr": "да је се што за са од као али то су из сам ће био била који која које много још након током "
          "године такође између само када ако чак нема има у",
    "mk": "дека тоа како тој таа неговата беше кои која кој многу уште по за од се да ќе сум е со во "
          "година исто така помеѓу само кога ако дури нема има",
}
_cyr = {code: set(words.split()) for code, words in CYRILLIC_STOPWORDS.items()}
_shared = {w for c in _cyr for w in _cyr[c] if sum(w in t for t in _cyr.values()) > 1}
CYRILLIC_STOPWORDS = {code: words - _shared for code, words in _cyr.items()}
CYRILLIC_MIN_SHARE = 0.04   # measured below; see geodequill_Languages-0.6.5_MEASURED_11-7-26.md

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


def latin_guess(text, table=None):
    """Name the language from the share of each language's own common words. `table` is STOPWORDS
    (Latin script) unless given; CYRILLIC_STOPWORDS is passed for Cyrillic text."""
    table = table or STOPWORDS
    # Cyrillic tables hold only each language's own words, so their shares run lower.
    floor, listed = ((CYRILLIC_MIN_SHARE, CYRILLIC_MIN_SHARE) if table is CYRILLIC_STOPWORDS
                     else (LATIN_MIN_SHARE, LATIN_MIN_LISTED))
    toks = [t.lower().replace("ё", "е") for t in WORD.findall(text)]
    shares = {code: sum(1 for t in toks if t in words) / len(toks) for code, words in table.items()} if toks else {}
    ranked = sorted(shares.items(), key=lambda kv: -kv[1])
    if len(toks) < 20 and (not ranked or ranked[0][1] == 0):
        return "en?", shares, len(toks)
    if len(ranked) < 2 or ranked[0][1] == 0:
        return None, shares, len(toks)
    (best, top), (runner, second) = ranked[0], ranked[1]
    if len(toks) >= 20 and best in LANGS and top >= floor and top >= second * LATIN_CLEAR_MARGIN:
        return best, shares, len(toks)
    if len(toks) >= 20 and top >= (listed if best in LANGS else floor):
        if top >= second * LATIN_MARGIN:
            return best, shares, len(toks)
        own = sum(1 for t in toks if t in table[best] and t not in table[runner])
        theirs = sum(1 for t in toks if t in table[runner] and t not in table[best])
        if own >= 5 and own >= 3 * theirs:
            return best, shares, len(toks)
    if best == "en" and len(toks) < 20 and top >= second * LATIN_SHORT_MARGIN:
        return "en?", shares, len(toks)
    return None, shares, len(toks)


# A language's own letters, for languages whose common words alone leave too much text unnamed.
# (needs: letters at least `share` of all letters; none of: letters other neighbours use).
# Russian: ы and э, which Ukrainian, Bulgarian, Serbian and Macedonian lack, and none of the
# letters Belarusian (ў, і), Ukrainian (і ї є ґ), Serbian or Macedonian (ј љ њ џ ђ ћ ѓ ќ ѕ) or the
# Cyrillic Turkic and Mongolic languages (ә ө ү ұ қ ғ ң һ җ) add.
# Turkish: dotless ı or ğ, and no Azerbaijani ə or the ä å õ ß of the languages around Finnish.
# Finnish: ä and ö, and none of Swedish å, Estonian õ, German ü and ß.
# The last number is how many of the neighbours' letters are allowed per letter of the language's
# own, so that a quoted name does not unname a text: Belarusian, Kazakh and Azerbaijani text run
# well above one half; Estonian and Swedish text run at 0.4 to 0.55 against Finnish ä and ö.
LETTER_HINTS = {
    "ru": ("ыэ", "іїєґўјљњџђћѓќѕәөүұқғңһҗ", 0.005, 0.5,
           "the letters ы and э, which only Russian among its neighbours uses"),
    "tr": ("ığ", "əäåõß", 0.003, 0.5, "it has the Turkish letters ı and ğ"),
    "fi": ("äö", "åõüß", 0.01, 0.15, "it has Finnish ä and ö and next to none of å, õ, ü or ß"),
}


def letter_hint(text, code):
    """The reason `code` is read from its letters, or None. Needs 40 letters at least."""
    want, refuse, share, allowed, why = LETTER_HINTS[code]
    letters = [ch for ch in text.lower() if ch.isalpha()]
    if len(letters) < 40:
        return None
    found = sum(1 for ch in letters if ch in want)
    other = sum(1 for ch in letters if ch in refuse)
    if found < share * len(letters) or other > allowed * found:
        return None
    return why


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
    elif main == "CYRILLIC":
        guess, ls, ntok = latin_guess(text, CYRILLIC_STOPWORDS)
        hint = letter_hint(text, "ru")
        if guess == "ru" and not hint:
            guess = None   # Russian is named only when its letters agree (see LETTER_HINTS)
        if hint:
            code, how = "ru", "Cyrillic script; " + hint
        elif guess and guess != "en?":
            pct = round(100 * ls[guess])
            code, how = guess, f"Cyrillic script; {pct}% of words are common {LANG_NAMES[guess]} words"
        else:
            ranked = [c for c, v in sorted(ls.items(), key=lambda kv: -kv[1]) if v > 0][:2]
            looks = " or ".join(LANG_NAMES[c] for c in ranked)
            code, how = None, ("Cyrillic script; the language could not be told" +
                               (f" (it looks most like {looks})" if looks else "") + " (use --lang to name it)")
    elif main == "LATIN":
        guess, ls, ntok = latin_guess(text)
        ranked = [c for c, v in sorted(ls.items(), key=lambda kv: -kv[1]) if v > 0][:2]
        if guess in LETTER_HINTS and not letter_hint(text, guess):
            guess = None   # its common words say so, but its letters do not (Estonian read as Finnish)
        if guess == "en?":
            code, how = "en", ("Latin script; too short to tell the language, so English is assumed "
                               "(use --lang to choose)")
        elif guess:
            pct = round(100 * ls[guess])
            code, how = guess, f"Latin script; {pct}% of words are common {LANG_NAMES[guess]} words"
        elif ranked and ranked[0] in LETTER_HINTS and ntok >= 20 and letter_hint(text, ranked[0]):
            # The common words lean one way but not clearly; that language's own letters settle it.
            code = ranked[0]
            how = (f"Latin script; its common words lean {LANG_NAMES[code]} and " + letter_hint(text, code))
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


IDENTIFIABLE = set(STOPWORDS) | set(CYRILLIC_STOPWORDS) | {"zh", "ja", "ko", "th", "lo", "bo"}
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
        fold = spec.get("fold") if spec else None
        low = fold(src) if fold else src.lower()
        # Languages with a fold match everything on the folded line; the fold keeps every
        # character in place, so a match's position is also its position in the original line.
        seen = low if fold else src
        spans = []
        for ph in (spec["phrases"] if spec else ()):
            if isinstance(ph, re.Pattern):
                for m in ph.finditer(low):
                    spans.append((m.start(), m.end()))
                    hits.append((no, "stock phrase", line[m.start():m.end()], line))
                continue
            i = low.find(ph)
            while i != -1:
                spans.append((i, i + len(ph)))
                hits.append((no, "stock phrase", line[i:i + len(ph)] if (lang == "zh" or fold) else ph, line))
                i = low.find(ph, i + len(ph))
        if spec:
            for m in spec["words"].finditer(seen):
                if not any(a <= m.start() < b for a, b in spans):
                    hits.append((no, "stock word", line[m.start():m.end()], line))
        for ph in (spec["mild"] if spec else ()):
            if isinstance(ph, tuple):          # (label, regex) for a connector that needs word edges
                n = len(ph[1].findall(low))
                if n:
                    mild[ph[0]] = mild.get(ph[0], 0) + n
            elif ph in low:
                mild[ph] = mild.get(ph, 0) + low.count(ph)
        if lang == "en":
            triples = len(re.findall(r"\b[A-Za-z-]+, [A-Za-z-]+,? (?:and|or) [A-Za-z-]+\b", line))
            if triples:
                mild["three-item lists"] = mild.get("three-item lists", 0) + triples
        for label, rx in (spec["patterns"] if spec else []) + COMMON_PATTERNS:
            for m in rx.finditer(seen):
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
        "tur": "tr", "pol": "pl", "ind": "id", "tha": "th", "swe": "sv", "dan": "da", "nob": "no",
        "fin": "fi", "bul": "bg", "bel": "be", "srp": "sr", "mkd": "mk"}


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
    if main in ("LATIN", "CYRILLIC") and (not want or main in want):
        guess, ls, ntok = latin_guess(text, CYRILLIC_STOPWORDS if main == "CYRILLIC" else None)
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


TOKEN = re.compile(rf"{WORD.pattern}|[{CHAR_UNIT}]")


def tokens(text):
    return TOKEN.findall(prose_only(text or ""))


def words_changed(before, after):
    """How much of the original's wording a rewrite changed: (percent, original tokens, added).
    A token is a word, or one character in scripts written without spaces. Matching is
    difflib's longest-matching-blocks comparison, so moved or reworded stretches count as
    changed and untouched ones as kept. Capitals are ignored: "lunch" to "Lunch" is not a new word."""
    a, b = [t.lower() for t in tokens(before)], [t.lower() for t in tokens(after)]
    if not a:
        return None
    kept = sum(blk.size for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(100 * (len(a) - kept) / len(a)), len(a), len(b) - kept


def changed_line(before, raw):
    got = words_changed(before, raw)
    if not got:
        return "wording changed: not measured (the original has no words)"
    pct, total, added = got
    return f"wording changed: {pct}% of the original's {total} words changed or cut, {added} added"


NO_SPACE_SCRIPTS = {"HAN", "HIRAGANA", "KATAKANA", "THAI", "LAO", "TIBETAN", "KHMER", "MYANMAR"}


def _edge(ch):
    return ch.isalnum() and script_of(ch) not in NO_SPACE_SCRIPTS


def keep_count(item, text):
    """How many times item stands in text as itself: an item that starts or ends with a letter or
    digit must not run on into another letter or digit of a spaced script ("Net 30" is not in
    "Net 300"). Characters of scripts written without spaces always count as a boundary."""
    n = 0
    for m in re.finditer(re.escape(item), text):
        a, b = m.start(), m.end()
        if _edge(item[0]) and a > 0 and _edge(text[a - 1]):
            continue
        if _edge(item[-1]) and b < len(text) and _edge(text[b]):
            continue
        n += 1
    return n


def keep_variant(item, text):
    """The text's spelling of a protected item written differently: other capitals, spaces or
    hyphens added or dropped. None when there is no such spelling."""
    chars = [c for c in item if not c.isspace() and c not in "-_"]
    if len(chars) < 3:
        return None
    rx = re.compile(r"[\s\-_]?".join(re.escape(c) for c in chars), re.I)
    for m in rx.finditer(norm(text)):
        if m.group(0) != item:
            return m.group(0)
    return None


def clean_keep(items):
    out = []
    for it in items or []:
        it = norm(str(it)).strip()
        it = re.sub(r"^[-*•]\s+", "", it).strip().strip('"').strip()
        if it and not it.startswith("#") and it not in out:
            out.append(it)
    return out


def keep_path():
    return os.path.join(geodequill_home(), "keep.md")


def saved_keep():
    return clean_keep((read_text(keep_path()) or "").splitlines())


def change_keep(add=(), remove=()):
    """Add and remove saved protected words; returns the saved list."""
    gone = set(clean_keep(remove))
    items = [i for i in saved_keep() if i not in gone]
    items += [i for i in clean_keep(add) if i not in items]
    os.makedirs(geodequill_home(), exist_ok=True)
    with open(keep_path(), "w", encoding="utf-8") as f:
        f.write("# Protected words: GeodeQuill keeps these exactly as written\n\n"
                + "".join(f"- {i}\n" for i in items))
    return items


def keep_report(raw, given=(), saved=(), before=None):
    """Lines for the protected-words part of a report, and how many are missing or altered.
    Items the user named for this text are always judged. Saved items are judged only against
    an original (before), and only when the original holds them. An item is missing when it no
    longer appears at all, and altered when it also appears spelled differently; fewer mentions
    than the original is reported but not flagged, because a rewrite may say "it" the second time."""
    text, old = norm(raw), norm(before) if before is not None else None
    out, bad = [], 0
    given = clean_keep(given)
    for it in given + [x for x in clean_keep(saved) if x not in given]:
        now = keep_count(it, text)
        was = keep_count(it, old) if old is not None else None
        if it not in given and not was:
            continue
        if was is None:
            ok, counts = now > 0, ""
        elif was == 0:
            out.append(f'"{it}": not in the original' + (f"; {now} now" if now else ""))
            continue
        else:
            ok, counts = now > 0, f" ({was} in the original, {now} now)"
        alt = keep_variant(it, raw)
        if ok and not alt:
            out.append(f'"{it}": kept' + counts)
            continue
        bad += 1
        if ok:
            out.append(f'"{it}": ALTERED' + counts + f'; also written as "{alt}"')
        else:
            out.append(f'"{it}": MISSING' + counts + (f'; written as "{alt}" instead' if alt else ""))
    return out, bad


def scan_report(raw, ptxt=None, profile=None, register="written", tone=None, lang=None, before=None,
                keep=(), saved=()):
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
        out.append(changed_line(before, raw))
    out.append("")
    kept_lines, missing = keep_report(raw, keep, saved, before)
    if kept_lines:
        out += ["== Protected words =="] + kept_lines + [""]
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
               + (f" {missing} protected word{'s' if missing != 1 else ''} missing or altered." if missing else "")
               + ("" if info["lists"] else " Phrases and stock words were not checked for this language.")
               + (" English was assumed, not identified: if the text is not English, its phrases and stock "
                  "words were not checked." if info["lists"] and "assumed" in info["how"] else ""))
    return "\n".join(out)


def cmd_scan(path, profile, register="written", tone=None, lang=None, before=None, keep=()):
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
    report = scan_report(raw, ptxt, profile, register, tone, lang, old, keep, saved_keep())
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


# Learning from the user's own edited text.
# A profile keeps ranges, not its samples, so new text is folded in with Welford's running mean
# and variance (Welford 1962; the update form in Chan, Golub and LeVeque 1979). Each range is
# first turned back into a centre and a spread the way it was built: suggest_targets pads the
# 10th-90th percentile of the windows (10 or more) or their lowest-to-highest span (under 10),
# so the padding is taken off and the span divided by the normal-distribution width of that
# kind of span: 2.563 standard deviations for 10th-90th, the d2 constant of a sample of n
# for lowest-to-highest (the control-chart table, e.g. Montgomery, Introduction to Statistical
# Quality Control). After the new windows are added the range is rebuilt the same way and
# padded with suggest_targets' own rule. Text near the voice's centre leaves a range about
# where it was; text outside it moves the range toward it, by less the more samples the voice
# already holds.
D2 = {2: 1.128, 3: 1.693, 4: 2.059, 5: 2.326, 6: 2.534, 7: 2.704, 8: 2.847, 9: 2.970}
Z90 = 2.563
LEARN_MIN_CHANGED = 10     # percent of the draft's words the user must have changed
LEARN_ASSUMED_WINDOWS = 3  # when the profile does not say how many samples built it


def span_width(n):
    return Z90 if n >= 10 else D2.get(max(n, 2), D2[2])


def unpad(lo, hi, n):
    """The unpadded range suggest_targets started from, before its padding and floors."""
    pad = 0.0
    for _ in range(30):
        w, top = max(hi - lo - 2 * pad, 0.0), hi - pad
        new = max(w * 0.1, abs(top) * 0.05, 0.05)
        if n < 3:
            new = max(new, abs(top) * 0.25)
        if abs(new - pad) < 1e-9:
            break
        pad = new
    return lo + pad, hi - pad


def learn_range(key, lo, hi, n, values):
    rlo, rhi = unpad(lo, hi, n)
    if rhi < rlo:
        rlo = rhi = (lo + hi) / 2
    mean, sd = (rlo + rhi) / 2, (rhi - rlo) / span_width(n)
    count, m2 = n, sd * sd * max(n - 1, 1)
    for x in values:
        count += 1
        d = x - mean
        mean += d / count
        m2 += d * (x - mean)
    half = math.sqrt(m2 / (count - 1)) * span_width(count) / 2
    nlo, nhi = mean - half, mean + half
    pad = max((nhi - nlo) * 0.1, abs(nhi) * 0.05, 0.05)
    if count < 3:
        pad = max(pad, abs(nhi) * 0.25)
    new_lo, new_hi = round(max(nlo - pad, 0), 2), round(max(nhi + pad, HI_FLOOR.get(key, 0)), 2)
    # A range stretches only toward text that fell outside it; inside text can only tighten it.
    if min(values) >= lo:
        new_lo = max(new_lo, lo)
    if max(values) <= hi:
        new_hi = min(new_hi, hi)
    if new_hi < new_lo:
        new_lo, new_hi = lo, hi
    return [new_lo, new_hi], count


def targets_json_block(ptxt):
    for m in re.finditer(r"```json\s*(\{.*?\})\s*```", ptxt, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(data, dict) and any(isinstance(data.get(k), dict) for k in ("targets", "targets_spoken")):
            return m, data
    return None, None


def _num(v):
    return str(int(v)) if float(v).is_integer() else repr(round(float(v), 2))


def format_targets(data):
    parts = []
    for k, v in data.items():
        if isinstance(v, dict):
            rows = ",\n".join(f"    {json.dumps(a)}: " + (f"[{_num(r[0])}, {_num(r[1])}]" if isinstance(r, list)
                                                         and len(r) == 2 else json.dumps(r)) for a, r in v.items())
            parts.append(f"  {json.dumps(k)}: {{\n{rows}\n  }}")
        else:
            parts.append(f"  {json.dumps(k)}: {json.dumps(v)}")
    return "{\n" + ",\n".join(parts) + "\n}"


def profile_windows(ptxt, data, key, lang, unit):
    known = (data.get("windows") or {}).get(key) if isinstance(data.get("windows"), dict) else None
    if isinstance(known, int) and known >= 1:
        return known, None
    reg = "spoken" if key == "targets_spoken" else "written"
    line = re.search(r"^samples:(.*)$", ptxt, re.M | re.I)
    line = line.group(1) if line else ""
    part = re.search(rf"\b{reg}\b(.*?)(?:;|$)", line, re.I)
    part = part.group(1) if part else (line if reg == "written" and "spoken" not in line.lower() else "")
    size = window_for(lang, unit)
    win = re.search(r"([\d,]+)\s+windows", part)
    if win:
        return max(int(win.group(1).replace(",", "")), 1), None
    pc = re.search(r"(\d+)\s+(?:pieces?|books?|files?|samples?)", part) or re.match(r"\s*(\d+)\b(?!,\d)", part)
    amount = re.search(r"about\s+([\d,]+)\s+(?:words|characters)", part)
    if pc or amount:
        got = max(int(pc.group(1)) if pc else 0,
                  int(amount.group(1).replace(",", "")) // size if amount else 0, 1)
        return got, None
    return LEARN_ASSUMED_WINDOWS, (f"the voice does not say how many samples built it; "
                                   f"{LEARN_ASSUMED_WINDOWS} were assumed")


def add_source_line(ptxt, line):
    m = re.search(r"^## Sources[ \t]*\n((?:[ \t]*-.*\n?|[ \t]*\n)*)", ptxt, re.M)
    if m:
        body = m.group(1).rstrip("\n \t")
        start = m.start(1)
        return ptxt[:start] + (body + "\n" if body else "") + line + "\n\n" + ptxt[start + len(m.group(1)):].lstrip("\n")
    t = re.search(r"^## Targets", ptxt, re.M)
    if t:
        return ptxt[:t.start()] + "## Sources\n" + line + "\n\n" + ptxt[t.start():]
    return ptxt.rstrip("\n") + "\n\n## Sources\n" + line + "\n"


def learn_result(ptxt, texts, register="written", lang=None, draft=None, today=None):
    """Fold the user's own edited text into a voice's ranges for one register. Returns
    {"ok": bool, "lines": [...], "profile": new profile text or None}."""
    key = "targets_spoken" if register == "spoken" else "targets"
    fail = lambda *lines: {"ok": False, "lines": list(lines) + ["Nothing was learned; the voice is unchanged."],
                           "profile": None}
    block, data = targets_json_block(ptxt or "")
    targets = parse_targets(ptxt or "", key)
    if not block or not targets:
        return fail(f"This voice has no {register} ranges to learn into. Set up its {register} habits first.")
    texts = [t for t in texts if has_words(t)]
    if not texts:
        return fail("The edited text has no words.")
    joined = "\n\n".join(texts)
    info = resolve_language(joined, lang)
    plang = profile_language(ptxt)
    if not same_language(plang, info):
        return fail(f"The edited text is {language_label(info['tag'])} and the voice was measured in "
                    f"{language_label(plang)}. A voice learns only from text in its own language.")
    if draft is not None:
        got = words_changed(draft, joined)
        if got and got[0] < LEARN_MIN_CHANGED:
            return fail(f"Only {got[0]}% of the draft's words were changed, so this is still mostly the AI's "
                        f"writing. A voice learns only from the user's own words; at least "
                        f"{LEARN_MIN_CHANGED}% must differ.")
    code, unit = info["code"], info["unit"]
    size = window_for(code, unit)
    floor = size * 3 // 10
    ms = [m for m in (metrics(p, code, unit) for t in texts for p in pieces(t, size)) if m["words"] >= floor]
    if not ms:
        got = wc(prose_only(joined))
        return fail(f"The edited text is {got} {unit} long; at least {floor} are needed to measure it. "
                    f"Several edits can be learned together once they add up to that.")
    n, assumed = profile_windows(ptxt, data, key, code, unit)
    new_targets, lines, kept, skipped = {}, [], [], []
    for k, (lo, hi) in targets.items():
        need = SPREAD_NEEDS.get(k)
        vals = [m[k] for m in ms if k in m and not (need and m.get(need[0], 0) < need[1])]
        if not vals:
            new_targets[k] = [lo, hi]
            skipped.append(k)
            continue
        rng, _count = learn_range(k, lo, hi, n, vals)
        new_targets[k] = rng
        if rng == [lo, hi] or (abs(rng[0] - lo) < 0.005 and abs(rng[1] - hi) < 0.005):
            new_targets[k] = [lo, hi]
            kept.append(k)
        else:
            lines.append(f"{k}: {_num(lo)} to {_num(hi)} -> {_num(rng[0])} to {_num(rng[1])}")
    count = n + len(ms)
    words = sum(m["words"] for m in ms)
    head = [f"Learned from {words} {unit} of the user's own edited text ({len(ms)} "
            f"sample{'s' if len(ms) != 1 else ''}); the voice's {register} habits now rest on "
            f"{count} samples."]
    if assumed:
        head.append(f"(Note: {assumed}.)")
    out = head + (["Ranges that moved:"] + lines if lines else ["No range moved: the edit sits inside the voice's habits."])
    if kept and lines:
        out.append("Unchanged: " + ", ".join(kept) + ".")
    if skipped:
        out.append("Not learned (the edit is too short for these measures): " + ", ".join(skipped) + ".")
    data = dict(data)
    data[key] = new_targets
    win = dict(data.get("windows") or {}) if isinstance(data.get("windows"), dict) else {}
    win[key] = count
    data["windows"] = win
    newp = ptxt[:block.start(1)] + format_targets(data) + ptxt[block.end(1):]
    day = today or __import__("datetime").date.today().isoformat()
    newp = add_source_line(newp, f"- the user's own edited text, learned {day}, about {words} {unit} | "
                                 f"{register} | own prose")
    return {"ok": True, "lines": out, "profile": newp}


def is_built_in(path):
    return os.path.dirname(os.path.abspath(path)) == BUILT_IN_VOICES


def cmd_learn(args, lang=None):
    def take(flag):
        nonlocal args
        if flag not in args:
            return None
        i = args.index(flag)
        val = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
        return val
    profile, draft_path = take("--profile"), take("--draft")
    register = take("--register") or "written"
    write = "--write" in args
    files = [a for a in args if a != "--write"]
    if not profile or not files or register not in ("written", "spoken") or any(f.startswith("--") for f in files):
        print("Usage: learn EDITED [EDITED ...] --profile P.md|NAME [--register written|spoken] "
              "[--draft DRAFT] [--lang CODE] [--write]")
        return 2
    path = profile if os.path.isfile(profile) else find_voice(profile)
    if not path:
        print(f"No voice found at or named {profile}.")
        return 1
    if is_built_in(path):
        print("Built-in voices do not learn. Save a copy as a voice of your own and learn into that.")
        return 3
    ptxt = read_text(path)
    texts, err = load_all(files)
    if ptxt is None or err:
        print(err or f"Cannot read {path}.")
        return 1
    draft = None
    if draft_path:
        draft = read_text(draft_path)
        if draft is None:
            print(f"Cannot read {draft_path}.")
            return 1
    res = learn_result(ptxt, texts, register, lang, draft)
    if res["ok"] and write:
        tmp = path + ".learning"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(res["profile"])
        os.replace(tmp, path)
        print(f"Saved {path}")
    elif res["ok"]:
        print("Not saved yet: add --write to save these changes.")
    print("\n".join(res["lines"]))
    return 0 if res["ok"] else 3


def cmd_keep(args):
    def grab(flag):
        out, rest, i = [], [], 0
        while i < len(args):
            if args[i] == flag and i + 1 < len(args):
                out.append(args[i + 1])
                i += 2
            else:
                rest.append(args[i])
                i += 1
        return out, rest
    adds, args = grab("--add")
    removes, args = grab("--remove")
    if args:
        print("Usage: keep [--add WORDS ...] [--remove WORDS ...]")
        return 2
    items = change_keep(adds, removes) if adds or removes else saved_keep()
    if not items:
        print(f"No protected words saved. They are kept in {keep_path()}.")
        return 0
    print(f"Protected words ({keep_path()}):")
    for i, it in enumerate(items, 1):
        print(f"{i}. {it}")
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
    if len(argv) >= 2 and argv[1] == "keep":
        return cmd_keep(argv[2:])
    if len(argv) < 3 or argv[1] not in ("stats", "scan", "habits", "learn"):
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
    if argv[1] == "learn":
        return cmd_learn(args, lang)
    keep = []
    while "--keep" in args:
        i = args.index("--keep")
        if i + 1 >= len(args) or not args[i + 1].strip():
            print("--keep needs the word or phrase to keep")
            return 2
        keep.append(args[i + 1])
        args = args[:i] + args[i + 2:]
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
    return cmd_scan(args[0], profile, register, tone, lang, before, keep)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
