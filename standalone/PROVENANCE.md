# Provenance

How the shipped DSperate binary is produced, and what it is linked against.
Everything here is measured from the build, not from memory.

## Source

| | |
| --- | --- |
| Upstream | `https://github.com/beebono/DSperate.git` |
| Tag | `main` |
| Commit | `f5fa35ea19f966543feae086798701f134d89619` |
| Licence | GPL-3.0-or-later (`LICENSE`) |
| Pak base | `cfb037e` (`v2.1.1`, merge of PR #6) &mdash; the released pak the Chinese series started from |
| Build | the pinned commit above, with `standalone/patches/0001-0010` applied in order (each sha256-locked); see the table below |
| Patches | `patches/0001-pak-cache-and-archive-policy.patch`, `patches/0002-save-durability.patch`, `patches/0003-lid-resume-no-fabricated-close.patch`, `patches/0004-deterministic-version.patch`, `patches/0005-dsperate-ra-account-adapter.patch`, `patches/0006-chinese-localization.patch`, `patches/0007-menu-ui-language-and-turbo-page.patch`, `patches/0008-cjk-drawing.patch`, `patches/0009-menu-tests.patch` and `patches/0010-face-pips-that-follow-the-pad-own-naming.patch` (the v3.0.0 series, re-anchored and sha256-locked; see below) |

## Patches are the v3.0.0 build

The ten patches are locked by sha256 in `upstream.lock.json`. They _are_ the
build: `build-dsperate.sh` clones the pinned commit, resets to it, and applies
the series in order, and the build refuses a patch whose hash differs. The
v2.1.1 series did not apply to v3.0.0 (upstream moved `text_width`,
`draw_text`, the settings tables and the version generator), so it was rebased
and re-anchored onto v3.0.0; the original v2.1.1 patches are kept under
`standalone/patches-legacy-v2.1.1/` for the audit trail and do not produce this
artifact.

Reviewed against [upstream v3.0.0](https://github.com/beebono/DSperate/releases/tag/v3.0.0)
on 2026-09-28:

| Patch | Decision |
| --- | --- |
| 0001 archive/cache policy | Keep and rebase. The cache-root, single-entry and unsafe-path policies are still absent upstream, so they are re-expressed against `find_rom` on v3.0.0. |
| 0002 save durability | Keep and rebase. Checked writes and firmware flush/close are unchanged. |
| 0003 lid/resume | Keep and rebase. v3.0.0's lid implementation is unchanged and still fabricates a close on a device with no switch. |
| 0004 deterministic `--version` | New. Prefers the lock's tag and commit over git so a source archive and a patched checkout report the same identity. |
| 0005 Leaf account adapter | New. The `standalone-ra-account-v1` consumer; upstream has no equivalent. |
| 0006 Chinese overlay | New. A WenQuanYi Micro Hei subset, the text layer that draws it, and `tr_data.inc` &mdash; 315 English&rarr;Chinese pairs keyed by the English the sources are written in. No UI string is touched. |
| 0007 Menu, UI language, Turbo page | New. The rows in `menu.cpp`/`settings.cpp`/`main.cpp`, written in English as upstream writes them; the Turbo (连发) page this pak adds; and the `ui.language` switch. Its Chinese comes from 0006's table, so translating a row is a line there and nothing here. |
| 0008 CJK drawing | New. Routes the drawing path through 0006's face, which is what makes a Chinese row readable. |
| 0009 Menu tests | New. The C++ menu tests: the page walk, the strict leak count, and the coverage test that walks every compiled settings table in Chinese mode. |
| 0010 Face pips | New. Points the controls page's diamond pips at the button the pad's own naming binds (v2.1.1's 0011). |

`standalone/patches/0001-pak-cache-and-archive-policy.patch` adds the pak's
archive policy.

It adds three opt-in command-line flags and the two settings behind them:

- `--cache-root-only` (`[cart] cache_root_only`): a configured `paths.cache` is
  the only place a deflated archive may be unpacked, never a `.dsperate`
  directory beside a writable ROM. The pak pins the cache to
  `$USERDATA_PATH/dsperate/cache/<key>/`.
- `--single-rom` (`[cart] single_nds`): refuse an archive that holds more than
  one eligible image entry instead of picking one by game database and
  revision. The pak wants one unambiguous game per archive.
- `--inspect-cart FILE`: print `kind`, `extract`, `bytes` and `entry` for a
  cartridge and exit without booting anything, or exit non-zero with the reason
  on stderr. The wrapper sizes and bounds its cache with this and refuses an
  unreadable archive before a window opens.

The same patch rejects an image entry whose name is absolute or carries a `..`
component. Upstream already refuses encryption, zip64 and unknown compression;
this closes the remaining path-shaped case, and the extraction target was never
derived from the entry name in any case.

`standalone/patches/0004-deterministic-version.patch` makes `--version` report
the lock's release tag and commit. Upstream's generator takes the tag from
`git describe` and the commit from `git rev-parse`, so a corresponding-source
archive without git says `unknown` and a patched checkout says `<hash>-dirty`.
The patch prefers `DSPERATE_LOCK_VERSION` and `DSPERATE_LOCK_COMMIT`, which
`build-in-container.sh` exports from the lock, and leaves ordinary git
development unchanged.

`standalone/patches/0005-dsperate-ra-account-adapter.patch` makes DSperate use
the RetroAchievements account saved in Leaf. It adds three files under
`src/cheevos/` and small hooks in the achievement client and the SDL frontend:

- `ra_account_contract.cpp` and `ra_account.h`: the contract classifier, the
  revision marker (`.umrk-ra-account`) and the transition table, the same logic
  as the Flycast consumer and the leaf-contracts reference.
  `make test-ra-account` replays the pinned leaf-contracts fixtures through
  this classifier.
- `ra_account_bridge.cpp`: captures `UMRK_RA_ACCOUNT_*` (and a leaked
  `JAWAKA_CHEEVOS_*` pair) into private memory and unsets them as the first
  thing the frontend does. It picks the transition, writes the marker as
  pending before a login, and hands the password to the native rcheevos login
  once. A verified token goes through the adapter's own checked writer: a
  0600 temporary in the same directory, then write, `fsync`, close and rename,
  each checked. Only after that does the marker become accepted. Any failure
  leaves the previous files in place and keeps the revision pending.
- An explicit `cheevos.enabled = false` (global or per-game INI) or
  `--no-cheevos` is decided before the handoff is consumed and wins over the
  managed account. The handoff is still captured and scrubbed, but nothing
  signs in and neither the marker nor the token is touched.
- Bridge failures are queued as notices that the achievement client drains
  into its own pop-up queue, the path upstream's sign-in failure uses. The
  frontend shows them even with `cheevos.toasts` off.
- Unmanaged launches keep upstream behavior: a menu sign-in lasts for the
  session and is not written anywhere. Upstream reads
  `<Config::dir()>/cheevos.token` but never writes one, and the Leaf wrapper
  gives every game its own `XDG_CONFIG_HOME`, so persisting there would
  scatter tokens across per-game directories.
- The account page says `MANAGED BY LEAF`, offers no manual sign-in for a
  managed account, and keeps its sign-out session-only.

The wrapper passes the managed directory as `--managed-account-dir`
(`$USERDATA_PATH/dsperate/retroachievements`). It copies and unsets the
snapshot before any helper runs and restores it only for the emulator's
`exec`. It passes a leaked RetroArch pair on by presence only, never by value.

The cache-root and single-ROM policies default off. Unsafe archive entry
names are rejected regardless of those flags.

## Chinese (Simplified) menu

Five patches add a second UI language and the face to draw it in. The sources
are written in English -- the language upstream writes them in, so that a
rebase onto a new tag is a small diff -- and the Chinese is a single overlay
table, `tr_data.inc`, keyed by that English. English is the default and needs
no table at all: `tr_text` hands back what it was given. Setting `ui.language`
to `zh` resolves every string through the table instead, and a string with no
entry stays English rather than breaking a row.

That direction is the point of it. The series before this one wrote the Chinese
into the sources and translated into English from it, so every UI line carried
a diff against upstream and a merge had to be read in two languages. Now an
upstream release is answered by adding Chinese for the strings that are new --
one line each in `tr_data.inc`, and nothing at the call sites.
`standalone/check-tr-coverage.py` lists exactly those.

`standalone/patches/0006-chinese-localization.patch` is the overlay and the
framework, and no UI string: `i18n.h` -- the `UiLang` enum, `tr_text`, `ds_tr`
and the counters the strict leak check uses -- `tr_data.inc`, 315
English&rarr;Chinese pairs, and `tools/make_menu_font.py`, which builds the face
the Chinese is drawn with. The table is generated and no generator ships with
the patch; the pair list in `tr_data.inc` is the source. The menu this patch
produces still says everything in English.

`standalone/patches/0007-menu-ui-language-and-turbo-page.patch` is the menu
itself, written in English: the rows in `menu.cpp`, `settings.cpp` and
`main.cpp`, the Turbo (连发) page this pak adds, and the switch that selects a
language. `tr_text` lives here, in `menu.cpp`, and `draw_text` and `text_width`
resolve every string through it, which is why a single setting flips the menu
and both settings pages at once -- labels, notes, choice values and page
titles -- with no per-string bookkeeping at the call sites. A UI LANGUAGE row
on the OPTIONS page toggles the `ui.language`
config key live and persists it to `dsperate.ini`; it is deliberately distinct
from `user.language`, which is the NDS firmware language games start in.

`standalone/patches/0008-cjk-drawing.patch` is the face: stb_truetype plus a
WenQuanYi Micro Hei subset embedded in `font_cn_data.inc`, and the text layer
that draws it. `next_cp` decodes one code point, `next_char` folds it to the
5x7 grid's ASCII letter, and `text_width` and `draw_text` both take their step
from `step_for`, so the measurement and the painting cannot disagree;
`cjk_square` is the single hand-over between the two paths. The subset carries
ASCII 0x20..0x7E as well as Han, so Latin is rasterised by the same face in the
same 7px box as Han and the two scripts come out the same size on a row; Latin
keeps the face's real advance plus one pixel of letter spacing, Han keeps the
wide step, and the 5x7 bitmap is left only as the fallback for glyphs the face
lacks -- the face-button pips. It is built by `tools/make_menu_font.py`, whose
SOURCES table records the package, the file and the SHA-256 of exactly the face
used (Debian/Ubuntu `fonts-wqy-microhei` 0.2.0-beta-3.1) -- the same face and
version as the one already shipped under `src/core/io/dsi_font/`, so the font
exception notice is that directory's. It scans `tr_data.inc` as well as the
sources, which after the English baseline is where the Chinese it has to carry
lives. `test_menu` links `cjk_font.cpp`, and two tests cover the regression
that shipped: a carried code point measures a square and draws the face's glyph
rather than the grid's `?`, and the pages draw with the language switched.

`standalone/patches/0009-menu-tests.patch` is the C++ menu tests: the page walk
with the strict leak counter on, and the coverage test that walks every
compiled settings table in Chinese mode and asks for each row's label, note and
choice. That last one is what answers, exactly, whether a row has its Chinese --
a regex over the sources cannot, because a row helper's arguments do not say
which is the label and which is an ini value.

The rest of the menu's own text is keyed in `tr_data.inc` the same way: the
settings values, the sentinels on fast forward and the picture-in-picture hold,
and every label the Controls page puts on a row -- the twenty hotkeys and the
thirteen rows that are neither a hotkey nor a DS button. A DS button's own name
is left alone: A, B, X, Y, L, R, START, SELECT and the d-pad are printed on the
console, and the value beside each is the same name, so translating either side
puts one word on both. Three rows format before they translate and are resolved
before the values go in for that reason: a selected value drawn between arrows,
a note wrapped on spaces, and the two halves of a disabled row's reason -- the
table holds the `snprintf` format, not the filled string, and `tr_text` matches
by `strcmp`. The options page's widest-row measurement resolves before it
measures too, or it measures one language and draws the other. Two rows are
renamed (the slot page's title, and the root's slot row), and the auto state's
row is drawn only when there is an auto state to load or delete. The slot row is
the one row `draw()` formats rather than takes whole, and it is the longest line
on the page: it did not fit the buffer, and `snprintf` cuts at a byte, so the
row ended inside a character; the buffer is named now and held against the
longest form by a `static_assert`.

`standalone/patches/0010-face-pips-that-follow-the-pad-own-naming.patch`
separates the two meanings of "x" on the MLP1 pad. The diamond pips on the
controls page are places, and the pad's own mapping is not: the MLP1 names its
face buttons by the letter printed on them, so its SDL `x` sits at the top of
the diamond and its SDL `y` on the left, where SDL's own assumption -- and
Xbox's, and the table's -- puts them the other way round. The bindings were
already right (revision 4 of the defaults binds `pad.x = x` and `pad.y = y`);
what pointed the wrong way was the picture beside the binding, and the compass
alias a hand-written `west` or `north` resolves to. A `pad.xy_naming` key says
which way the pad names them, `position` by default and `printed` on this pak,
and the pip and the alias are taken from the other row when it is `printed`.
The pak ships the key and migrates it as revision 5 of the defaults.

v3.0 adds `pad.face_fix`, which is on by default and is the same correction
done automatically: it compares the pad's SDL mapping against the kernel's
positional gamepad codes and, finding the printed X above and the printed Y to
the left of where SDL expects them, renumbers the raw button before the
bindings above are read. That is the other half of revision 4's fix, and the
two halves cancel. On this device it turns a press on the button printed Y
into `pad.x`, so the v2.1.1 controls would silently come back swapped under
v3.0 for anyone who upgraded rather than reinstalled. The defaults are revised
to 6, migrated as `pad.face_fix = off`, which leaves the explicit binding as
the only half in play. A player who sets `face_fix = auto` themselves keeps it:
the migration only seeds a key that is missing.

`standalone/patches/0007-menu-ui-language-and-turbo-page.patch` does the
same for the account page's status line, which 0005 rewrote. The page wraps
that line to the panel, so what reaches `draw_text` is a fragment and never the
whole sentence, and a name or a hash joined onto the end is no more an entry
than a fragment is: the frontend now resolves each of the ten forms before it
joins either and before the page cuts it. The ten pairs go into the table,
including the managed-by-Leaf tag, in both the shape that ends a line and the
one that starts it. What the bridge reports as its reason is left alone: that
text is `standalone-ra-account-v1`'s own vocabulary, shared with Leaf and with
the contract's fixtures, and a menu language is not the place to rename it.

A leak check rides along with the drawing: with English set, a string carrying a
Han character or a fullwidth form is a Chinese literal the sources should no
longer hold, so the player is about to read a row in the wrong language. A row
drawn in the wrong
language looks exactly like one drawn in the right one, so the drawing counts
these when the tests arm the check, and the menu test walks every page -- by
row, into the slot page, into delete mode and through every value every row can
hold -- and requires zero.

The other direction is not a thing the drawing can count. A string with no
entry is drawn as the English it was written in, which on a Chinese screen is
indistinguishable from a ROM title or a number that is meant to be English. It
is answered statically instead: `standalone/check-tr-coverage.py` asks whether
each English literal the sources can draw has a Chinese entry, and the coverage
test in 0009 asks the same of every compiled settings row. Both fail the run,
and both are what an upstream release is run against.

`standalone/check-upstream-text.py` reads the UI text
out of a pristine upstream tree and compares it with
`standalone/localization.baseline.tsv` (490 entries at the pinned commit), so an
upstream release that adds or rewords screen text is visible as a list of the
strings that are new rather than as a silent drift; it is run by hand after a
release, and the numbers it reports are recorded in `upstream.lock.json` under
`localization.check`.

## What the merge cost the table, and what now catches it

The table is 315 English&rarr;Chinese pairs, keyed by the English the sources are
written in. It was 287 zh/en pairs before the English baseline, and the three-way
merge into v3.0.0 had already lost 28 of the rows the later patches had added
while keeping the call sites that read them. `tr_text` answers for the string it
is handed, so a row whose entry is missing is not a row that draws a gap: it is a
row that draws English with Chinese set, and the only thing that can tell the two
apart is the coverage check, which asks the table rather than the screen. Four
kinds of string had lost their entries by then, and all four are fixed here
rather than in a patch, because the tree they belong to is this one:

- **Notes the settings tables carry.** A note reaches the canvas through
  `tr_text` only if the page asks for it, so it has no `tr_text` call of its own
  for a scanner to find, and until 2026-09-28 none were found. `fit()` resolves
  the string and only then cuts it to the panel, which makes a missing note
  worse than a missing label: it is not one row in Chinese, it is the row every
  time it is cut. `video.aa` and `video.gpu3d` were both missing theirs.
- **Keys the table reworded once.** An entry keyed
  `两块屏幕上下叠放或左右并排时的面板像素间距` was never a string any source line
  says, and its English was upstream's note minus the second sentence. The real
  note, from `video.screen_gap`, is the entry now.
- **The Controls page's own key names.** Fifteen of `kExtras[].label` were
  written in Chinese and resolved nowhere, so the page that translates itself
  was the one page whose rows stayed Chinese. They are written in English now,
  like every other piece of the page's wording, and go through `tr_text` with
  the rest of it.
- **A setting the merge kept.** `emu.fast_load` is a v2.1.1 key that v3.0.0
  dropped and nothing reads; the merge kept it because the v2.1.1 side had it
  and takes its CLI whitelist as a union. A switch that does nothing but be
  switchable is worse than no switch, so the row is gone and the defaults stay
  v3.0.0's.

`standalone/check-tr-coverage.py` is the guard. It reads the table and asks a
specific question -- does *this* string have a Chinese -- rather than comparing
sets, so it has no baseline to drift from, and it checks three kinds of site:
`tr_text` with a string constant, `kActionLabels`, and `kExtras`' label. A
literal carrying Han anywhere under `src/` fails it too, because after the
English baseline that is a string the flip missed. The settings rows are the
fourth kind and are left to the C++ test, which walks the compiled tables and so
does not have to guess which of a helper's arguments is the label and which is
an ini value.

`make test-tr-coverage` runs it, and so does `make check`. It is also the tool
to reach for after an upstream release: it prints exactly the English strings
that have no Chinese yet.

The same thing happened one level up: `src/frontend/sdl/CMakeLists.txt` had lost
`input.cpp` from its `add_executable`, which is upstream's own translation unit
and the one that defines `Input::handle`, `update_stylus`, `collisions` and
`close`, all of which `main.cpp` and `menu.cpp` call. Everything else compiled
and only the link failed, with eleven undefined symbols, so nothing short of a
link can catch it. The unit is back in the list, in upstream's position, and the
comment above it says why it is there.

The C++ tests were wired into `make check` as `make test-cpp` at the same time.
Nothing reached them before, and one of the three could not compile:
`g_strict_i18n` and `g_i18n_leaks` are defined in `menu.cpp` and declared in no
header, so `menu_test.cpp` had never built. The two declarations are in
`i18n.h` now, next to `tr_text`, which is the only header that carries those
names. `test_input` does not build on a macOS host -- `gpu_present.h` wants
`<SDL.h>` and `display_fbdev.h` wants `linux/fb.h` -- and the target says so
with a SKIP rather than a pass.

`standalone/patches/0003-lid-resume-no-fabricated-close.patch` stops the
host-resume lid pulse from fabricating a close on a device with no lid switch
(the MLP1). Upstream pulses the emulated lid whenever the clocks show a suspend
it did not see, which on these devices is every resume. A game that blanks its
screens on lid-close and restores them only on an open it saw coming (Contra 4)
then stays black; emulation, audio and input all keep running. The pulse now
fires only for a lid already believed closed, so with no switch nothing happens
and the screens survive a resume.

`standalone/patches/0002-save-durability.patch` makes battery-save and
save-state writes durable. Upstream writes to `<file>.tmp`, closes it without
checking the result, and renames. A buffered write on a full or read-only card
can report success from `fwrite` and still never reach the disk, so a save
reported as successful might not be there. The patch adds a checked helper
(`write_file_durable`): `fwrite`, `fflush`, `fsync`, `fclose` and `rename` are
all checked, the temporary is removed on failure, and the previous committed
file is left untouched. It also checks the firmware-override flush and close.
A failed battery save stays dirty, so the next flush retries.

Save loading now follows upstream v2.0.0. For a known chip, upstream loads the
portion that fits and saves the original mismatched file as `.bak`; for an
unknown chip, a supported save size selects the chip. This is different from
refusing every short save. The removed guard read into live SRAM before checking
the count, so it did not actually undo partial reads even in the old patch.
The checked-write helper covers DS battery saves and save-state files, not
upstream's new DSi NAND/SD persistence or mismatch-backup writes.

Upstream writes state format 3 and accepts DS format 2 from v1.15.1. This is a
source-reviewed compatibility promise, not a device migration test. Back up your
states before updating: v1.15.1 cannot read states newly written by v2.0.0.

## Toolchain and flags

Built inside the digest-pinned `mlp1-toolchain` image
(`sha256:66aac16fb8b07e663c9b4d66970f272df195a6eba98dfad8286eabbaa617faf9`)
with the cross prefix `aarch64-buildroot-linux-gnu` and the target sysroot at
`/opt/mlp1-toolchain/aarch64-buildroot-linux-gnu/sysroot`.

CMake configuration (see `standalone/build-in-container.sh`):

| Setting | Value | Why |
| --- | --- | --- |
| `CMAKE_SYSTEM_PROCESSOR` | `aarch64` | selects the AArch64 JIT and NEON kernels |
| `CMAKE_BUILD_TYPE` | `RelWithDebInfo` | upstream default; debug info is stripped from the artifact |
| `DSPERATE_TESTS` | `OFF` | no test binaries ship |
| `DSPERATE_HEADLESS` | `OFF` | the measurement harness does not ship |
| `DSPERATE_CHEEVOS` | `ON` | upstream default; libcurl is `dlopen`ed at runtime, not linked |
| `DSPERATE_NET` | `ON` | upstream default; vendored ENet and libslirp are linked statically; network sessions default off |
| `CMAKE_CXX_FLAGS` | `-DSDL_VIDEO_DRIVER_WAYLAND=1` | exposes `SDL_SysWMinfo`'s Wayland fields so the dmabuf tier compiles (see below) |
| `DSPERATE_WAYLAND` | `ON` | build the Wayland dmabuf tier; the build fails rather than substituting the stub |
| `DSPERATE_CHEEVOS_VERSION` | `3.0.0` | passed explicitly; a shallow checkout has no tags for upstream's `git describe` fallback |
| `DSPERATE_PGO` | `off` | no profile fits this toolchain (see below); plain `-O2` |

`SOURCE_DATE_EPOCH` is the pinned commit's committer timestamp
(`1791414282`). `DSPERATE_LOCK_VERSION=v3.0.0` and
`DSPERATE_LOCK_COMMIT=f5fa35e` are exported from the lock so `--version` is
deterministic.

## Profile-guided optimisation

**This build has no PGO profile.** Upstream v3.0.0 ships profiles trained by
GCC 13.3.0; the MLP1 toolchain is Buildroot GCC 12.3.0, and CMake's fingerprint
check refuses the mismatch (recorded as `pgo.build_fingerprint` in the lock), so
the build runs with `-DDSPERATE_PGO=off` and plain `-O2`. That is a performance
difference and not a correctness one: the emulator was measurably faster under
the retrained profile on v2.1.1, and no performance claim is made for this
candidate. Training a profile against the v3.0.0 source needs ROM play sessions
on the device and a profile that survives a source this repository produces by
patching; until that exists, the honest setting is off, and
`upstream.lock.json` records it with `pgo.state = "none"` rather than dropping
the field. The v2.1.1 profile this pak trained is in `history[0].pgo` for the
audit trail and does not apply here. `make test-pgo` checks, without a build or a
device, that the build flags match the lock's `pgo` record.

## Archives

`make dist-pakrat` and `make dist-source` write the pak ZIP and the
corresponding-source tarball with `scripts/make-archive.py`, run inside the
same pinned image so the Python and zlib doing the compression are fixed.
Entries are sorted, every timestamp is `SOURCE_DATE_EPOCH`, owner and group are
0 with no names, modes are 0755 or 0644, the ZIP has no extra fields and the
gzip header has no name or timestamp. `make test-archives` builds both twice
with every input's mtime and the umask changed in between and requires the
same sha256. `make test-version` extracts the source archive, rebuilds from it
with no git, and requires the locked binary and `DSperate v3.0.0 (f5fa35e)`.

## Linkage

`readelf -d` on the stripped artifact reports exactly:

```text
libSDL2-2.0.so.0
libstdc++.so.6
libm.so.6
libgcc_s.so.1
libc.so.6
```

Every one is provided by the MLP1 in `/lib`; the pak bundles no shared
libraries. The artefact is AArch64, stripped, carries no RPATH/RUNPATH and its
highest glibc symbol version is `GLIBC_2.38`, the device's glibc.

## Artifacts

| | `bin/dsperate` | `bin/dsperate-notice` |
| --- | --- | --- |
| Source | the pinned commit `f5fa35e` plus `standalone/patches/0001-0010` applied in order | `standalone/notice/notice.c` (this repository) |
| Licence | GPL-3.0-or-later | MIT |
| sha256 | `f588bd2e51466f375a112b7f585ac29ac4508f202e32f9a0618c356b17338583` | `c52bf4d447c5c855dd02dfb24d8eef962a5d3d079c15b3e4438ae2a5df34a160` |
| Size | 5,480,208 bytes | 14,224 bytes |
| Reproduced | two clean builds agreed byte for byte, less the PGO profile (below) | `FORCE=1` builds agreed byte for byte |

The emulator is stripped with `$CROSS-strip --strip-unneeded`, the same step
the v2.1.1 pipeline took and the device verification requires: an unstripped
build fails `standalone/verify-binary.sh` on sight, and it is 10&times; the size.
The notice program is unchanged from v2.1.1.

The notice program is the fullscreen message the wrapper shows when a launch
cannot proceed. It links only SDL2 and SDL_ttf, both provided by the MLP1, and
resolves the launcher's own font at runtime; the pak bundles neither a library
nor a font. It is verified with the same AArch64/stripped/glibc/allowlist checks
as the emulator (see `build/standalone/verify-notice.txt`).

## The Wayland dmabuf tier is built

The MLP1's own `libSDL2-2.0.so.0` (2.28.5) is built with its Wayland video
driver, but the toolchain sysroot's SDL2 2.28.5 is a KMSDRM-only build:
`SDL_config.h` leaves `SDL_VIDEO_DRIVER_WAYLAND` undefined, so `SDL_syswm.h`
hides `SDL_SysWMinfo`'s Wayland fields and DSperate's dmabuf tier cannot
compile against those headers.

The build defines `SDL_VIDEO_DRIVER_WAYLAND=1` for this pak only. That exposes
the header fields; it does not, and cannot, add a Wayland driver to a runtime
SDL that lacks one. The fields live in SDL's public `SDL_SysWMinfo` union,
whose reserved space is the same whether or not the macro is set, and the
binary is dynamically linked to the device's Wayland-capable SDL. The dmabuf
tier loads `libwayland-client.so.0` with `dlopen` at runtime, so `libwayland`
is not a link-time dependency.

Independent ABI check (2026-09-16), compiled for AArch64 with the pinned SDK:
`sizeof(SDL_SysWMinfo) = 72`, `offsetof(info) = 8`, Wayland member size 64,
`offsetof(info.wl.surface) = 16`, and `offsetof(info.wl.xdg_toplevel) = 48`.
The public structure size and union offset agree with and without the define.
A separate full build with the define reproduced the then-pinned v1.15.1 artifact hash.
This check applies to these pinned SDL 2.28.5 headers and the qualified device
SDL; changing the SDK or runtime SDL requires checking the ABI again.

Evidence in the pinned artifact: `strings` shows `zwp_linux_dmabuf_v1`,
`zwp_linux_dmabuf_feedback_v1`, `/dev/dma_heap` and `libwayland-client.so.0`,
and the `NEEDED` set is unchanged from the window-surface-only build. The build
also fails if CMake's Wayland probe or the compilation of `display_wl.cpp`
does not confirm the real tier, so a silently stubbed build cannot ship.

The dmabuf allocation, Weston import, orientation and performance are qualified
on the device separately; the SDL window-surface route remains the fallback.

## Verification status

The v2.0.0 release checks below are retained as history. The v3.0.0 candidate
this revision ships is host-verified only: the pinned commit plus the patch series builds to
`f588bd2e…` (5,480,208 bytes) with `SOURCE_DATE_EPOCH` pinned and
`DSPERATE_CHEEVOS_VERSION=3.0.0`, `--version` reports `v3.0.0 (f5fa35e)` from
the lock's own exported identity, the device verification passes (AArch64,
stripped, no RPATH, `GLIBC_2.38` ceiling, every `NEEDED` library on the MLP1
allowlist), seven real-executable archive CLI checks pass, and `make check`,
`make validate` and `make package-mlp1` pass (42 lock checks, 118 wrapper
checks, the 27 pinned account fixtures, the account state and bridge fault
tests, and packaged-tree validation). Device requalification of this build,
including the performance an absent PGO profile means to re-measure and a
native sign-in with this exact build, is pending.

Two things this candidate is not, stated here because neither shows up in a test
run. It carries no PGO profile (see above), so it is slower than the v2.1.1 it
replaces. It was built without Vulkan, because the pinned toolchain image has no
`vulkan.h` and upstream v3.0.0's own CI installs the headers to get them; the
GPU 3D setting is therefore inert here, and it says so in Chinese on the
settings page rather than failing silently. A build with the headers would
enable that tier.

The v2.1.1 record, for comparison with what this revision changes: the patched
source built with the retrained GCC 12.3.0 profile to `d95b0a56…`, two clean
`FORCE=1` builds agreed, the strict profile check passed, and `--version`
reported `v2.1.1 (baec965)` from the lock. Its artifact hashes are kept in
`upstream.lock.json` under `history`.

Two clean `FORCE=1` builds agreed on both artifact hashes. The SDK, flags and
runtime library allowlist are unchanged. The larger emulator contains the new
DSi core, generated system fonts and vendored networking code. The package
carries FreeBIOS, miniz, rcheevos, ENet, libslirp and both font notices in
`LICENSE-THIRD-PARTY.txt`, copied from the exact pinned source; the complete
corresponding source retains all file-level notices.

Checks passed on 2026-09-17:

- 82 wrapper checks and 14 MLP1 profile checks.
- Seven real-executable archive CLI checks (raw, stored, deflated, ambiguous,
  opt-in selection, unsafe path and malformed ZIP).
- Eight upstream AArch64 tests in the pinned container: `scheduler`,
  `cart_save`, `fastmem`, `spu`, `config`, `input`, `firmware` and `zip`.
- AArch64, stripping, GLIBC ceiling, library allowlist and real Wayland backend.

Run the archive check against a Linux executable with
`python3 tests/test-archive-cli.py /path/to/dsperate`. In the pinned AArch64
container, prefix the executable with the SDK's `lib/ld-linux-aarch64.so.1`
and `--library-path` naming its `lib` and `usr/lib` directories.

The patched v2.0.0 build passed MLP1 launch, controls, save faults, sleep and
sustained pacing checks on 2026-09-17. The locked PGO build was subsequently
installed on the same device; both core pickers, selection persistence after a
device reboot, the visible `.7z` refusal and stick-driven stylus input were
verified there. Local Pak Rat install/reinstall/uninstall passed and preserved
all 35 tested settings, save and state files byte for byte.
DSiWare, NAND/SD persistence and networking are not
qualified Leaf features in this update. The pak version is `2.0.0`.
