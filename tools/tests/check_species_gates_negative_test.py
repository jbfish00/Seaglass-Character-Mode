#!/usr/bin/env python3
"""Negative test for check_species_gates.py.

The inventory is worth nothing unless it FAILS when the set of ChoosePartyMon
call sites changes, when a decoded gate stops testing the species it is
recorded as testing, when a reward stops being handed over, or when either
name table moves under it. Break it on purpose in each of those directions,
with a control at each end -- a checker that rejected everything would pass
every negative case and look correct.

  1. control                  -- the real inventory passes
  2. a SITE deleted           -- a way to hand a Pokemon to an NPC is now
                                 uninventoried, i.e. arriving silently
  3. a bogus SITE added       -- the inventory describes a site the ROM does
                                 not have (a stale inventory, or the wrong ROM)
  4. a gate species CHANGED   -- the recorded species is no longer what the
                                 script compares
  5. a reward CHANGED         -- the recorded give-item no longer sits there
  6. an item probe CHANGED    -- the item-name table moved, so every reward in
                                 the report would name the wrong item
  7. a species probe CHANGED  -- ditto for the species-name table
  8. the scanner blinded      -- the special id is wrong, so the scan reaches
                                 nothing; an empty result satisfies check 2 and
                                 only the anti-vacuity check catches it
  9. control again

A case marked n/a is one this port cannot have (Seaglass's only gate is tested
in native code and gives no item, so it has no species operand and no reward
to bend); it is reported, and it is NOT counted as a pass.

WARNING Every tamper must both CHANGE something and PARSE: a SyntaxError also
exits 1 and would read exactly like the checker catching the tamper. This
workspace has mistaken a bad tamper for a real result more than once -- a
"MISS" in a negative test is more often a bad tamper than a real gap.
"""
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "check_species_gates.py")


def run(path):
    p = subprocess.run([sys.executable, path], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    if not os.path.isfile(REAL):
        print("SKIP: no check_species_gates.py here")
        return 0
    src = open(REAL, encoding="utf-8").read()
    fails, passes, na, tmps = [], 0, 0, []

    def skip(name, why):
        nonlocal na
        na += 1
        print("  [n/a ] %s -- %s" % (name, why))

    def case(name, text, want_rc, want_in_output=None):
        nonlocal passes
        if text != src:
            try:
                ast.parse(text)
            except SyntaxError as e:
                fails.append("%s: TAMPER DID NOT PARSE (%s)" % (name, e))
                return
        elif want_rc != 0:
            fails.append("%s: TAMPER CHANGED NOTHING" % name)
            return
        path = os.path.join(HERE, "_negtest_species_gates.py")
        open(path, "w", encoding="utf-8").write(text)
        tmps.append(path)
        rc, out = run(path)
        ok = (rc == want_rc)
        if ok and want_in_output:
            ok = want_in_output in out
        print("  [%s] %s (rc=%d, wanted %d)" % ("PASS" if ok else "MISS",
                                                name, rc, want_rc))
        if ok:
            passes += 1
        else:
            fails.append(name)

    print("negative test: check_species_gates.py")
    case("1 control -- the real inventory passes", src, 0)

    first = re.search(r"\nSITES = \(\n    (0x[0-9a-f]+),\n", src)
    case("2 an inventoried call SITE deleted",
         src.replace(first.group(0), "\nSITES = (\n", 1),
         1, "every ChoosePartyMon call site in the ROM is inventoried")

    case("3 a bogus SITE added",
         src.replace("SITES = (\n", "SITES = (\n    0x08000004,\n", 1),
         1, "every inventoried call site is still present in the ROM")

    m = re.search(r"\n  \((\d+),(\)| \d+)", src)
    if m:
        bent = src.replace(m.group(0),
                           "\n  (%d,%s" % (int(m.group(1)) + 7, m.group(2)), 1)
        case("4 a recorded gate species CHANGED", bent,
             1, "still compares its recorded species")
    else:
        skip("4 a recorded gate species CHANGED",
             "no gate in this port has a species operand (all native tests)")

    m = re.search(r"\((0x[0-9a-f]+), (\d+), (\d+)\)", src)
    if m:
        bent = src.replace(m.group(0), "(%s, %d, %s)"
                           % (m.group(1), int(m.group(2)) + 1, m.group(3)), 1)
        case("5 a recorded reward CHANGED", bent,
             1, "still gives that item, at that address")
    else:
        skip("5 a recorded reward CHANGED", "no gate in this port gives an item")

    m = re.search(r"ITEM_PROBES = \(\((\d+), '([^']*)'\)", src)
    case("6 an item-name probe CHANGED",
         src.replace(m.group(0),
                     "ITEM_PROBES = ((%s, '%sX')" % (m.group(1), m.group(2)), 1),
         1, "the item-name table still reads what this file recorded")

    m = re.search(r"SPECIES_PROBES = \(\((\d+), '([^']*)'\)", src)
    case("7 a species-name probe CHANGED",
         src.replace(m.group(0),
                     "SPECIES_PROBES = ((%s, '%sX')" % (m.group(1), m.group(2)), 1),
         1, "the species-name table still reads what this file recorded")

    # Blind it through WAITSTATE, not CHOOSE_SPECIAL: 0x2F was measured to
    # follow the special at zero sites in all four ROMs, while several
    # plausible wrong special ids still match one or two sites by accident.
    case("8 the scanner blinded (waitstate constant wrong)",
         src.replace("WAITSTATE = 0x27", "WAITSTATE = 0x2F", 1),
         1, "the scan reached at least one call site")

    case("9 control again", src, 0)

    for p in tmps:
        try:
            os.remove(p)
        except OSError:
            pass

    print("\n%d/%d negative cases behaved%s"
          % (passes, passes + len(fails), ", %d n/a" % na if na else ""))
    if fails:
        print("MISSED: " + "; ".join(fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
