#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [26] -- 100% catch for on-roster
species (2026-10-09).

Each case breaks a COPY of the built ROM in one way and requires the matching
[26] check to report FAIL BY NAME (any tamper also fails the BPS round-trip, so a
bare non-zero exit would prove nothing); the other built-ROM [26] checks must
stay PASS.

  1. control                                   -- every check passes
  2. the odds compare restored                 -- the hook is gone
  3. the veneer aimed one halfword off          -- jumps into the middle of the stub
  4. the stub's compare made `cmp r3,#255`      -- off-by-one: 255 would shake
  5. CM_CatchOdds reads gBattlerAttacker        -- the wrong battler's species
  6. control again                              -- nothing left behind

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
    "site": "the odds compare is a BL to the catch veneer",
    "veneer": "the veneer is ldr r3,[pc]; bx r3 -> CM_CatchOddsStub",
    "stub": "redoes `cmp r3,#254` before returning",
    "fn": "CM_CatchOdds reads gBattlerTarget, gBattlerPartyIndexes, gEnemyParty",
}
SITE = 0x0A6284
VENEER = 0x001C3458


def _child_env():
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    path = os.path.join(HERE, "_negtest_verify_sure.%d.py" % os.getpid())  # gitignored
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
    syms = _syms()
    stub = (syms["CM_CatchOddsStub"] & ~1) - 0x08000000
    fn = (syms["CM_CatchOdds"] & ~1) - 0x08000000
    tgt = fn + bytes(good[fn:stub]).find((0x02000509).to_bytes(4, "little"))
    assert tgt > fn, "gBattlerTarget literal not found in CM_CatchOdds"
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
                detail = "every [26] built check passes"
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

        print("negative test: verify_artifacts [26] 100% roster catch")
        case("1 control -- the real build", None, None)

        def restore(d):
            d[SITE:SITE + 4] = bytes.fromhex("4b46fe2b")
        case("2 the odds compare restored", restore, "site")

        def off_by_one(d):
            w = int.from_bytes(d[VENEER + 4:VENEER + 8], "little")
            d[VENEER + 4:VENEER + 8] = (w + 2).to_bytes(4, "little")
        case("3 the veneer aimed one halfword off", off_by_one, "veneer")

        def cmp255(d):
            i = stub + bytes(d[stub:stub + 20]).find(bytes.fromhex("fe2b"))
            d[i] = 0xFF
        case("4 the stub's compare made cmp r3,#255", cmp255, "stub")

        def attacker(d):
            d[tgt:tgt + 4] = (0x02000508).to_bytes(4, "little")
        case("5 CM_CatchOdds reads another battler byte", attacker, "fn")

        case("6 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "sure_catch_negative_test")


if __name__ == "__main__":
    sys.exit(main())
