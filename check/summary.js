
const FORMAT_KINDS = new Set(["Title Case heading", "bold-lead bullet", "emoji"]);

const MEASURES = {
	avg_sentence_words: ["shorter sentences", "longer sentences"],
	sentence_cv: ["sentence lengths that vary less", "sentence lengths that vary more"],
	paragraph_cv: ["paragraph lengths that vary less", "paragraph lengths that vary more"],
	contractions_per_100w: ["fewer contractions (like \"it's\" and \"don't\")", "more contractions (like \"it's\" and \"don't\")"],
	em_dashes_per_1000w: ["fewer long dashes (—)", "more long dashes (—)"],
	semicolons_per_1000w: ["fewer semicolons", "more semicolons"],
	exclamations_per_1000w: ["fewer exclamation marks", "more exclamation marks"],
	questions_per_1000w: ["fewer questions", "more questions"],
	fillers_per_1000w: ["fewer spoken fillers (like \"well,\" or \"you know\")", "more spoken fillers (like \"well,\" or \"you know\")"],
	first_person_per_100w: ["less \"I\", \"me\" and \"my\"", "more \"I\", \"me\" and \"my\""],
	i_led_sentence_pct: ["fewer sentences that start with \"I\"", "more sentences that start with \"I\""],
	bullet_line_share: ["fewer bulleted lines", "more bulleted lines"],
};

function plural(n, one, many) {
	return n === 1 ? one : many;
}

function section(lines, title) {
	const start = lines.findIndex((l) => l.startsWith(title));
	if (start < 0) return null;
	const out = [];
	for (let i = start + 1; i < lines.length && lines[i].trim() !== ""; i++) out.push(lines[i]);
	return out;
}

function listed(items) {
	if (items.length <= 1) return items.join("");
	return items.slice(0, -1).join(", ") + " and " + items[items.length - 1];
}

export function plainSummary(report, voiceLabel) {
	if (!report) return [];
	if (report.startsWith("Nothing to check")) return ["There was nothing to check: the draft has no words."];
	const lines = report.split("\n");
	const out = [];
	const sum = report.match(/^Summary: (\d+) strong tells, (\d+) stock words and (\d+) formatting marks .*?, (\d+) habits off\./m);
	if (!sum) return ["The report is below."];
	const [strong, weak, fmt] = [Number(sum[1]), Number(sum[2]), Number(sum[3])];
	const noLists = /not checked for this language|none for this language yet/.test(report);

	const tells = section(lines, "== Machine-writing tells ==") || [];
	const examples = [];
	for (const l of tells) {
		const m = l.match(/^line \d+: (.+?): "(.*)"$/);
		if (m && m[1] !== "stock word" && !FORMAT_KINDS.has(m[1]) && examples.length < 3 && !examples.includes(`"${m[2]}"`)) {
			examples.push(`"${m[2]}"`);
		}
	}
	if (noLists) {
		out.push("GeodeQuill has no phrase list for this language yet, so it checked only punctuation, layout and rhythm.");
	} else if (strong > 0) {
		out.push(`It found ${strong} ${plural(strong, "phrase or pattern", "phrases or patterns")} that machine-written text leans on` +
			(examples.length ? `, for example ${listed(examples)}` : "") + ". Those lines are the first to rewrite in your own words.");
	} else {
		out.push("It found none of the phrases or patterns on its list.");
	}
	if (weak > 0) {
		out.push(`It also found ${weak} overused ${plural(weak, "word", "words")}. Real writers use these too, so they only matter in a crowd.`);
	}
	if (fmt > 0) {
		out.push(`It found ${fmt} formatting ${plural(fmt, "mark", "marks")} (a Title Case heading, a bold start to a bullet, or an emoji). These are fine on their own.`);
	}
	const mild = tells.find((l) => l.startsWith("mild connectors, worth thinning: "));
	if (mild) {
		const words = [...mild.slice("mild connectors, worth thinning: ".length).matchAll(/\s*([^,]+?),? x(\d+)/g)]
			.map((m) => `"${m[1].trim()}" (${m[2]} times)`);
		if (words.length) out.push(`Some linking words come up often: ${listed(words)}. Using fewer would help.`);
	}

	const versus = section(lines, "== Versus the voice profile");
	if (versus) {
		const who = voiceLabel || "the voice";
		const off = [];
		let judged = 0;
		let short = false;
		let shortSkips = 0;
		let langSkips = 0;
		for (const l of versus) {
			const m = l.match(/^(\w+): (-?[\d.]+) \(profile (-?[\d.]+) to (-?[\d.]+)\) (.*)$/);
			if (!m) {
				if (/: not measured for this language$/.test(l)) langSkips++;
				continue;
			}
			const [key, val, lo, hi, state] = [m[1], Number(m[2]), Number(m[3]), Number(m[4]), m[5]];
			if (state.startsWith("not judged")) {
				if (state.includes("different language")) langSkips++;
				else shortSkips++;
				continue;
			}
			judged++;
			if (state.startsWith("OUTSIDE")) {
				if (state.includes("short text")) short = true;
				const words = MEASURES[key] || [`less ${key}`, `more ${key}`];
				off.push(val < lo ? words[0] : words[1]);
			}
		}
		const other = report.match(/\(the voice was measured in (.+?) and this text is (.+?): /);
		if (other) {
			out.push(`${who} was measured in ${other[1]} and this draft is in ${other[2]}, so only the measures that don't depend on language were compared.`);
		}
		if (judged === 0) {
			out.push(`None of the measures could be compared with ${who}.`);
		} else if (off.length === 0) {
			out.push(judged === 1
				? `It matches ${who}'s measured habits on the one measure it could compare.`
				: `It matches ${who}'s measured habits on all ${judged} measures it could compare.`);
		} else {
			out.push(`Compared with ${who}, ${off.length} of ${judged} ${plural(judged, "measure", "measures")} ${plural(off.length, "is", "are")} outside the voice's range. The draft has ${listed(off)}.` +
				(short ? " The draft is short, so treat these as hints." : ""));
		}
		if (shortSkips > 0) {
			out.push(`${shortSkips} more ${plural(shortSkips, "measure needs", "measures need")} a longer draft (more sentences or paragraphs) before ${plural(shortSkips, "it", "they")} can be compared.`);
		}
	} else {
		const general = section(lines, "== General checks ==") || [];
		const flags = general.filter((l) => l !== "nothing flagged" && !l.startsWith("("));
		if (flags.length) {
			out.push("Rhythm: " + flags.map((f) => f.replace(/ \(variation [\d.]+\)/, "")).join("; ") + ".");
		}
	}
	if (/English was assumed, not identified/.test(report)) {
		out.push("It assumed the draft is English. If it isn't, pick its language above and check again.");
	}
	return out.map((x) => x.charAt(0).toUpperCase() + x.slice(1));
}
