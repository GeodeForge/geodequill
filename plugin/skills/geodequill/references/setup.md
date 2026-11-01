# Set up a voice

Build a profile that the writing job loads later. The profile holds only what the samples show and what the user says. Never invent a habit.

Each voice can hold two registers: **written** (polished prose: essays, letters, posts, books) and **spoken** (speeches, talks, verbatim interview transcripts, voice-note transcripts). People write and talk differently, so each register is measured on its own.

## Steps

1. **Look for existing voices.** Run `voices`. If any exist, list their names and ask in the reply whether to update one or add a new one.

2. **Find out whose voice it is.**
   - **The user's own voice, or an invented character:** go to step 3.
   - **A real, named person:** follow `references/public-persona.md` first. It decides whether you may search for the person's work, how to find written and spoken sources, and how to get the text. Then continue at step 4.

3. **Ask for samples and personality in one message,** as plain text in the reply. Ask for:
   - Written samples: three or more pieces, about 600 words in total or more. Mixed kinds are best: an email, a post, a letter.
   - Spoken samples, if they have any: transcripts of talks, voice notes, or recorded conversations, about 600 words or more. Optional, but they let the voice sound right in speeches and casual replies.
   - A few words on the personality they want on the page. Offer these prompts: how would friends describe the way you talk; blunt or gentle; formal or casual; dry, warm, or playful; how strongly do you state opinions; who usually reads or hears you.
   - Words and phrases they love, words they would never use, and formatting habits (bullets, headers, emoji, exclamation marks).

   Every answer is optional. The samples matter most. Pasted text or files both work.

4. **Check and clean the samples.** Save each sample to a temporary file and label it written or spoken. Run `scan` on each. In large collections of human writing the strong-tell rate was 0.3 per 10,000 words or less in English, Chinese and Spanish, but a few of these phrases are ordinary in business writing, so treat the result as a hint. If a user's own sample shows several strong tells in a few hundred words, ask whether it was machine-assisted; if it was, ask for one they wrote themselves. Machine-written samples teach the profile the habits it should remove.

   If a sample came from a scan or a PDF copy, with lines broken mid-sentence or words split by hyphens, join the lines into paragraphs and repair split words before measuring. Strip speaker labels, timestamps, and interviewer questions from transcripts so only the person's own words remain.

5. **Measure each register separately.** For the written files, run `stats <files> --targets` and `habits <files>`. Do the same for the spoken files. The ranges come from how the person's own pieces vary, with long files cut into 500-word windows, so they fit piece-sized writing. The script widens ranges on its own when a register has only one or two pieces. The output names the language it measured and whether lengths were counted in words or in characters (Chinese and Japanese have no spaces between words). If it names the wrong language, or says it could not tell, run it again with `--lang <code>` for the language the samples are in. Copy its `language` value into the profile. Samples in two languages make two voices, one per language. Under about 600 words in a register, mark its ranges rough in the profile. With no spoken samples, leave the spoken parts out.

6. **Write the profile** using the layout in `references/profile-template.md`, as `<name>.md` in the personal voices folder (create it if missing) unless the user wants it kept with the project. Use a short lowercase name with hyphens. Rules:
   - Written ranges go under `"targets"`; spoken ranges under `"targets_spoken"`.
   - Fill the "In one line" section; the voice list shows it.
   - Record the personality in the user's own words. Do not add traits they did not state or the samples do not show.
   - Keep at most five short characteristic phrases per register, each under twelve words, copied exactly. Do not copy whole sentences or paragraphs from the samples.
   - List every source with its register and reliability in the Sources section.
   - Leave out private details from the samples (names, addresses, account numbers).

7. **Test once.** Write about 100 words on a topic the user picks in the written register, and, if there is a spoken register, a few lines as if spoken aloud. Ask whether it sounds right and what is off. Adjust the profile from the answer. One round unless they want more.

8. **Finish.** Give the user the finished profile in full, or as a file to download, and ask them to keep it: in chat apps on the web or a phone, the saved copy is gone when the chat ends. Tell the user, in plain words, where the profile is saved and how to use it: ask for "write this in my voice", or paste text and say "make this sound like me". Say plainly that nothing else is waiting on them.
