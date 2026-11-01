# Machine-writing habits to remove

Based on the public catalog "Signs of AI writing" kept by Wikipedia's WikiProject AI Cleanup, reworded and trimmed. The script catches the mechanical ones. Judgment catches the rest.

## Words and phrases

- **Stock vocabulary:** delve, tapestry, testament, pivotal, vibrant, intricate, underscore, showcase, foster, garner, multifaceted, leverage, robust, seamless, elevate, holistic, transformative. Use the plain word instead.
- **Stock phrases:** "in today's fast-paced world", "it's important to note", "plays a crucial role", "navigate the complexities", "unlock the potential", "shed light on", "at the end of the day", "when it comes to".
- **Chat leftovers:** "I hope this helps", "let me know if", "great question", "certainly!", "feel free to".
- **Grand significance:** calling something a game-changer, a turning point, or a lasting legacy when nothing in the text earns it.
- **Fancy stand-ins for "is" and "has":** serves as, stands as, boasts, features. Write "is" and "has".

## Sentence shapes

- **Negative parallelism:** "It's not just X, it's Y." Say Y.
- **Reflex triples:** three adjectives or three items every time. Use the number the content has.
- **Tacked-on -ing clause:** ", highlighting the importance of...", ", ensuring that...". Cut it, or make it its own sentence with a real claim.
- **Vague attribution:** "experts say", "studies show". In a draft, name the source if the writer gave one, otherwise drop the claim. In a rewrite, keep it as written and flag it in the closing line.
- **Stacked hedges:** "may potentially", "could possibly". Pick one hedge or none.
- **Question then answer:** "The result? Chaos." "Here's the thing:". State it.
- **Synonym cycling:** calling the same thing by a new name each sentence to avoid repeating a word. Repeat the word.
- **False ranges:** "from X to Y" where there is no real scale between them.

## Structure and layout

- **Wrap-up lines:** a closing sentence on every paragraph that restates it, and a final "Overall, ..." paragraph. End when the point is made.
- **Every-side balance:** "While X, it's also important to consider Y" used on every point.
- **Even rhythm:** all sentences about the same length, all paragraphs about the same size.
- **Formatting for show:** Title Case headings, a header over every short section, bold-lead bullets ("**Key point:** ..."), emoji in headings, bullets where two sentences would do.
- **Sycophantic opener:** praising the question or the idea before answering.
- **Connector pile-up:** Moreover, Furthermore, Additionally at the start of consecutive sentences.

## How strong each signal is

Measured on three collections of human writing: 23 books by Mark Twain (1.74 million words), 85,000 words of his speeches, and 141 documents that ship with ordinary software packages (192,000 words). No collection of machine-written text has been measured yet.

- **Phrases and patterns are strong.** They fired 0.2 to 0.3 times per 10,000 words in all three collections. Fix every one.
- **A single stock word is weak.** 0.6 and 1.4 per 10,000 words in the books and the software documents (intricate, testament, robust, foster, seamlessly turned up). Swap it for a plainer word if one fits. Do not hunt for it.
- **Formatting marks are weak.** Title Case headings, bold labels on bullets, and emoji fired 17 times per 10,000 words in the software documents, all written by people. Remove them from personal prose; in a README they may be the writer's habit.
- **Punctuation and contractions are the writer's habit, not machine marks.** Twain averaged about 9 em dashes and 11 semicolons per 1,000 words. Almost half the software documents used no contractions at all. Match the writer, not a rule.
- **Even rhythm is the better signal.** In every one of the 23 books, sentence-length variation stayed between 0.69 and 1.15 and paragraph-size variation between 0.68 and 1.55. One software document in 141 fell below 0.5. Only human text was measured, so low variation is a hint, not proof. These are whole-book figures; in 500-word windows the sentence floor was about 0.5.

## Check yourself

After removing these, read the text once more. If it is clean but nobody seems to be behind it, add voice using only what the writer gave you: their opinion, a real detail, a plain remark. If they gave none, ask. See `human-texture.md`.
