#!/usr/bin/env python3
"""Negative test for verify_artifacts.py check [25] -- reusable TMs (2026-10-09).

Each case breaks a COPY of the built ROM in one way and requires the matching
[25] check to report FAIL BY NAME (any tamper also fails the BPS round-trip, so a
bare non-zero exit would prove nothing); the other built-ROM [25] checks must
stay PASS.

  1. control                              -- every check passes
  2. TM50 left consumable (importance 0)  -- one TM still disappears when taught
  3. TM07 importance 3 instead of 1       -- a neighbouring bit was clobbered
  4. HM03's importance byte changed       -- an HM was edited
  5. a TM record's price byte changed     -- a stray edit inside the records
  6. control again                        -- nothing left behind

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
    "imp": "every TM01-TM100 record has importance 1",
    "only": "exactly 100 bytes changed across the TM records, HMs untouched",
}
TM01_NAME = 0x0068A674   # file offset of TM01's inline name (base ROM); stride 84
STRIDE = 84


def _child_env():
    env = dict(os.environ)
    env.pop("CM_EXPECT_CHECKS", None)
    env.pop("CM_EXPECT_CASES", None)
    return env


def run(rom_path):
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    path = os.path.join(HERE, "_negtest_verify_tm.%d.py" % os.getpid())  # gitignored
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


def tm(k):
    return TM01_NAME + (k - 1) * STRIDE


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM -- run the injector first")
        return 0
    good = bytearray(open(BUILT, "rb").read())
    assert good[tm(1):tm(1) + 4] == bytes([0xCE, 0xC7, 0xA1, 0xA2]), "TM01 name moved"
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
                detail = "every [25] built check passes"
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

        print("negative test: verify_artifacts [25] reusable TMs")
        case("1 control -- the real build", None, None)

        def tm50(d):
            d[tm(50) + 0x2C] &= ~1
        # TM50 back to the base byte: [25] imp fails, but the diff count is
        # then 99, so "only" fails too -- require imp and accept only's FAIL.
        CHECKS_SAVED = dict(CHECKS)
        del CHECKS["only"]
        case("2 TM50 left consumable", tm50, "imp")
        CHECKS.update(CHECKS_SAVED)

        def tm07(d):
            d[tm(7) + 0x2C] |= 2
        case("3 TM07 importance 3 instead of 1", tm07, "imp")

        def hm03(d):
            d[tm(100) + 3 * STRIDE + 0x2C] ^= 0x02
        case("4 HM03's importance byte changed", hm03, "only")

        def price(d):
            d[tm(23) + 0x3C] ^= 0x01
        case("5 a TM record's price byte changed", price, "only")

        case("6 control again -- nothing left behind", None, None)

    total = passes + len(fails)
    if fails:
        print("RESULT: %d/%d -- MISSED: %s" % (passes, total, ", ".join(fails)))
        return 1
    print("RESULT: %d/%d ALL PASS" % (passes, total))
    return assert_cases(total, EXPECT_CASES, "reusable_tm_negative_test")


if __name__ == "__main__":
    sys.exit(main())
