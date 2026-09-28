#!/usr/bin/env bash
# The C++ unit tests. They live in the pinned tree beside the code they test,
# and the tree configures them with CMake -- which this repository does not
# carry a copy of, and does not want a second copy of. So they are compiled
# directly, with the same include paths CMake would have set, which is what
# makes them runnable without installing CMake or a toolchain into the repo.
#
# They have been here since 0008 and were green on nobody: `make check` did not
# reach them, and two of them did not compile at all until an extern for the
# strict-i18n counters existed in i18n.h. So the point of this target is not
# only "run them now" but "run them every time": a merge that keeps a call site
# and drops its translation entry, or a header that grows a global no test can
# see, is exactly the fault this suite exists to catch.
#
# test_input needs SDL2's headers and, through display_fbdev.h, linux/fb.h. On
# a non-Linux host that is not something to work around: it is a header this
# build's targets do not have, and the test is about code that is only ever
# compiled there. Skipped, loudly, and named as skipped.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:-$REPO_ROOT/build/dsperate-src}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

CXX="${CXX:-clang++}"
if ! command -v "$CXX" >/dev/null 2>&1; then CXX="$(command -v c++ || true)"; fi
if [ -z "$CXX" ]; then
  echo "test-cpp: no C++ compiler found (set CXX)" >&2
  exit 2
fi

# The include paths the tree's CMakeLists sets for its own targets, plus SDL2
# where a host has it. SDL's own layout differs by platform, and this tree's
# headers say <SDL2/SDL.h> while one of them says <SDL.h>; the shim answers
# that one without touching the tree.
SDL_INC=""
for d in /opt/homebrew/include /usr/local/include /usr/include; do
  [ -d "$d/SDL2" ] && SDL_INC="-I$d"
done
SHIM="$WORK/shim"
mkdir -p "$SHIM"
printf '#pragma once\n#include <SDL2/SDL.h>\n' > "$SHIM/SDL.h"

pass=0; fail=0; skip=0

# run NAME SRCS...  -- compiles the sources with a test main into $WORK/NAME
# and runs it; a compile that fails for want of a host header is a skip.
run() {
  local name="$1"; shift
  local out="$WORK/$name"
  local log
  log="$($CXX -std=c++17 -O1 -Isrc -I. -I"$SHIM" $SDL_INC -o "$out" "$@" 2>&1)"
  if [ $? -ne 0 ]; then
    # A missing system header is this host not being the tree's platform, not
    # a broken tree. Anything else in the log is a real failure.
    if grep -qE "fatal error: '(linux/|SDL2/|SDL\.h)" <<<"$log"; then
      printf '  SKIP  %-11s needs a host header this one does not have\n' "$name"
      skip=$((skip + 1))
      return 0
    fi
    printf '  FAIL  %-11s does not compile\n' "$name" >&2
    grep -E "error:" <<<"$log" | head -5 >&2
    fail=$((fail + 1))
    return 0
  fi
  local err
  err="$("$out" 2>&1)"
  if [ $? -eq 0 ]; then
    printf '  ok    %-11s\n' "$name"
    pass=$((pass + 1))
  else
    printf '  FAIL  %-11s\n' "$name" >&2
    head -10 <<<"$err" >&2
    fail=$((fail + 1))
  fi
}

if [ ! -d "$SRC" ]; then
  echo "test-cpp: no tree at $SRC (pass the path as \$1)" >&2
  exit 2
fi
cd "$SRC" || exit 2

echo "C++ unit tests, tree $SRC"
run menu  tests/menu_test.cpp   src/frontend/sdl/menu.cpp \
                                src/frontend/sdl/settings.cpp src/frontend/sdl/cjk_font.cpp
run config tests/config_test.cpp src/frontend/sdl/config.cpp
# Linux-only through display_fbdev.h; a non-Linux host skips it.
run input tests/input_test.cpp src/frontend/sdl/input.cpp \
                               src/frontend/sdl/pad_faces.cpp src/frontend/sdl/config.cpp

echo "test-cpp: $pass passed, $skip skipped, $fail failed"
[ "$fail" -eq 0 ]
