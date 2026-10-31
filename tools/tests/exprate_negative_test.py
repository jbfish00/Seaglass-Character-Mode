#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [31] -- EXP rate (QoL, user 2026-10-29).

Each case breaks a COPY of the built ROM in one way and requires the matching [31] check to report FAIL BY NAME
(any tamper also fails the BPS round-trip, so a bare non-zero exit would prove nothing); the other built-ROM [31]
checks must stay PASS. (The compiled-code check reads build/cm.bin; run_tests.sh proves it fails on the CM_NO_EXPRATE
build.)

  1. control                                            -- every check passes
  2. the getexp BL put back on ApplyExperienceMultipliers -- the rate is never applied
  3. row 16's callback aimed one halfword off           -- the START row runs garbage
  4. the builder appends action 15 instead of 16        -- EDIT STATS, not EXP RATE
  5. the input handler skips the fade for action 15     -- the chooser opens on a black screen
  6. the chooser's initial row read from VAR 0x8001     -- the current rate is not preselected
  7. control again                                      -- nothing left behind

THE ROM IS NEVER MODIFIED IN PLACE.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cm_tally import assert_cases  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VERIFY = os.path.join(HERE, "verify_artifacts.py")
BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")

CHECKS = {
    "bl": "getexp: the BL at 0x0809441E called ApplyExperienceMultipliers",
    "table": "START: both sStartMenuItems readers point at the copy",
    "build": "START: BuildNormalStartMenu's tail writes SAVE (5)",
    "input": "START: HandleStartMenuInput skips the fade for action 16",
    "script": "the chooser script: lockall",
}
BL_SITE, BL_ORIG = 0x09441E, bytes.fromhex("13f04bff")
ROW16_FUNC = 0xFA9000 + 16 * 8 + 4
BUILD_MOVS16 = 0x1FF7B2
INPUT_CMP16 = 0x20002E
SCRIPT_INITIAL = 0xFA9100 + 20


def _child_env():
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    path = os.path.join(HERE, "_negtest_verify_exprate.%d.py" % os.getpid())  # gitignored
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
EXPECT_CASES = 7


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM -- run the injector first")
        return 0
    good = bytearray(open(BUILT, "rb").read())
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
                detail = "every [31] built check passes"
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

        print("negative test: verify_artifacts [31] EXP rate")
        case("1 control -- the real build", None, None)

        def bl_back(d):
            d[BL_SITE:BL_SITE + 4] = BL_ORIG
        case("2 the getexp BL put back on ApplyExperienceMultipliers", bl_back, "bl")

        def row_off(d):
            v = int.from_bytes(d[ROW16_FUNC:ROW16_FUNC + 4], "little")
            d[ROW16_FUNC:ROW16_FUNC + 4] = (v + 2).to_bytes(4, "little")
        case("3 row 16's callback aimed one halfword off", row_off, "table")

        def build15(d):
            assert d[BUILD_MOVS16:BUILD_MOVS16 + 2] == bytes.fromhex("1022")
            d[BUILD_MOVS16] = 0x0F
        case("4 the builder appends action 15", build15, "build")

        def input15(d):
            assert d[INPUT_CMP16:INPUT_CMP16 + 2] == bytes.fromhex("1028")
            d[INPUT_CMP16] = 0x0F
        case("5 the input handler skips the fade for action 15", input15, "input")

        def initial(d):
            assert d[SCRIPT_INITIAL:SCRIPT_INITIAL + 2] == bytes.fromhex("0080")
            d[SCRIPT_INITIAL] = 0x01
        case("6 the chooser's initial row read from VAR 0x8001", initial, "script")

        case("7 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "exprate_negative_test")


if __name__ == "__main__":
    sys.exit(main())
