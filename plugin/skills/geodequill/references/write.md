# Write in a voice

The rules in `SKILL.md` apply throughout.

## Before writing

1. **Load the voice.** Use the voice the user named, or the one chosen earlier in the conversation. Otherwise follow "Choose a voice" in `SKILL.md`. If the user has no voice of their own, say so in one line and offer to set one up (`references/setup.md`) or to use a built-in voice. If the user wants a one-off, accept a pasted sample and work from it without saving.
2. **Pin down the job.** What is the piece, who reads it, and what does the writer want to say? If the piece would be much better with a real example, number, or opinion from the writer and none was given, ask for it in one short line. If they say to just write it, write it.
3. **Pick the tone.** Use the tone the user named or chose earlier in the conversation (see "Choose a tone" in `SKILL.md`). With none, write in the voice's natural tone. Follow `references/tones.md` for what the tone shifts and what it leaves alone.
4. **Pick the register.** Use the profile's spoken habits for things meant to be heard or read like talk: speeches, toasts, talks, podcast or video scripts, interview answers, chat messages, casual replies. Use the written habits for essays, articles, letters, reports, and posts. A piece can mix them, such as a written letter with a spoken warmth; lead with one. If the profile has no spoken habits, use the written ones. The user can name the register.

## Modes

- **Draft.** Write a new piece from the user's notes or request.
- **Rewrite.** The user pastes text. Keep the substance, change the voice.
- **Stay in voice.** If the user says "stay in my voice" or similar, apply this job to all prose you write for the rest of the conversation, until they say stop. Skip the check step for short replies.

## Writing

1. Write in the profile's voice, in the chosen register and tone. Follow its sentence length, fillers, openers, contractions, punctuation, vocabulary, Always/Never lines, and personality. Show personality through word choice, what the writer notices, and attitude. Do not caricature. Use a signature phrase at most once per piece; repeating one is its own tell.
2. Add human texture. See `references/human-texture.md`.
3. **Writing in a language other than the voice's.** Carry over the voice's attitude, humour and sentence shapes, not its punctuation counts: a dash or semicolon rate measured in English does not transfer. In Chinese, more than an occasional —— reads as machine-written; so do one-line aphorisms closing every paragraph.
4. Remove machine habits. Go through `references/ai-tells.md`. Do not over-correct: stripping tells without adding voice leaves bland text that is just as noticeable.

## Check

1. Save the draft to a temporary file.
2. Run `scan <file> --profile <profile path> --lang <code>`, where the code names the language you wrote the draft in (`en`, `zh`, `es`, `fr`, `ja` and so on). Add `--register spoken` when the piece uses the spoken register and `--tone <name>` when a tone was chosen, so the checker does not flag the tone's own shifts as off-voice. If Python or the script is unavailable, skip this step and review the draft against the references by hand.
3. Fix what the report flags, using judgment. Act on strong tells and on clusters. A single stock word or formatting mark is weak evidence, and a flagged word or phrase that the profile says the writer uses is fine. The profile ranges fit pieces of about 250 words or more; on shorter drafts treat range misses as hints. A rhythm flag (sentences too even) is a hint, not proof: rewrite a flat stretch if one reads flat, but do not split or merge sentences only to change the number. If the report says phrases and words were not checked for this language, review the draft against `references/ai-tells.md` by reading it. Rerun once. Stop after two rounds. Do not show the report to the user.

## Deliver

Give the text with nothing before it. After it, add a closing note of one or two short sentences, covering only what applies, in the language of the reply:

- open placeholders, or one fact you could not verify;
- for a real person other than the user, that the text is in the style of that person;
- when the draft is in a language other than the voice's, that the voice was measured in that other language, so only rhythm and layout were compared;
- for a language with no phrase lists, that the phrase check did not run and you reviewed the wording by reading it.

No lecture, no "here is your humanized version".
