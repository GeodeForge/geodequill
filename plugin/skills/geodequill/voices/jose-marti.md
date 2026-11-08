---
voice: jose-marti
built: 2026-11-07
language: es
samples: written chronicles, essays, articles and letters, about 140,000 words; spoken speeches, about 13,500 words
---

# Voice: jose-marti

## In one line
José Martí (public domain): exalted, image-filled Spanish in long periods of parallel clauses; on the page a chronicle that turns to a moral, out loud an even longer climb of clauses joined by y that ends in a call to act.

## Personality (a real person: each note says where it came from)
- Tone: lofty, tender and urgent; a moral claim in every paragraph (Nuestra América, 1891: "Trincheras de ideas valen más que trincheras de piedra")
- Thinks in images from nature and the body: trunk and graft, roots, blood, hand, heart ("Injértese en nuestras repúblicas el mundo", the same essay)
- Refuses division by race (the same essay: "No hay odio de razas, porque no hay razas")
- Opens a speech by naming his audience, Cubanos, and then its cause (Tampa, November 26, 1891: "Para Cuba, que sufre, la primera palabra")
- Rarely says "yo" on the page (first person about 0.4 per 100 words); the subject is the people, the country, the cause
- Usual audience: readers of Latin American newspapers (La Nación of Buenos Aires and others), and Cuban exiles in Florida and New York

## Written habits
- Language: Spanish
- Sentence length: average 34 words, a very wide mix (sentence_cv 1.23): short exclamations beside periods of 80 words or more
- Reading level: hard (reading_lix 55.2)
- Paragraphs: about 3 or 4 sentences; a third are a single sentence
- Punctuation: many semicolons (10 per 1,000 words); opening and closing marks on questions and exclamations (¿? ¡!), each about 3 per 1,000; dashes few
- Openers: "Y" (8% of sentences), then articles ("Los", "El", "La"), "No", "En", "Pero"
- Formatting: no bullets, headers or emoji

## Spoken habits
- Sentence length: average 53 words, far longer than the page: anaphora and parallel clauses run on for 100 words or more ("le enseñaré" seven times in one sentence at Tampa)
- Reading level: very hard (reading_lix 72.2)
- Exclamations: about 7 per 1,000 words, twice the page rate; questions about 3 per 1,000, often in a run of questions that each begin "¿Qué saben"
- Openers: "Y" (11% of sentences), "Para", "Ni", "No", "Pues", "Yo"
- How a point lands: a long climb of parallel clauses, then a short motto ("Con todos, para el bien de todos")

## Vocabulary
- Uses often: patria, pueblo, hombre, alma, vida, libertad, tierra, corazón, guerra, amor, mano, sangre, sino, aquel
- Signature phrases (exact, from the sources):
  - written: "Trincheras de ideas valen más que trincheras de piedra"
  - written: "No hay odio de razas, porque no hay razas"
  - written: "Gobernante, en un pueblo nuevo, quiere decir creador"
  - written: "Dolor infinito debía ser el único nombre de estas páginas"
  - spoken: "Para Cuba, que sufre, la primera palabra"
  - spoken: "Con todos, para el bien de todos"
  - spoken: "los pinos nuevos"

## Always / Never
- Always: present the text as "in the style of José Martí", never as his words
- Always: write in the language the user asks in or names, as SKILL.md says; the voice's own language never decides it. When that language is not Spanish, say in the closing note that this voice was measured in Spanish, so its ranges will not judge the draft
- Never: bullets, headers or emoji
- Never: put an invented quotation in his mouth, or say what he would think of a present-day question, party or government, in Cuba or anywhere
- Never: the period's attitudes; borrow his manner, not the attitudes of his time

## Sources
- Los Estados Unidos, Madrid, 1915 (Internet Archive abk4784.0001.001.umich.edu; first collected 1902 to 1905): his newspaper chronicles from New York, 1881 to 1891 | written | own prose; uncorrected scan text, with misread words in places
- "Nuestra América" (1891), "La verdad sobre los Estados Unidos" (1894), "El Congreso de Washington" (1889) and "Maestros ambulantes" (1884), from Spanish Wikisource | written | own prose
- Obras completas, edited by Alberto Ghiraldo, Madrid, Atlántida, volume III (Internet Archive obras-completas_202603): "El presidio político en Cuba" (1871) and his later articles in that volume | written | own prose; uncorrected scan text
- The same edition, volume IV (Internet Archive metodos-democraticos-bases-del-partido-revolucionario-cubano-primer-discurso-seg): the article "Responsabilidades" and the letters to Manuel Mercado and Federico Henríquez y Carvajal (1895) | written | own prose; uncorrected scan text
- The same volume: the speeches at Tampa, November 26 and 27, 1891, and at Hardman Hall, New York, February 17, 1892; audience reactions removed | spoken | reported: taken down as delivered and printed afterwards; uncorrected scan text, with misread words in places
- Not measured: the editor's notes, the party's founding resolutions (adopted by a meeting), his verse
- Copyright: he died in 1895, so his own texts are public domain in the United States and in life-plus-70 countries; only his text was measured, never an editor's (Ghiraldo died in 1946, so even his notes are public domain in life-plus-70 countries since 2017)

## Targets
```json
{
  "targets": {
    "avg_sentence_words": [
      16.04,
      77.96
    ],
    "reading_lix": [
      37.39,
      93.91
    ],
    "sentence_cv": [
      0.54,
      1.28
    ],
    "paragraph_cv": [
      0.14,
      0.88
    ],
    "em_dashes_per_1000w": [
      0,
      8.02
    ],
    "semicolons_per_1000w": [
      0.0,
      23.47
    ],
    "exclamations_per_1000w": [
      0,
      9.52
    ],
    "questions_per_1000w": [
      0,
      9.7
    ],
    "first_person_per_100w": [
      0,
      1.09
    ],
    "bullet_line_share": [
      0,
      0.05
    ]
  },
  "targets_spoken": {
    "avg_sentence_words": [
      31.96,
      120.04
    ],
    "reading_lix": [
      50.32,
      138.88
    ],
    "sentence_cv": [
      0.6,
      1.14
    ],
    "paragraph_cv": [
      0,
      0.96
    ],
    "em_dashes_per_1000w": [
      0,
      4.33
    ],
    "semicolons_per_1000w": [
      4.77,
      17.85
    ],
    "exclamations_per_1000w": [
      0.69,
      15.92
    ],
    "questions_per_1000w": [
      0,
      10.04
    ],
    "first_person_per_100w": [
      0,
      1.5
    ],
    "bullet_line_share": [
      0,
      0.05
    ]
  }
}
```
