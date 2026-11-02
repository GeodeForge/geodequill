# Write in a voice

The rules in `SKILL.md` apply throughout.

## Before writing

1. **Load the voice.** Use the voice the user named, or the one chosen earlier in the conversation. Otherwise follow "Choose a voice" in `SKILL.md`. If the user has no voice of their own, say so in one line and offer to set one up (`references/setup.md`) or to use a built-in voice. If the user wants a one-off, accept a pasted sample and work from it without saving.
2. **Pin down the job.** What is the piece, who reads it, and what does the writer want to say? If the piece would be much better with a real example, number, or opinion from the writer and none was given, ask for it in one short line. If they say to just write it, write it.
3. **Pick the language.** Use the language the user named. If they named none, use the language of their request for all of it, the piece and the closing note; for a rewrite, keep the language of the text. The voice's own language never decides this: an English author's voice writes Vietnamese when asked in Vietnamese.
4. **Pick the tone.** Use the tone the user named or chose earlier in the conversation (see "Choose a tone" in `SKILL.md`). With none, write in the voice's natural tone. Follow `references/tones.md` for what the tone shifts and what it leaves alone.
5. **Pick the register.** Use the profile's spoken habits for things meant to be heard or read like talk: speeches, toasts, talks, podcast or video scripts, interview answers, chat messages, casual replies. Use the written habits for essays, articles, letters, reports, and posts. A piece can mix them, such as a written letter with a spoken warmth; lead with one. If the profile has no spoken habits, use the written ones. The user can name the register.

## Modes

- **Draft.** Write a new piece from the user's notes or request.
- **Rewrite.** The user pastes text. Keep the substance, change the voice.
- **Stay in voice.** If the user says "stay in my voice" or similar, apply this job to all prose you write for the rest of the conversation, until they say stop. Skip the review for short conversational replies; a piece the user asked for (a note, letter, post) is always reviewed.

## Writing

1. Write in the profile's voice, in the chosen register and tone. Follow its sentence length, fillers, openers, contractions, punctuation, vocabulary, Always/Never lines, and personality. Show personality through word choice, what the writer notices, and attitude. Do not caricature. Use a signature phrase at most once per piece; repeating one is its own tell.
2. Add human texture. See `references/human-texture.md`.
3. **Writing in a language other than the voice's.** Write every line of the piece in that language, salutation and sign-off included. Do not drop in the voice's signature phrases in their original language; carry the idea over, or leave it out. Carry over the voice's attitude, humour and sentence shapes, not its punctuation counts: a dash or semicolon rate measured in English does not transfer. In Chinese, more than an occasional —— reads as machine-written; so do one-line aphorisms closing every paragraph.
4. Remove machine habits. Go through `references/ai-tells.md`. Do not over-correct: stripping tells without adding voice leaves bland text that is just as noticeable.

## Check

Review every piece you write in this job, however short. Only the conversational replies of "Stay in voice" skip it.

1. Read the draft once, sentence by sentence, for anything it says about the writer's life that the user did not give you: when or why they are writing ("I cannot let another day pass" says they are late), how they felt, what kind of person they are, what happened or will happen, how long people have known each other or been together, and what the other person did or how they did it (readily, at a cost, just in time). General remarks are fine; a claim about this writer or this reader is not. Cut it, or turn it into a bracketed note. Confirm the piece is in the language picked above.
2. Read it again against `references/ai-tells.md` and the voice's Always and Never lines, and fix what you find. This reading review is the check that always happens.
3. Only when the user says yes to the closing note's offer, or asks you to check a text: run the checker for exact measurements: save exactly the text you will deliver to a new temporary file with a unique name (for example from `mktemp`; never a fixed name another chat could also use), and run `scan <file> --profile <profile path> --lang <code>`, where the code names the language you wrote the draft in (`en`, `zh`, `es`, `fr`, `ja` and so on). Add `--register spoken` when the piece uses the spoken register and `--tone <name>` when a tone was chosen. If code is unavailable or the user declines it, skip this step without asking again.
4. When the checker has run, fix what it flags, using judgment. Act on strong tells and on clusters. A single stock word or formatting mark is weak evidence, and a flagged word or phrase that the profile says the writer uses is fine. The profile ranges fit pieces of about 250 words or more; on shorter drafts treat range misses as hints. A rhythm flag (sentences too even) is a hint, not proof: rewrite a flat stretch if one reads flat, but do not split or merge sentences only to change the number. If the report warns that the text reads as another language, rewrite the draft in the right one. Stop after two rounds. Do not show the report to the user.

## Deliver

Give the text with nothing before it. After it, set apart, add a closing note of one or two short sentences, covering only what applies, in the language of the reply. The note is not part of the text; keep it short so it is easy to leave out when the user copies the text.

- open placeholders, or one fact you could not verify;
- for a real person other than the user, that the text is in the style of that person;
- last, one short question offering the checker, such as "Want me to run the checker on it?" (not in "Stay in voice" replies, and not after the user says to stop asking).

Apart from that question, the note says nothing about checking: never that the piece was checked, passed or reads as human. If the user says yes and code cannot run in this app, say plainly that the checker's measurements can't run here, then go through the text again by hand against `references/ai-tells.md` and the voice's Always and Never lines and say what you changed, with no numbers, scores or ranges; never describe results of a check that did not run. No lecture, no "here is your humanized version".
