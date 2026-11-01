# GeodeQuill user guide

GeodeQuill helps an AI write the way you do. You give it a few things you wrote, and it learns your voice. After that, ask it to write or rewrite anything in that voice, in whatever tone you need.

## 1. Install it

Get the files from geodeforge.com/geodequill/. Then pick the line for the AI you use.

- **Claude on the web or in the desktop app** (every plan, including Free): go to **Customize**, then **Skills**. Select **+**, then **Create skill**, then **Upload a skill**, and choose the file that starts with `geodequill-skill`. Code execution has to be turned on in Claude's settings.
- **Claude desktop app**, the other way in: install the file that ends in `.plugin`.
- **Claude Code:** type `/plugin marketplace add GeodeForge/geodequill`, then `/plugin install geodequill@geodeforge`.
- **ChatGPT:** in the sidebar, select **Plugins**, then the **Skills** tab. Select **Create**, then **Upload from your computer**, and choose the file that starts with `geodequill-skill`. ChatGPT checks the file before it turns on. Not every ChatGPT plan has skills yet. One OpenAI help page names the business plans; another says every paid plan except Free and Go. If you don't see the Skills tab, your plan doesn't have it.
- **Codex, GitHub Copilot, Gemini CLI, Cursor and other tools that use skills:** unzip the file that starts with `geodequill-skill` into the tool's skills folder. Your tool's help pages say where that folder is.
- **Tools that use MCP connectors** (such as Claude Desktop, Cursor, VS Code): see the README that comes with the file that starts with `geodequill-mcp`.

**Updating from an earlier version.** Your saved voices and tones stay where they are; updating never touches them. Add the new file the same way you added the first one. If your app says a skill with that name already exists, delete the old one, then add the new one. In Claude Code, run `claude plugin marketplace update geodeforge` and then `claude plugin update geodequill@geodeforge` in a terminal, then restart Claude Code. In other tools, replace the old skill folder with the new one.

## 2. On a phone or tablet

- **ChatGPT:** add GeodeQuill on chatgpt.com. OpenAI's help page counts the website and the phone app as one place, so your phone should get it too; we haven't tested that yet. The ChatGPT desktop app needs it added separately.
- **Claude:** we haven't confirmed that skills work in the Claude phone app. Use Claude on the web or in the desktop app.
- A phone app can't keep your voice as a file. Save the voice as text at the end of setup, and paste it in when you want it. Section 6 explains.

## 3. Teach it your voice

Say: **"Set up my voice."**

It asks for three or more things you wrote yourself: emails, posts, letters, anything. About a page in total is enough. If you also have transcripts of yourself talking, add those. They teach it how you sound out loud, for speeches and casual replies.

It also asks how you'd like to come across, such as blunt or gentle, or formal or casual. Every answer is optional. Your samples matter most.

At the end it writes a short test paragraph and asks whether it sounds like you. Tell it what's off.

## 4. Write in your voice

- **"Write this in my voice:"** followed by your notes.
- **"Make this sound like me:"** followed by text you want rewritten. It keeps every fact and changes only the wording.
- **"Stay in my voice."** Everything it writes for the rest of the chat uses your voice.

If a real example or number would make the piece better, it asks you for one instead of making it up.

AI apps sometimes answer a short request themselves without opening GeodeQuill. Anthropic's own guide for people who write skills says Claude tends to skip a skill on a short, simple request, even when the request matches the skill's description exactly (the skill-creator guide at github.com/anthropics/skills). To make sure it's used, start with **"Use GeodeQuill to…"**, for example **"Use GeodeQuill to write a thank-you note like Jane Austen."**

## 5. Pick a voice or a tone

- **"List my voices"** shows your saved voices, then the built-in ones, as a numbered list. Answer with a number or a name.
- **"List tones"** shows the tones: professional, formal, casual, friendly, modest, confident, intimate, playful, direct, diplomatic, empathetic and persuasive.
- Or just name one: **"in a formal tone"**, **"make it slightly warmer"**, **"very casual"**.

A tone changes how your voice speaks, not who is speaking. You can describe a tone of your own and ask GeodeQuill to save it.

You can keep several voices: a work voice, a casual voice, a character. GeodeQuill also comes with five built-in voices of famous authors whose books are free of copyright: Mark Twain, Jane Austen, Charles Dickens, Abraham Lincoln and Oscar Wilde. Say **"write this like Jane Austen"**, or pick one from the list. You can build others the same way. Writing in a real person's voice is always labelled "in the style of" them.

## 6. Where your voices are kept

On your computer, in a folder named `.geodequill` inside your home folder. Every AI tool on that computer can use the same voices.

**In ChatGPT, in Claude on the web, and in phone apps,** each chat starts fresh and can't keep files. At the end of setup, GeodeQuill gives you your voice as a file or as text. Save it, and attach or paste it at the start of any chat where you want your voice.

## 7. What it won't do

- It won't promise to get past AI detectors. They guess, and they're often wrong.
- It won't invent memories, quotes, numbers or opinions and put them in your mouth.
- It won't use tricks like invisible characters or deliberate typos.
- It won't check every language the same way. It writes in any language; if you don't say which, it writes in the language you asked in. It looks for machine-writing phrases in English, Chinese (simplified and traditional) and Spanish. In every language it checks punctuation, layout and paragraph rhythm, and sentence rhythm wherever the writing marks where sentences end (Thai, Lao and Tibetan don't). For a language with no phrase list, its report says when the phrase check didn't run.

## 8. If something seems off

- **It doesn't sound like you:** give it more samples, especially casual ones, and say "update my voice".
- **It asks to set up a voice when you already have one:** in ChatGPT, attach your saved voice file first. Elsewhere, say "list my voices" to check it's there.
- **It doesn't seem to be using GeodeQuill** (no voice, no "in the style of" label, no note at the end): start the request with "Use GeodeQuill to…".
- **It says it can't run its checker:** the tool has no Python. GeodeQuill still works and checks the draft by reading it instead.

## 9. Tell us what's wrong

Found a fault, or a claim that doesn't hold up? Email **quill@geodeforge.com**. An example helps a lot, but leave it out if it's private. A person reads every message.

GeodeQuill is free and open source under the MIT licence. The code is at github.com/GeodeForge/geodequill.
