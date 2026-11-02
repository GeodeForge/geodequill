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


BUILT_IN = ["abraham-lincoln", "charles-dickens", "jane-austen", "mark-twain", "oscar-wilde"]


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
        for name, lang in (("ja.txt", "Japanese"), ("fr.txt", "French")):
            _code, out = run("scan", fx(name))
            self.assertIn(f"Checked as: {lang}", out)
            self.assertIn("NOT checked", out)
            self.assertIn("Phrases and stock words were not checked for this language.", out)
            self.assertNotIn("\nnone found\n", out)

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
        ru = ("Вчера я долго гулял по городу. Было холодно, но солнечно. Я зашёл в маленькое кафе. "
              "Там пахло кофе и свежим хлебом. Официантка улыбнулась и принесла меню.\n\n") * 3
        m = json.loads(run("stats", scratch(ru, suffix=".txt"), "--targets")[1])
        self.assertEqual(m["language"], "und-cyrillic")
        prof = scratch("language: " + m["language"] + "\n\n```json\n" +
                       json.dumps({"targets": m["suggested"]["targets"]}) + "\n```\n", suffix=".md")
        _code, out = run("scan", scratch(ru, suffix=".txt"), "--profile", prof)
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
    that every AI tool on the computer shares, then the built-in voices that ship with the skill,
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
            for ranges in targets.values():
                for lo, hi in ranges.values():
                    self.assertLessEqual(lo, hi)
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

    def test_twelve_built_in_tones_and_every_move_is_understood(self):
        _code, out = run("tones", "--json", env=self.env)
        tones = json.loads(out)["tones"]
        self.assertEqual([t["name"] for t in tones][:3], ["professional", "formal", "casual"])
        self.assertEqual(len(tones), 12)
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
                    checked = text(await call("check_draft", {"text": machine}))
                    against = text(await call("check_draft", {"text": machine, "voice": "twain"}))
                    measured = json.loads(text(await call("measure_samples", {"samples": [machine]})))
                    tones = json.loads(text(await call("list_tones", {})))["tones"]
                    saved_tone = text(await call("save_tone", {"name": "board-letter", "summary": "Very correct.", "moves": "contractions down, dashes down"}))
                    bad_tone = text(await call("save_tone", {"name": "odd", "summary": "x", "moves": "volume up"}))
                    toned = text(await call("check_draft", {"text": machine, "voice": "twain", "tone": "board-letter"}))
                    main = text(await call("get_instructions", {"part": "main"}))
                    prompts = [p.name for p in (await s.list_prompts()).prompts]
                    return (tools, empty, saved, again, listed, read, checked, against, measured, main, prompts,
                            tones, saved_tone, bad_tone, toned)

        try:
            (tools, empty, saved, again, listed, read, checked, against, measured, main, prompts,
             tones, saved_tone, bad_tone, toned) = asyncio.run(drive())
        finally:
            shutil.rmtree(home)
        self.assertEqual(tools, ["check_draft", "get_instructions", "list_tones", "list_voices",
                                 "measure_samples", "read_voice", "save_tone", "save_voice"])
        self.assertEqual(len(tones), 12)
        self.assertIn("Saved", saved_tone)
        self.assertIn("not understood", bad_tone)
        self.assertIn("(tone: board-letter; loosened in its direction: contractions_per_100w, em_dashes_per_1000w)", toned)
        self.assertEqual([v["name"] for v in empty], BUILT_IN)
        self.assertIn("Saved", saved)
        self.assertIn("already exists", again)
        self.assertEqual([v["name"] for v in listed], ["twain-corpus"] + BUILT_IN)
        self.assertEqual([v["built_in"] for v in listed][:2], [False, True])
        self.assertIn("## Targets", read)
        self.assertGreaterEqual(summary(checked)[0], 8)
        self.assertIn("== Versus the voice profile (written) ==", against)
        self.assertIn("targets", measured["stats"]["suggested"])
        self.assertIn("## Choose a voice", main)
        self.assertEqual(prompts, ["geodequill"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
