#!/usr/bin/env python3
"""Does every string the menu can draw exist in the translation table?

`tr_text()` resolves a string by matching it against kTr, and returns what it
was handed when nothing matches. That is the right behaviour for a config
value the translator never saw -- "left" is a word, not a row -- and the wrong
one for a literal written in the other language: with English set, a literal
the table cannot resolve is drawn in Chinese, and with Chinese set the same
literal is drawn in English. Nothing else catches it. The tests walk the menu
with the strict flag on and count the leaks they pass through, but a leak on a
path the walk does not take -- the achievements status line, the Controls page's
own rows -- draws exactly as clean, and a merge that keeps a call site and
drops its entry is silent.

So: read the table, read the call sites, and say which literals have no entry.
A literal is a call to tr_text with a string constant, plus every Chinese
literal in the two label tables the Controls page reads -- kActionLabels,
which tr_text is passed, and kExtras' label, which is not.

The settings tables are the fourth kind, and they are the ones that get missed:
a row's label and its note both reach the canvas through tr_text only if the
page asks for them, so they carry no tr_text of their own to find, and a note
that is missing still draws -- cut to the panel by fit(), which resolves the
string before it measures it, so the player sees a clipped line and not a
translated one. Scanning the helpers' own arguments is what closes that.

Reported as a list, and as a failure. There is no baseline: the question is not
whether the set of strings has moved, it is whether a specific string is in it,
and a baseline would only paper over the answer.
"""

import argparse
import glob
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = os.path.join(REPO_ROOT, "build", "dsperate-src")
TR_DATA = "src/frontend/sdl/tr_data.inc"

EXIT_OK = 0
EXIT_MISSING = 1

CJK = re.compile(r"[一-鿿　-〿＀-￯]")
PAIR = re.compile(r'\{"((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"\}')
TR_TEXT = re.compile(r'tr_text\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
# A display string the font draws in capitals: the language other than ours.
CAPS = re.compile(r'^(?:[A-Z0-9]+)(?:[ ,.%<>:+\-/()]*[A-Z0-9]+)*$')
# A label table is `constexpr ... kX[] = { ... };` and its entries are braced.
TABLE = re.compile(r'\b(kActionLabels|kExtras)\b[^{]*=\s*\{([^{}]*)\}', re.S)
# The settings helpers, which take the row's label and its note as their own
# string arguments and never call tr_text themselves.
HELPER = re.compile(r'\b(?:number|pick|boolean)\s*\(')


def read_table(path):
    """Return (zh, en): the two sides of kTr."""
    with open(path, encoding="utf-8") as f:
        pairs = PAIR.findall(f.read())
    return {z for z, _ in pairs}, {e for _, e in pairs}


def literals(blob):
    return [s for s in re.findall(r'"((?:[^"\\]|\\.)*)"', blob)]


def balanced(text, start):
    """From the `(` at `start`, the index just past its match."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '"':                            # not inside a string literal
            j = i + 1
            while j < len(text) and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j
        elif text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def gather(sources, tr_data):
    """Return [(kind, file, line, string)] for every string needing an entry."""
    out = []
    for path in sources:
        rel = os.path.relpath(path, REPO_ROOT)
        text = open(path, encoding="utf-8", errors="replace").read()
        for i, line in enumerate(text.splitlines(), 1):
            for s in TR_TEXT.findall(line):
                out.append(("tr_text", rel, i, s))
        for name, body in TABLE.findall(text):
            if name == "kActionLabels":
                for s in literals(body):
                    out.append(("kActionLabels", rel, 0, s))
            else:                                     # kExtras: the last literal
                for entry in re.findall(r'\{([^{}]*)\}', body):
                    ls = literals(entry)
                    if ls:
                        out.append(("kExtras.label", rel, 0, ls[-1]))
        for m in HELPER.finditer(text):
            span = text[m.end() - 1:balanced(text, m.end() - 1)]
            line = text.count("\n", 0, m.start()) + 1
            for s in literals(span):
                out.append(("settings.row", rel, line, s))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=DEFAULT_SRC,
                    help="the tree to scan (default: %(default)s)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="only the verdict line")
    args = ap.parse_args()

    tr_data = os.path.join(args.src, TR_DATA)
    if not os.path.isfile(tr_data):
        print("no translation table at %s" % tr_data)
        return EXIT_MISSING
    zh, en = read_table(tr_data)

    sources = sorted(glob.glob(os.path.join(args.src, "src", "**", "*.cpp"), recursive=True))
    sources += sorted(glob.glob(os.path.join(args.src, "tests", "*.cpp")))

    missing = []
    for kind, rel, line, s in gather(sources, tr_data):
        if CJK.search(s):
            if s not in zh:
                missing.append((kind, rel, line, s, "no entry, so English draws Chinese"))
        elif kind != "settings.row" and CAPS.match(s) and len(s) >= 2 and s not in en:
            # A settings row's ASCII argument is upstream's own -- "100" is a
            # default, "DNS" is a protocol's name and "GPU 3D" is the label the
            # setting goes by. The other tables hold labels the localization
            # wrote itself, where an all-caps string that the table does not
            # know is a row reading English with Chinese set.
            missing.append((kind, rel, line, s, "no entry, so Chinese draws English"))

    if args.json:
        import json
        print(json.dumps({"entries": len(zh) + len(en), "checked": len(sources),
                          "missing": [{"kind": k, "file": f, "line": ln,
                                       "string": s, "why": w} for k, f, ln, s, w in missing]}))
        return EXIT_OK if not missing else EXIT_MISSING

    if not args.quiet:
        total = len(gather(sources, tr_data))
        print("translation table: %d entries across %d sources, %d strings checked"
              % (len(zh), len(sources), total))
        for kind, rel, line, s, why in missing:
            where = ":%d" % line if line else ""
            print("  MISSING  %-16s %s%s  %r  (%s)" % (kind, rel, where, s, why))
    print("PASS: every string the menu draws has an entry" if not missing
          else "FAIL: %d string(s) have no entry" % len(missing))
    return EXIT_OK if not missing else EXIT_MISSING


if __name__ == "__main__":
    sys.exit(main())
