#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [21] -- the roster display's
entry scripts and code (2026-09-27).

Break the built ROM in each way the entry can be wrong and require the
matching check to report FAIL BY NAME (a tampered ROM also fails the BPS
round-trip and diff containment, so a bare exit code proves nothing).

  1. control                      -- the real build passes all seven
  2. roster code bent             -- one byte inside the linked unit
  3. roots literal bent           -- the compiled ROSTER_ROOTS_ADDR points one
                                     entry off: every row would be another
                                     character's. ⭐ Plausible-wrong: real species.
  4. clipboard pointer inserted   -- the BG pointer goes straight to the old
                                     entry (the shape an INSERTED pre-entry
                                     would leave: the appended check fires)
  5. clipboard row 2 re-aimed     -- "Questionnaire" now runs the cheat device
  6. bedroom row 1 re-aimed       -- "Character code" skips the callnative
  7. pre-entries split            -- the bedroom's row 0 targets a different
                                     block than the clipboard's
  8. roster block set 2 -> 1      -- the list would draw ITEM icons: the ROM's
                                     own set, a real callback set, the wrong one
  9. stack form argc 1 -> 0       -- the handler returns early: no list at all
 10. control again                -- nothing left behind

⚠️ THE ROM IS NEVER MODIFIED IN PLACE: tampered copies in a temp directory,
verified by a copy of verify_artifacts.py.
"""
import os
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
ROSTER_BIN = os.path.join(ROOT, "build", "roster_display.bin")

BG_EVENT_PTR_OFF = 0x123ACC
BEDROOM_BG_PTR_OFF = 0xA89A98
ORIG_CM_ENTRY = 0x08EE3800
ORIG_CHEAT_DEVICE = 0x0830FBC9
_INJ = open(os.path.join(ROOT, "tools", "inject_character_mode.py"), encoding="utf-8").read()
import re  # noqa: E402
ROSTER_MENU_ADDR = int(re.search(r"^ROSTER_MENU_ADDR\s*=\s*(0x[0-9A-Fa-f]+)", _INJ, re.M).group(1), 16)
ROSTER_ROOTS_ADDR = int(re.search(r"^ROSTER_ROOTS_ADDR\s*=\s*(0x[0-9A-Fa-f]+)", _INJ, re.M).group(1), 16)

CHECKS = {
    "inrom": "roster code in-ROM == roster_display.bin",
    "consts": "compiled roster code carries ROSTER_ROOTS_ADDR",
    "appended": "starts exactly at the old blob's end",
    "clip": "clipboard pre-entry: lockall, menu",
    "bed": "bedroom pre-entry: same menu",
    "share": "both pre-entries share one roster block",
    "block": "roster block: callnative CM_RosterPushRows",
}


def _child_env():
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    path = os.path.join(HERE, "_negtest_verify_roster_entry.py")
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


def u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


# Pre-entry layout (verify_artifacts._rd_decode): checkflag+goto_if 9, lockall
# 1, dynmultichoice 12 + 3*4, then three 11-byte compare/goto_if rows.
ROWS_AT = 9 + 1 + 12 + 12


def row_target_off(d, pre_ptr, row):
    return (pre_ptr & 0x01FFFFFF) + ROWS_AT + row * 11 + 7


EXPECT_CASES = 10


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM -- run the injector first")
        return 0
    good = bytearray(open(BUILT, "rb").read())
    clip = u32(good, BG_EVENT_PTR_OFF)
    bed = u32(good, BEDROOM_BG_PTR_OFF)
    roster_block = u32(good, row_target_off(good, clip, 0)) & 0x01FFFFFF
    code_off = ROSTER_MENU_ADDR & 0x01FFFFFF
    code_len = len(open(ROSTER_BIN, "rb").read())
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
                ok = all(_hit(out, k, "PASS") for k in CHECKS)
                detail = "all seven roster-entry checks pass"
            else:
                ok = _hit(out, want_fail, "FAIL")
                detail = "%r reported FAIL" % CHECKS[want_fail]
                for k in also_pass:
                    if not _hit(out, k, "PASS"):
                        ok = False
                        detail += "; but %r did not PASS" % CHECKS[k]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: verify_artifacts [21] roster display entry + code")
        case("1 control -- the real build", None, None)

        def bend_code(d):
            d[code_off + 8] ^= 0x01
        case("2 roster code bent", bend_code, "inrom", also_pass=("clip", "bed", "block"))

        def bend_roots_lit(d):
            for i in range(code_off, code_off + code_len - 3, 4):
                if u32(d, i) == ROSTER_ROOTS_ADDR:
                    struct.pack_into("<I", d, i, ROSTER_ROOTS_ADDR + 4)
        case("3 compiled roots literal one entry off", bend_roots_lit, "consts",
             also_pass=("clip", "bed", "block"))

        def insert_shape(d):
            struct.pack_into("<I", d, BG_EVENT_PTR_OFF, ORIG_CM_ENTRY)
        case("4 clipboard pointer straight to the old entry", insert_shape, "appended",
             also_pass=("bed",))

        def clip_row2(d):
            struct.pack_into("<I", d, row_target_off(d, clip, 2), ORIG_CHEAT_DEVICE)
        case("5 clipboard 'Questionnaire' re-aimed at the cheat device", clip_row2, "clip",
             also_pass=("bed", "share", "block"))

        def bed_row1(d):
            o = row_target_off(d, bed, 1)
            struct.pack_into("<I", d, o, u32(d, o) + 5)   # past the callnative
        case("6 bedroom 'Character code' skips CM_OpenCodeEntry", bed_row1, "bed",
             also_pass=("clip", "share", "block"))

        def split(d):
            o = row_target_off(d, bed, 0)
            struct.pack_into("<I", d, o, u32(d, o) + 5)
        case("7 bedroom row 0 aimed at a different block", split, "share",
             also_pass=("clip",))

        def set_one(d):
            d[roster_block + 16 + 10] = 1
        case("8 roster block callback set 2 -> 1 (item icons)", set_one, "block",
             also_pass=("clip", "bed", "share"))

        def argc_zero(d):
            d[roster_block + 16 + 11] = 0
        case("9 stack form argc 1 -> 0 (handler returns early)", argc_zero, "block",
             also_pass=("clip", "bed", "share"))

        case("10 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "roster_entry_negative_test")


if __name__ == "__main__":
    sys.exit(main())
