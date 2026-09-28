#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [20] -- the relocated
dynamic multichoice callback table (roster display, 2026-09-27).

The eight checks are worth exactly what they FAIL on, so break the built ROM in
each way the relocation can be wrong and require the matching check to report
FAIL BY NAME. A tampered ROM also breaks the BPS round-trip and diff
containment, so a bare non-zero exit would prove nothing about these eight.

  1. control                      -- the real build passes all eight
  2. a copied callback bent       -- [1].OnSelectionChanged no longer matches
                                     the base ROM's table
  3. the roster set's slot bent   -- slot [2] no longer holds the three
                                     callbacks linked into roster_display.elf
  4. one literal left behind      -- 0x081F02B0 still names the OLD table, so
                                     the init path and the change path read
                                     different tables. Both the literal check
                                     and the exhaustion check must fire.
  5. a literal off by one entry   -- ⭐ THE PLAUSIBLE-WRONG CASE: it points
                                     inside the new table, at real function
                                     pointers, so the copied-entries check
                                     stays green and only the literal fires
  6. a stray extra reference      -- something else now points at the new
                                     table, which the exhaustion check owns
  7. a table load retargeted      -- the ldr at 0x081F01CC no longer reads the
                                     repointed literal
  8. NONE changed to 2            -- `cmp r1, #255` -> `cmp r1, #2` at one
                                     load: slot [2] would become the sentinel
                                     and its callbacks would never run
  9. control again                -- proves cases 2-8 left nothing behind

⚠️ THE ROM IS NEVER MODIFIED IN PLACE. Each case writes a tampered COPY to a
temporary directory and runs a COPY of verify_artifacts.py pointed at it.
"""
import os
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cm_tally import assert_cases  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VERIFY = os.path.join(HERE, "verify_artifacts.py")
BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")

# Derived from the injector, never restated: a rebased table would otherwise be
# tampered at its old address and every case would MISS for a reason that is
# not about the checker.
_INJ = open(os.path.join(ROOT, "tools", "inject_character_mode.py"),
            encoding="utf-8").read()
TABLE_ADDR = int(re.search(r"^DYN_EVENT_TABLE_ADDR\s*=\s*(0x[0-9A-Fa-f]+)",
                           _INJ, re.M).group(1), 16)
TABLE_ORIG = int(re.search(r"^DYN_EVENT_TABLE_ORIG\s*=\s*(0x[0-9A-Fa-f]+)",
                           _INJ, re.M).group(1), 16)
TABLE_OFF = TABLE_ADDR - 0x08000000
ENTRY = 12
LIT_LEFT_BEHIND = 0x1F02B0        # the literal shared by two loads
LIT_OFF_BY_ONE = 0x1F05C4
LOAD_RETARGET = 0x081F01CC        # ldr r3, [pc, #224] -> 0x081F02B0
NONE_CMP = 0x081F04D4             # cmp r1, #255 guarding the OnDestroy load
STRAY_AT = 0x08FA5000             # free, 0xFF in base and build

CHECKS = {
    # Substrings, not whole sentences (see roster_roots_negative_test.py).
    "entries": "== the base ROM's table at",
    "reserved": "== the roster set's OnInit/OnSelectionChanged/",
    "lit_first": "literal 0x81efff4 ->",
    "lit_left": "literal %#x ->" % (LIT_LEFT_BEHIND + 0x08000000),
    "lit_obo": "literal %#x ->" % (LIT_OFF_BY_ONE + 0x08000000),
    "exhaust": "no reference to the old table remains",
    "loads": "table loads are pc-relative ldr's",
    "none": "is gated by `cmp r1, #255`",
}


def _child_env():
    """Strip the tally overrides: an inherited CM_EXPECT_CHECKS pins the CHILD
    too, and then the control fails for a reason unrelated to any tamper."""
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    # Must live in tools/tests/: verify_artifacts resolves the repo root from
    # its own __file__.
    path = os.path.join(HERE, "_negtest_verify_dyn.py")
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
    return any(line.strip().startswith(marker) and CHECKS[key] in line
               for line in out.splitlines())


def failed(out, key):
    return _hit(out, key, "FAIL")


def passed(out, key):
    return _hit(out, key, "PASS")


# A deliberate LITERAL -- see cm_tally.assert_cases.
EXPECT_CASES = 9


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM at %s -- run the injector first"
              % os.path.relpath(BUILT, ROOT))
        return 0
    good = bytearray(open(BUILT, "rb").read())
    fails, passes = [], 0

    with tempfile.TemporaryDirectory() as tmp:

        def case(name, mutate, want_fail, also_pass=()):
            nonlocal passes
            data = bytearray(good)
            if mutate is not None:
                mutate(data)
                if data == good:
                    fails.append("%s: TAMPER CHANGED NOTHING" % name)
                    print("  [MISS] %s -- TAMPER CHANGED NOTHING" % name)
                    return
            rom = os.path.join(tmp, "tampered.gba")
            open(rom, "wb").write(bytes(data))
            _rc, out = run(rom)
            if want_fail is None:
                ok = all(passed(out, k) for k in CHECKS)
                detail = "all eight callback-table checks pass"
            else:
                wants = want_fail if isinstance(want_fail, tuple) else (want_fail,)
                ok = all(failed(out, k) for k in wants)
                detail = " and ".join("%r reported FAIL" % CHECKS[k] for k in wants)
                # Checks that must stay SILENT prove the tamper was precise.
                for k in also_pass:
                    if not passed(out, k):
                        ok = False
                        detail += "; but %r did not PASS" % CHECKS[k]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: verify_artifacts [20] relocated callback table")
        case("1 control -- the real build", None, None)

        def bend_copied(d):
            o = TABLE_OFF + 1 * ENTRY + 4
            v, = struct.unpack_from("<I", d, o)
            struct.pack_into("<I", d, o, v + 4)
        case("2 a copied callback bent", bend_copied, "entries",
             also_pass=("reserved", "exhaust"))

        def bend_slot2(d):
            # the ROM's own set-1 OnSelectionChanged: a REAL callback, just
            # the wrong one -- the plausible-wrong shape
            struct.pack_into("<I", d, TABLE_OFF + 2 * ENTRY + 4, 0x081EFC7D)
        case("3 the roster set's OnSelectionChanged swapped for set 1's", bend_slot2,
             "reserved", also_pass=("entries",))

        def leave_one(d):
            struct.pack_into("<I", d, LIT_LEFT_BEHIND, TABLE_ORIG)
        case("4 one literal left at the OLD table", leave_one,
             ("lit_left", "exhaust"), also_pass=("lit_obo", "loads"))

        def off_by_one(d):
            struct.pack_into("<I", d, LIT_OFF_BY_ONE, TABLE_ADDR + ENTRY)
        case("5 a literal off by one entry (inside the new table)", off_by_one,
             "lit_obo", also_pass=("entries", "reserved", "lit_left"))

        def stray(d):
            struct.pack_into("<I", d, STRAY_AT - 0x08000000, TABLE_ADDR)
        case("6 a stray extra reference to the new table", stray, "exhaust",
             also_pass=("lit_left", "lit_obo"))

        def retarget(d):
            o = LOAD_RETARGET - 0x08000000
            h, = struct.unpack_from("<H", d, o)
            struct.pack_into("<H", d, o, (h & 0xFF00) | ((h + 1) & 0xFF))
        case("7 a table load retargeted", retarget, "loads",
             also_pass=("lit_left", "none"))

        def none_is_two(d):
            o = NONE_CMP - 0x08000000
            assert struct.unpack_from("<H", d, o)[0] == 0x29FF, \
                "NONE_CMP no longer holds cmp r1, #255 -- re-derive it"
            struct.pack_into("<H", d, o, 0x2902)
        case("8 NONE changed from 0xFF to 2 at one load", none_is_two, "none",
             also_pass=("loads",))

        case("9 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "dyn_event_table_negative_test")


if __name__ == "__main__":
    sys.exit(main())
