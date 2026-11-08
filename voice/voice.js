import { loadPyodide } from "../check/pyodide-314.0.7/pyodide.mjs";

const SKILL = new URL("../plugin/skills/geodequill/", import.meta.url);
const ENGINE = new URL("../check/pyodide-314.0.7/", import.meta.url).href;
const HANDOFF = "geodequill-voice";
const $ = (id) => document.getElementById(id);
let ready = null;
let measured = null;

const HELPERS = `
import json
import voice_check as vc

def gq_sample(raw, lang):
    info = vc.resolve_language(raw, lang or None)
    hits, mild = vc.find_tells(raw, info["code"])
    strong = [h[2] for h in hits if h[1] != "stock word" and h[1] not in vc.FORMAT_KINDS]
    return json.dumps({"words": vc.wc(vc.prose_only(raw)), "strong": strong, "tag": info["tag"],
                       "lists": bool(info["lists"])}, ensure_ascii=False)

def gq_measure(texts, lang):
    texts = list(texts)
    return json.dumps({"stats": vc.stats_result(texts, None, False, True, lang or None),
                       "habits": vc.habits_result(texts, lang or None)}, ensure_ascii=False)
`;

const STOP = new Set(("the a an and or but of to in on at for with from by as is are was were be been it its this that " +
	"these those i you he she we they me him her us them my your his our their not no so if then than there here " +
	"what which who when where how all any some just very can will would could should have has had do does did").split(" "));

const LANGS = { en: "English", zh: "Chinese", es: "Spanish", fr: "French", de: "German", pt: "Portuguese", it: "Italian",
	nl: "Dutch", ja: "Japanese", ko: "Korean", vi: "Vietnamese", ru: "Russian", ar: "Arabic", hi: "Hindi", tr: "Turkish",
	pl: "Polish", th: "Thai" };

function say(text) {
	$("status").textContent = text;
}

async function fetchText(url) {
	const r = await fetch(url, { cache: "no-cache" });
	if (!r.ok) throw new Error("could not load " + url.pathname + " (" + r.status + ")");
	return r.text();
}

function engine() {
	if (!ready) {
		ready = (async () => {
			say("Loading the measuring engine. The first time downloads about 12 MB, so this can take a moment.");
			const py = await loadPyodide({ indexURL: ENGINE, packageBaseUrl: ENGINE });
			py.FS.writeFile("/home/pyodide/voice_check.py", await fetchText(new URL("scripts/voice_check.py", SKILL)));
			py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')\n" + HELPERS);
			return py;
		})();
		ready.catch(() => {
			ready = null;
		});
	}
	return ready;
}

function call(py, fn, a, b) {
	const f = py.globals.get(fn);
	const arg = Array.isArray(a) ? py.toPy(a) : a;
	try {
		return JSON.parse(f(arg, b));
	} finally {
		if (arg !== a) arg.destroy();
		f.destroy();
	}
}

function split(text) {
	return text.split(/^[ \t]*-{3,}[ \t]*$/m).map((s) => s.trim()).filter((s) => /[\p{L}\p{N}]/u.test(s));
}

function langName(tag) {
	const code = String(tag || "").split("-")[0];
	return LANGS[code] || null;
}

function roughLimit(stats) {
	if (stats.counted_in !== "characters") return 600;
	const code = String(stats.language || "").split("-")[0];
	return code === "ja" ? 1440 : 900;
}

function num(n) {
	return Math.round(n).toLocaleString("en-US");
}

function phrases(texts, unit, max) {
	if (unit === "characters") return [];
	const counts = new Map();
	for (const t of texts) {
		for (const sent of t.split(/(?<=[.!?…])\s+|\n+/)) {
			const toks = [...sent.matchAll(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu)];
			for (let n = 3; n <= 8; n++) {
				for (let i = 0; i + n <= toks.length; i++) {
					const last = toks[i + n - 1];
					const s = sent.slice(toks[i].index, last.index + last[0].length).replace(/\s+/g, " ");
					counts.set(s, (counts.get(s) || 0) + 1);
				}
			}
		}
	}
	const bare = (w) => w.replace(/[^\p{L}\p{N}'’-]/gu, "").toLowerCase();
	const meaningful = (s) => {
		const ws = s.split(" ");
		return !STOP.has(bare(ws[ws.length - 1])) && ws.some((w) => bare(w).length >= 4 && !STOP.has(bare(w)));
	};
	const cands = [...counts].filter(([s, c]) => c >= 2 && meaningful(s))
		.sort((x, y) => y[1] - x[1] || y[0].length - x[0].length);
	const kept = [];
	for (const [s, c] of cands) {
		if (kept.some(([k, kc]) => kc >= c && k.includes(s))) continue;
		kept.push([s, c]);
		if (kept.length >= max) break;
	}
	return kept;
}

function paragraph(cls, text) {
	const p = document.createElement("p");
	if (cls) p.className = cls;
	p.textContent = text;
	return p;
}

function listPicks(box, list) {
	box.replaceChildren();
	if (!list.length) {
		box.append(paragraph("hint", "None repeat often enough to suggest. You can type your own below."));
		return;
	}
	list.forEach(([s, c], i) => {
		const label = document.createElement("label");
		label.className = "pick";
		const cb = document.createElement("input");
		cb.type = "checkbox";
		cb.value = s;
		cb.id = box.id + "-" + i;
		const span = document.createElement("span");
		span.textContent = "“" + s + "”, " + c + " times";
		label.append(cb, span);
		box.append(label);
	});
}

function describeRegister(name, pieces, stats) {
	const unit = stats.counted_in === "characters" ? "characters" : "words";
	let line = name + ": " + pieces + (pieces === 1 ? " piece" : " pieces") + ", about " + num(stats.words) + " " + unit;
	const ln = langName(stats.language);
	line += ln ? ", measured as " + ln + "." : ".";
	if (stats.reading_level) line += " Reading level: " + stats.reading_level + ".";
	return line;
}

$("sampleform").addEventListener("submit", async (ev) => {
	ev.preventDefault();
	const written = split($("written").value);
	const spoken = split($("spoken").value);
	if (!written.length) {
		say("Paste some things you wrote first.");
		$("written").focus();
		return;
	}
	const lang = $("lang").value;
	$("measure").disabled = true;
	try {
		const py = await engine();
		say("Measuring…");
		const notes = [];
		const regs = [["written", "Your writing", written], ["spoken", "Your speaking", spoken]];
		const result = { lang, regs: {} };
		for (const [key, label, texts] of regs) {
			if (!texts.length) continue;
			const m = call(py, "gq_measure", texts, lang);
			const stats = m.stats;
			result.regs[key] = { texts, stats, habits: m.habits, sizes: [] };
			notes.push(["", describeRegister(label, texts.length, stats)]);
			if (/assumed|could not be told/.test(stats.language_how || "")) {
				notes.push(["warn", label + ": the language could not be told for sure. If it is not " +
					(langName(stats.language) || "what it guessed") + ", choose the language above and measure again."]);
			}
			if (stats.words < roughLimit(stats)) {
				notes.push(["", label + " is under " + num(roughLimit(stats)) + " " + stats.counted_in +
					", so its ranges will be rough. More samples make them steadier."]);
			}
			if (texts.length < 3) {
				notes.push(["", label + ": with fewer than three pieces the ranges are widened to be safe. Three or more pieces give truer ranges."]);
			}
			const label1 = key === "written" ? "Writing sample " : "Speaking sample ";
			texts.forEach((t, i) => {
				const s = call(py, "gq_sample", t, lang);
				result.regs[key].sizes.push(s.words);
				const per1000 = s.words ? (s.strong.length * 1000) / s.words : 0;
				if (s.strong.length >= 3 && per1000 >= 3) {
					notes.push(["warn", label1 + (i + 1) + " has " + s.strong.length + " phrases that machine-written text leans on (" +
						s.strong.slice(0, 5).map((x) => "“" + x + "”").join(", ") + "). If a tool helped write it, leave it out " +
						"or swap in something you wrote yourself, then measure again."]);
				} else if (s.strong.length) {
					notes.push(["", label1 + (i + 1) + " has " + s.strong.length + (s.strong.length === 1 ? " phrase" : " phrases") +
						" that machine-written text often uses (" + s.strong.slice(0, 3).map((x) => "“" + x + "”").join(", ") +
						"). Some are ordinary in business writing, so this is only a hint."]);
				}
				const sl = String(s.tag).split("-")[0];
				const rl = String(stats.language).split("-")[0];
				if (!lang && s.words >= 150 && LANGS[sl] && LANGS[rl] && sl !== rl) {
					notes.push(["warn", label1 + (i + 1) + " looks like " + LANGS[sl] + ", and the rest like " + LANGS[rl] +
						". A voice holds one language: make a separate voice for each."]);
				}
			});
		}
		const wl = result.regs.written.stats.language;
		if (result.regs.spoken && String(result.regs.spoken.stats.language).split("-")[0] !== String(wl).split("-")[0]) {
			notes.push(["warn", "Your writing and your speaking were measured as different languages. A voice holds one language."]);
		}
		$("found").replaceChildren(...notes.map(([cls, text]) => paragraph(cls, text)));
		for (const key of ["written", "spoken"]) {
			const r = result.regs[key];
			$(key + "picks").hidden = !r;
			$(key + "own").value = "";
			if (r) {
				r.picks = phrases(r.texts, r.stats.counted_in, 8);
				listPicks($(key + "list"), r.picks);
			}
		}
		measured = result;
		$("out").hidden = true;
		$("aboutform").hidden = false;
		say("Measured. Nothing you pasted left this page. Choose your phrases below, then make the voice file.");
		$("foundhead").focus();
	} catch (err) {
		say("The measuring could not run in this browser: " + (err && err.message ? err.message : err));
	} finally {
		$("measure").disabled = false;
	}
});

function slug(name) {
	const s = name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
	return s || "my-voice";
}

function today() {
	const d = new Date();
	return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
}

function mix(cv) {
	if (cv < 0.4) return "fairly even lengths";
	if (cv < 0.7) return "some short, some long";
	return "a wide mix of short and long";
}

function often(per100) {
	if (per100 >= 3) return "often";
	if (per100 >= 1.5) return "fairly often";
	if (per100 >= 0.5) return "now and then";
	if (per100 > 0) return "rarely";
	return "never";
}

function rate(per1000, what) {
	if (!per1000) return "no " + what;
	if (per1000 < 1) return what + " rarely";
	return what + " about " + (Math.round(per1000 * 10) / 10) + " per 1,000 words";
}

function openers(habits) {
	const en = String(habits.language || "").startsWith("en");
	const o = Object.entries(habits.sentence_openers_pct || {}).filter(([w, p]) => p >= 4 && /^[\p{L}\p{N}]/u.test(w)).slice(0, 4);
	if (!o.length) return null;
	return "sentences often start with " + o.map(([w, p]) => "“" + (en && w === "i" ? "I" : w) + "” (" + p + "%)").join(", ");
}

function contractions(per100) {
	return per100 ? "contractions " + often(per100) : "no contractions";
}

function targetsBlock(t) {
	const reg = (obj) => Object.entries(obj).map(([k, v]) => "    " + JSON.stringify(k) + ": " + (Array.isArray(v) ? "[" + v.join(", ") + "]" : JSON.stringify(v))).join(",\n");
	const parts = Object.entries(t).map(([k, v]) => "  " + JSON.stringify(k) + ": {\n" + reg(v) + "\n  }");
	return "{\n" + parts.join(",\n") + "\n}";
}

function chosen(key, r) {
	const words = r.stats.counted_in === "characters";
	const ticked = [...$(key + "list").querySelectorAll("input:checked")].map((c) => c.value);
	const typed = $(key + "own").value.split("\n").map((s) => s.trim().replace(/\s+/g, " ")).filter(Boolean);
	const hay = r.texts.join("\n").replace(/\s+/g, " ");
	const ok = [];
	const bad = [];
	for (const p of [...ticked, ...typed]) {
		const short = words ? [...p].length <= 20 : p.split(" ").length < 12;
		if (!hay.includes(p) || !short) bad.push(p);
		else if (!ok.includes(p)) ok.push(p);
	}
	return { ok: ok.slice(0, 5), dropped: ok.length > 5, bad };
}

function habitLines(r, spokenOf) {
	const s = r.stats;
	const h = r.habits;
	const unit = s.counted_in === "characters" ? "characters" : "words";
	const out = [];
	if (s.avg_sentence_words !== undefined) {
		let l = "- Sentence length: average " + s.avg_sentence_words + " " + unit + ", " + mix(s.sentence_cv);
		if (spokenOf && spokenOf.avg_sentence_words !== undefined) l += "; in writing " + spokenOf.avg_sentence_words;
		out.push(l);
	}
	if (s.reading_lix !== undefined) out.push("- Reading level: " + s.reading_level + " (reading_lix " + s.reading_lix + ")");
	if (!spokenOf && h.avg_sentences_per_paragraph !== undefined) {
		const one = h.one_sentence_paragraph_pct ? h.one_sentence_paragraph_pct + "% are one sentence long" : "none are one sentence long";
		out.push("- Paragraphs: usually " + h.avg_sentences_per_paragraph + " sentences; " + one);
	}
	if (s.contractions_per_100w !== undefined) {
		out.push("- Contractions: " + (s.contractions_per_100w ? often(s.contractions_per_100w) + ", about " +
			s.contractions_per_100w + " per 100 words" : "none in the samples"));
	}
	if (spokenOf) {
		if (s.fillers_per_1000w !== undefined) out.push("- Fillers and turns: " + rate(s.fillers_per_1000w, "fillers"));
		out.push("- Questions to the audience: " + rate(s.questions_per_1000w, "questions"));
	} else {
		out.push("- Punctuation: " + [rate(s.em_dashes_per_1000w, "em dashes"), rate(s.semicolons_per_1000w, "semicolons"),
			rate(s.exclamations_per_1000w, "exclamation marks"), rate(s.questions_per_1000w, "question marks")].join("; "));
	}
	const op = openers(h);
	if (op) out.push("- Openers: " + op);
	if (!spokenOf) {
		const lay = $("layout").value.trim();
		const bullets = s.bullet_line_share ? "bullet points on " + Math.round(s.bullet_line_share * 100) + "% of lines" : "no bullet points in the samples";
		out.push("- Formatting: " + bullets + (lay ? "; in your words: " + lay : ""));
	}
	return out;
}

function oneLine(w) {
	const s = w.stats;
	const parts = [];
	if (s.avg_sentence_words !== undefined) {
		parts.push("sentences average " + s.avg_sentence_words + (s.counted_in === "characters" ? " characters" : " words") +
			" (" + mix(s.sentence_cv) + ")");
	}
	if (s.contractions_per_100w !== undefined) parts.push(contractions(s.contractions_per_100w));
	parts.push(rate(s.exclamations_per_1000w, "exclamation marks"));
	return parts.join("; ").replace(/^./, (c) => c.toUpperCase()) + ".";
}

function buildVoice() {
	const w = measured.regs.written;
	const sp = measured.regs.spoken;
	const name = slug($("name").value);
	const lang = String(w.stats.language || "und");
	const L = [];
	let samples = "written " + w.texts.length + ", about " + num(w.stats.words) + " " + w.stats.counted_in;
	if (sp) samples += "; spoken " + sp.texts.length + ", about " + num(sp.stats.words) + " " + sp.stats.counted_in;
	L.push("---", "voice: " + name, "built: " + today(), "language: " + lang, "samples: " + samples, "---", "", "# Voice: " + name, "");
	L.push("## In one line", $("oneline").value.trim() || oneLine(w), "");
	const manner = $("manner").value.trim();
	const audience = $("audience").value.trim();
	if (manner || audience) {
		L.push("## Personality (the user's words)");
		if (manner) L.push("- In their words: " + manner);
		if (audience) L.push("- Usual audience: " + audience);
		L.push("");
	}
	L.push("## Written habits", ...habitLines(w, null), "");
	if (sp) L.push("## Spoken habits", ...habitLines(sp, w.stats), "");
	const loves = $("loves").value.trim();
	const never = $("never").value.trim();
	const wp = chosen("written", w);
	const spp = sp ? chosen("spoken", sp) : { ok: [], dropped: false, bad: [] };
	const vocab = [];
	if (loves) vocab.push("- Uses often (in their words): " + loves);
	if (never) vocab.push("- Never uses: " + never);
	if (wp.ok.length || spp.ok.length) {
		vocab.push("- Signature phrases (at most five per register, each under twelve words, exact):");
		wp.ok.forEach((p) => vocab.push("  - written: \"" + p + "\""));
		spp.ok.forEach((p) => vocab.push("  - spoken: \"" + p + "\""));
	}
	if (vocab.length) L.push("## Vocabulary", ...vocab, "");
	L.push("## Sources");
	w.texts.forEach((t, i) => L.push("- Writing sample " + (i + 1) + ", about " + num(w.sizes[i]) + " " + w.stats.counted_in + " | written | own prose"));
	if (sp) sp.texts.forEach((t, i) => L.push("- Speaking sample " + (i + 1) + ", about " + num(sp.sizes[i]) + " " + sp.stats.counted_in + " | spoken | verbatim"));
	L.push("", "## Targets");
	if (w.stats.words < roughLimit(w.stats)) L.push("- Written ranges are rough: built from under " + num(roughLimit(w.stats)) + " " + w.stats.counted_in + ".");
	if (sp && sp.stats.words < roughLimit(sp.stats)) L.push("- Spoken ranges are rough: built from under " + num(roughLimit(sp.stats)) + " " + sp.stats.counted_in + ".");
	const targets = { targets: w.stats.suggested.targets };
	if (sp) targets.targets_spoken = sp.stats.suggested.targets;
	targets.windows = { targets: w.stats.suggested.based_on_pieces };
	if (sp) targets.windows.targets_spoken = sp.stats.suggested.based_on_pieces;
	L.push("```json", targetsBlock(targets), "```", "");
	return { text: L.join("\n"), name, notes: [wp, spp] };
}

$("aboutform").addEventListener("submit", (ev) => {
	ev.preventDefault();
	if (!measured) return;
	const v = buildVoice();
	$("voicefile").value = v.text;
	$("out").hidden = false;
	const msgs = ["Your voice file is ready."];
	const bad = [...v.notes[0].bad, ...v.notes[1].bad];
	if (bad.length) msgs.push("Left out, because they do not appear exactly in your samples or are too long: " + bad.map((p) => "“" + p + "”").join(", ") + ".");
	if (v.notes[0].dropped || v.notes[1].dropped) msgs.push("Only the first five phrases per kind were kept.");
	msgs.push("Save it or copy it: it is not kept anywhere else.");
	say(msgs.join(" "));
	$("outhead").focus();
});

$("save").addEventListener("click", () => {
	const name = slug($("name").value);
	const blob = new Blob([$("voicefile").value], { type: "text/markdown;charset=utf-8" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = name + ".md";
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
	say("Saved as " + name + ".md in your downloads.");
});

$("copy").addEventListener("click", async () => {
	try {
		await navigator.clipboard.writeText($("voicefile").value);
		say("Copied. Paste it wherever you keep it.");
	} catch (e) {
		$("voicefile").focus();
		$("voicefile").select();
		say("Your browser did not allow copying. The text is selected: press Ctrl+C, or Cmd+C on a Mac.");
	}
});

$("try").addEventListener("click", () => {
	try {
		sessionStorage.setItem(HANDOFF, $("voicefile").value);
		location.href = "../check/#own";
	} catch (e) {
		say("This browser would not pass the voice to the check page. Copy it, open the check page, choose “My own voice” and paste it there.");
	}
});
