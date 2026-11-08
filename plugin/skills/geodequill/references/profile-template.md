# Voice profile layout

Save as `<name>.md` in the personal voices folder, or in the project's `voice-profiles` folder (see `SKILL.md`). Fill every section from evidence. Delete a line if there is no evidence for it. Leave out the spoken parts if there were no spoken samples.

````markdown
---
voice: <name>
built: <date>
language: <the language code from the stats output, such as en, zh or es>
samples: written <number of pieces>, about <number> words; spoken <number of pieces>, about <number> words
---

# Voice: <name>

## In one line
<One sentence: how this person sounds on the page and out loud.>

## Personality (the user's words, or for a real person, where each note came from)
- Tone: <blunt or gentle>, <formal or casual>, <dry, warm, or playful>
- Humor: <kind, or none>
- Opinions: <states them flatly / softens them / mostly stays neutral>
- Usual audience: <who>

## Written habits
- Sentence length: average <n> words, mix of <short/long>
- Reading level: <very easy / easy / standard / hard / very hard> (reading_lix <n>)
- Paragraphs: <usually n sentences; sometimes a one-line paragraph>
- Contractions: <always / mostly / rarely>
- Punctuation: <em dashes, semicolons, exclamation marks, ellipses, parentheses: how often>
- Openers: <how sentences and paragraphs usually start>
- Formatting: <bullets, headers, emoji: used or not>

## Spoken habits
- Sentence length: average <n> words; <how it differs from writing>
- Contractions: <rate>
- Fillers and turns: <"well", "now", "you know": how often>
- Questions to the audience: <how often>
- Openers: <how spoken sentences start>
- How a joke or point lands: <pause, short line, aside>

## Vocabulary
- Uses often: <words or phrases>
- Never uses: <words or phrases>
- Signature phrases (at most five per register, each under twelve words, exact):
  - written: "<phrase>"
  - spoken: "<phrase>"

## Always / Never
- Always: <habit>
- Never: <habit>

## Sources
- <title or description> | written or spoken | verbatim / own prose / reported

## Targets
```json
{
  "targets": {
    "avg_sentence_words": [12, 18],
    "reading_lix": [36, 46],
    "sentence_cv": [0.55, 0.9],
    "paragraph_cv": [0.3, 0.7],
    "contractions_per_100w": [1.5, 4],
    "em_dashes_per_1000w": [0, 2],
    "exclamations_per_1000w": [0, 1],
    "fillers_per_1000w": [0, 2],
    "bullet_line_share": [0, 0.1]
  },
  "targets_spoken": {
    "avg_sentence_words": [8, 16],
    "reading_lix": [24, 36],
    "sentence_cv": [0.6, 1.1],
    "contractions_per_100w": [2, 6],
    "fillers_per_1000w": [1, 8],
    "questions_per_1000w": [2, 12]
  },
  "windows": {
    "targets": 6,
    "targets_spoken": 4
  }
}
```
````

The Targets block is read by `voice_check.py scan --profile` (written) and `scan --profile ... --register spoken` (spoken). Keys must match the names printed by `voice_check.py stats`. Each value is `[low, high]`. `"windows"` holds the `based_on_pieces` count from `stats --targets` for each register: how many samples the ranges rest on. `learn` updates the ranges and these counts, and adds a Sources line such as `- the user's own edited text, learned 2026-11-07, about 240 words | written | own prose`.

Reading level is `reading_lix`, from `stats`: words per sentence plus the share of words longer than six letters. Its plain names: under 30 very easy, 30 to 40 easy, 40 to 50 standard, 50 to 60 hard, 60 or more very hard. `stats` prints the plain name as `reading_level`. It is measured for Latin-script text only; leave the line out when `stats` gives none.
