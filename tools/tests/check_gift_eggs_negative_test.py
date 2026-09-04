#!/usr/bin/env python3
"""Negative test for check_gift_eggs.py.

The inventory is only worth anything if it FAILS when the set of scripted gift
eggs changes, when a recorded one disappears, when one starts giving a
different species, or when a verdict claims an enforcement this repo does not
have. So break it on purpose in each of those directions, with a control at
each end -- a checker that rejected everything would pass every negative case
and look correct.

  1. control                  -- the real inventory passes
  2. an entry DELETED         -- a real gift egg is now uninventoried, i.e. a
                                 new way into the party arriving silently
  3. a bogus entry ADDED      -- the inventory describes an egg the ROM does
                                 not have (a stale inventory)
  4. an operand CHANGED       -- the recorded species no longer matches what
                                 the script gives
  5. a verdict tampered       -- the hatch hook path cleared while every verdict still claims GATED
  6. the anchor test broken   -- the decoder now reaches nothing; an empty
                                 result satisfies checks 2, 3 and 4, and only
                                 the anti-vacuity check catches it
  7. control again

⚠️ Every tamper must both CHANGE something and PARSE: a SyntaxError also exits
1 and would read exactly like the checker catching the tamper. This workspace
has mistaken a bad tamper for a real result more than once -- a "MISS" in a
negative test is more often a bad tamper than a real gap.
"""
import ast
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "check_gift_eggs.py")


def run(path):
    p = subprocess.run([sys.executable, path], capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def main():
    if not os.path.isfile(REAL):
        print("SKIP: no check_gift_eggs.py here")
        return 0
    src = open(REAL, encoding="utf-8").read()
    fails, passes, tmps = [], 0, []

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
        path = os.path.join(HERE, "_negtest_gift_eggs.py")
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

    print("negative test: check_gift_eggs.py")
    case("1 control -- the real inventory passes", src, 0)

    # 2. delete the first inventory entry
    first = re.search(r"\n    (0x[0-9a-f]+): \(.*?\),\n(?=    0x|\})", src, re.S)
    case("2 an inventoried gift egg DELETED", src.replace(first.group(0), "\n"),
         1, "every giveegg site in the ROM is inventoried")

    # 3. add an entry the ROM does not have
    case("3 a bogus entry ADDED",
         src.replace("INVENTORY = {",
                     "INVENTORY = {\n    0x00000004: (1, 'UNGATED', 'bogus'),", 1),
         1, "every inventoried site is still present in the ROM")

    # 4. change a recorded operand
    m = re.search(r"\n    (0x[0-9a-f]+): \((\d+),", src)
    case("4 a recorded operand CHANGED",
         src.replace(m.group(0), "\n    %s: (%d," % (m.group(1),
                                                     int(m.group(2)) + 1), 1),
         1, "still gives what it is recorded as giving")

    # 5. a verdict that lies about this repo's enforcement
    case("5 a verdict tampered -- the hatch hook path cleared while every verdict still claims GATED", src.replace("HATCH_HOOK = 'tools/character_mode/egg_hook.py'", "HATCH_HOOK = None", 1),
         1, "GATED verdicts exist exactly when this repo hooks the egg hatch")

    # 6. break the anchor test so the decode reaches nothing
    case("6 the anchor test broken (decoder reaches nothing)",
         src.replace("if b[i] == 0x0F and b[i + 1] == 0x00:",
                     "if b[i] == 0x0F and b[i + 1] == 0x77:", 1),
         1, "the scan reached at least one giveegg site")

    case("7 control again", src, 0)

    for p in tmps:
        try:
            os.remove(p)
        except OSError:
            pass

    print("\n%d/7 negative cases behaved" % passes)
    if fails:
        print("MISSED: " + "; ".join(fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
