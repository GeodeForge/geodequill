import { loadPyodide } from "./pyodide-314.0.7/pyodide.mjs";
import { plainSummary } from "./summary.js";

const SKILL = new URL("../plugin/skills/geodequill/", import.meta.url);
const ENGINE = new URL("./pyodide-314.0.7/", import.meta.url).href;
const $ = (id) => document.getElementById(id);
let ready = null;

function say(text) {
	$("status").textContent = text;
}

function showPlain(sentences) {
	const box = $("plain");
	box.replaceChildren(...sentences.map((s) => {
		const p = document.createElement("p");
		p.textContent = s;
		return p;
	}));
	$("plainbox").hidden = sentences.length === 0;
}

function voiceName() {
	const sel = $("voice");
	if (sel.value === "own") return "your voice";
	if (!sel.value) return null;
	return sel.options[sel.selectedIndex].text;
}

async function fetchText(url) {
	const r = await fetch(url, { cache: "no-cache" });
	if (!r.ok) throw new Error("could not load " + url.pathname + " (" + r.status + ")");
	return r.text();
}

function engine() {
	if (!ready) {
		ready = (async () => {
			say("Loading the checker. The first time downloads about 12 MB, so this can take a moment.");
			const py = await loadPyodide({ indexURL: ENGINE, packageBaseUrl: ENGINE });
			py.FS.writeFile("/home/pyodide/voice_check.py", await fetchText(new URL("scripts/voice_check.py", SKILL)));
			py.runPython("import sys\nsys.path.insert(0, '/home/pyodide')\nimport voice_check");
			return py;
		})();
		ready.catch(() => {
			ready = null;
		});
	}
	return ready;
}

function takeVoice() {
	if (location.hash !== "#own") return;
	let text = null;
	try {
		text = sessionStorage.getItem("geodequill-voice");
		sessionStorage.removeItem("geodequill-voice");
	} catch (e) {
		text = null;
	}
	if (!text) return;
	$("voice").value = "own";
	$("ownbox").hidden = false;
	$("ownvoice").value = text;
	say("Your new voice is filled in. Paste a draft above and press Check it.");
}

takeVoice();

$("voice").addEventListener("change", () => {
	$("ownbox").hidden = $("voice").value !== "own";
});

$("checkform").addEventListener("submit", async (ev) => {
	ev.preventDefault();
	const draft = $("draft").value;
	if (!draft.trim()) {
		say("Paste a draft first.");
		return;
	}
	const voice = $("voice").value;
	if (voice === "own" && !$("ownvoice").value.trim()) {
		say("Paste your saved voice, or pick another option.");
		return;
	}
	$("go").disabled = true;
	$("report").textContent = "";
	showPlain([]);
	try {
		const py = await engine();
		say("Checking…");
		let profile = "";
		let ptxt = "";
		if (voice === "own") {
			profile = "your voice";
			ptxt = $("ownvoice").value;
		} else if (voice) {
			profile = voice;
			ptxt = await fetchText(new URL("voices/" + voice + ".md", SKILL));
		}
		const args = py.toPy({ raw: draft, ptxt, profile, register: $("register").value, lang: $("lang").value });
		py.globals.set("ARGS", args);
		const report = py.runPython(
			"voice_check.scan_report(ARGS['raw'], ARGS['ptxt'] or None, ARGS['profile'] or None, " +
				"ARGS['register'], None, ARGS['lang'] or None)",
		);
		args.destroy();
		$("report").textContent = report;
		showPlain(plainSummary(report, voiceName()));
		say("Done. Nothing you pasted left this page.");
	} catch (err) {
		say("The checker could not run in this browser: " + (err && err.message ? err.message : err));
	} finally {
		$("go").disabled = false;
	}
});
