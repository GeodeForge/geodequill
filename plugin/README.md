# GeodeQuill

Writes in a saved voice and personality, lets you pick from your saved voices, and checks each draft for the habits that make text read as machine-written.

## Use it

1. Say "set up my voice". Give it three or more things you wrote yourself, and describe the personality you want. It saves a voice.
2. Say "list my voices" to see your saved voices and pick one. Say "list tones" to pick a tone, or just name one: "write this in a formal tone", "make it slightly warmer".
3. Say "write this in my voice", or paste text and say "make this sound like me".
4. Say "stay in my voice" to keep the voice for the rest of the conversation.

AI apps sometimes answer a short request themselves without opening GeodeQuill. Anthropic's own guide for people who write skills says Claude tends to skip a skill on a short, simple request, even when the request matches the skill's description exactly (the skill-creator guide at https://github.com/anthropics/skills). To make sure it's used, start with "Use GeodeQuill to…".

A tone changes how a voice speaks, not who is speaking. Twelve come built in: professional, formal, casual, friendly, modest, confident, intimate, playful, direct, diplomatic, empathetic and persuasive. You can describe your own and save it.

You can keep several voices: a work voice, a casual voice, a character. Each voice keeps two sets of habits, written and spoken. Speeches, scripts and casual replies use the spoken set.

## Install it

Download the files from https://geodeforge.com/geodequill/. GeodeQuill comes in three forms. They hold the same instructions and the same checker.

A simple step-by-step guide for users is in `USER-GUIDE.md`.

- **Claude on the web or in the desktop app (every plan, with code execution turned on):** in Claude, go to Customize, then Skills. Select +, then Create skill, then Upload a skill, and choose `geodequill-skill.zip`.
- **Claude desktop app, the other way in:** install `geodequill.plugin`.
- **Claude Code:** add the GitHub repository as a plugin marketplace with `/plugin marketplace add GeodeForge/geodequill`, then run `/plugin install geodequill@geodeforge`.
- **ChatGPT:** in the sidebar, select Plugins, then the Skills tab. Select Create, then Upload from your computer, and choose `geodequill-skill.zip`. It runs inside ChatGPT; no server is needed. Skills are not on every ChatGPT plan yet: one OpenAI help page names the business plans, another says every paid plan except Free and Go.
- **Any AI tool that reads Agent Skills** (the open SKILL.md format: Codex, GitHub Copilot, Gemini CLI, Cursor, VS Code, Windsurf, Goose and others): unzip `geodequill-skill.zip` into the tool's skills folder. Each tool documents where that folder is.
- **Any AI tool that takes MCP connectors** (Claude Desktop, Cursor, VS Code, Windsurf, Zed, Cline and others): unzip `geodequill-mcp.zip`, install the MCP package with `pip install mcp`, and add the connector to the tool's MCP settings as a local command: `python3` (on Windows, `python`) followed by the full path to `geodequill_mcp.py` in the unzipped folder.

## Where your voices are kept

In a folder named `.geodequill/voices` inside your home folder; your own tones go in `.geodequill/tones` beside it. Every AI tool on the same computer reads the same folder, so a voice set up in one tool shows up in the others. To keep a voice with a single project instead, ask for it to be saved there; it goes in a `voice-profiles` folder in that project.

In ChatGPT and other web chats, each chat starts fresh. The voice is given to you at the end of setup; save it, and attach or paste it at the start of a later chat.

## What you need

- Python 3.8 or later on the computer running the AI tool, for the checker. Without it, drafts are reviewed by hand.
- For the MCP form only: Python 3.10 or later and the MCP package.

## What it does not do

- It does not promise to beat any AI detector. Detectors guess from patterns and are often wrong. It never gives a score.
- It is built not to invent memories, quotes, numbers or opinions. Where a real detail would help, it asks you or leaves a bracketed note. Read drafts before sending them: no check catches every invented detail.
- Every draft is reviewed by reading, against the list of machine-writing habits and the voice's habits. Each piece ends with an offer to run the checker, which measures the draft exactly; say yes and the app visibly runs code. Apps that can't run code can't run the checker.
- It does not use tricks such as invisible characters or planted typos.
- For real people, it searches only for authors whose work is public domain. Writing in a real person's voice is always labelled "in the style of" that person, with no invented quotes.

Use it on your own writing, and follow the rules of wherever you submit it.

## Phones and tablets

Add the skill on chatgpt.com. OpenAI's help page counts the website and the phone app as one place, so the phone app should have it too; not yet tested. The ChatGPT desktop app needs it added separately. The Claude phone app cannot add the skill; add it once from a computer (the Claude website or the desktop app). The phone app then uses it. Phone apps can't keep a voice file, so the voice is given as text at the end of setup, to paste in later.

## Not covered

Chat apps that accept neither skills nor MCP connectors cannot load GeodeQuill. ChatGPT plans without skills cannot add it; OpenAI's help pages disagree on which plans those are. The MCP connector does not work in ChatGPT, which takes connectors only from a server on the internet; ChatGPT users use the skill instead.

GeodeQuill writes in any language. The checker measures punctuation, layout and paragraph rhythm in any language and script, and sentence rhythm wherever the script marks where sentences end (Thai, Lao and Tibetan do not). Its lists of machine-writing phrases and words cover English, Chinese (simplified and traditional) and Spanish; for other languages its report says those were not checked.

## How it was checked

The checker was run over three collections of human writing: 23 books by Mark Twain (1.74 million words), 85,000 words of his speeches, and 141 documents that ship with ordinary software packages (192,000 words). Its strong flags fired 0.2 to 0.3 times per 10,000 words in all three. A 108-word machine-style sample drew 10. No collection of real machine-written text has been measured yet. None of this shows how any AI detector will score a piece.

## Credits

The tell list builds on Wikipedia's "Signs of AI writing" catalogue (WikiProject AI Cleanup) and the idea behind existing humanizer skills such as blader/humanizer. Common tone presets (formal, casual, friendly, confident, empathetic, persuasive and others, with a strength setting) are standard across writing tools; GeodeQuill layers them on a measured voice. GeodeQuill adds saved, measured voices with written and spoken habits, the voice and tone pickers, and the checker.

The Chinese list takes its categories from Humanizer-zh (op7418) and the Spanish list is adapted from Signs of AI Writing (PeopleWorks), both MIT. The Spanish common words used to tell languages apart come from the Snowball stop-word list (BSD). The traditional-Chinese table was generated with OpenCC. The notices are in `skills/geodequill/LICENSE.txt`.

## Feedback

Found a bug, or a claim that doesn't hold up? Email quill@geodeforge.com. An example helps enormously, though we understand if yours is too private to share.

## Licence

MIT. The names GeodeForge and GeodeQuill and the GeodeForge brand images are not part of that grant; see `TRADEMARKS.md` in the repository.
