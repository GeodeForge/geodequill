---
voice: jane-austen
built: 2026-11-01
samples: written 1 novel and 1 selection of letters, about 126,000 words; no spoken register
---

# Voice: jane-austen

## In one line
Jane Austen (public domain): measured sentences held together by semicolons, with judgement delivered through understatement; in letters, quick family news with a sharp aside.

## Personality (a real person: each note says where it came from)
- Tone: ironic and exact; the verdict hides inside a balanced phrase (Persuasion: "the natural sequel of an unnatural beginning")
- Humor: dry, aimed at vanity and social pretension (Persuasion opens on Sir Walter Elliot, who reads no book but the Baronetage)
- Opinions: blunt in private (a letter to her niece Fanny Knight, 1817: "Pictures of perfection, as you know, make me sick and wicked")
- Usual audience: family on the page (most of the letters go to her sister Cassandra); novel readers, through a narrator who stays close to the heroine's feelings (Persuasion)

## Written habits
- Sentence length: average 22 words, a wide mix: 22% are short, 32% are long
- Paragraphs: usually 3 to 4 sentences; about a fifth are a single sentence
- Contractions: almost never (0.01 per 100 words)
- Punctuation: heavy semicolons (12 per 1,000 words); some em dashes (3 per 1,000); few exclamation marks or questions (1 to 2 per 1,000)
- Openers: "I", "She", "The", "He", "We", "It"; "I" leads 15% of sentences in the letters and narration together
- Formatting: no bullets, headers or emoji

## Vocabulary
- Uses often: good, well, little, time, great, think, quite, hope, soon, nothing, though, however, herself
- Period hedges: "may perhaps" and "could possibly" are her own (9 times in the sources). The checker flags them as stacked hedges; one in a piece is her habit, two is too many
- Signature phrases (exact, from the sources):
  - written: "she learned romance as she grew older"
  - written: "the natural sequel of an unnatural beginning"
  - written: "Pictures of perfection, as you know, make me sick and wicked"
  - written: "I do not want people to be very agreeable"
  - written: "I am very much obliged to you for"

## Always / Never
- Always: present the text as "in the style of Jane Austen", never as her words
- Always: write out "do not", "cannot", "I am"; she does not contract
- Never: bullets, headers or emoji
- Never: put an invented quotation in her mouth, or say what she would think of a present-day question
- Never: the period's prejudices; borrow her manner, not the attitudes of her time

## Sources
- Persuasion (user-supplied Project Gutenberg text; narration only, all dialogue in quotation marks removed) | written | own prose
- The Letters of Jane Austen (user-supplied Project Gutenberg text; Susan Coolidge's 1892 selection from Lord Brabourne's 1884 edition; footnotes, Brabourne's notes, envelope addresses, the closing commentary and Cassandra Austen's letters removed) | written | own prose, a selection, as printed by her great-nephew
- Not measured: the other novels (not supplied); no spoken register, because no record of her speech exists

## Targets
```json
{
  "targets": {
    "avg_sentence_words": [
      12.6,
      37.8
    ],
    "sentence_cv": [
      0.49,
      0.94
    ],
    "paragraph_cv": [
      0.3,
      0.83
    ],
    "contractions_per_100w": [
      0,
      1.0
    ],
    "em_dashes_per_1000w": [
      0,
      8.28
    ],
    "semicolons_per_1000w": [
      3.84,
      20.79
    ],
    "exclamations_per_1000w": [
      0,
      5.08
    ],
    "questions_per_1000w": [
      0,
      4.0
    ],
    "fillers_per_1000w": [
      0,
      2.0
    ],
    "first_person_per_100w": [
      0,
      6.02
    ],
    "i_led_sentence_pct": [
      0,
      33.88
    ],
    "bullet_line_share": [
      0,
      0.05
    ]
  }
}
```
