#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [24] -- the overworld sprite
(2026-10-03) -- and [9b]'s reading of the activation callnative.

Each case breaks a COPY of the built ROM in one way and requires the matching
check to report FAIL BY NAME (a tampered ROM also fails the BPS round-trip, so a
bare non-zero exit would prove nothing); the other [24] checks must stay PASS.

  1. control                          -- every check passes
  2. the entry trampoline reverted    -- GetObjectEventGraphicsInfo is vanilla
  3. a pixel of Misty's walk frame    -- the art no longer equals her sheet
  4. Misty's info pointer zeroed      -- an offered character loses her sprite
  5. one palette reader left on base  -- that reader can't find the new tags
  6. an NPC's info pointer changed    -- the game's own table was edited
  7. the activation callnative aimed at the bare sweep -- the refresh is gone
  8. control again                    -- nothing left behind

⚠️ THE ROM IS NEVER MODIFIED IN PLACE.
"""
import json
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
sys.path.insert(0, os.path.join(ROOT, "tools", "character_mode"))
import seaglass_ow_player as owp  # noqa: E402

CHECKS = {
    "tramp": "GetObjectEventGraphicsInfo's entry is ldr r3,[pc]; bx r3",
    "table": "the info table gives every offered character with art an info",
    "pals": "all 12 palette readers share one copy",
    "art": "every sheet character's info draws its own sheet",
    "npc": "gObjectEventGraphicsInfoPointers is untouched",
    "wrap": "it is the overworld wrapper",
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
    path = os.path.join(HERE, "_negtest_verify_ow.%d.py" % os.getpid())  # unique per run; gitignored
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


# A deliberate LITERAL -- see cm_tally.assert_cases.
EXPECT_CASES = 8


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM -- run the injector first")
        return 0
    good = bytearray(open(BUILT, "rb").read())
    out = subprocess.run(["arm-none-eabi-nm", os.path.join(ROOT, "build", "ow_sprite.elf")],
                         check=True, capture_output=True, text=True).stdout
    chars = json.loads(owp.CHAR_MANIFEST.read_text())["characters"]
    misty = next(i for i, c in enumerate(chars) if c["character"] == "Misty")
    _hook = int(re.search(r"^([0-9a-f]+) T CM_GetObjectEventGraphicsInfo$", out, re.M).group(1), 16)
    base = (owp.ROOT / "rom" / "seaglass v3.0.gba").read_bytes()
    tab_off = owp.R(owp.build(base, chars)[2])      # the planner, replayed on the base ROM
    info = struct.unpack_from("<I", good, tab_off + 4 * misty)[0]
    imgs = struct.unpack_from("<I", good, owp.R(info) + 0x1C)[0]
    frame3 = owp.R(struct.unpack_from("<I", good, owp.R(imgs) + 24)[0])
    wrap = int(re.search(r"^([0-9a-f]+) T CM_SweepThenRefresh$", out, re.M).group(1), 16) | 1
    cm = subprocess.run(["arm-none-eabi-nm", os.path.join(ROOT, "build", "cm.elf")],
                        check=True, capture_output=True, text=True).stdout
    sweep = int(re.search(r"^([0-9a-f]+) T CM_SweepPartyToPCNative$", cm, re.M).group(1), 16) | 1
    fails, passes = [], 0

    with tempfile.TemporaryDirectory() as tmp:

        def case(name, mutate, want_fail):
            nonlocal passes
            data = bytearray(good)
            if mutate is not None:
                mutate(data)
                if data == good:
                    fails.append(name)
                    print("  [MISS] %s -- TAMPER CHANGED NOTHING" % name)
                    return
            rom = os.path.join(tmp, "tampered.gba")
            open(rom, "wb").write(bytes(data))
            _rc, out = run(rom)
            if want_fail is None:
                ok = all(_hit(out, k, "PASS") for k in CHECKS)
                detail = "every [24]/[9b] check passes"
            else:
                ok = _hit(out, want_fail, "FAIL")
                detail = "%r reported FAIL" % CHECKS[want_fail]
                for k in CHECKS:
                    if k != want_fail and not _hit(out, k, "PASS"):
                        ok = False
                        detail += "; but %r did not PASS" % CHECKS[k]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: verify_artifacts [24] overworld sprite")
        case("1 control -- the real build", None, None)

        def revert_tramp(d):
            o = owp.R(owp.GET_INFO)
            d[o:o + 8] = owp.GET_INFO_ORIG
        case("2 the entry trampoline reverted", revert_tramp, "tramp")

        def pixel(d):
            d[frame3 + 40] ^= 0xFF
        case("3 a pixel of Misty's walk frame changed", pixel, "art")

        def zero_misty(d):
            struct.pack_into("<I", d, tab_off + 4 * misty, 0)
        case("4 Misty's info pointer zeroed", zero_misty, "table")

        def one_reader(d):
            struct.pack_into("<I", d, owp.R(owp.PAL_TABLE_REFS[5]), owp.PAL_TABLE)
        case("5 one palette reader left on the base table", one_reader, "pals")

        def npc(d):
            o = owp.R(owp.INFO_TABLE) + 4 * 7
            struct.pack_into("<I", d, o, info)
        case("6 an NPC's info pointer changed", npc, "npc")

        def bare_sweep(d):
            k = d.find(bytes([0x23]) + struct.pack("<I", wrap), 0xEE3800, 0xEE3B00)
            assert k > 0, "activation callnative not found"
            struct.pack_into("<I", d, k + 1, sweep)
        case("7 the activation callnative aimed at the bare sweep", bare_sweep, "wrap")

        case("8 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "ow_sprite_negative_test")


if __name__ == "__main__":
    sys.exit(main())
