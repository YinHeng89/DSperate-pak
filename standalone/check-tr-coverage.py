#!/usr/bin/env python3
"""Does every string the menu can draw have its Chinese?

The menu's sources are written in English -- upstream's language, so that a
rebase stays readable -- and the Chinese lives in one table, tr_data.inc, keyed
by that English. tr_text() returns what it was handed when nothing matches, so
an English literal with no entry is a row the player reads in English with
Chinese set. Nothing else catches it: on screen that row is indistinguishable
from one that is meant to be English, and the runtime leak check cannot see it
either, because what it counts is Chinese drawn with English set -- the other
direction.

So: read the table, read the call sites, and say which literals have no entry.
A literal is a call to tr_text with a string constant, plus every entry in the
two label tables the Controls page reads -- kActionLabels, which tr_text is
passed, and kExtras' label, which is not.

The settings tables are the fourth kind, and they are checked by the C++ test
instead: tests/menu_test.cpp walks the compiled tables in Chinese mode and asks
for every row's label, note and choice, which is both exact and immune to the
shape of the helper that built the row. This script leaves them alone rather
than guess which of a helper's arguments is the label and which is an ini value.

It also reads the sources the other way round: a Chinese literal anywhere under
src/ is one the flip to an English baseline missed, and is reported. tests/ is
exempt, because that is where the expected Chinese lives.

Reported as a list, and as a failure. There is no baseline: the question is not
whether the set of strings has moved, it is whether a specific string has its
Chinese, and a baseline would only paper over the answer.

This is the check to run after an upstream release: it lists exactly the new
English strings that still need a line in tr_data.inc, and nothing else.
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
    """Return {en: zh}: the English the sources write, keyed to its Chinese."""
    with open(path, encoding="utf-8") as f:
        pairs = PAIR.findall(f.read())
    return {e: z for e, z in pairs}


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
    table = read_table(tr_data)

    sources = sorted(glob.glob(os.path.join(args.src, "src", "**", "*.cpp"), recursive=True))
    sources += sorted(glob.glob(os.path.join(args.src, "tests", "*.cpp")))

    missing = []
    for kind, rel, line, s in gather(sources, tr_data):
        if CJK.search(s):
            # A Chinese literal under src/ is one the English baseline missed.
            # tests/ is where the expected Chinese is written down, so it is
            # not a source and is not held to this.
            if not rel.startswith("tests" + os.sep) and kind != "settings.row":
                missing.append((kind, rel, line, s,
                                "Chinese in a source; the sources are English now"))
            continue
        if s in table:
            continue                                  # it has its Chinese
        if kind != "settings.row" and CAPS.match(s) and len(s) >= 2:
            # A settings row's ASCII argument is upstream's own -- "100" is a
            # default, "DNS" is a protocol's name -- and the C++ test asks the
            # compiled row instead. The other tables hold labels the menu wrote
            # itself, where an all-caps string the table does not know is a row
            # reading English with Chinese set.
            missing.append((kind, rel, line, s, "no entry, so Chinese draws English"))

    if args.json:
        import json
        print(json.dumps({"entries": len(table), "checked": len(sources),
                          "missing": [{"kind": k, "file": f, "line": ln,
                                       "string": s, "why": w} for k, f, ln, s, w in missing]}))
        return EXIT_OK if not missing else EXIT_MISSING

    if not args.quiet:
        total = len(gather(sources, tr_data))
        print("translation table: %d entries (English -> Chinese) across %d sources, "
              "%d strings checked" % (len(table), len(sources), total))
        for kind, rel, line, s, why in missing:
            where = ":%d" % line if line else ""
            print("  MISSING  %-16s %s%s  %r  (%s)" % (kind, rel, where, s, why))
    print("PASS: every string the menu draws has an entry" if not missing
          else "FAIL: %d string(s) have no entry" % len(missing))
    return EXIT_OK if not missing else EXIT_MISSING


if __name__ == "__main__":
    sys.exit(main())
