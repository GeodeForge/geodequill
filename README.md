# GeodeQuill

**Write in your own voice, in the tone you pick.** GeodeQuill learns how you write from a few
things you wrote yourself, keeps your voices and tones to pick from, and writes or rewrites
text in them. It runs inside the AI app you already use: Claude, ChatGPT (on plans with skills), Codex,
Copilot, Gemini CLI, Cursor and others that read skills.

It also comes with five built-in voices measured from public-domain works: Mark Twain, Jane
Austen, Charles Dickens, Abraham Lincoln and Oscar Wilde. Each profile lists its sources, in
`plugin/skills/geodequill/voices/`.

A [GeodeForge](https://geodeforge.com) tool. Downloads and install steps:
**https://geodeforge.com/geodequill/**

---

## What it won't do

- Promise to get past AI detectors. They guess from patterns and are often wrong. It never
  gives a score.
- Invent memories, quotes, numbers or opinions and put them in your mouth.
- Use tricks such as invisible characters or planted typos.
- Check every language the same way. It writes in any language. It looks for machine-writing phrases in
  English, Chinese (simplified and traditional) and Spanish. In every language it checks punctuation,
  layout and paragraph rhythm, and sentence rhythm wherever the writing marks where sentences end (Thai,
  Lao and Tibetan don't). For a language with no phrase list, its report says when the phrase check
  didn't run.

## What's in here

| Folder | What it is |
|---|---|
| `plugin/` | The plugin: the skill, its checker script, and the manifests for Claude and for OpenAI's portable plugin format. `plugin/README.md` covers install; `plugin/USER-GUIDE.md` is the plain guide. |
| `mcp/` | The same skill served as an MCP connector, for tools that take connectors. |
| `test/` | The tests, with their sample texts. |
| `download/` | The ready-made files the web page offers. `build/build.py` makes them, and the guide page, from the sources. |
| `index.html`, `guide/`, `privacy/`, `style.css`, `assets/` | The web page at geodeforge.com/geodequill. |

Claude Code can install straight from this repository:
`/plugin marketplace add GeodeForge/geodequill`, then `/plugin install geodequill@geodeforge`.
To update later, run `claude plugin marketplace update geodeforge` and then `claude plugin update geodequill@geodeforge` in a terminal, then restart Claude Code. Saved voices and tones are never touched by an update. To get updates on their own, type `/plugin`, open
Marketplaces, pick geodeforge, and choose Enable auto-update. To hear about every new version, watch this
repository's releases (Watch, then Custom, then Releases).

## Check for yourself

The checker is one Python file, `plugin/skills/geodequill/scripts/voice_check.py`. It reads
text and prints numbers. It makes no network requests; search it for `import` and see.

To check a draft without installing anything, paste it at
[geodeforge.com/geodequill/check](https://geodeforge.com/geodequill/check/). The same file runs
there, inside your browser, and what you paste stays on your device.

Run the tests (Python 3.10 or later):

```
python3 -I test/test_voice_check.py
```

Two groups skip themselves unless `skills-ref` and `mcp` are installed.

What you write still goes to the company whose AI app you use, under that company's terms.
GeodeQuill adds no connection of its own.

## Feedback

Found a bug, or a claim that doesn't hold up? Email **quill@geodeforge.com**. An example
helps enormously, though we understand if yours is too private to share.

## Licence

MIT — see [`LICENSE`](LICENSE). Names and brand images: see [`TRADEMARKS.md`](TRADEMARKS.md).
