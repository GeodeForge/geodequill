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
    f = tempfile.NamedTemporaryFile(mode, suffix=suffix, delete=False)
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
            self.assertEqual(code, 0, out)

    def test_missing_input_and_bad_usage_exit_codes(self):
        self.assertEqual(run("scan", os.path.join(FIX, "nope.txt"))[0], 1)
        self.assertEqual(run("stats", "--targets")[0], 1)
        self.assertEqual(run("scan", fx("human.txt"), "--register", "shouting")[0], 2)


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


class Voices(unittest.TestCase):
    """The picker shows every stored voice, from the project folder and the personal folder
    that every AI tool on the computer shares, and never touches the real home folder."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.project = tempfile.mkdtemp()
        self.env = {"GEODEQUILL_HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.home)
        shutil.rmtree(self.project)

    def test_nothing_saved_says_where_it_looked(self):
        _code, out = run("voices", env=self.env, cwd=self.project)
        self.assertIn("No saved voices", out)
        self.assertIn(os.path.join(self.home, "voices"), out)

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
        self.assertEqual(names, ["talky", "twain-corpus"])


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
        self.assertEqual(empty, [])
        self.assertIn("Saved", saved)
        self.assertIn("already exists", again)
        self.assertEqual([v["name"] for v in listed], ["twain-corpus"])
        self.assertIn("## Targets", read)
        self.assertGreaterEqual(summary(checked)[0], 8)
        self.assertIn("== Versus the voice profile (written) ==", against)
        self.assertIn("targets", measured["stats"]["suggested"])
        self.assertIn("## Choose a voice", main)
        self.assertEqual(prompts, ["geodequill"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
