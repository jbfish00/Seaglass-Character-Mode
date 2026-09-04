#!/usr/bin/env python3
"""Negative test for the egg-hatch sweep checks in verify_artifacts.py.

The five checks added for the hatch hook (game_plans/rowe_parity.md
§13.16/§13.18) are worth exactly what they FAIL on. So break the built ROM on
purpose, in each direction the hook can be wrong, and require the matching
check to report FAIL by name -- not merely that the run exits 1, because a
tampered ROM also breaks the BPS round-trip check and that would look like a
catch while proving nothing about these five.

  1. control                    -- the real build passes all five
  2. the goto operand bent      -- the hatch jumps to the wrong tail
  3. the splice reverted        -- the stock tail is back, so the hook is
                                   simply absent while everything else is fine
  4. the callnative target bent -- the tail calls something that is not the
                                   activation sweep (this is the one a "looks
                                   like a callnative" test cannot catch)
  5. the sweep moved BEFORE the -- ordering is load-bearing: run before the
     waitstate                     waitstate the sweep sees an egg, and the
                                   egg exemption then keeps the hatchling
  6. control again

⚠️ The ROM is never modified in place. Each case writes a tampered COPY to a
temporary directory and runs a COPY of verify_artifacts.py pointed at it. The
base ROM under rom/ and the build under build/ are read-only here.
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VERIFY = os.path.join(HERE, "verify_artifacts.py")
BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")

sys.path.insert(0, os.path.join(ROOT, "tools", "character_mode"))
import egg_hook  # noqa: E402

EGG_TAIL_OFF = 0x8fa0000 - 0x08000000

CHECKS = {
    # ⚠️ Substrings, not full check names: the wording differs slightly between
    # the three ports' verifiers ("then callnative, then end" vs "callnative,
    # end"). Matching the whole sentence made this test report three MISSES --
    # control included -- which is the signature of a broken harness, not a
    # broken checker.
    "goto": "overlaid with `goto <egg tail>`",
    "shape": "egg tail replays hatch/waitstate",
    "sweep": "native IS the activation sweep",
}


def run(rom_path, tmp):
    """Run verify_artifacts against `rom_path`; return (rc, stdout)."""
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    # ⚠️ The copy must live in tools/tests/, not in the temp directory:
    # verify_artifacts.py resolves the repo root from its OWN __file__, so a
    # copy run from /tmp looks for rom/ and build/ beside /tmp and every check
    # fails for a reason that has nothing to do with the tamper. That is what
    # this test hit on its first run -- all six cases MISSED, control included,
    # which is the signature of a broken harness rather than a broken checker.
    path = os.path.join(HERE, "_negtest_verify_egg.py")
    open(path, "w", encoding="utf-8").write(src)
    try:
        p = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, cwd=ROOT)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return p.returncode, p.stdout + p.stderr


def _hit(out, key, marker):
    """True if the named check reported `marker` in this run.

    ⚠️ The two verifiers in this workspace print differently -- "[FAIL] name"
    in the FireRed pair, "FAIL name" in the Emerald pair -- so match the word
    at the start of the line rather than a bracketed token.
    """
    for line in out.splitlines():
        t = line.strip().lstrip("[")
        if t.startswith(marker) and CHECKS[key] in line:
            return True
    return False


def failed(out, key):
    return _hit(out, key, "FAIL")


def passed(out, key):
    return _hit(out, key, "PASS")


def main():
    if not os.path.isfile(BUILT):
        print("SKIP: no built ROM at %s -- run the injector first"
              % os.path.relpath(BUILT, ROOT))
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
                    fails.append("%s: TAMPER CHANGED NOTHING" % name)
                    return
            rom = os.path.join(tmp, "tampered.gba")
            open(rom, "wb").write(bytes(data))
            _rc, out = run(rom, tmp)
            if want_fail is None:
                ok = all(passed(out, k) for k in CHECKS)
                detail = "all five egg checks pass"
            else:
                ok = failed(out, want_fail)
                detail = "%r reported FAIL" % CHECKS[want_fail]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: the egg-hatch sweep checks")
        case("1 control -- the real build", None, None)

        def bend_goto(d):
            struct.pack_into("<I", d, egg_hook.SPLICE_FILE_OFF + 1, 0x8fa0100)
        case("2 the goto operand bent to another address", bend_goto, "goto")

        def revert(d):
            o = egg_hook.SPLICE_FILE_OFF
            d[o:o + len(egg_hook.SPLICE_ORIG)] = egg_hook.SPLICE_ORIG
        case("3 the splice reverted (the hook simply absent)", revert, "goto")

        def bend_native(d):
            struct.pack_into("<I", d, EGG_TAIL_OFF + 6, 0x08000001)
        case("4 the callnative target bent off the sweep", bend_native, "sweep")

        def reorder(d):
            # sweep first, then the hatch and its waitstate: same bytes, same
            # length, and every "is there a callnative" test still passes.
            d[EGG_TAIL_OFF:EGG_TAIL_OFF + 11] = (
                bytes([0x23]) + d[EGG_TAIL_OFF + 6:EGG_TAIL_OFF + 10]
                + bytes([0x25]) + d[EGG_TAIL_OFF + 1:EGG_TAIL_OFF + 3]
                + bytes([0x27, egg_hook.OPCODE_RELEASEALL, 0x02]))
        case("5 the sweep moved BEFORE the hatch's waitstate", reorder, "shape")

        case("6 control again", None, None)

    print("\n%d/6 negative cases behaved" % passes)
    if fails:
        print("MISSED: " + "; ".join(fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
