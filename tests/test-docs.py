#!/usr/bin/env python3
"""Keep README.md and standalone/PROVENANCE.md describing the locked build.

    python3 tests/test-docs.py

The two documents quote the binary hash, its size and the patch series. They
drifted before (a candidate's docs cited the previous binary and patch count),
so this checks them against standalone/upstream.lock.json:

- PROVENANCE.md quotes the locked binary sha256 and size and names every
  locked patch file;
- every full sha256 in PROVENANCE.md is one the lock pins (binary, notice,
  toolchain digest or PGO profile), and every short `xxxxxxxx…` hash in either
  document is the locked binary's or notice's;
- README.md's Status section quotes the locked binary and the patch count.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
checks = 0
failures = 0


def check(ok: bool, what: str) -> None:
    global checks, failures
    checks += 1
    if not ok:
        failures += 1
        print(f"FAIL {what}")


def main() -> int:
    lock = json.loads((REPO / "standalone/upstream.lock.json").read_text(encoding="utf-8"))
    provenance = (REPO / "standalone/PROVENANCE.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    binary = lock["artifact"]["sha256"]
    notice = lock["notice"]["sha256"]
    size = f"{lock['artifact']['size_bytes']:,} bytes"
    patches = [p["file"] for p in lock["patches"]]
    count = WORDS[len(patches)] if len(patches) < len(WORDS) else str(len(patches))

    check(binary in provenance, "PROVENANCE.md quotes the locked binary sha256")
    check(size in provenance, f"PROVENANCE.md quotes the locked binary size ({size})")
    for name in patches:
        check(name in provenance, f"PROVENANCE.md names {name}")
    check(re.search(rf"\b{count}\s+patches\b", provenance, re.I) is not None,
          f"PROVENANCE.md says {count} patches")

    pinned = {binary, notice, lock["pgo"]["sha256"],
              lock["toolchain"]["digest"].removeprefix("sha256:")}
    # The merged tree the v3.0.0 artifact is built from, and every earlier
    # release's recorded artifact and profile: PROVENANCE quotes all of them as
    # history, and the lock pins all of them, so quoting one is never a drift.
    if "source_tree" in lock.get("core", {}):
        pinned.add(lock["core"]["source_tree"]["sha256"])
    for released in lock.get("history", []):
        for key in ("artifact_sha256",):
            if released.get(key):
                pinned.add(released[key])
        if released.get("artifact_sha256"):
            pinned.add(released["artifact_sha256"][:8])
    for full in sorted(set(re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", provenance))):
        check(full in pinned, f"PROVENANCE.md sha256 {full[:12]}… is not one the lock pins")

    short_ok = {binary[:8], notice[:8]} | {
        released["artifact_sha256"][:8]
        for released in lock.get("history", []) if released.get("artifact_sha256")
    }
    for name, text in (("README.md", readme), ("PROVENANCE.md", provenance)):
        for short in sorted(set(re.findall(r"`?([0-9a-f]{8})…", text))):
            check(short in short_ok, f"{name} cites {short}…, which is not the locked binary")

    status = readme.split("## Status", 1)[1].split("\n## ", 1)[0] if "## Status" in readme else ""
    check(bool(status), "README.md has a Status section")
    check(binary[:8] in status, f"README.md Status cites the locked binary {binary[:8]}…")
    check(re.search(rf"\b{count}\s+reviewed\s+pak\s+patches\b", status, re.I) is not None,
          f"README.md Status says {count} reviewed pak patches")

    print(f"test-docs: {checks - failures}/{checks} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
