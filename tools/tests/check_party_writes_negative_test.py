#!/usr/bin/env python3
"""Negative test for check_party_writes.py.

The inventory's whole value is that it FAILS when the set of mon-sized copies
into gPlayerParty changes, or when one arrives through a copy primitive nobody
has looked at. So break it on purpose, in each direction, with a control at
each end -- a checker that rejected everything would pass every negative case
and look correct.

  1. control                   -- the real inventory passes
  2. an entry DELETED          -- a real copy site is now uninventoried, i.e. a
                                  new way into the party arriving silently
  3. a bogus entry ADDED       -- the inventory describes a copy the ROM does
                                  not have (a stale inventory)
  4. a callee REMOVED from     -- a mon reaching the party through an
     EXPECT_CALLEES               unexamined primitive must fail check 3
  5. every GATED downgraded    -- an inventory with no enforcement copy at all
                                  still satisfies 2, 3 and 4; check 4 catches it
  6. control again

Every tamper must both CHANGE something and PARSE: a SyntaxError also exits 1
and would read exactly like the checker catching the tamper. This workspace has
mistaken a bad tamper for a real result more than once.
"""
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "check_party_writes.py")


def run(path):
    return subprocess.run([sys.executable, path], capture_output=True,
                          text=True).returncode


def main():
    if not os.path.isfile(REAL):
        print("SKIP: no check_party_writes.py here")
        return 0
    src = open(REAL, encoding="utf-8").read()
    fails, passes, tmps = [], 0, []

    def case(label, want, mutated=None):
        nonlocal passes
        if mutated is None:
            got = run(REAL)
        else:
            if mutated == src:
                print("  FAIL  %-52s TAMPER CHANGED NOTHING" % label)
                fails.append(label + " (inert tamper)")
                return
            try:
                ast.parse(mutated)
            except SyntaxError as e:
                print("  FAIL  %-52s TAMPER IS NOT VALID PYTHON: %s" % (label, e))
                fails.append(label + " (broken tamper)")
                return
            p = os.path.join(HERE, "_tmp_pw_%d.py" % len(tmps))
            tmps.append(p)
            open(p, "w", encoding="utf-8").write(mutated)
            got = run(p)
        ok = (got == 0) == (want == 0)
        print("  %-5s %-52s exit=%d" % ("ok" if ok else "FAIL", label, got))
        if ok:
            passes += 1
        else:
            fails.append(label)

    try:
        case("control: the real inventory passes", 0)

        m = re.search(r"^    0x[0-9a-fA-F]+: \(\"[A-Z-]+\",\n"
                      r"(?:\s+\"(?:[^\"\\]|\\.)*\"\n)*"
                      r"\s+\"(?:[^\"\\]|\\.)*\"\),\n", src, re.M)
        if not m:
            print("  FAIL  could not find an inventory row to delete -- the "
                  "tamper hit nothing, which is not the same as the checker "
                  "being fine")
            fails.append("tamper 2")
        else:
            case("a deleted inventory entry fails", 1,
                 src[:m.start()] + src[m.end():])

        case("a bogus inventory entry fails", 1,
             src.replace("INVENTORY = {",
                         'INVENTORY = {\n    0x00000010: ("EXEMPT", "not a real copy site"),', 1))

        mc = re.search(r"EXPECT_CALLEES = frozenset\(\{(0x[0-9a-fA-F]+)", src)
        if not mc:
            print("  FAIL  could not find EXPECT_CALLEES to tamper")
            fails.append("tamper 4")
        else:
            case("a copy primitive missing from EXPECT_CALLEES fails", 1,
                 src[:mc.start(1)] + "0x08000002" + src[mc.end(1):])

        case("an inventory with no GATED copy fails", 1,
             src.replace('("GATED",', '("UNVERIFIED",'))

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
    print("\nparty-write inventory negative test: %d/%d PASS" % (passes, passes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
