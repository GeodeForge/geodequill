#!/usr/bin/env python3
"""Behaviour tests for GeodeQuill. Run: python3 -I test_voice_check.py

The plugin's script and connector carry no commentary; the reasons for each behaviour live here.
Fixtures sit in ./fixtures. Edge-case files (bad bytes, empty, Windows line endings) and voice
folders are written at run time into temporary folders, so nothing on the machine is touched.

Two groups skip themselves, and say so, when their tools are absent:
  - the open-format check needs the reference validator (pip install skills-ref);
  - the connector check needs the MCP package (pip install mcp).
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "plugin", "skills", "geodequill")
SCRIPT = os.path.join(SKILL, "scripts", "voice_check.py")
SERVER = os.path.join(HERE, "..", "mcp", "geodequill_mcp.py")
FIX = os.path.join(HERE, "fixtures")
REPO = os.path.join(HERE, "..")
SUMMARY = re.compile(r"Summary: (\d+) strong tells, (\d+) stock words and (\d+) formatting marks .*?, (\d+) habits off\.")


def run(*args, env=None, cwd=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, "-I", SCRIPT, *args], capture_output=True, text=True, env=e, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def fx(name):
    return os.path.join(FIX, name)


def summary(out):
    m = SUMMARY.search(out)
    if not m:
        raise AssertionError("no summary line in:\n" + out)
    return tuple(int(x) for x in m.groups())


def scratch(content, mode="w", suffix=".txt"):
    f = tempfile.NamedTemporaryFile(mode, suffix=suffix, delete=False, encoding=None if "b" in mode else "utf-8")
    f.write(content)
    f.close()
    return f.name


class Detection(unittest.TestCase):
    def test_machine_style_sample_is_caught(self):
        code, out = run("scan", fx("machine.txt"))
        strong, _weak, _fmt, _off = summary(out)
        self.assertEqual(code, 0)
        self.assertGreaterEqual(strong, 8)

    def test_human_sample_is_clean(self):
        _code, out = run("scan", fx("human.txt"))
        self.assertEqual(summary(out), (0, 0, 0, 0))

    def test_new_twain_style_pieces_pass_their_profile(self):
        for piece in ("twain-piece-1.txt", "twain-piece-2.txt"):
            _code, out = run("scan", fx(piece), "--profile", fx("twain-corpus-profile.md"))
            strong, weak, _fmt, off = summary(out)
            self.assertEqual((strong, weak, off), (0, 0, 0), piece)

    def test_phrase_and_its_stock_word_are_reported_once(self):
        _code, out = run("scan", fx("phrases.txt"))
        self.assertIn('stock phrase: "a testament to"', out)
        self.assertNotIn('stock word: "testament"', out)

    def test_patterns_that_used_to_slip_through(self):
        _code, out = run("scan", fx("phrases.txt"))
        for found in ("isn't merely a tool — it's", "Studies have shown", "can potentially", "The bottom line?"):
            self.assertIn(found, out)

    def test_ordinary_phrases_only_count_when_they_pile_up(self):
        _code, out = run("scan", fx("phrases.txt"))
        self.assertIn("mild connectors", out)
        self.assertNotIn('stock phrase: "in conclusion"', out)

    def test_formatting_marks_are_weak_not_strong(self):
        path = scratch("## Installation And Usage Guide\n\n- **Source:** here\n\nDone ✅ today.\n")
        _code, out = run("scan", path)
        strong, _weak, fmt, _off = summary(out)
        self.assertEqual((strong, fmt), (0, 3))

    def test_comment_lines_inside_code_blocks_are_not_headings(self):
        path = scratch("Intro text here.\n\n```python\n# A Simple Example Here\nx = 1\n```\n")
        _code, out = run("scan", path)
        self.assertNotIn("Title Case heading", out)

    def test_symbols_are_not_emoji(self):
        path = scratch("Checked ✓ and starred ★ and boxed ☐.\n")
        _code, out = run("scan", path)
        self.assertNotIn("emoji", out)


class Robustness(unittest.TestCase):
    def test_missing_profile_falls_back_with_a_message(self):
        code, out = run("scan", fx("human.txt"), "--profile", os.path.join(FIX, "nope.md"))
        self.assertEqual(code, 0)
        self.assertIn("profile not found", out)

    def test_bad_target_shapes_are_skipped(self):
        code, out = run("scan", fx("phrases.txt"), "--profile", fx("profile-badshape.md"))
        self.assertEqual(code, 0)
        self.assertIn("paragraph_cv", out)
        self.assertNotIn("avg_sentence_words: 4.6 (profile", out)

    def test_targets_as_a_list_falls_back(self):
        code, out = run("scan", fx("phrases.txt"), "--profile", fx("profile-list.md"))
        self.assertEqual(code, 0)
        self.assertIn("no readable targets", out)

    def test_second_json_block_is_found(self):
        _code, out = run("scan", fx("phrases.txt"), "--profile", fx("profile-two-blocks.md"))
        self.assertIn("== Versus the voice profile (written) ==", out)

    def test_non_utf8_empty_and_windows_files_do_not_crash(self):
        paths = [scratch(b"Caf\xe9 said \x93hi\x94. It was fine.\n", "wb"),
                 scratch(""),
                 scratch(b"line one.\r\n\r\nline two is here.\r\n", "wb")]
        for p in paths:
            code, out = run("scan", p)
            # An empty file is refused on purpose since 0.6.0 (no words), not a crash.
            self.assertEqual(code, 1 if p == paths[1] else 0, out)
            self.assertNotIn("Traceback", out)

    def test_missing_input_and_bad_usage_exit_codes(self):
        self.assertEqual(run("scan", os.path.join(FIX, "nope.txt"))[0], 1)
        self.assertEqual(run("stats", "--targets")[0], 1)
        self.assertEqual(run("scan", fx("human.txt"), "--register", "shouting")[0], 2)


class ShortPieces(unittest.TestCase):
    """A spread measure (how much paragraph or sentence lengths vary) means nothing for one paragraph or
    one sentence. Found in the first live run, 2026-11-01: every one-paragraph speech was flagged for
    "paragraph_cv", whatever was written."""

    def test_one_paragraph_is_not_judged_on_paragraph_spread(self):
        profile = scratch('```json\n{"targets": {"paragraph_cv": [0.2, 0.9], "sentence_cv": [0.2, 1.0]}}\n```\n', suffix=".md")
        piece = scratch("One sentence stands here. Another follows it, a little longer than the first one was. A third ends it.\n")
        _code, out = run("scan", piece, "--profile", profile)
        self.assertIn("paragraph_cv: 0.0 (profile 0.2 to 0.9) not judged: needs 3 or more paragraphs", out)
        self.assertIn("0 habits off", out)

    def test_three_paragraphs_are_judged(self):
        profile = scratch('```json\n{"targets": {"paragraph_cv": [0.5, 0.9]}}\n```\n', suffix=".md")
        piece = scratch("Two words.\n\nTwo more.\n\nAnd two.\n")
        _code, out = run("scan", piece, "--profile", profile)
        self.assertIn("paragraph_cv: 0.0 (profile 0.5 to 0.9) OUTSIDE", out)


class Registers(unittest.TestCase):
    def test_spoken_comparison_is_labelled_spoken(self):
        _code, out = run("scan", fx("spoken.txt"), "--profile", fx("profile-registers.md"), "--register", "spoken")
        self.assertIn("== Versus the voice profile (spoken) ==", out)

    def test_spoken_text_against_written_targets_is_flagged(self):
        _code, out = run("scan", fx("spoken.txt"), "--profile", fx("profile-registers.md"))
        self.assertIn("(written)", out)
        self.assertEqual(summary(out)[3], 3)

    def test_spoken_asked_without_spoken_targets_says_so(self):
        _code, out = run("scan", fx("spoken.txt"), "--profile", fx("twain-corpus-profile.md"), "--register", "spoken")
        self.assertIn("no spoken targets", out)

    def test_a_question_is_not_a_filler(self):
        path = scratch("Do you know the way? You know, I think so.\n")
        _code, out = run("stats", path)
        self.assertEqual(json.loads(out)["fillers_per_1000w"], 100.0)


class Measuring(unittest.TestCase):
    def test_sentence_splitter_keeps_dialogue_tags_and_abbreviations(self):
        _code, out = run("stats", fx("dialogue.txt"))
        d = json.loads(out)
        self.assertEqual((d["sentences"], d["words"]), (4, 24))
        self.assertGreater(d["em_dashes_per_1000w"], 0)

    def test_an_unbroken_transcript_is_cut_into_windows(self):
        text = " ".join(open(fx("twain-piece-1.txt"), encoding="utf-8").read().split()) + " "
        path = scratch(text * 5)
        _code, out = run("stats", path, "--targets")
        self.assertGreaterEqual(json.loads(out)["suggested"]["based_on_pieces"], 3)

    def test_one_short_sample_gets_wide_ranges(self):
        _code, out = run("stats", fx("spoken.txt"), "--targets")
        lo, hi = json.loads(out)["suggested"]["targets"]["avg_sentence_words"]
        self.assertGreaterEqual(hi - lo, 0.4 * hi)

    def test_a_mark_absent_from_every_sample_is_still_allowed_once(self):
        _code, out = run("stats", fx("human.txt"), fx("machine.txt"), "--targets")
        t = json.loads(out)["suggested"]["targets"]
        self.assertGreaterEqual(t["em_dashes_per_1000w"][1], 2.0)
        self.assertGreaterEqual(t["contractions_per_100w"][1], 1.0)

    def test_first_person_measures_are_profile_targets(self):
        """Measured on Twain: speeches and books overlap on every other range, but 'I' as a
        sentence opener (median 23% spoken, 5% written) and first-person rate separate them."""
        _code, out = run("stats", fx("spoken.txt"), "--targets")
        d = json.loads(out)
        self.assertEqual(d["i_led_sentence_pct"], 30.0)
        t = d["suggested"]["targets"]
        self.assertIn("first_person_per_100w", t)
        self.assertGreaterEqual(t["i_led_sentence_pct"][1], 10.0)

    def test_habits_on_short_text_lists_no_one_off_words(self):
        _code, out = run("habits", fx("human.txt"))
        d = json.loads(out)
        self.assertTrue(all(v >= 2 * 10000 / d["words"] - 1 for v in d["common_words_per_10k"].values()))


BUILT_IN = ["abraham-lincoln", "charles-dickens", "frederick-douglass", "jane-austen", "jose-marti", "louisa-may-alcott",
            "lu-xun", "mark-twain", "oscar-wilde", "will-rogers"]


class Languages(unittest.TestCase):
    """Any language and script: the product's English is not the user's.

    zh-human.txt is Lu Xun, 从百草园到三味书屋 (1926, public domain); es-human.txt is Galdós,
    Misericordia (1897, public domain, from the CoNSSA corpus). zh-machine.txt and es-machine.txt are
    imitations of machine prose written by the building session, like machine.txt. ja.txt and fr.txt were
    written by the session too and test only that the language is named, never that a writer is human.
    Before this, Chinese text was split into sentences only at .!? and its words were counted by spaces,
    so a whole Chinese paragraph was one "word" and every tell list was English.
    """

    def test_chinese_machine_prose_is_caught_with_chinese_lists(self):
        code, out = run("scan", fx("zh-machine.txt"))
        strong, weak, _fmt, _off = summary(out)
        self.assertEqual(code, 0)
        self.assertIn("Checked as: Chinese", out)
        self.assertIn("counted in characters", out)
        self.assertGreaterEqual(strong, 8)
        for found in ("在当今社会", "希望这对你有帮助", "不仅仅是一种工具，更是", "可能也许"):
            self.assertIn(found, out)

    def test_chinese_human_prose_is_clean_and_measured_in_characters(self):
        _code, out = run("scan", fx("zh-human.txt"))
        self.assertEqual(summary(out)[0], 0)
        m = json.loads(run("stats", fx("zh-human.txt"))[1])
        self.assertEqual((m["language"], m["counted_in"]), ("zh", "characters"))
        self.assertGreater(m["words"], 500)
        self.assertGreaterEqual(m["sentences"], 15)
        self.assertNotIn("contractions_per_100w", m)

    def test_chinese_sentences_end_at_chinese_marks_without_spaces(self):
        # The common Chinese splitting rule ends a sentence after 。！？ and any closing quote, so “好！” and
        # 他说。 count as two, as Chinese segmenters do; a blank line also ends one.
        m = json.loads(run("stats", scratch("我来了。你呢？“好！”他说。今天下雨\n\n明天晴。", suffix=".txt"))[1])
        self.assertEqual(m["sentences"], 6)

    def test_spanish_machine_prose_is_caught_and_galdos_is_not(self):
        _code, out = run("scan", fx("es-machine.txt"))
        self.assertIn("Checked as: Spanish", out)
        self.assertGreaterEqual(summary(out)[0], 8)
        self.assertIn("no se trata solo de", out)
        _code, out = run("scan", fx("es-human.txt"))
        self.assertIn("Checked as: Spanish", out)
        self.assertEqual(summary(out)[0], 0)

    def test_a_language_without_lists_says_so_instead_of_a_clean_result(self):
        # Japanese was the second example here until it got its own lists (0.6.5); Ukrainian
        # (a UDHR preamble, see udhr-neighbours.json) took its place.
        with open(fx("udhr-neighbours.json"), encoding="utf-8") as f:
            uk = scratch(json.load(f)["uk"], suffix=".txt")
        for path, lang in ((fx("fr.txt"), "French"), (uk, "Ukrainian")):
            _code, out = run("scan", path)
            self.assertIn(f"Checked as: {lang}", out)
            self.assertIn("NOT checked", out)
            self.assertIn("Phrases and stock words were not checked for this language.", out)
            self.assertNotIn("\nnone found\n", out)

    def test_six_more_languages_catch_machine_prose_and_pass_the_classics(self):
        # <lang>-human.txt: public-domain writing, from the measured populations' sources:
        # Akutagawa, 蜘蛛の糸 (1918, Aozora Bunko); Hyeon Jin-geon, 운수 좋은 날 (1924, Wikisource);
        # Ömer Seyfettin, Kaşağı (1919, Wikisource); Kafka, Die Verwandlung (1915, Project Gutenberg
        # 22367); Chekhov, Хамелеон (1884, Wikisource); Juhani Aho, Rautatie (1884, Project Gutenberg
        # 10481). <lang>-machine.txt: imitations of machine prose written by the building session.
        for lang, name in (("ja", "Japanese"), ("ko", "Korean"), ("tr", "Turkish"), ("de", "German"),
                           ("ru", "Russian"), ("fi", "Finnish")):
            _code, out = run("scan", fx(f"{lang}-machine.txt"))
            self.assertIn(f"Checked as: {name}", out, lang)
            self.assertIn(f"Machine-writing habit lists: {name}.", out, lang)
            self.assertGreaterEqual(summary(out)[0], 8, lang)
            _code, out = run("scan", fx(f"{lang}-human.txt"))
            self.assertIn(f"Checked as: {name}", out, lang)
            self.assertEqual(summary(out)[0], 0, lang)

    def test_neighbour_languages_never_get_these_lists(self):
        # UDHR preambles (OHCHR translations, udhr npm package 6.0.0). Ukrainian, Bulgarian,
        # Belarusian, Serbian, Macedonian and Kazakh share the Cyrillic script with Russian; Estonian
        # shares common words with Finnish; Azerbaijani shares letters and words with Turkish.
        with open(fx("udhr-neighbours.json"), encoding="utf-8") as f:
            texts = json.load(f)
        for code in ("uk", "bg", "be", "sr", "mk", "kk", "et", "az"):
            _code, out = run("scan", scratch(texts[code], suffix=".txt"))
            self.assertIn("Phrases and stock words were not checked for this language.", out, code)
        for code, name in (("ru", "Russian"), ("fi", "Finnish"), ("tr", "Turkish")):
            _code, out = run("scan", scratch(texts[code], suffix=".txt"))
            self.assertIn(f"Machine-writing habit lists: {name}.", out, code)

    def test_turkish_capitals_and_russian_yo_are_read_as_typed(self):
        # Turkish İ and I lower-case to i and ı; Russian ё is read as е. Before the fold, "İşte"
        # style capitals missed their phrase and "разберёмся" missed "разберемся".
        tr = "UZAKTAN ÇALIŞMA KRİTİK BİR ROL OYNAMAKTADIR. " * 3 + "Bu konuda pek çok görüş var ve tartışma sürüyor."
        out = run("scan", scratch(tr, suffix=".txt"), "--lang", "tr")[1]
        self.assertIn('stock phrase: "KRİTİK BİR ROL OYNAMAKTADIR"', out)
        ru = "Давайте разберёмся, как это устроено. Мы долго спорили, но так ничего и не решили сегодня."
        out = run("scan", scratch(ru, suffix=".txt"), "--lang", "ru")[1]
        self.assertIn('stock phrase: "Давайте разберёмся"', out)

    def test_russian_with_a_quoted_ukrainian_name_is_still_russian(self):
        ru = ("Вчера я долго гулял по городу. Было холодно, но солнечно. Я зашёл в маленькое кафе "
              "«Їжак», которое держит мой старый знакомый. Там пахло кофе и свежим хлебом.\n\n") * 2
        self.assertIn("Checked as: Russian", run("scan", scratch(ru, suffix=".txt"))[1])

    def test_words_with_accents_and_vowel_signs_are_one_word_each(self):
        m = json.loads(run("stats", scratch("Việt Nam là một quốc gia.\n\nहिन्दी भाषा सुंदर है।", suffix=".txt"))[1])
        self.assertEqual(m["words"], 10)
        self.assertEqual(m["sentences"], 2)

    def test_a_mixed_piece_reports_what_it_checked(self):
        text = "我们用 Docker 部署了 Python 服务，然后在 Kubernetes 上做了压力测试。结果比预想的好。" * 3
        _code, out = run("scan", scratch(text, suffix=".txt"))
        self.assertIn("Checked as: Chinese", out)
        self.assertIn("Other scripts in the text, not checked against any list: Latin", out)

    def test_a_few_chinese_characters_do_not_claim_to_rule_out_japanese(self):
        _code, out = run("scan", scratch("関数", suffix=".txt"))
        self.assertIn("too short to rule out Japanese", out)

    def test_lang_sets_the_language_and_a_bad_code_is_refused(self):
        _code, out = run("scan", fx("human.txt"), "--lang", "es")
        self.assertIn("Checked as: Spanish (chosen with --lang)", out)
        code, out = run("scan", fx("human.txt"), "--lang", "not a code")
        self.assertEqual(code, 2)

    def test_an_english_voice_judges_only_language_free_measures_on_chinese(self):
        _code, out = run("scan", fx("zh-human.txt"), "--profile", fx("twain-corpus-profile.md"))
        self.assertIn("measured in English and this text is Chinese", out)
        self.assertIn("avg_sentence_words", out)
        self.assertRegex(out, r"avg_sentence_words: [\d.]+ \(profile [\d.]+ to [\d.]+\) not judged: different language")
        self.assertRegex(out, r"sentence_cv: [\d.]+ \(profile [\d.]+ to [\d.]+\) (ok|OUTSIDE)")

    def test_a_chinese_voice_can_be_measured_and_listed(self):
        m = json.loads(run("stats", fx("zh-human.txt"), "--targets")[1])
        t = m["suggested"]["targets"]
        self.assertIn("first_person_per_100w", t)
        self.assertNotIn("contractions_per_100w", t)
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, "voices"))
            with open(os.path.join(home, "voices", "lu.md"), "w", encoding="utf-8") as f:
                f.write("voice: Lu\nlanguage: zh\n\n## In one line\nPlain.\n\n```json\n"
                        + json.dumps({"targets": t}) + "\n```\n")
            _code, out = run("voices", env={"GEODEQUILL_HOME": home})
            self.assertIn("(written, in Chinese)", out)
            _code, out = run("scan", fx("zh-human.txt"), "--profile", os.path.join(home, "voices", "lu.md"))
            self.assertNotIn("different language", out)
            self.assertEqual(summary(out)[3], 0)

    def test_unlisted_latin_languages_never_get_english_or_spanish_lists(self):
        # Preamble paragraphs of eight translations of the Universal Declaration of Human Rights:
        # OHCHR translations, via the Unicode "UDHR in Unicode" project and the udhr npm package. In 0.5.0 before the review, Turkish, Swedish and others were "English is assumed"
        # and given a clean English result; Polish was confidently named English.
        with open(fx("udhr-preambles.json"), encoding="utf-8") as f:
            texts = json.load(f)
        for code, text in texts.items():
            _code, out = run("scan", scratch(text, suffix=".txt"))
            self.assertNotIn("Machine-writing habit lists: English", out, code)
            self.assertNotIn("Machine-writing habit lists: Spanish", out, code)
            if code == "tr":   # Turkish has its own lists since 0.6.5
                self.assertIn("Machine-writing habit lists: Turkish.", out)
                continue
            self.assertIn("Phrases and stock words were not checked for this language.", out, code)

    def test_traditional_characters_get_the_chinese_lists(self):
        # zh-machine-trad.txt is zh-machine.txt converted with OpenCC s2tw. Before the fix: 0 tells.
        simp = summary(run("scan", fx("zh-machine.txt"))[1])[0]
        trad = summary(run("scan", fx("zh-machine-trad.txt"))[1])[0]
        self.assertEqual(trad, simp)
        self.assertIn("發揮著至關重要的作用", run("scan", fx("zh-machine-trad.txt"))[1])

    def test_a_contrast_pile_up_counts_once_and_a_single_contrast_does_not(self):
        two = "这不是速度问题，而是方向问题。我们要的不是更多功能，而是更少的打扰。"
        one = "错误发生在保存阶段，不是上传阶段，而是在写入磁盘的时候。后来我们换了一块硬盘，问题就没再出现过。"
        self.assertIn("contrast pile-up", run("scan", scratch(two, suffix=".txt"))[1])
        self.assertNotIn("contrast pile-up", run("scan", scratch(one, suffix=".txt"))[1])

    def test_chinese_typed_with_half_width_marks_still_splits(self):
        m = json.loads(run("stats", scratch("我来了.你呢?好!", suffix=".txt"))[1])
        self.assertEqual(m["sentences"], 3)

    def test_language_names_and_codes_are_understood(self):
        _code, out = run("scan", fx("zh-human.txt"), "--lang", "Chinese")
        self.assertIn("Checked as: Chinese (chosen with --lang)", out)
        for line in ('language: "zh"', "Language: zh", "language: zho", "language: Chinese"):
            prof = scratch(line + "\n\n```json\n{\"targets\": {\"sentence_cv\": [0, 5]}}\n```\n", suffix=".md")
            _code, out = run("scan", fx("zh-human.txt"), "--profile", prof)
            self.assertNotIn("different language", out, line)

    def test_a_voice_in_an_unidentified_script_is_not_read_back_as_english(self):
        # Georgian: a script the checker names no language for. Russian was the example here until
        # Cyrillic text began to be told apart by its common words.
        ka = ("გუშინ დიდხანს ვსეირნობდი ქალაქში. ცივოდა, მაგრამ მზიანი დღე იყო. პატარა კაფეში შევედი. "
              "იქ ყავისა და ახალი პურის სუნი იდგა. ოფიციანტმა გაიღიმა და მენიუ მომიტანა.\n\n") * 3
        m = json.loads(run("stats", scratch(ka, suffix=".txt"), "--targets")[1])
        self.assertEqual(m["language"], "und-georgian")
        prof = scratch("language: " + m["language"] + "\n\n```json\n" +
                       json.dumps({"targets": m["suggested"]["targets"]}) + "\n```\n", suffix=".md")
        _code, out = run("scan", scratch(ka, suffix=".txt"), "--profile", prof)
        self.assertNotIn("different language", out)

    def test_a_voice_and_a_draft_in_the_same_unnamed_language_are_judged_as_one(self):
        # The agent always names the draft's language with --lang (SKILL.md). A voice built without
        # --lang records "und-cyrillic"; before the fix, "und-cyrillic" voice against a "--lang ru"
        # draft (and the reverse) counted as two languages, so 5 of 8 measures went unjudged.
        ru = ("Вчера я долго гулял по городу. Было холодно, но солнечно. Я зашёл в маленькое кафе. "
              "Там пахло кофе и свежим хлебом. Официантка улыбнулась и принесла меню.\n\n") * 3
        draft = scratch(ru, suffix=".txt")
        t = json.loads(run("stats", draft, "--targets")[1])["suggested"]["targets"]
        for voice, lang in (("und-cyrillic", ["--lang", "ru"]), ("ru", []), ("Russian", [])):
            prof = scratch(f"language: {voice}\n\n```json\n" + json.dumps({"targets": t}) + "\n```\n", suffix=".md")
            _code, out = run("scan", draft, "--profile", prof, *lang)
            self.assertNotIn("different language", out, voice)
        prof = scratch("language: en\n\n```json\n" + json.dumps({"targets": t}) + "\n```\n", suffix=".md")
        self.assertIn("different language", run("scan", draft, "--profile", prof)[1])
        prof = scratch("language: und-arabic\n\n```json\n" + json.dumps({"targets": t}) + "\n```\n", suffix=".md")
        self.assertIn("different language", run("scan", draft, "--profile", prof)[1])

    def test_short_text_that_is_only_assumed_english_says_its_phrases_may_be_unchecked(self):
        # Under 20 words the language often cannot be told, and English is assumed. Before the fix a
        # short Turkish or Swedish note came back "none found" with nothing to say English lists had
        # been used on it.
        _code, out = run("scan", scratch("Yarın sabah toplantıya geliyorum, görüşürüz.", suffix=".txt"))
        self.assertIn("English was assumed, not identified", out)
        for text in ("Jag kommer till mötet i morgon bitti.", "Hẹn gặp lại bạn vào sáng mai nhé.",
                     "Rytoj ryte ateisiu į susitikimą, iki pasimatymo."):
            line = [l for l in run("scan", scratch(text, suffix=".txt"))[1].splitlines() if l.startswith("Summary:")][0]
            self.assertTrue("English was assumed" in line or "not checked for this language" in line, line)
        _code, out = run("scan", scratch("Jag kommer till mötet i morgon bitti.", suffix=".txt"), "--lang", "en")
        self.assertNotIn("English was assumed", out)

    def test_accents_typed_as_separate_marks_are_read_the_same(self):
        # Some keyboards and PDF copies store "é" as "e" plus a combining accent. Before the fix the
        # Spanish fixture typed that way lost a tell, and decomposed Vietnamese could not be told.
        import unicodedata
        with open(fx("es-machine.txt"), encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(summary(run("scan", scratch(unicodedata.normalize("NFD", text), suffix=".txt"))[1]),
                         summary(run("scan", fx("es-machine.txt"))[1]))

    def test_every_chinese_list_item_is_caught_in_traditional_characters(self):
        # zh-list-traditional.json is written by build/zh_traditional.py: every Chinese list item and
        # its OpenCC s2t, s2tw, s2hk and s2twp forms. Adding a list item without re-running that
        # script fails here, and so does any traditional form the table misses. In the first 0.5.1
        # candidate 5 of 7 newly added phrases missed (穩 結 願 並 were not in the table).
        sys.dont_write_bytecode = True
        sys.path.insert(0, os.path.dirname(SCRIPT))
        try:
            import voice_check as vc
        finally:
            sys.path.pop(0)
        with open(fx("zh-list-traditional.json"), encoding="utf-8") as f:
            data = json.load(f)["items"]
        self.assertEqual([i for i, _ in data["words"]], vc.ZH_WORDS.pattern.split("|"))
        self.assertEqual([i for i, _ in data["phrases"]], list(vc.ZH_PHRASES))
        self.assertEqual([i for i, _ in data["mild"]], list(vc.ZH_MILD))
        self.assertEqual(len(data["patterns"]), len(vc.ZH_PATTERNS))
        labels = [label for label, _rx in vc.ZH_PATTERNS]
        for kind, rows in data.items():
            for n, (item, forms) in enumerate(rows):
                for text in [item] + forms:
                    hits, mild = vc.find_tells(text * 2 if kind == "contrast" else text, "zh")
                    kinds = [h[1] for h in hits]
                    caught = {"words": "stock word" in kinds, "phrases": "stock phrase" in kinds,
                              "mild": bool(mild), "contrast": any(k.startswith("contrast pile-up") for k in kinds),
                              "patterns": kind == "patterns" and labels[n] in kinds}[kind]
                    self.assertTrue(caught, f"{kind}: {text}")

    def test_a_file_not_saved_as_utf8_says_so(self):
        path = scratch("我们今天去公园。".encode("gbk"), mode="wb")
        _code, out = run("scan", path)
        self.assertIn("is not saved as UTF-8", out)
        _code, out = run("stats", path)
        self.assertIn("warnings", json.loads(out))

    def test_utf16_with_a_byte_order_mark_is_read(self):
        path = scratch("我们今天去公园。天气很好。".encode("utf-16"), mode="wb")
        self.assertIn("Checked as: Chinese", run("scan", path)[1])
        with open(fx("zh-machine.txt"), encoding="utf-8") as f:
            text = f.read()
        # UTF-32 also starts FF FE; it was read as UTF-16 and came back "0 strong tells" unread.
        self.assertEqual(summary(run("scan", scratch(text.encode("utf-32"), mode="wb"))[1]),
                         summary(run("scan", fx("zh-machine.txt"))[1]))

    def test_old_mac_and_windows_line_endings_read_the_same(self):
        # Reading raw bytes for the encoding fix stopped line endings being converted: a file with
        # carriage returns only lost its paragraphs, and one starting with a heading read as no words.
        with open(fx("machine.txt"), encoding="utf-8") as f:
            text = f.read()
        want = json.loads(run("stats", fx("machine.txt"))[1])
        for ending in ("\r", "\r\n"):
            got = json.loads(run("stats", scratch(text.replace("\n", ending).encode("utf-8"), mode="wb"))[1])
            self.assertEqual((got["words"], got["paragraph_cv"]), (want["words"], want["paragraph_cv"]), repr(ending))

    def test_a_language_code_with_a_note_after_it_is_understood(self):
        for line in ("language: zh (simplified)", "language: es (Spain)", "language: zh,"):
            prof = scratch(line + "\n\n```json\n{\"targets\": {\"avg_sentence_words\": [0, 99]}}\n```\n", suffix=".md")
            out = run("scan", fx("zh-human.txt" if "zh" in line else "es-human.txt"), "--profile", prof)[1]
            self.assertNotIn("different language", out, line)

    def test_long_unbroken_text_is_fast(self):
        # One 128,000-character Chinese paragraph took 80 s before the e-mail pattern was made linear.
        path = scratch("我们的发展社会问题时间工作文化经济" * 7600, suffix=".txt")
        import time
        start = time.time()
        code, _out = run("scan", path)
        self.assertEqual(code, 0)
        self.assertLess(time.time() - start, 10)

    def test_a_console_that_is_not_utf8_still_gets_a_report(self):
        # run() uses -I, which ignores PYTHONIOENCODING, so the console is forced to cp1252 here instead.
        # Before this repair the test passed with the fix removed.
        wrap = ("import io,runpy,sys;sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='cp1252');"
                "sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')")
        p = subprocess.run([sys.executable, "-I", "-B", "-c", wrap, SCRIPT, "habits", fx("zh-human.txt")], capture_output=True)
        code, out = p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        self.assertEqual(code, 0)
        self.assertIn('"words"', out)
        self.assertIn('"language_how"', out)

    def test_scripts_without_sentence_marks_do_not_claim_sentence_measures(self):
        _code, out = run("scan", scratch("ภาษาไทยเป็นภาษาราชการของประเทศไทย มีผู้พูดหลายล้านคน\n", suffix=".txt"))
        self.assertIn("sentence measures were not taken", out)
        self.assertIn("Paragraph rhythm, punctuation and layout were.", out)
        self.assertNotIn("sentence_cv", out)

    def test_japanese_does_not_list_its_own_kana_as_other_scripts(self):
        _code, out = run("scan", fx("ja.txt"))
        self.assertNotIn("Other scripts", out)

    def test_a_huge_report_is_capped(self):
        _code, out = run("scan", scratch("It is important to note this.\n" * 600, suffix=".txt"))
        self.assertIn("more (counted in the summary)", out)
        self.assertEqual(summary(out)[0], 600)

    def test_the_languages_command_names_every_list(self):
        _code, out = run("languages")
        for words in ("en  English", "zh  Chinese", "es  Spanish", "no lists yet"):
            self.assertIn(words, out)


class Voices(unittest.TestCase):
    """The picker shows every stored voice, from the project folder and the personal folder
    that every AI app with GeodeQuill on the computer shares, then the built-in voices that ship with the skill,
    and never touches the real home folder."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.project = tempfile.mkdtemp()
        self.env = {"GEODEQUILL_HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.home)
        shutil.rmtree(self.project)

    def test_nothing_saved_says_where_it_looked_and_still_offers_the_built_in_voices(self):
        _code, out = run("voices", env=self.env, cwd=self.project)
        self.assertIn("No voices of your own saved yet", out)
        self.assertIn(os.path.join(self.home, "voices"), out)
        self.assertIn("1. abraham-lincoln (built in): Abraham Lincoln (public domain)", out)
        _code, out = run("voices", "--json", env=self.env, cwd=self.project)
        listed = json.loads(out)["voices"]
        self.assertEqual([v["name"] for v in listed], BUILT_IN)
        self.assertTrue(all(v["built_in"] for v in listed))

    def test_personal_and_project_voices_are_both_listed_with_their_habits(self):
        os.makedirs(os.path.join(self.home, "voices"))
        shutil.copy(fx("twain-corpus-profile.md"), os.path.join(self.home, "voices", "twain.md"))
        os.makedirs(os.path.join(self.project, "voice-profiles"))
        shutil.copy(fx("profile-registers.md"), os.path.join(self.project, "voice-profiles", "talky.md"))
        _code, out = run("voices", env=self.env, cwd=self.project)
        self.assertIn("1. talky", out)
        self.assertIn("written and spoken", out)
        self.assertIn("2. twain-corpus: A first-person storyteller", out)
        _code, out = run("voices", "--json", env=self.env, cwd=self.project)
        names = [v["name"] for v in json.loads(out)["voices"]]
        self.assertEqual(names, ["talky", "twain-corpus"] + BUILT_IN)

    def test_your_own_voice_hides_a_built_in_of_the_same_name(self):
        os.makedirs(os.path.join(self.home, "voices"))
        shutil.copy(fx("twain-corpus-profile.md"), os.path.join(self.home, "voices", "mark-twain.md"))
        _code, out = run("voices", "--json", env=self.env, cwd=self.project)
        listed = json.loads(out)["voices"]
        mine = [v for v in listed if not v["built_in"]]
        self.assertEqual([os.path.basename(v["file"]) for v in mine], ["mark-twain.md"])
        self.assertNotIn("mark-twain", [v["name"] for v in listed if v["built_in"]])
        self.assertEqual(len(listed), len(BUILT_IN))

    def test_every_built_in_voice_is_complete_and_honest_about_its_sources(self):
        folder = os.path.join(SKILL, "voices")
        self.assertEqual(sorted(n[:-3] for n in os.listdir(folder)), BUILT_IN)
        for name in BUILT_IN:
            text = open(os.path.join(folder, name + ".md"), encoding="utf-8").read()
            self.assertRegex(text, r"(?m)^voice: " + name + r"$")
            self.assertIn("(public domain)", text)
            self.assertIn('present the text as "in the style of', text)
            self.assertIn("Never: put an invented quotation in", text)
            self.assertRegex(text, r"(?m)^## Sources\n(- .+\| (written|spoken) \| .+\n)+")
            self.assertIn("Not measured:", text)
            targets = json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))
            spoken = "## Spoken habits" in text
            self.assertEqual(sorted(targets), ["targets"] + (["targets_spoken"] if spoken else []))
            latin = not re.search(r"(?m)^language: (zh|ja|ko|th)$", text)  # reading level is Latin-script only
            for ranges in targets.values():
                for lo, hi in ranges.values():
                    self.assertLessEqual(lo, hi)
                if latin:
                    self.assertIn("reading_lix", ranges, name)
                else:
                    self.assertNotIn("reading_lix", ranges, name)
                    self.assertIn("no reading range", text, name)
            phrases = re.findall(r'(?m)^  - (written|spoken): "(.+)"$', text)
            for register in ("written", "spoken") if spoken else ("written",):
                mine = [p for r, p in phrases if r == register]
                self.assertTrue(1 <= len(mine) <= 5, name + " " + register)
                self.assertTrue(all(len(p.split()) < 12 for p in mine), name)

    def test_saving_never_writes_into_the_built_in_folder(self):
        sys.path.insert(0, os.path.join(SKILL, "scripts"))
        was, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            import voice_check
        finally:
            sys.path.pop(0)
            sys.dont_write_bytecode = was
        self.assertNotIn(voice_check.BUILT_IN_VOICES, voice_check.voice_dirs())
        self.assertEqual(os.path.dirname(voice_check.BUILT_IN_VOICES), os.path.abspath(SKILL))


class Tones(unittest.TestCase):
    """A tone changes how a voice speaks, so the checker must not flag the tone's own shifts as
    off-voice. Tone moves are judgement, not measurement; the tests pin what they do."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = {"GEODEQUILL_HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.home)

    def test_thirteen_built_in_tones_and_every_move_is_understood(self):
        _code, out = run("tones", "--json", env=self.env)
        tones = json.loads(out)["tones"]
        self.assertEqual([t["name"] for t in tones][:3], ["professional", "formal", "casual"])
        self.assertEqual(len(tones), 13)
        plain = [t for t in tones if t["name"] == "plain"][0]
        self.assertEqual(plain["moves"], [["sentence length", "down"], ["reading level", "down"]])
        text = open(os.path.join(SKILL, "references", "tones.md"), encoding="utf-8").read()
        written = [len([m for m in line.split(":", 1)[1].split(",") if m.strip()])
                   for line in text.splitlines() if line.startswith("Moves:")]
        self.assertEqual(written, [len(t["moves"]) for t in tones])

    def test_a_formal_draft_is_not_flagged_for_dropping_contractions(self):
        profile = scratch('```json\n{"targets": {"contractions_per_100w": [2, 6]}}\n```\n', suffix=".md")
        draft = scratch("We do not expect delays. The report is attached. It covers the year in full.\n" * 30)
        _code, plain = run("scan", draft, "--profile", profile, env=self.env)
        _code, formal = run("scan", draft, "--profile", profile, "--tone", "formal", env=self.env)
        self.assertIn("contractions_per_100w: 0.0 (profile 2 to 6) OUTSIDE", plain)
        self.assertIn("contractions_per_100w: 0.0 (profile 0 to 6) ok", formal)

    def test_a_casual_draft_may_go_above_the_voice_range(self):
        profile = scratch('```json\n{"targets": {"contractions_per_100w": [0, 1]}}\n```\n', suffix=".md")
        _code, out = run("scan", fx("spoken.txt"), "--profile", profile, "--tone", "casual", env=self.env)
        self.assertIn("contractions_per_100w: 5.68 (profile 0 to 2) OUTSIDE", out)
        _code, out = run("scan", fx("spoken.txt"), "--profile", profile, "--tone", "very-casual", env=self.env)
        self.assertIn("tone not found: very-casual", out)

    def test_your_own_tone_is_listed_and_wins_over_a_built_in_of_the_same_name(self):
        os.makedirs(os.path.join(self.home, "tones"))
        with open(os.path.join(self.home, "tones", "formal.md"), "w", encoding="utf-8") as f:
            f.write("In one line: My board-letter formal.\nMoves: dashes down\n")
        _code, out = run("tones", env=self.env)
        self.assertIn("formal: My board-letter formal. (yours:", out)
        profile = scratch('```json\n{"targets": {"contractions_per_100w": [2, 6], "em_dashes_per_1000w": [3, 9]}}\n```\n', suffix=".md")
        _code, out = run("scan", fx("human.txt"), "--profile", profile, "--tone", "formal", env=self.env)
        self.assertIn("loosened in its direction: em_dashes_per_1000w)", out)


def load_checker():
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    was, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        import voice_check
    finally:
        sys.path.pop(0)
        sys.dont_write_bytecode = was
    return voice_check


class ReadingLevel(unittest.TestCase):
    """Reading level is LIX (Bjornsson 1968): words per sentence plus the percentage of words
    longer than six letters. It is published, needs no word list, and works across Latin-script
    languages, so it ships to any user. It is not language-neutral: a draft in another language
    from the voice is not judged on it. Character-counted scripts get none, because a "word over
    six letters" means nothing there; other alphabets are left out until someone measures them.
    Design rule: with a voice, keep its measured level; "easier to read" asks
    for simpler language than the text has (the plain tone)."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = {"GEODEQUILL_HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.home)

    def stats(self, text, *extra):
        _code, out = run("stats", scratch(text), *extra, env=self.env)
        return json.loads(out)

    def test_the_score_follows_the_published_formula(self):
        # 5 words, 2 sentences, 1 word over six letters: 5/2 + 100*1/5 = 22.5
        m = self.stats("Extraordinary events happen. We wait.", "--lang", "en")
        self.assertEqual(m["reading_lix"], 22.5)
        self.assertEqual(m["reading_level"], "very easy")
        # apostrophes and hyphens are not letters: "don't" has 4, "well-known" has 9
        m = self.stats("I don't know. It is well-known.", "--lang", "en")
        self.assertEqual(m["reading_lix"], round(6 / 2 + 100 * 1 / 6, 1))

    def test_plain_names_follow_the_lix_bands(self):
        vc = load_checker()
        for lix, name in ((0, "very easy"), (29.9, "very easy"), (30, "easy"), (39.9, "easy"),
                          (40, "standard"), (50, "hard"), (59.9, "hard"), (60, "very hard"), (85, "very hard")):
            self.assertEqual(vc.reading_level(lix), name, lix)

    def test_other_latin_script_languages_are_scored(self):
        m = self.stats(open(fx("es-human.txt"), encoding="utf-8").read())
        self.assertEqual(m["language"], "es")
        self.assertIn("reading_lix", m)

    def test_character_counted_scripts_and_other_alphabets_get_no_score(self):
        for text in (open(fx("zh-human.txt"), encoding="utf-8").read(),
                     open(fx("ja.txt"), encoding="utf-8").read(),
                     "Это простой текст для проверки. Он очень короткий и ясный. Мы читаем его медленно."):
            m = self.stats(text)
            self.assertNotIn("reading_lix", m)
            self.assertNotIn("reading_level", m)

    def test_a_voice_gets_a_reading_range_and_each_file_a_score(self):
        m = self.stats(open(fx("human.txt"), encoding="utf-8").read(), "--targets", "--each")
        self.assertIn("reading_lix", m["suggested"]["targets"])
        lo, hi = m["suggested"]["targets"]["reading_lix"]
        self.assertLessEqual(lo, m["reading_lix"])
        self.assertGreaterEqual(hi, m["reading_lix"])
        self.assertIn("reading_lix", list(m["per_file"].values())[0])

    def test_the_report_names_the_reading_level(self):
        _code, out = run("scan", fx("human.txt"), env=self.env)
        self.assertRegex(out, r"(?m)^reading_lix: [\d.]+ \((very easy|easy|standard|hard|very hard)\)$")
        _code, out = run("scan", fx("zh-human.txt"), env=self.env)
        self.assertNotIn("reading_lix", out)

    def test_a_voice_holds_a_draft_to_its_reading_level(self):
        profile = scratch('---\nlanguage: en\n---\n```json\n{"targets": {"reading_lix": [55, 70]}}\n```\n', suffix=".md")
        draft = scratch("We went home. The dog ran out. It was a good day. We ate and slept.\n\n" * 12)
        _code, out = run("scan", draft, "--profile", profile, env=self.env)
        self.assertRegex(out, r"reading_lix: [\d.]+ \(profile 55 to 70\) OUTSIDE")

    def test_a_draft_in_another_language_is_not_judged_on_reading_level(self):
        profile = scratch('---\nlanguage: en\n---\n```json\n{"targets": {"reading_lix": [20, 25]}}\n```\n', suffix=".md")
        _code, out = run("scan", fx("es-human.txt"), "--profile", profile, env=self.env)
        self.assertRegex(out, r"reading_lix: [\d.]+ \(profile 20 to 25\) not judged: different language")

    def test_the_plain_tone_lets_a_draft_read_easier_than_the_voice(self):
        profile = scratch('---\nlanguage: en\n---\n```json\n{"targets": {"reading_lix": [45, 60], '
                          '"avg_sentence_words": [16, 24]}}\n```\n', suffix=".md")
        draft = scratch("We went home. The dog ran out. It was a good day. We ate and slept.\n\n" * 12)
        _code, out = run("scan", draft, "--profile", profile, "--tone", "plain", env=self.env)
        self.assertIn("(tone: plain; loosened in its direction: avg_sentence_words, reading_lix)", out)
        self.assertRegex(out, r"reading_lix: [\d.]+ \(profile 0 to 60\) ok")

    def test_an_easier_to_read_request_reports_before_and_after(self):
        before = scratch("Notwithstanding considerable organisational complexity, implementation "
                         "necessitates comprehensive stakeholder consultation throughout subsequent "
                         "deliberations, particularly regarding infrastructure expenditure.\n")
        after = scratch("The work is complex. We must ask everyone it affects before we decide. "
                        "That matters most for what we spend on buildings.\n")
        _code, out = run("scan", after, "--before", before, "--tone", "plain", env=self.env)
        self.assertRegex(out, r"(?m)^reading level: before [\d.]+ \(very hard\), after [\d.]+ \((very easy|easy)\)$")
        _code, out = run("scan", after, "--before", scratch("短文。"), env=self.env)
        self.assertIn("reading level: before not measured for this language", out)
        _code, out = run("scan", after, "--before", os.path.join(self.home, "missing.txt"), env=self.env)
        self.assertIn("Cannot read", out)

    def test_the_voice_layout_carries_the_reading_level(self):
        text = open(os.path.join(SKILL, "references", "profile-template.md"), encoding="utf-8").read()
        self.assertIn('"reading_lix"', text)
        self.assertIn("Reading level:", text)


class LearnFromEdits(unittest.TestCase):
    """0.6.5: the user hands back their own edited version of a draft and the voice takes it as one
    more sample. A profile keeps ranges, not samples, so each range is turned back into a centre and
    a spread the way suggest_targets built it, the new windows are added with Welford's running
    mean and variance, and the range is rebuilt the same way. Only the user's words may teach the
    voice: text that is still mostly the AI's draft is refused."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = {"GEODEQUILL_HOME": self.home}
        base = open(fx("twain-corpus-profile.md"), encoding="utf-8").read()
        self.big = os.path.join(self.home, "big.md")
        open(self.big, "w", encoding="utf-8").write(base)
        self.small = os.path.join(self.home, "small.md")
        open(self.small, "w", encoding="utf-8").write(
            re.sub(r"(?m)^samples:.*$", "samples: written 3 pieces, about 900 words", base))

    def tearDown(self):
        shutil.rmtree(self.home)

    def ranges(self, path, key="targets"):
        return load_checker().parse_targets(open(path, encoding="utf-8").read(), key)

    def test_text_like_the_voice_barely_moves_a_voice_built_on_many_samples(self):
        before = self.ranges(self.big)
        code, out = run("learn", fx("twain-piece-1.txt"), fx("twain-piece-2.txt"), "--profile", self.big,
                        "--write", env=self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("now rest on 976 samples", out)
        after = self.ranges(self.big)
        for k in before:
            self.assertLess(abs(after[k][0] - before[k][0]), 0.1, k)
            self.assertLess(abs(after[k][1] - before[k][1]), 0.1, k)

    def test_text_far_from_a_small_voice_pulls_the_range_toward_it(self):
        vc = load_checker()
        casual = open(fx("casual-edit.txt"), encoding="utf-8").read()
        rate = vc.metrics(casual)["contractions_per_100w"]
        before = self.ranges(self.small)["contractions_per_100w"]
        self.assertGreater(rate, before[1])
        code, out = run("learn", fx("casual-edit.txt"), "--profile", self.small, "--write", env=self.env)
        self.assertEqual(code, 0, out)
        after = self.ranges(self.small)["contractions_per_100w"]
        self.assertGreater(after[1], before[1] + 3)
        self.assertEqual(after[0], before[0])
        self.assertRegex(out, r"contractions_per_100w: 0 to 1\.31 -> 0 to [\d.]+")

    def test_a_range_stretches_only_toward_text_that_fell_outside_it(self):
        _code, _out = run("learn", fx("casual-edit.txt"), "--profile", self.small, "--write", env=self.env)
        self.assertEqual(self.ranges(self.small)["bullet_line_share"], [0, 0.05])

    def test_the_math_follows_the_running_mean_and_variance(self):
        vc = load_checker()
        # A range built from 10 or more windows is a padded 10th-90th percentile: 2.563 standard deviations.
        rng, n = vc.learn_range("avg_sentence_words", 10.0, 22.0, 20, [16.0])
        rlo, rhi = vc.unpad(10.0, 22.0, 20)
        mean, sd = (rlo + rhi) / 2, (rhi - rlo) / 2.563
        self.assertEqual(n, 21)
        self.assertAlmostEqual((rng[0] + rng[1]) / 2, mean, places=1)
        # The value sat at the centre: the spread can only shrink, by the n-1 to n step.
        self.assertLessEqual(rng[1] - rng[0], 12.0)
        self.assertGreater(rng[1] - rng[0], 12.0 * 0.95)
        # Padding is taken off exactly as suggest_targets put it on.
        lo, hi = 3.0, 9.0
        pad = max((hi - lo) * 0.1, hi * 0.05, 0.05)
        self.assertEqual([round(x, 6) for x in vc.unpad(lo - pad, hi + pad, 12)], [lo, hi])

    def test_a_voice_on_one_sample_is_padded_like_setup_pads_two(self):
        vc = load_checker()
        a, b = vc.metrics(open(fx("twain-piece-1.txt"), encoding="utf-8").read()), \
            vc.metrics(open(fx("casual-edit.txt"), encoding="utf-8").read())
        one = vc.suggest_targets([open(fx("twain-piece-1.txt"), encoding="utf-8").read()])
        both = vc.suggest_targets([open(fx("twain-piece-1.txt"), encoding="utf-8").read(),
                                   open(fx("casual-edit.txt"), encoding="utf-8").read()])["targets"]
        lo, hi = one["targets"]["avg_sentence_words"]
        rng, n = vc.learn_range("avg_sentence_words", lo, hi, one["based_on_pieces"], [b["avg_sentence_words"]])
        self.assertEqual(n, 2)
        self.assertLessEqual(rng[0], min(a["avg_sentence_words"], b["avg_sentence_words"]))
        self.assertGreaterEqual(rng[1], max(a["avg_sentence_words"], b["avg_sentence_words"]))
        self.assertLess(abs(rng[1] - both["avg_sentence_words"][1]), 0.25 * both["avg_sentence_words"][1])

    def test_text_that_is_mostly_the_draft_is_refused(self):
        was = open(self.small, encoding="utf-8").read()
        tweak = open(fx("casual-edit.txt"), encoding="utf-8").read().replace("Okay, so", "So")
        code, out = run("learn", scratch(tweak), "--draft", fx("casual-edit.txt"), "--profile", self.small,
                        "--write", env=self.env)
        self.assertEqual(code, 3)
        self.assertIn("still mostly the AI's writing", out)
        self.assertIn("Nothing was learned", out)
        self.assertEqual(open(self.small, encoding="utf-8").read(), was)

    def test_short_text_another_language_and_built_in_voices_are_refused(self):
        code, out = run("learn", fx("human.txt"), "--profile", self.small, env=self.env)
        self.assertEqual(code, 3)
        self.assertIn("at least 150 are needed", out)
        code, out = run("learn", fx("zh-human.txt"), "--profile", self.small, env=self.env)
        self.assertEqual(code, 3)
        self.assertIn("learns only from text in its own language", out)
        code, out = run("learn", fx("casual-edit.txt"), "--profile", "mark-twain", "--write", env=self.env)
        self.assertEqual(code, 3)
        self.assertIn("Built-in voices do not learn", out)
        code, _out = run("learn", fx("casual-edit.txt"), env=self.env)
        self.assertEqual(code, 2)

    def test_without_write_nothing_is_saved(self):
        was = open(self.small, encoding="utf-8").read()
        code, out = run("learn", fx("casual-edit.txt"), "--profile", self.small, env=self.env)
        self.assertEqual(code, 0)
        self.assertIn("Not saved yet", out)
        self.assertEqual(open(self.small, encoding="utf-8").read(), was)

    def test_saving_changes_only_the_ranges_their_count_and_one_source_line(self):
        was = open(self.small, encoding="utf-8").read()
        run("learn", fx("casual-edit.txt"), "--profile", self.small, "--write", env=self.env)
        now = open(self.small, encoding="utf-8").read()
        strip = lambda t: re.sub(r"```json.*?```", "", re.sub(r"(?m)^- the user's own edited text.*\n|^## Sources\n", "", t), flags=re.S)
        self.assertEqual(strip(now).replace("\n", ""), strip(was).replace("\n", ""))
        self.assertRegex(now, r"(?m)^- the user's own edited text, learned \d{4}-\d\d-\d\d, about 185 words \| written \| own prose$")
        self.assertIn('"windows": {\n    "targets": 4\n  }', now)
        self.assertNotIn("printer", now)  # none of the user's words are copied in
        code, out = run("learn", fx("casual-edit.txt"), "--profile", self.small, env=self.env)
        self.assertIn("now rest on 5 samples", out)
        code, out = run("scan", fx("casual-edit.txt"), "--profile", self.small, env=self.env)
        self.assertIn("== Versus the voice profile (written) ==", out)

    def test_the_spoken_register_learns_into_its_own_ranges(self):
        prof = os.path.join(self.home, "both.md")
        shutil.copy(fx("profile-registers.md"), prof)
        written = self.ranges(prof)
        code, out = run("learn", fx("casual-edit.txt"), "--profile", prof, "--register", "spoken", "--write",
                        env=self.env)
        self.assertEqual(code, 0, out)
        self.assertIn("assumed", out)
        self.assertEqual(self.ranges(prof), written)
        self.assertIn("the voice's spoken habits", out)

    def test_the_sample_count_is_read_from_every_kind_of_samples_line(self):
        vc = load_checker()
        cases = {"samples: written 3, about 1,278 words; spoken 2, about 887 words": (3, 2),
                 "samples: written 3 pieces, about 900 words": (3, None),
                 "samples: 5 books, about 575,000 words, measured in 974 windows of about 500 words": (974, None),
                 "samples: written 1 book and 1 essay, about 71,000 words; spoken 3 lectures, about 18,000 words": (142, 36)}
        for line, (w, sp) in cases.items():
            text = "---\n" + line + "\n---\n"
            self.assertEqual(vc.profile_windows(text, {}, "targets", "en", "words"), (w, None), line)
            got = vc.profile_windows(text, {}, "targets_spoken", "en", "words")
            self.assertEqual(got[0], sp or 3, line)
            self.assertEqual(got[1] is None, sp is not None, line)
        self.assertEqual(vc.profile_windows("", {"windows": {"targets": 7}}, "targets", "en", "words"), (7, None))

    def test_a_voice_made_in_setup_records_how_many_samples_built_it(self):
        out = json.loads(run("stats", fx("twain-piece-1.txt"), fx("twain-piece-2.txt"), "--targets", env=self.env)[1])
        self.assertEqual(out["suggested"]["based_on_pieces"], 2)
        with open(os.path.join(SKILL, "references", "profile-template.md"), encoding="utf-8") as f:
            self.assertIn('"windows": {', f.read())
        with open(os.path.join(REPO, "voice", "voice.js"), encoding="utf-8") as f:
            self.assertIn("targets.windows = { targets: w.stats.suggested.based_on_pieces }", f.read())


class LightEdit(unittest.TestCase):
    """0.6.5: a tidy fixes mistakes and machine phrases and keeps the user's sentences. With
    --before, the report says how much of the original's wording changed, so a tidy that
    rewrote too much shows."""

    def test_the_report_says_how_much_wording_changed(self):
        orig = scratch("We moved the meeting to Tuesday. It's important to note that lunch is provided.\n")
        tidy = scratch("We moved the meeting to Tuesday. Lunch is provided.\n")
        _code, out = run("scan", tidy, "--before", orig)
        self.assertRegex(out, r"(?m)^wording changed: 36% of the original's 14 words changed or cut, 0 added$")
        _code, out = run("scan", orig, "--before", orig)
        self.assertIn("wording changed: 0% of the original's 14 words changed or cut, 0 added", out)

    def test_characters_are_counted_where_there_are_no_spaces(self):
        _code, out = run("scan", scratch("我们明天开会。\n"), "--before", scratch("我们今天开会。\n"))
        self.assertIn("wording changed: 17% of the original's 6 words changed or cut, 1 added", out)

    def test_the_skill_routes_light_edits_to_the_tidy(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            main = f.read()
        with open(os.path.join(SKILL, "references", "write.md"), encoding="utf-8") as f:
            write = f.read()
        for words in ('"light edit"', '"just polish"', '"keep my wording"'):
            self.assertIn(words, main.split("---")[1])
        self.assertIn("A tidy needs no voice", main)
        self.assertIn("## Tidy", write)


class ProtectedWords(unittest.TestCase):
    """0.6.5: words the user says never to change. The checker reports any that went missing or
    were written differently; saved ones are judged only against an original that held them."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = {"GEODEQUILL_HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.home)

    def test_the_saved_list_is_kept_beside_the_voices(self):
        code, out = run("keep", env=self.env)
        self.assertIn("No protected words saved", out)
        run("keep", "--add", "GeodeQuill", "--add", "Net 30", "--add", "GeodeQuill", env=self.env)
        run("keep", "--remove", "Net 30", "--add", "- Tuesday club", env=self.env)
        code, out = run("keep", env=self.env)
        self.assertEqual(code, 0)
        self.assertIn(os.path.join(self.home, "keep.md"), out)
        self.assertRegex(out, r"1\. GeodeQuill\n2\. Tuesday club\n?$")
        self.assertEqual(run("keep", "--odd", env=self.env)[0], 2)

    def test_a_missing_or_respelled_word_is_reported(self):
        orig = scratch("Our GeodeQuill plugin ships on Net 30 terms. GeodeQuill is free.\n")
        bad = scratch("Our Geode Quill plugin ships on 30-day terms. It is free.\n")
        code, out = run("scan", bad, "--before", orig, "--keep", "GeodeQuill", "--keep", "Net 30", env=self.env)
        self.assertIn('"GeodeQuill": MISSING (2 in the original, 0 now); written as "Geode Quill" instead', out)
        self.assertIn('"Net 30": MISSING (1 in the original, 0 now)', out)
        self.assertIn("2 protected words missing or altered.", out)
        summary(out)
        good = scratch("Our GeodeQuill plugin ships on Net 30 terms, and GeodeQuill is free.\n")
        _code, out = run("scan", good, "--before", orig, "--keep", "GeodeQuill", env=self.env)
        self.assertIn('"GeodeQuill": kept (2 in the original, 2 now)', out)
        self.assertNotIn("missing or altered", out)
        once = scratch("Our GeodeQuill plugin ships on Net 30 terms, and it is free.\n")
        _code, out = run("scan", once, "--before", orig, "--keep", "GeodeQuill", env=self.env)
        self.assertIn('"GeodeQuill": kept (2 in the original, 1 now)', out)
        self.assertNotIn("missing or altered", out)
        mixed = scratch("Our GeodeQuill plugin ships on Net 30 terms, and Geodequill is free.\n")
        _code, out = run("scan", mixed, "--before", orig, "--keep", "GeodeQuill", env=self.env)
        self.assertIn('"GeodeQuill": ALTERED (2 in the original, 1 now); also written as "Geodequill"', out)
        self.assertIn("1 protected word missing or altered.", out)

    def test_saved_words_are_judged_only_against_an_original_that_held_them(self):
        run("keep", "--add", "Net 30", "--add", "Tuesday club", env=self.env)
        text = scratch("Payment is due in thirty days.\n")
        _code, out = run("scan", text, env=self.env)
        self.assertNotIn("Protected words", out)
        _code, out = run("scan", text, "--before", scratch("Payment terms are Net 30.\n"), env=self.env)
        self.assertIn('"Net 30": MISSING', out)
        self.assertNotIn("Tuesday club", out)

    def test_a_word_inside_a_longer_word_does_not_count_but_one_beside_chinese_does(self):
        _code, out = run("scan", scratch("Terms are Net 300 days.\n"), "--keep", "Net 30", env=self.env)
        self.assertIn('"Net 30": MISSING', out)
        _code, out = run("scan", scratch("我们的产品叫GeodeQuill，使用极光笔品牌。\n"), "--keep", "GeodeQuill",
                         "--keep", "极光笔", env=self.env)
        self.assertIn('"GeodeQuill": kept', out)
        self.assertIn('"极光笔": kept', out)
        self.assertEqual(run("scan", scratch("x y z.\n"), "--keep", env=self.env)[0], 2)

    def test_the_skill_keeps_them_in_every_job(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            main = f.read()
        self.assertIn("**Protected words stay exactly as written.**", main)
        self.assertIn("the plain tone included", main)


class VoiceNames(unittest.TestCase):
    """A built-in voice is found by the name a person types, not only by its file slug.
    Spaces, hyphens, underscores and letter case are treated alike."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.old = os.environ.get("GEODEQUILL_HOME")
        os.environ["GEODEQUILL_HOME"] = self.home

    def tearDown(self):
        if self.old is None:
            os.environ.pop("GEODEQUILL_HOME", None)
        else:
            os.environ["GEODEQUILL_HOME"] = self.old
        shutil.rmtree(self.home)

    def test_a_voice_is_found_however_its_name_is_typed(self):
        vc = load_checker()
        for typed in ("jane-austen", "Jane Austen", "jane_austen", "  JANE   AUSTEN ", "Jane-Austen"):
            path = vc.find_voice(typed)
            self.assertIsNotNone(path, typed)
            self.assertEqual(os.path.basename(path), "jane-austen.md")
        self.assertIsNone(vc.find_voice("nobody at all"))
        self.assertIsNone(vc.find_voice(""))


class Packaging(unittest.TestCase):
    """One package serves Claude and ChatGPT. The rules checked here are the ones OpenAI's plugin
    pages state for skills-only plugins; the portable schema file itself was unreachable from the
    build session, so these tests are the stand-in for its validator."""

    PLUGIN = os.path.join(HERE, "..", "plugin")

    def load(self, *parts):
        with open(os.path.join(self.PLUGIN, *parts), encoding="utf-8") as f:
            return json.load(f)

    def test_portable_manifest_follows_the_stated_rules(self):
        m = self.load("plugin.json")
        self.assertEqual(m["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertRegex(m["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(m["name"]), 64)
        self.assertRegex(m["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(0 < len(m["description"]) <= 4000)
        ui = m["extensions"]["com.openai"]["interface"]
        self.assertNotIn("screenshots", ui)
        self.assertNotIn("apps", m["extensions"]["com.openai"])
        self.assertLessEqual(len(ui["longDescription"]), 4000)
        self.assertTrue(all(isinstance(x, str) for x in ui["defaultPrompt"]))

    def test_versions_and_names_agree_everywhere(self):
        portable, claude = self.load("plugin.json"), self.load(".claude-plugin", "plugin.json")
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            skill_version = re.search(r'version: "([^"]+)"', f.read()).group(1)
        self.assertEqual(portable["name"], claude["name"])
        self.assertEqual(portable["version"], claude["version"])
        self.assertEqual(portable["version"], skill_version)
        self.assertTrue(claude["description"].strip())

    def test_skill_frontmatter_fits_the_agent_skills_limits(self):
        # agentskills.io/specification: name up to 64 characters, lowercase letters, digits and hyphens,
        # matching the folder; description 1 to 1,024 characters. An app may refuse an upload that breaks these.
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            front = f.read().split("---")[1]
        name = re.search(r"^name: (.+)$", front, re.M).group(1).strip()
        desc = re.search(r"^description: (.+)$", front, re.M).group(1).strip()
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)
        self.assertEqual(name, os.path.basename(os.path.normpath(SKILL)))
        self.assertTrue(0 < len(desc) <= 1024, len(desc))
        self.assertNotRegex(desc, r": |\s#|[<>]")

    def test_skills_only_layout(self):
        self.assertTrue(os.path.isfile(os.path.join(self.PLUGIN, "skills", "geodequill", "SKILL.md")))
        for banned in (".app.json", ".mcp.json", "mcp.json", "hooks"):
            self.assertFalse(os.path.exists(os.path.join(self.PLUGIN, banned)), banned)

    def test_the_user_guide_covers_every_way_in(self):
        with open(os.path.join(self.PLUGIN, "USER-GUIDE.md"), encoding="utf-8") as f:
            guide = f.read()
        for words in ("Claude", "ChatGPT", "Upload from your computer", "geodequill-skill", "List my voices", "List tones"):
            self.assertIn(words, guide)


    def test_feedback_address_is_everywhere_a_user_looks(self):
        address = "quill@geodeforge.com"
        for parts in (("USER-GUIDE.md",), ("README.md",), ("skills", "geodequill", "SKILL.md")):
            with open(os.path.join(self.PLUGIN, *parts), encoding="utf-8") as f:
                self.assertIn(address, f.read(), parts)
        for m in (self.load("plugin.json"), self.load(".claude-plugin", "plugin.json")):
            self.assertEqual(m["author"]["email"], address)

    def test_licence_is_stated_the_same_way_everywhere(self):
        for m in (self.load("plugin.json"), self.load(".claude-plugin", "plugin.json")):
            self.assertEqual(m["license"], "MIT")
            self.assertEqual(m["repository"], "https://github.com/GeodeForge/geodequill")
            self.assertTrue(m["homepage"].endswith("/"))
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r"\nlicense: MIT\n")
        licence = os.path.join(REPO, "LICENSE")
        if os.path.isfile(licence):
            with open(licence, encoding="utf-8") as f:
                self.assertTrue(f.read().startswith("MIT License"))


class ScanLimits(unittest.TestCase):
    """0.6.0: text with no words is refused, and a narrow wrong-language warning."""

    EN_LETTER = ("Dear friend,\n\nI am very much obliged to you for your kindness last week. It was a great help "
                 "to me, and I shall not soon forget it. Please accept my warmest thanks, and believe me to be "
                 "your grateful friend always.\n\nYours,\n[name]\n")
    VI_NO_MARKS = ("Kinh gui chi Lan,\n\nEm xin chan thanh cam on chi da giup em trong buoi hop tuan truoc. Nho co "
                   "chi ma em da hoan thanh bao cao dung han va nhan duoc nhan xet tot tu sep. Em that su biet on "
                   "chi rat nhieu va mong co dip duoc moi chi mot bua com de cam on.\n\nEm,\n[ten]\n")

    def test_no_words_is_refused(self):
        for text in ("", "   \n\n \t\n", "\n\n"):
            code, out = run("scan", scratch(text))
            self.assertEqual(code, 1, repr(text))
            self.assertIn("Nothing to check", out)

    def test_short_texts_in_other_scripts_are_scanned(self):
        for text in ("你好朋友。", "ありがとう。", "ขอบคุณครับ", "شكرا لك"):
            code, out = run("scan", scratch(text + "\n"))
            self.assertEqual(code, 0, text)
            self.assertIn("== Language ==", out)

    def test_language_warning_is_narrow(self):
        self.assertIn("reads as English", run("scan", scratch(self.EN_LETTER), "--lang", "vi")[1])
        self.assertIn("written in Chinese characters",
                      run("scan", scratch("亲爱的朋友，非常感谢你上周的帮助，我一直记在心里，希望我们很快能再见面。\n"), "--lang", "vi")[1])
        for text in (self.VI_NO_MARKS, "Chuc mung sinh nhat anh! Chuc anh mot tuoi moi that nhieu niem vui.\n",
                     "Happy birthday! Wishing you a year full of joy and good health.\n"):
            self.assertNotIn("Warning: --lang", run("scan", scratch(text), "--lang", "vi")[1], text[:30])
        self.assertNotIn("Warning: --lang", run("scan", scratch(self.EN_LETTER), "--lang", "en")[1])


class Repository(unittest.TestCase):
    """The public repository doubles as the web page and as a Claude Code plugin marketplace.
    These checks skip when the tests run from an unpacked download rather than the repository."""

    def setUp(self):
        if not os.path.isfile(os.path.join(REPO, "index.html")):
            self.skipTest("not running from the repository")

    def read(self, name):
        with open(os.path.join(REPO, name), encoding="utf-8") as f:
            return f.read()

    def version(self):
        with open(os.path.join(REPO, "plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f)["version"]

    def test_marketplace_points_at_the_plugin(self):
        with open(os.path.join(REPO, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
            market = json.load(f)
        self.assertTrue(market["name"] and market["owner"]["name"])
        (entry,) = market["plugins"]
        self.assertEqual(entry["name"], "geodequill")
        self.assertTrue(entry["source"].startswith("./"))
        self.assertTrue(os.path.isfile(os.path.join(REPO, entry["source"], ".claude-plugin", "plugin.json")))
        self.assertEqual(entry["version"], self.version())

    def test_pages_ask_nothing_of_any_other_site(self):
        outside = re.compile(r"^(?:https?:)?//")
        for name in ("index.html", "guide/index.html", "privacy/index.html", "style.css"):
            text = self.read(name)
            scripts = [t for t in re.findall(r"<script[^>]*>", text) if "application/ld+json" not in t]
            self.assertEqual(scripts, [], name)
            loads = re.findall(r'(?:src|srcset|poster|data)="([^"]+)"', text)
            for tag in re.findall(r"<link[^>]*>", text):
                rel = re.search(r'rel="([^"]+)"', tag)
                href = re.search(r'href="([^"]+)"', tag)
                if href and not (rel and rel.group(1) == "canonical"):
                    loads.append(href.group(1))
            loads += re.findall(r"url\(\s*['\"]?([^'\")]+)", text)
            self.assertEqual([u for u in loads if outside.match(u)], [], name)
            self.assertNotIn("@import", text, name)

    def test_every_local_link_on_the_pages_exists(self):
        for name in ("index.html", "guide/index.html", "privacy/index.html"):
            here = os.path.dirname(os.path.join(REPO, name))
            for ref in re.findall(r'(?:href|src)="([^"#?:]*)(?:[?#][^"]*)?"', self.read(name)):
                if ref.startswith("//"):
                    continue
                target = os.path.normpath(os.path.join(here, ref or "."))
                if ref == "" or ref.endswith("/"):
                    target = os.path.join(target, "index.html")
                self.assertTrue(os.path.isfile(target), f"{name} links {ref!r}")
            self.assertNotRegex(self.read(name), r'href="[^"]*\.html"', name)

    def test_the_page_offers_the_current_files_and_the_feedback_address(self):
        page = self.read("index.html")
        self.assertIn(f'<span id="version">{self.version()}</span>', page)
        self.assertIn(f'"softwareVersion":"{self.version()}"', page)
        self.assertIn("We invite you to double-check our work", page)
        self.assertIn("mailto:quill@geodeforge.com", page)
        for name in ("geodequill-skill.zip", "geodequill.plugin", "geodequill-mcp.zip"):
            self.assertIn(f"download/{name}", page)
        self.assertIn(self.version(), self.read("guide/index.html"))

    def test_every_download_carries_the_licence_notices(self):
        import zipfile
        for name in ("geodequill.plugin", "geodequill-skill.zip", "geodequill-mcp.zip"):
            with zipfile.ZipFile(os.path.join(REPO, "download", name)) as z:
                notice = [n for n in z.namelist() if n.endswith("geodequill/LICENSE.txt")]
                self.assertTrue(notice, name)
                text = z.read(notice[0]).decode("utf-8")
                for holder in ("GeodeForge", "歸藏", "PeopleWorks"):
                    self.assertIn(holder, text, name)

    def test_downloads_match_the_sources(self):
        import zipfile
        with zipfile.ZipFile(os.path.join(REPO, "download", "geodequill-skill.zip")) as z:
            self.assertEqual(z.read("geodequill/SKILL.md"), open(os.path.join(SKILL, "SKILL.md"), "rb").read())
            self.assertEqual(z.read("geodequill/scripts/voice_check.py"), open(SCRIPT, "rb").read())
        with zipfile.ZipFile(os.path.join(REPO, "download", "geodequill.plugin")) as z:
            self.assertEqual(json.loads(z.read("plugin.json"))["version"], self.version())
            self.assertFalse([n for n in z.namelist() if "__pycache__" in n])
        with zipfile.ZipFile(os.path.join(REPO, "download", "geodequill-mcp.zip")) as z:
            self.assertEqual(z.read("geodequill-mcp/geodequill_mcp.py"), open(SERVER, "rb").read())


class OpenFormat(unittest.TestCase):
    """Other AI tools read the skill only if it follows the open Agent Skills format."""

    def test_skill_passes_the_reference_validator(self):
        try:
            import pathlib
            import skills_ref
        except ImportError:
            self.skipTest("reference validator absent (pip install skills-ref)")
        self.assertEqual(skills_ref.validate(pathlib.Path(SKILL)), [])

    def test_skill_carries_nothing_tied_to_one_vendor(self):
        for root, dirs, files in os.walk(SKILL):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for n in files:
                with open(os.path.join(root, n), encoding="utf-8") as f:
                    text = f.read()
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", text, n)
                self.assertNotIn("Claude", text, n)

    def test_the_connector_leaves_no_cache_files_in_the_skill(self):
        self.assertFalse(os.path.isdir(os.path.join(SKILL, "scripts", "__pycache__")))


class Connector(unittest.TestCase):
    """The MCP connector is started as a separate process and driven over standard input and
    output, exactly as an AI tool would drive it."""

    def test_connector_end_to_end(self):
        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client
        except ImportError:
            self.skipTest("MCP package absent (pip install mcp)")
        home = tempfile.mkdtemp()
        machine = open(fx("machine.txt"), encoding="utf-8").read()
        profile = open(fx("twain-corpus-profile.md"), encoding="utf-8").read()

        async def drive():
            params = StdioServerParameters(command=sys.executable, args=[SERVER],
                                           env={**os.environ, "GEODEQUILL_HOME": home})
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    tools = sorted(t.name for t in (await s.list_tools()).tools)
                    call = lambda n, a: s.call_tool(n, a)
                    text = lambda res: res.content[0].text
                    empty = json.loads(text(await call("list_voices", {})))["voices"]
                    saved = text(await call("save_voice", {"name": "twain", "profile": profile}))
                    again = text(await call("save_voice", {"name": "twain", "profile": profile}))
                    listed = json.loads(text(await call("list_voices", {})))["voices"]
                    read = text(await call("read_voice", {"name": "twain-corpus"}))
                    by_name = text(await call("read_voice", {"name": "Jane Austen"}))
                    plainer = text(await call("check_draft", {"text": "We met. It went well.", "before": machine}))
                    checked = text(await call("check_draft", {"text": machine}))
                    against = text(await call("check_draft", {"text": machine, "voice": "twain"}))
                    measured = json.loads(text(await call("measure_samples", {"samples": [machine]})))
                    tones = json.loads(text(await call("list_tones", {})))["tones"]
                    saved_tone = text(await call("save_tone", {"name": "board-letter", "summary": "Very correct.", "moves": "contractions down, dashes down"}))
                    bad_tone = text(await call("save_tone", {"name": "odd", "summary": "x", "moves": "volume up"}))
                    toned = text(await call("check_draft", {"text": machine, "voice": "twain", "tone": "board-letter"}))
                    main = text(await call("get_instructions", {"part": "main"}))
                    learned = text(await call("learn_voice", {"voice": "twain", "edited": open(fx("casual-edit.txt"), encoding="utf-8").read()}))
                    refused = text(await call("learn_voice", {"voice": "Jane Austen", "edited": machine}))
                    keep = json.loads(text(await call("protected_words", {"add": ["GeodeQuill", "Net 30"]})))
                    kept = text(await call("check_draft", {"text": "Our Geode Quill plugin.", "before": "Our GeodeQuill plugin.", "keep": ["plugin"]}))
                    prompts = [p.name for p in (await s.list_prompts()).prompts]
                    return (tools, empty, saved, again, listed, read, checked, against, measured, main, prompts,
                            tones, saved_tone, bad_tone, toned, by_name, plainer, learned, refused, keep, kept)

        try:
            (tools, empty, saved, again, listed, read, checked, against, measured, main, prompts,
             tones, saved_tone, bad_tone, toned, by_name, plainer, learned, refused, keep, kept) = asyncio.run(drive())
        finally:
            shutil.rmtree(home)
        self.assertEqual(tools, ["check_draft", "get_instructions", "learn_voice", "list_tones", "list_voices",
                                 "measure_samples", "protected_words", "read_voice", "save_tone", "save_voice"])
        self.assertIn("Saved", learned)
        self.assertIn("Learned from 185 words", learned)
        self.assertIn("Built-in voices do not learn", refused)
        self.assertEqual(keep["protected"], ["GeodeQuill", "Net 30"])
        self.assertIn('"GeodeQuill": MISSING (1 in the original, 0 now); written as "Geode Quill" instead', kept)
        self.assertIn('"plugin": kept', kept)
        self.assertEqual(len(tones), 13)
        self.assertIn("Saved", saved_tone)
        self.assertIn("not understood", bad_tone)
        self.assertIn("(tone: board-letter; loosened in its direction: contractions_per_100w, em_dashes_per_1000w)", toned)
        self.assertEqual([v["name"] for v in empty], BUILT_IN)
        self.assertIn("Saved", saved)
        self.assertIn("already exists", again)
        self.assertEqual([v["name"] for v in listed], ["twain-corpus"] + BUILT_IN)
        self.assertEqual([v["built_in"] for v in listed][:2], [False, True])
        self.assertIn("## Targets", read)
        self.assertRegex(by_name, r"(?m)^voice: jane-austen$")
        self.assertRegex(plainer, r"(?m)^reading level: before [\d.]+ \(.+\), after [\d.]+ \(very easy\)$")
        self.assertGreaterEqual(summary(checked)[0], 8)
        self.assertIn("== Versus the voice profile (written) ==", against)
        self.assertIn("targets", measured["stats"]["suggested"])
        self.assertIn("## Choose a voice", main)
        self.assertEqual(prompts, ["geodequill"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
