#!/usr/bin/env python3
"""Negative test for check_acquisition_paths.py.

The inventory's whole value is that it FAILS when the set of party-count
writers changes. So break it on purpose, in each direction, with a control at
each end -- a checker that rejected everything would pass all the negative
cases and look correct.

  1. control                      -- the real inventory passes
  2. an entry DELETED             -- a real writer is now uninventoried, i.e.
                                     a new acquisition path arriving silently
  3. a bogus entry ADDED          -- the inventory describes a writer the ROM
                                     does not have (a stale inventory)
  4. every GATED downgraded       -- an inventory with no enforcement point at
                                     all still satisfies (2) and (3); check 3
                                     is what catches it
  5. control again

The tampered copies are written beside the original so its `from cm_tally
import` still resolves, and removed in a finally block. Nothing writes to the
ROM or to the real checker.
"""
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "check_acquisition_paths.py")


def run(path):
    return subprocess.run([sys.executable, path], capture_output=True,
                          text=True).returncode


def main():
    if not os.path.isfile(REAL):
        print("SKIP: no check_acquisition_paths.py here")
        return 0
    src = open(REAL, encoding="utf-8").read()
    fails, passes, tmps = [], 0, []

    def case(label, want, mutated=None):
        nonlocal passes
        if mutated is None:
            got = run(REAL)
        else:
            # A tamper that produces a SyntaxError also exits 1, which would
            # look like the checker catching it. Four times in this workspace a
            # result has turned out to be a bad tamper rather than a real
            # finding; assert the mutation is valid Python AND that it actually
            # changed something, so neither can be mistaken for evidence.
            if mutated == src:
                print("  FAIL  %-50s TAMPER CHANGED NOTHING" % label)
                fails.append(label + " (inert tamper)")
                return
            try:
                ast.parse(mutated)
            except SyntaxError as e:
                print("  FAIL  %-50s TAMPER IS NOT VALID PYTHON: %s"
                      % (label, e))
                fails.append(label + " (broken tamper)")
                return
            p = os.path.join(HERE, "_tmp_acq_%d.py" % len(tmps))
            tmps.append(p)
            open(p, "w", encoding="utf-8").write(mutated)
            got = run(p)
        ok = (got == 0) == (want == 0)
        print("  %-5s %-50s exit=%d" % ("ok" if ok else "FAIL", label, got))
        if ok:
            passes += 1
        else:
            fails.append(label)

    try:
        case("control: the real inventory passes", 0)

        # delete the first inventory row
        # Multi-line reasons are the norm, so match a whole row: the verdict
        # tuple plus every continuation string up to the closing "),".
        m = re.search(r"^    0x[0-9a-fA-F]+: \(\"[A-Z-]+\",\n"
                      r"(?:\s+\"(?:[^\"\\]|\\.)*\"\n)*"
                      r"\s+\"(?:[^\"\\]|\\.)*\"\),\n", src, re.M)
        if not m:
            print("  FAIL  could not find an inventory row to delete "
                  "-- the tamper hit nothing, which is not the same as the "
                  "checker being fine")
            fails.append("tamper 2")
        else:
            case("a deleted inventory entry fails", 1,
                 src[:m.start()] + src[m.end():])

        # add a writer the ROM does not contain
        case("a bogus inventory entry fails", 1,
             src.replace("INVENTORY = {",
                         'INVENTORY = {\n    0x00000010: ("GATED", "not a real writer"),', 1))

        # an inventory with no enforcement point at all
        case("an inventory with no GATED writer fails", 1,
             src.replace('("GATED",', '("UNVERIFIED",'))

        # check 4, both directions: a NEW ungated path must fail, and a known
        # one that quietly stopped being ungated must fail too.
        case("a new UNGATED path fails", 1,
             src.replace("INVENTORY = {",
                         'INVENTORY = {\n    0x00040c3e: ("UNGATED", "pretend hole"),',
                         1).replace('    0x00040c3e: ("EXEMPT",', '    0x000c3e00: ("EXEMPT",', 1)
             if '0x00040c3e: ("EXEMPT",' in src else
             src.replace("EXPECT_UNGATED = frozenset({", "EXPECT_UNGATED = frozenset({0x00000004, ", 1)
             if "EXPECT_UNGATED = frozenset({" in src else
             src.replace("EXPECT_UNGATED = frozenset()",
                         "EXPECT_UNGATED = frozenset({0x00000004})", 1))
        case("an UNGATED path that vanished from the set fails", 1,
             src.replace('("UNGATED",', '("EXEMPT",', 1)
             if '("UNGATED",' in src else
             src.replace("EXPECT_UNGATED = frozenset()",
                         "EXPECT_UNGATED = frozenset({0x00000008})", 1))

        case("control: the real inventory still passes", 0)
    finally:
        for p in tmps:
            try:
                os.remove(p)
            except OSError:
                pass

    if fails:
        print("\nFAILURES: " + ", ".join(fails))
        return 1
    print("\nacquisition inventory negative test: %d/%d PASS" % (passes, passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
