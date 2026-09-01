#!/usr/bin/env python3
"""Negative test for emit_characters.py's EMPTY_ROSTER_EXPECTED inventory.

rowe_parity.md §10 asks for an inventory so that a NEW character silently
mapping to nothing fails a check instead of sitting in a report line.  This
proves that inventory actually fails, in both directions, and that it stays
quiet on the real data.

It drives `assert_empty_inventory` directly rather than running the emitter
with tampered inputs.  That is deliberate: this workspace has already written
tampered data into a committed artifact by running a generator during a
measurement loop, and the corruption survived the input being restored.  No
file is written here at all.

Cases (the control is the one that matters -- a guard that rejected everything
would pass both negative cases and look correct):

  1. the real set              -> quiet          (control)
  2. a character gains a roster-> SystemExit      (index-shift warning)
  3. a new character empties   -> SystemExit
  4. both at once              -> SystemExit
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CM = os.path.abspath(os.path.join(HERE, "..", "character_mode"))
sys.path.insert(0, CM)

spec = importlib.util.spec_from_file_location(
    "emit_characters", os.path.join(CM, "emit_characters.py"))
ec = importlib.util.module_from_spec(spec)
sys.modules["emit_characters"] = ec
spec.loader.exec_module(ec)

fails = []


def case(label, empty, want_exit):
    try:
        ec.assert_empty_inventory(list(empty))
        got = False
    except SystemExit:
        got = True
    ok = got == want_exit
    print("  %-4s %-52s %s" % ("ok" if ok else "FAIL", label,
                               "raised" if got else "quiet"))
    if not ok:
        fails.append(label)


def main():
    real = set(ec.EMPTY_ROSTER_EXPECTED)
    if not real:
        print("EMPTY_ROSTER_EXPECTED is empty -- nothing to test, and that is "
              "itself suspicious; this repo is meant to have empty rosters.")
        return 1

    # The inventory must describe what the emitter really produces, or it is
    # pinning a fiction. Derive the live set the same way the emitter does.
    with open(os.path.join(CM, "rosters_mapped.json")) as f:
        mapped = json.load(f)
    order = ec.load_order(mapped)
    _built, live, _warn = ec.build_rosters(mapped, order)
    if set(live) != real:
        print("  FAIL inventory does not match the live emit: only-in-inventory"
              " %s, only-in-emit %s" % (sorted(real - set(live)),
                                        sorted(set(live) - real)))
        fails.append("inventory matches live emit")
    else:
        print("  ok   inventory matches the live emit (%d character(s))"
              % len(real))

    victim = sorted(real)[0]
    print("empty-roster inventory negative test")
    case("control: the real set is accepted", real, False)
    case("a listed character gaining a roster fails (%s)" % victim,
         real - {victim}, True)
    case("an unlisted character emptying fails", real | {"ZZ_Nonexistent"}, True)
    case("both directions at once fails", (real - {victim}) | {"ZZ_Nonexistent"},
         True)

    if fails:
        print("\nFAILURES: " + ", ".join(fails))
        return 1
    print("\nempty-roster inventory test: 5/5 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
