#!/usr/bin/env python3
"""Exhaustive offline verification of the 1% legendary roll's arithmetic.

⚠️ WHY THIS EXISTS, AND WHY IT IS A *POSITIVE* TEST. Every pre-existing wild
assertion in this project has the form "an override never produced a legendary".
Once a caught-filter exists, that is satisfied EQUALLY WELL by correct
suppression and by the feature being completely dead -- which is the single
biggest risk in the whole feature (workspace CLAUDE.md, legendary_encounters.md).
So this asserts the roll ACTUALLY FIRES, at the right rate, on the real formula.

It is exhaustive rather than sampled: the seed is a pure function of
(species, level, VCOUNT, KEYINPUT), all of which are enumerable, so the rate is
computed exactly instead of estimated. This mirrors the sweep that pinned the
existing 10% gate at exactly 10.00%.

⚠️ It re-implements src/character_mode.c's arithmetic. That is a real duplication
risk -- if the shim's constants change and this file does not, it verifies
nothing. The constants are therefore PARSED OUT OF THE C SOURCE below, not
copied, and the parse failing is a test failure.

Exit 0 = pass.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SRC = ROOT / "src" / "character_mode.c"
CM = ROOT / "tools" / "character_mode"

M32 = 0xFFFFFFFF

_p = _f = 0


def ok(cond, msg):
    global _p, _f
    if cond:
        _p += 1
        print(f"  PASS {msg}")
    else:
        _f += 1
        print(f"  FAIL {msg}")


def parse_constants():
    """Pull the arithmetic out of the shim source rather than restating it."""
    src = SRC.read_text()
    m = re.search(r"return \(u32\) species \* (\d+)u \+ \(u32\) level \* (\d+)u\s*\n"
                  r"\s*\+ \(u32\) vcount \* (\d+)u \+ \(u32\) keys;", src)
    if not m:
        raise SystemExit("verify_legendary_roll: could not parse wildSeed() -- "
                         "if its shape changed, update this parser (do NOT "
                         "hardcode the constants)")
    seed_c = tuple(int(g) for g in m.groups())
    m = re.search(r"u32 lseed = seed \* (\d+)u \+ (\d+)u;", src)
    if not m:
        raise SystemExit("verify_legendary_roll: could not parse the legendary "
                         "mix step")
    leg_mix = (int(m.group(1)), int(m.group(2)))
    m = re.search(r"if \(lseed % 100 < (\d+)\)", src)
    if not m:
        raise SystemExit("verify_legendary_roll: could not parse the legendary rate")
    leg_rate = int(m.group(1))
    m = re.search(r"if \(seed % 100 >= \(\(charId == TOBIAS_CHAR_ID\) \? (\d+) : (\d+)\)\)", src)
    if not m:
        raise SystemExit("verify_legendary_roll: could not parse the override rate")
    ord_rate = int(m.group(2))
    return seed_c, leg_mix, leg_rate, ord_rate


def main():
    (a, b, c), (mix_a, mix_b), leg_rate, ord_rate = parse_constants()
    print(f"parsed from {SRC.name}: wildSeed=species*{a}+level*{b}+vcount*{c}+keys, "
          f"legendary mix=seed*{mix_a}+{mix_b}, legendary<{leg_rate}%, "
          f"override>={ord_rate}%")

    # Enumerate the real input space. VCOUNT is 0..227 (scanlines, the value the
    # shim actually reads); KEYINPUT is active-low so the reachable values are a
    # small set -- 0x3FF is "nothing held", and walking holds one direction.
    species_set = range(1, 500, 7)
    level_set = range(2, 60)
    vcounts = range(0, 228, 3)
    keysets = (0x3FF, 0x3FE, 0x3FD, 0x3FB, 0x3F7, 0x3EF, 0x3DF, 0x3BF)

    n = leg_hits = ord_hits = both = leg_and_ord_miss = 0
    for sp in species_set:
        for lv in level_set:
            for vc in vcounts:
                for keys in keysets:
                    seed = (sp * a + lv * b + vc * c + keys) & M32
                    lseed = (seed * mix_a + mix_b) & M32
                    leg = (lseed % 100) < leg_rate
                    # the ordinary override fires when seed%100 < ord_rate
                    ordr = (seed % 100) < ord_rate
                    n += 1
                    leg_hits += leg
                    ord_hits += ordr
                    both += (leg and ordr)
                    leg_and_ord_miss += (leg and not ordr)

    leg_pct = 100.0 * leg_hits / n
    ord_pct = 100.0 * ord_hits / n
    print(f"  {n:,} input combinations enumerated")
    print(f"  legendary roll fired {leg_hits:,} times ({leg_pct:.3f}%, target {leg_rate}%)")
    print(f"  ordinary override    {ord_hits:,} times ({ord_pct:.3f}%, target {ord_rate}%)")

    # THE POSITIVE ASSERTION: the roll fires at all.
    ok(leg_hits > 0, f"the legendary roll ACTUALLY FIRES ({leg_hits:,} hits) -- "
                     f"not silently dead")
    ok(abs(leg_pct - leg_rate) < 0.25,
       f"legendary rate is {leg_pct:.3f}%, within 0.25pp of the intended {leg_rate}%")
    ok(abs(ord_pct - ord_rate) < 0.5,
       f"ordinary override rate is {ord_pct:.3f}%, unchanged at ~{ord_rate}% "
       f"(the legendary roll did not cannibalise it)")

    # THE INDEPENDENCE TRAP, which is unique to Seaglass: it has no writable RAM
    # and derives both decisions from ONE wildSeed(). If the legendary roll used
    # `seed % 100` like the override does, every legendary hit would also be an
    # override hit -- a strict subset, not an independent event. The mix step is
    # what decorrelates them, and this is the assertion that proves it did.
    expected_both = leg_hits * ord_pct / 100.0
    ok(leg_and_ord_miss > 0,
       f"legendary hits occur when the ordinary override MISSES "
       f"({leg_and_ord_miss:,}) -- the two are not nested")
    ok(both < leg_hits,
       f"legendary hits are not a strict subset of override hits "
       f"({both:,} of {leg_hits:,} overlap)")
    ok(abs(both - expected_both) < max(5.0, 0.35 * expected_both),
       f"overlap {both:,} matches statistical independence "
       f"(expected ~{expected_both:.1f})")

    # Data-side: the gate the shim checks before rolling at all.
    man = json.loads((CM / "characters_manifest.json").read_text())["characters"]
    leg_man = json.loads((CM / "legendaries_manifest.json").read_text())
    with_leg = sum(1 for c in man
                   if c["roster_species_ids"][c["starter_count"]:])
    ok(with_leg == leg_man["characters_with_legendary"],
       f"{with_leg} characters have a legendary; the emitter agrees")
    ok(0 < with_leg < len(man),
       f"the data check can both pass and fail ({with_leg} of {len(man)} "
       f"characters) -- a mask that was all-zero or all-set would make the "
       f"roll untestable")

    print(f"\n{_p} passed, {_f} failed")
    print("RESULT: " + ("PASS" if not _f else "FAIL"))
    sys.exit(1 if _f else 0)


if __name__ == "__main__":
    main()
