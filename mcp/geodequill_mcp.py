#!/usr/bin/env python3
import importlib.util
import json
import os
import re
import sys

USAGE = """GeodeQuill MCP connector.

Run by an AI tool that speaks MCP, over standard input and output:
  python3 geodequill_mcp.py

Needs the MCP Python package (pip install mcp) and the geodequill skill folder
beside this file, or GEODEQUILL_SKILL set to that folder. Saved voices live in
~/.geodequill/voices, or in GEODEQUILL_HOME/voices when that is set. Built-in voices of
public-domain authors come with the skill folder."""

HERE = os.path.dirname(os.path.abspath(__file__))


def find_skill():
    for c in (os.environ.get("GEODEQUILL_SKILL"),
              os.path.join(HERE, "geodequill"),
              os.path.join(HERE, "..", "plugin", "skills", "geodequill")):
        if c and os.path.isfile(os.path.join(c, "SKILL.md")):
            return os.path.abspath(c)
    sys.exit("GeodeQuill: cannot find the skill folder. Put the geodequill folder beside this file, "
             "or set GEODEQUILL_SKILL to its path.")


if "--help" in sys.argv or "-h" in sys.argv:
    print(USAGE)
    sys.exit(0)

SKILL = find_skill()
sys.dont_write_bytecode = True
_spec =importlib.util.spec_from_file_location("voice_check", os.path.join(SKILL, "scripts", "voice_check.py"))
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)

try:
    from mcp.server.mcpserver import MCPServer as Server
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as Server
    except ImportError:
        sys.exit("GeodeQuill: the MCP Python package is missing. Install it with: pip install mcp")

PARTS = {
    "main": "SKILL.md",
    "setup": "references/setup.md",
    "write": "references/write.md",
    "public-persona": "references/public-persona.md",
    "profile-template": "references/profile-template.md",
    "ai-tells": "references/ai-tells.md",
    "human-texture": "references/human-texture.md",
    "tones": "references/tones.md",
}

server = Server("geodequill", instructions=(
    "GeodeQuill writes in a saved voice and checks drafts for machine-writing habits. "
    "Call get_instructions first and follow it. In this connector the tools replace the script "
    "commands the instructions mention: list_voices for voices, list_tones for tones, check_draft for "
    "scan, measure_samples for stats and habits, read_voice, save_voice and save_tone for files."))


def voice_path(name):
    _dirs, found = vc.find_voices()
    key = (name or "").strip().lower()
    for v in found:
        stem = os.path.splitext(os.path.basename(v["file"]))[0].lower()
        if key in (v["name"].lower(), stem):
            return v["file"]
    return None


@server.tool(description="Return GeodeQuill's instructions. part is one of: main, setup, write, "
                         "public-persona, profile-template, ai-tells, human-texture, tones. Start with main.")
def get_instructions(part: str = "main") -> str:
    rel = PARTS.get(part)
    if not rel:
        return "Unknown part. Choose one of: " + ", ".join(PARTS)
    return vc.read_text(os.path.join(SKILL, rel)) or "That part is missing from the skill folder."


@server.tool(description="List voices to choose from: the user's own, then the built-in voices of "
                         "public-domain authors (built_in true). Each has a name, one-line description, "
                         "whether it has written and spoken habits, and its file. Show them to the user "
                         "as a numbered list in the reply and ask which to use.")
def list_voices() -> str:
    dirs, found = vc.find_voices()
    return json.dumps({"searched": dirs, "voices": found}, indent=2)


@server.tool(description="Return the full profile of a saved voice, by name.")
def read_voice(name: str) -> str:
    path = voice_path(name)
    text = vc.read_text(path) if path else None
    return text or f"No saved voice named {name}. Call list_voices to see the names."


@server.tool(description="Save a voice profile as name.md in the personal voices folder, which every AI "
                         "tool on this computer can read. name: lowercase letters, numbers and hyphens. "
                         "Refuses to replace an existing voice unless overwrite is true.")
def save_voice(name: str, profile: str, overwrite: bool = False) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name or ""):
        return "Use a short lowercase name with hyphens, like work-voice."
    folder = vc.voice_dirs()[-1]
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".md")
    if os.path.exists(path) and not overwrite:
        return f"A voice named {name} already exists at {path}. Ask the user before replacing it."
    with open(path, "w", encoding="utf-8") as f:
        f.write(profile)
    return f"Saved {path}"


@server.tool(description="List tones to choose from: the built-in ones and the user's own. Show them as a "
                         "numbered list in the reply and ask which to use.")
def list_tones() -> str:
    return json.dumps({"tones": vc.find_tones()}, indent=2)


@server.tool(description="Save the user's own tone as name.md in the personal tones folder. summary is one "
                         "line describing it. moves lists what it pushes up or down, for example "
                         "'contractions down, sentence length up'; measures: contractions, fillers, "
                         "exclamations, questions, first person, sentence length, dashes, semicolons. "
                         "guidance is a few lines on how to write in it.")
def save_tone(name: str, summary: str, moves: str = "", guidance: str = "", overwrite: bool = False) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name or ""):
        return "Use a short lowercase name with hyphens, like board-letter."
    text = f"In one line: {summary.strip()}\nMoves: {moves.strip()}\n\n{guidance.strip()}\n"
    parsed = vc.parse_tone_blocks(text, name)
    if moves.strip() and len(parsed[0]["moves"]) != len([m for m in moves.split(",") if m.strip()]):
        return "Some moves were not understood. Each must be a measure from the list followed by up or down."
    folder = os.path.join(vc.geodequill_home(), "tones")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".md")
    if os.path.exists(path) and not overwrite:
        return f"A tone named {name} already exists at {path}. Ask the user before replacing it."
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return f"Saved {path}"


@server.tool(description="Check a draft for machine-writing habits and, when a voice is named, compare it "
                         "with that voice's habits. register is written or spoken. tone, when one was "
                         "chosen, stops the tone's own shifts being flagged as off-voice. language is a code "
                         "such as en, zh or es; leave it empty to read it from the text. Fix what the "
                         "report flags; do not show the report to the user.")
def check_draft(text: str, voice: str = "", register: str = "written", tone: str = "", language: str = "") -> str:
    if register not in ("written", "spoken"):
        return "register must be written or spoken"
    profile, ptxt = None, None
    if voice:
        path = voice_path(voice)
        profile = path or voice
        ptxt = vc.read_text(path) if path else None
    return vc.scan_report(text, ptxt, profile, register, tone or None, language or None)


@server.tool(description="Measure writing samples for a voice profile. Pass one register at a time: all "
                         "the written samples, or all the spoken ones. Returns habit numbers, suggested "
                         "ranges for the profile's targets, and word-level habits. language is a code such as "
                         "en, zh or es; leave it empty to read it from the samples.")
def measure_samples(samples: list[str], language: str = "") -> str:
    texts = [s for s in samples if s and s.strip()]
    if not texts:
        return "Give at least one sample."
    return json.dumps({"stats": vc.stats_result(texts, targets=True, lang=language or None),
                       "habits": vc.habits_result(texts, language or None)}, indent=2, ensure_ascii=False)


@server.prompt(description="Load GeodeQuill's instructions for writing in a saved voice.")
def geodequill() -> str:
    return get_instructions("main")


if __name__ == "__main__":
    server.run()
