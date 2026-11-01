#!/usr/bin/env python3
"""Build the download files and the guide page from the sources.

Run from anywhere:  python3 -I build/build.py YYYY-MM-DD
The date is the release date. It is printed on the page and stamped on every file in the
archives, so the same sources and date always give byte-identical downloads.
"""
import datetime
import html
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
SKILL = os.path.join(PLUGIN, "skills", "geodequill")
OUT = os.path.join(ROOT, "download")


def files_under(base):
    found = []
    for root, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for n in sorted(names):
            if n.endswith(".pyc") or n == ".DS_Store":
                continue
            found.append(os.path.join(root, n))
    return found


def write_zip(path, entries, stamp):
    dirs = set()
    for arc, _src in entries:
        parts = arc.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]) + "/")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d in sorted(dirs):
            info = zipfile.ZipInfo(d, stamp)
            info.external_attr = (0o40755 << 16) | 0x10
            z.writestr(info, b"")
        for arc, src in sorted(entries):
            info = zipfile.ZipInfo(arc, stamp)
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(src, "rb") as f:
                z.writestr(info, f.read())


def inline(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\b([\w.+-]+@geodeforge\.com)\b", r'<a href="mailto:\1">\1</a>', t)
    t = re.sub(r"(?<![\w/@.])((?:github\.com|geodeforge\.com)(?:/[\w./-]*[\w/])?)",
               r'<a href="https://\1" rel="noopener">\1</a>', t)
    return t


def markdown_to_html(md):
    out, para, items = [], [], []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()
        if items:
            out.append("<ul>\n" + "\n".join("<li>" + inline(i) + "</li>" for i in items) + "\n</ul>")
            items.clear()

    for line in md.splitlines():
        s = line.rstrip()
        if not s:
            flush()
        elif s.startswith("# "):
            flush()
            out.append("<h1>" + inline(s[2:]) + "</h1>")
        elif s.startswith("## "):
            flush()
            out.append("<h2>" + inline(s[3:]) + "</h2>")
        elif s.startswith("- "):
            if para:
                flush()
            items.append(s[2:])
        elif items and line.startswith("  "):
            items[-1] += " " + s.strip()
        else:
            if items:
                flush()
            para.append(s)
    flush()
    return "\n".join(out)


GUIDE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>User guide — GeodeQuill</title>
<meta name="description" content="How to install GeodeQuill in ChatGPT, Claude and other AI apps, set up your voice, and pick a tone."/>
<link rel="icon" href="../assets/logo-favicon-64.png" type="image/png"/>
<link rel="canonical" href="https://geodeforge.com/geodequill/guide/"/>
<link rel="stylesheet" href="../style.css?v=1"/>
</head>
<body>
<header class="bar">
  <a class="brand" href="../"><img src="../assets/geodequill-nib.svg" alt="" width="32" height="32"/><span>GeodeQuill</span></a>
  <nav><a href="../#download">Download</a><a href="../">← Back to GeodeQuill</a></nav>
</header>

<main class="prose">
  <section>
__BODY__
    <p class="meta">Version __VERSION__ · __RELEASED__</p>
  </section>
</main>

<footer>
  <span>
    <a href="https://github.com/GeodeForge/geodequill" rel="noopener">Source</a> ·
    <a href="../privacy/">Privacy</a> ·
    <a href="mailto:quill@geodeforge.com">quill@geodeforge.com</a>
  </span>
  <span>&copy; 2026 &middot; A <a href="https://geodeforge.com/">GeodeForge</a> tool</span>
</footer>
</body>
</html>
"""


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sys.argv[1]):
        sys.exit("usage: python3 -I build/build.py YYYY-MM-DD")
    day = datetime.date.fromisoformat(sys.argv[1])
    stamp = (day.year, day.month, day.day, 0, 0, 0)
    released = f"{day.day} {day.strftime('%B')} {day.year}"
    with open(os.path.join(PLUGIN, "plugin.json"), encoding="utf-8") as f:
        version = json.load(f)["version"]
    os.makedirs(OUT, exist_ok=True)

    plugin_files = [(os.path.relpath(p, PLUGIN).replace(os.sep, "/"), p) for p in files_under(PLUGIN)]
    write_zip(os.path.join(OUT, "geodequill.plugin"), plugin_files, stamp)

    skill_files = [("geodequill/" + os.path.relpath(p, SKILL).replace(os.sep, "/"), p) for p in files_under(SKILL)]
    write_zip(os.path.join(OUT, "geodequill-skill.zip"), skill_files, stamp)

    mcp_files = [("geodequill-mcp/" + a, p) for a, p in skill_files]
    mcp_files += [("geodequill-mcp/geodequill_mcp.py", os.path.join(ROOT, "mcp", "geodequill_mcp.py")),
                  ("geodequill-mcp/README.md", os.path.join(PLUGIN, "README.md")),
                  ("geodequill-mcp/USER-GUIDE.md", os.path.join(PLUGIN, "USER-GUIDE.md"))]
    write_zip(os.path.join(OUT, "geodequill-mcp.zip"), mcp_files, stamp)

    with open(os.path.join(PLUGIN, "USER-GUIDE.md"), encoding="utf-8") as f:
        body = markdown_to_html(f.read())
    page = GUIDE.replace("__BODY__", body).replace("__VERSION__", version).replace("__RELEASED__", released)
    os.makedirs(os.path.join(ROOT, "guide"), exist_ok=True)
    with open(os.path.join(ROOT, "guide", "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(page)

    index = os.path.join(ROOT, "index.html")
    with open(index, encoding="utf-8") as f:
        text = f.read()
    text = re.sub(r'<span id="version">[^<]*</span>', f'<span id="version">{version}</span>', text)
    text = re.sub(r'<span id="released">[^<]*</span>', f'<span id="released">{released}</span>', text)
    text = re.sub(r'"softwareVersion":"[^"]*"', f'"softwareVersion":"{version}"', text)
    with open(index, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    for n in sorted(os.listdir(OUT)):
        print(f"{n}  {os.path.getsize(os.path.join(OUT, n))} bytes")
    print(f"guide/index.html and index.html set to version {version}, {released}")


if __name__ == "__main__":
    main()
