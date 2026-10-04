#!/usr/bin/env python3
"""Two checks that keep the documentation honest. Exit status 0 only when both pass.

    python3 tools/check_docs.py              # links, then docs/REFERENCE.md against the source
    python3 tools/check_docs.py --links      # links only: no Foundry needed, well under a second

  (a) Every relative link and every #anchor in every Markdown file git knows about (tracked, or new and not ignored)
      points at a file that exists and, for a Markdown target, at a heading that exists. Anchors are slugged the way
      GitHub does it; GitLab differs in one respect (it collapses a run of hyphens where GitHub keeps it), so a link
      to a heading whose two slugs differ is reported too, as not portable. http(s), mailto and other schemes are
      skipped, as is anything inside a fenced code block or a code span.
  (b) docs/REFERENCE.md is what tools/gen_reference.py produces from this tree, ignoring the commit-hash line.

Standard library only.
"""
import difflib
import os
import re
import subprocess
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.dont_write_bytecode = True          # importing gen_reference must not leave a .pyc in an unignored directory

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]\(\s*(<[^>]*>|[^()\s]*(?:\([^()\s]*\)[^()\s]*)*)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFDEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
HTML_ID = re.compile(r"<a\s+[^>]*?(?:name|id)=[\"']([^\"']+)[\"']", re.I)
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def markdown_files():
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "--", "*.md"], cwd=ROOT,
                         stdout=subprocess.PIPE, text=True, check=True).stdout
    return sorted(f for f in out.splitlines() if f and os.path.isfile(os.path.join(ROOT, f)))


def prose_lines(text):
    """(line number, line) for every line outside a fenced code block, with `code spans` blanked"""
    fence = None
    for n, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip().strip(fence[0]):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        yield n, re.sub(r"(`+)(.+?)\1", lambda s: " " * len(s.group(0)), line)


def plain(heading):
    """the text a renderer slugs: link targets, images, emphasis markers and code ticks removed"""
    h = re.sub(r"!?\[((?:[^\[\]]|\[[^\[\]]*\])*)\]\([^)]*\)", r"\1", heading)
    h = re.sub(r"<[^>]+>", "", h)
    h = h.replace("`", "")
    h = re.sub(r"(?<![\w\\])([*_]{1,3})(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", h)
    return h.replace("\\", "").strip()


def slug_github(text):
    return re.sub(r"[^\w\- ]", "", text.lower(), flags=re.UNICODE).replace(" ", "-")


def slug_gitlab(text):
    return re.sub(r"-{2,}", "-", slug_github(text))


def anchors_of(text):
    """-> ({github slug: gitlab slug}, explicit html ids). Duplicate headings get -1, -2 ... on both hosts."""
    slugs, seen_gh, seen_gl, ids = {}, {}, {}, set()
    raw = text.split("\n")
    lines = list(prose_lines(text))
    original = {n: raw[n - 1] for n, _ in lines}
    for k, (n, line) in enumerate(lines):
        title = None
        m = re.match(r"^ {0,3}(#{1,6})(?:\s+(.*?))?(?:\s+#+)?\s*$", original[n])
        if m:
            title = m.group(2) or ""
        elif k + 1 < len(lines) and line.strip() and re.match(r"^ {0,3}(=+|-+)\s*$", lines[k + 1][1]) \
                and lines[k + 1][0] == n + 1 and (k == 0 or not lines[k - 1][1].strip() or lines[k - 1][0] != n - 1):
            title = original[n].strip()
        if title is not None:
            t = plain(title)
            gh, gl = slug_github(t), slug_gitlab(t)
            c = seen_gh.get(gh, 0)
            seen_gh[gh] = c + 1
            gh_final = gh if c == 0 else "%s-%d" % (gh, c)
            c = seen_gl.get(gl, 0)
            seen_gl[gl] = c + 1
            gl_final = gl if c == 0 else "%s-%d" % (gl, c)
            slugs[gh_final] = gl_final
        for hid in HTML_ID.findall(original[n]):
            ids.add(hid)
    return slugs, ids


def check_links(files):
    problems, n_links, cache = [], 0, {}

    def anchors(path):
        if path not in cache:
            with open(path, encoding="utf-8") as f:
                cache[path] = anchors_of(f.read())
        return cache[path]

    for rel in files:
        path = os.path.join(ROOT, rel)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for n, line in prose_lines(text):
            targets = [m.group(1) for m in LINK.finditer(line)]
            d = REFDEF.match(line)
            if d:
                targets.append(d.group(1))
            for t in targets:
                t = t.strip()
                if t.startswith("<") and t.endswith(">"):
                    t = t[1:-1]
                if not t or SCHEME.match(t) or t.startswith("//"):
                    continue
                n_links += 1
                where = "%s:%d" % (rel, n)
                target, _, frag = t.partition("#")
                target = urllib.parse.unquote(target.split("?")[0])
                if target.startswith("/"):
                    dest = os.path.normpath(os.path.join(ROOT, target.lstrip("/")))     # both hosts: repository root
                elif target:
                    dest = os.path.normpath(os.path.join(os.path.dirname(path), target))
                else:
                    dest = path
                if not (dest == ROOT or dest.startswith(ROOT + os.sep)):
                    problems.append("%s: link `%s` leaves the repository" % (where, t))
                    continue
                if not os.path.exists(dest):
                    problems.append("%s: link `%s` -> no such file %s" % (where, t, os.path.relpath(dest, ROOT)))
                    continue
                if not frag:
                    continue
                if not dest.endswith(".md"):
                    if not re.fullmatch(r"L\d+(-L?\d+)?", frag):
                        problems.append("%s: link `%s` -> `#%s` on a file that is not Markdown" % (where, t, frag))
                    continue
                slugs, ids = anchors(dest)
                frag_l = urllib.parse.unquote(frag).lower()
                if frag_l in slugs:
                    if slugs[frag_l] != frag_l:
                        problems.append("%s: link `%s` -> the heading exists, but GitLab slugs it `#%s`: not portable, "
                                        "reword the heading" % (where, t, slugs[frag_l]))
                elif frag not in ids:
                    problems.append("%s: link `%s` -> no heading slugs to `#%s` in %s" % (where, t, frag, os.path.relpath(dest, ROOT)))
    return problems, n_links


def check_reference():
    import gen_reference
    path = gen_reference.OUT
    rel = os.path.relpath(path, ROOT)
    if not os.path.exists(path):
        return ["%s does not exist: run `python3 tools/gen_reference.py`" % rel]
    fresh, _ = gen_reference.generate()
    with open(path, encoding="utf-8") as f:
        committed = f.read()

    def strip(text):
        return [l for l in text.split("\n") if not l.startswith(gen_reference.COMMIT_MARKER)]

    a, b = strip(committed), strip(fresh)
    if a == b:
        return []
    diff = list(difflib.unified_diff(a, b, rel + " (committed)", rel + " (regenerated)", lineterm="", n=1))
    shown = [l if len(l) <= 240 else l[:240] + " ..." for l in diff[:40]]
    more = ["... %d more diff lines" % (len(diff) - 40)] if len(diff) > 40 else []
    return ["%s is out of date: run `python3 tools/gen_reference.py` and commit the result\n%s" % (rel, "\n".join(shown + more))]


def main(argv):
    files = markdown_files()
    problems, n_links = check_links(files)
    summary = "%d relative links in %d Markdown files" % (n_links, len(files))
    if "--links" not in argv:
        problems += check_reference()
        summary += "; docs/REFERENCE.md matches the source"
    if problems:
        for p in problems:
            print("FAIL " + p)
        print("check_docs: %d problem%s" % (len(problems), "" if len(problems) == 1 else "s"))
        return 1
    print("check_docs: OK - " + summary)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
