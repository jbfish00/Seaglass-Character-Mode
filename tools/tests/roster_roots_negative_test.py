#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [19] -- the roster-display roots.

The nine checks added for the in-game roster display
(../../game_plans/roster_display.md) are worth exactly what they FAIL on. So
break the built ROM on purpose, in each direction the blob can be wrong, and
require the matching check to report FAIL BY NAME -- not merely that the run
exits 1, because a tampered ROM also breaks the BPS round-trip and the diff
containment checks, and that would look like a catch while proving nothing
about these nine.

  1. control                     -- the real build passes all nine
  2. a root bent to a BLANK      -- species 387 exists as a table slot but has
     species slot                   no name. The row would render empty, and
                                    this is the case that justifies reading
                                    names out of the BUILT ROM rather than out
                                    of the JSON dump the emitter already used.
  3. a count bent               -- the character's row count disagrees with
                                    the manifest; every later character still
                                    reads fine, so only the entry check fires
  4. a first_root bent          -- the entry points into the middle of another
                                    character's roots. ⭐ THE PLAUSIBLE-WRONG
                                    CASE: every id it reads is a real species
                                    with a real NAME, so the name check stays
                                    green and only the structural ones fire.
                                    This is the WILDPOOL_STRIDE failure mode in
                                    a new place -- a wrong Pokemon, not an
                                    invalid one.
  5. a root value changed       -- one species swapped for another real one;
                                    nothing structural moves
  6. the LAST character's count -- the entries no longer tile roots[] exactly,
     bent                          which no single-character check would catch
  7. a count zeroed             -- a new empty roster appears that the
                                    emitter's list does not know about, and a
                                    consumer assuming >= 1 row would read the
                                    next character's roots
  8. the LATE probe's roots     -- character #193 specifically. A tamper at
     bent                          record 0 cannot catch a stride error at all
                                    (record 0 starts at byte 0 and reads
                                    correctly under any stride), which is why
                                    the check probes far from the base and why
                                    this case exists.
  9. control again              -- proves cases 2-8 left nothing behind

⭐⭐ CASES 4 AND 6 EACH FOUND A REAL DEFECT IN THE CHECK THEY WERE WRITTEN
AGAINST, before it had ever run green -- which is the entire argument for
writing these at all:
  * [19] re-derived the roots from roster_roots.bin instead of from the BUILT
    ROM, so SEVEN of its nine checks could not be made to fail by corrupting
    the ROM at all. It was comparing the manifest against the very file the ROM
    was built from.
  * its tiling check accumulated the MANIFEST's counts and compared the total
    to the manifest's own total -- it re-derived total_roots from total_roots
    and could not fail. It now sums the blob's own counts and checks
    contiguity.
Both are fixed, and these two cases are what hold them fixed.

⚠️ THE ROM IS NEVER MODIFIED IN PLACE. Each case writes a tampered COPY to a
temporary directory and runs a COPY of verify_artifacts.py pointed at it. The
base ROM under rom/ and the build under build/ are read-only here.
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cm_tally import assert_cases  # noqa: E402
import json  # noqa: E402
import tempfile  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VERIFY = os.path.join(HERE, "verify_artifacts.py")
BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")
CM = os.path.join(ROOT, "tools", "character_mode")

_MAN = json.load(open(os.path.join(CM, "characters_manifest.json"),
                      encoding="utf-8"))["characters"]
_ROOTS = json.load(open(os.path.join(CM, "roster_roots_manifest.json"),
                        encoding="utf-8"))

# Derived from the injector, never restated -- if the blob is ever rebased, a
# hardcoded copy here would tamper with whatever moved into the old address and
# every case would report MISS for a reason that is not about the checker.
_INJ = open(os.path.join(ROOT, "tools", "inject_character_mode.py"),
            encoding="utf-8").read()
import re  # noqa: E402
ROOTS_ADDR = int(re.search(r"^ROSTER_ROOTS_ADDR\s*=\s*(0x[0-9A-Fa-f]+)",
                           _INJ, re.M).group(1), 16)
ROOTS_OFF = ROOTS_ADDR - 0x08000000
ENTRY_SZ = _ROOTS["entry_size_bytes"]
ROOTS_START = ROOTS_OFF + len(_MAN) * ENTRY_SZ

# A real table slot with NO name (all zero bytes). Measured, not assumed: the
# ROM has 502 named species in 1489 slots.
BLANK_SPECIES = 387

CHECKS = {
    # ⚠️ Substrings, not whole check names -- matching full sentences is what
    # made a sibling's negative test report MISSES including its own CONTROL,
    # which is the signature of a broken harness, not a broken checker.
    "inrom": "roster roots in-ROM == roster_roots.bin",
    "entry": "and root slice re-derive from the",
    "tile": "entries tile roots[] exactly",
    "name": "resolves to a non-empty name in the BUILT ROM",
    "late": "late probe: character #",
    "empty": "characters with zero roots in-ROM ==",
}


def _child_env():
    """Environment for a spawned checker, with the tally overrides STRIPPED.

    ⚠️ MEASURED 2026-09-17 in this repo: subprocess inherits the environment,
    so running a negative test with CM_EXPECT_CHECKS set (as
    checker_guard_test.sh does) pinned the CHILD to that number too, and the
    CONTROL case failed for a reason that had nothing to do with the tamper.
    A control that an inherited variable can break is not a control.
    """
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    """Run verify_artifacts against `rom_path`; return (rc, output)."""
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    # ⚠️ The copy must live in tools/tests/, not in the temp directory:
    # verify_artifacts.py resolves the repo root from its OWN __file__, so a
    # copy run from /tmp looks for rom/ and build/ beside /tmp and every check
    # fails for a reason that has nothing to do with the tamper.
    path = os.path.join(HERE, "_negtest_verify_roots.py")
    open(path, "w", encoding="utf-8").write(src)
    try:
        p = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, cwd=ROOT, env=_child_env())
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return p.returncode, p.stdout + p.stderr


def _hit(out, key, marker):
    for line in out.splitlines():
        t = line.strip().lstrip("[")
        if t.startswith(marker) and CHECKS[key] in line:
            return True
    return False


def failed(out, key):
    return _hit(out, key, "FAIL")


def passed(out, key):
    return _hit(out, key, "PASS")


def entry_off(ci):
    return ROOTS_OFF + ci * ENTRY_SZ


def root_off(idx):
    return ROOTS_START + idx * 2


def first_count(data, ci):
    return struct.unpack_from("<HH", data, entry_off(ci))


# How many tamper cases this negative test must run. A deliberate LITERAL --
# see cm_tally.assert_cases. ⚠️ Without this, deleting cases takes the tally
# from "9/9 ALL PASS" to "5/5 ALL PASS" and still exits 0: every tally computed
# from its own run agrees with itself by construction.
EXPECT_CASES = 9


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM at %s -- run the injector first"
              % os.path.relpath(BUILT, ROOT))
        return 0
    good = bytearray(open(BUILT, "rb").read())
    fails, passes = [], 0

    # Pick a character with a decent roster, far from record 0.
    late = len(_MAN) - 1
    big = max((ci for ci in range(len(_MAN))
               if first_count(good, ci)[1] >= 4), key=lambda ci: ci)

    with tempfile.TemporaryDirectory() as tmp:

        def case(name, mutate, want_fail, also_pass=()):
            nonlocal passes
            data = bytearray(good)
            if mutate is not None:
                mutate(data)
                if data == good:
                    # ⚠️ "A MISS is more often a bad tamper than a real gap" --
                    # three times in one sweep in this workspace. Fail loudly
                    # on a tamper that changed nothing rather than reporting it
                    # as a checker that missed.
                    fails.append("%s: TAMPER CHANGED NOTHING" % name)
                    print("  [MISS] %s -- TAMPER CHANGED NOTHING" % name)
                    return
            rom = os.path.join(tmp, "tampered.gba")
            open(rom, "wb").write(bytes(data))
            _rc, out = run(rom)
            if want_fail is None:
                ok = all(passed(out, k) for k in CHECKS)
                detail = "all nine roster-roots checks pass"
            else:
                ok = failed(out, want_fail)
                detail = "%r reported FAIL" % CHECKS[want_fail]
                # Cases that must stay SILENT prove the tamper was precise --
                # a checker that fails everything would "catch" every case.
                for k in also_pass:
                    if not passed(out, k):
                        ok = False
                        detail += "; but %r did not PASS" % CHECKS[k]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: verify_artifacts [19] roster display roots")
        case("1 control -- the real build", None, None)

        def blank_name(d):
            f, _c = first_count(d, big)
            struct.pack_into("<H", d, root_off(f), BLANK_SPECIES)
        case("2 a root bent to a nameless species slot", blank_name, "name")

        def bend_count(d):
            f, c = first_count(d, big)
            struct.pack_into("<HH", d, entry_off(big), f, c - 1)
        case("3 a character's row count bent", bend_count, "entry")

        def bend_first(d):
            f, c = first_count(d, big)
            struct.pack_into("<HH", d, entry_off(big), f + 1, c)
        # ⭐ The plausible-wrong case: it reads real, named species -- just the
        # wrong character's. The NAME check must stay green, or this case would
        # be "caught" for the wrong reason rather than for reading the wrong
        # Pokemon. ⚠️ `tile` is deliberately NOT required to pass here: this
        # tamper also leaves a one-entry discontinuity, and the tiling check
        # was strengthened to notice exactly that (it used to sum the manifest
        # against itself and could not fail at all). Requiring silence from it
        # would be pinning the old, vacuous behaviour.
        case("4 a first_root bent into another character's roots",
             bend_first, "entry", also_pass=("name",))

        def bend_root(d):
            f, _c = first_count(d, big)
            cur, = struct.unpack_from("<H", d, root_off(f))
            struct.pack_into("<H", d, root_off(f), 25 if cur != 25 else 1)
        case("5 a root swapped for a different real species",
             bend_root, "entry", also_pass=("name",))

        def bend_last_count(d):
            f, c = first_count(d, late)
            struct.pack_into("<HH", d, entry_off(late), f, c + 1)
        case("6 the last character's count bent -- roots no longer tile",
             bend_last_count, "tile")

        def zero_count(d):
            f, _c = first_count(d, big)
            struct.pack_into("<HH", d, entry_off(big), f, 0)
        case("7 a count zeroed -- an empty roster appears",
             zero_count, "empty")

        def bend_late_roots(d):
            f, _c = first_count(d, late)
            cur, = struct.unpack_from("<H", d, root_off(f))
            struct.pack_into("<H", d, root_off(f), 25 if cur != 25 else 1)
        case("8 the LATE probe's own roots bent", bend_late_roots, "late")

        case("9 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "roster_roots_negative_test")


if __name__ == "__main__":
    sys.exit(main())
