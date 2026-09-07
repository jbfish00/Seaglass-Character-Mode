#!/usr/bin/env python3
"""Negative test for the PC-exit sweep checks in verify_artifacts.py.

The ten checks added for the PC-exit hook (five per site, two sites)
(game_plans/rowe_parity.md §13.24/§13.26c) are worth exactly what they FAIL on.
So break the built ROM on purpose, in each direction the hook can be wrong, and
require the matching check to report FAIL by name -- not merely that the run
exits 1, because a tampered ROM also breaks the BPS round-trip check and that
would look like a catch while proving nothing about these five.

  1. control                    -- the real build passes all ten
  2. the goto operand bent      -- the PC script jumps to the wrong tail
  3. the splice reverted        -- the stock tail is back, so the hook is
                                   simply absent while everything else is fine
  4. the callnative target bent -- the tail calls something that is not the
                                   activation sweep (this is the one a "looks
                                   like a callnative" test cannot catch)
  5. the sweep moved BEFORE the -- ordering is load-bearing: run before the
     waitstate                     waitstate the sweep sees the party the
                                   player walked IN with, a silent no-op
  6. the CROSS-WIRE             -- site 0's tail rejoins site 1's caller. The
                                   tail is still perfectly well-formed and
                                   every check but the rejoin passes, while the
                                   player is sent to the wrong PC menu on exit.
                                   ⭐ A single-site splice cannot have this
                                   case; any multi-site one needs it.
  7. control again

⚠️ The ROM is never modified in place. Each case writes a tampered COPY to a
temporary directory and runs a COPY of verify_artifacts.py pointed at it. The
base ROM under rom/ and the build under build/ are read-only here.
"""
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
VERIFY = os.path.join(HERE, "verify_artifacts.py")
BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")

sys.path.insert(0, os.path.join(ROOT, "tools", "character_mode"))
import pc_hook  # noqa: E402

PC_TAIL_OFF = 0x8fa1000 - 0x08000000

CHECKS = {
    # ⚠️ Substrings, not full check names -- the wording differs between the
    # ports, and matching whole sentences made the egg version of this test
    # report three MISSES including the CONTROL, which is the signature of a
    # broken harness rather than a broken checker.
    # ⭐ Every tamper below hits SITE 0, and each substring is prefixed [PC0]
    # so a tamper cannot be "caught" by the OTHER site's check failing for an
    # unrelated reason.
    "goto": "[PC0] PC script tail overlaid",
    "shape": "[PC0] PC tail replays special/waitstate",
    "sweep": "[PC0] the PC tail's native IS the activation sweep",
}


def run(rom_path):
    """Run verify_artifacts against `rom_path`; return (rc, stdout)."""
    src = open(VERIFY, encoding="utf-8").read()
    src = src.replace('ROM_OUT = ROOT / "build" / "seaglass_cm.gba"',
                      'ROM_OUT = Path(%r)' % rom_path, 1)
    # ⚠️ The copy must live in tools/tests/, not in the temp directory:
    # verify_artifacts.py resolves the repo root from its OWN __file__, so a
    # copy run from /tmp looks for rom/ and build/ beside /tmp and every check
    # fails for a reason that has nothing to do with the tamper.
    path = os.path.join(HERE, "_negtest_verify_pc.py")
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
            _rc, out = run(rom)
            if want_fail is None:
                ok = all(passed(out, k) for k in CHECKS)
                detail = "all ten PC checks pass"
            else:
                ok = failed(out, want_fail)
                detail = "%r reported FAIL" % CHECKS[want_fail]
            print("  [%s] %s -- %s" % ("PASS" if ok else "MISS", name, detail))
            if ok:
                passes += 1
            else:
                fails.append(name)

        print("negative test: the PC-exit sweep checks")
        case("1 control -- the real build", None, None)

        def bend_goto(d):
            struct.pack_into("<I", d, pc_hook.SITES[0][1] + 1, 0x8fa1900)
        case("2 the goto operand bent to another address", bend_goto, "goto")

        def revert(d):
            o, orig = pc_hook.SITES[0][1], pc_hook.SITES[0][2]
            d[o:o + len(orig)] = orig
        case("3 the splice reverted (the hook simply absent)", revert, "goto")

        def bend_native(d):
            # A plausible-looking callnative that is NOT the sweep -- the case a
            # "looks like a callnative" test cannot catch.
            struct.pack_into("<I", d, PC_TAIL_OFF + 5, 0x08ed2275)
        case("4 the callnative target bent off the sweep", bend_native, "sweep")

        def reorder(d):
            # Sweep BEFORE the special/waitstate: same bytes, same length, and
            # every "is there a callnative" test still passes -- but the sweep
            # would run before the storage UI opens, seeing the party the player
            # walked IN with. A silent no-op.
            o = PC_TAIL_OFF
            d[o:o + 9] = (bytes([0x23]) + d[o + 5:o + 9]
                          + bytes([0x25]) + d[o + 1:o + 3] + bytes([0x27]))
        case("5 the sweep moved BEFORE the PC's waitstate", reorder, "shape")

        def crosswire(d):
            # ⭐ THE TAMPER THE EGG HOOK DID NOT NEED: point site 0's tail at
            # site 1's return address. The tail is still perfectly well-formed
            # -- right special, right waitstate, right sweep -- and every check
            # except the rejoin passes, but the player would be sent to the
            # wrong PC menu on exit.
            struct.pack_into("<I", d, PC_TAIL_OFF + 10,
                             struct.unpack_from("<I", pc_hook.SITES[1][2], 5)[0])
        case("6 site 0's tail rejoins site 1's caller", crosswire, "shape")

        case("7 control again", None, None)

    print("\n%d/7 negative cases behaved" % passes)
    if fails:
        print("MISSED: " + "; ".join(fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
