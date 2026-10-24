#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [29] -- the Exp. Share for every
new game, Character Mode on or off (2026-10-24).

Each case breaks a COPY of the built ROM in one way and requires the matching
[29] check to report FAIL BY NAME (any tamper also fails the BPS round-trip, so a
bare non-zero exit would prove nothing); the other built-ROM [29] check must
stay PASS.

  1. control                                     -- every check passes
  2. NewGameInitData's BL restored               -- the hook is gone
  3. the veneer aimed one halfword off            -- jumps into the middle of the function
  4. CM_NewGameExpShare sets flag 0x21            -- the wrong flag (Cmd_getexp reads 0x20)
  5. CM_NewGameExpShare drops its first call      -- ResetContestLinkResults no longer runs
  6. control again                                -- nothing left behind

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
    "site": "the BL goes through the veneer (ldr r3,[pc]; bx r3) to CM_NewGameExpShare",
    "fn": "CM_NewGameExpShare calls ResetContestLinkResults, FlagSet(0x20), CheckBagHasItem / AddBagItem(461)",
}
SITE = 0x176F50
VENEER = 0x1C3460
ORIG_BL_TARGET = 0x080E83A8


def _child_env():
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    path = os.path.join(HERE, "_negtest_verify_newgame.%d.py" % os.getpid())  # gitignored
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


def thumb_bl(src, dst):
    off = dst - (src + 4)
    return ((0xF000 | ((off >> 12) & 0x7FF)).to_bytes(2, "little")
            + (0xF800 | ((off >> 1) & 0x7FF)).to_bytes(2, "little"))


# A deliberate LITERAL -- see cm_tally.assert_cases.
EXPECT_CASES = 6


def _syms():
    out = subprocess.run(["arm-none-eabi-nm", os.path.join(ROOT, "build", "cm.elf")],
                         check=True, capture_output=True, text=True).stdout
    return {l.split()[2]: int(l.split()[0], 16) for l in out.splitlines()
            if len(l.split()) == 3}


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM -- run the injector first")
        return 0
    good = bytearray(open(BUILT, "rb").read())
    fn = (_syms()["CM_NewGameExpShare"] & ~1) - 0x08000000
    flag = fn + bytes(good[fn:fn + 0x20]).find(bytes.fromhex("2020"))      # movs r0,#0x20
    assert flag > fn, "movs r0,#0x20 not found in CM_NewGameExpShare"
    pool = fn + bytes(good[fn:fn + 0x48]).find((ORIG_BL_TARGET | 1).to_bytes(4, "little"))
    assert pool > fn, "ResetContestLinkResults literal not found in CM_NewGameExpShare"
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
                detail = "every [29] built check passes"
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

        print("negative test: verify_artifacts [29] new-game Exp. Share")
        case("1 control -- the real build", None, None)

        def restore(d):
            d[SITE:SITE + 4] = thumb_bl(0x08000000 + SITE, ORIG_BL_TARGET)
        case("2 NewGameInitData's BL restored", restore, "site")

        def off_by_one(d):
            w = int.from_bytes(d[VENEER + 4:VENEER + 8], "little")
            d[VENEER + 4:VENEER + 8] = (w + 2).to_bytes(4, "little")
        case("3 the veneer aimed one halfword off", off_by_one, "site")

        def wrong_flag(d):
            d[flag] = 0x21
        case("4 CM_NewGameExpShare sets flag 0x21", wrong_flag, "fn")

        def no_reset(d):
            d[pool:pool + 4] = (0x0810D255).to_bytes(4, "little")   # first call now FlagSet, not the original
        case("5 CM_NewGameExpShare drops ResetContestLinkResults", no_reset, "fn")

        case("6 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "newgame_exp_share_negative_test")


if __name__ == "__main__":
    sys.exit(main())
