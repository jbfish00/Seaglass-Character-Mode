#!/usr/bin/env python3
"""How much of THIS GAME's own wild data is on each character's roster?

Ported from ROWE's tools/character_mode/roster_playability_report.py
(../../game_plans/rowe_parity.md §0). ROWE reads its encounter tables out of a
decomp JSON; there is no such file here, so this reads them straight out of the
ROM -- see "LOCATING THE TABLE" below.

WHY THIS EXISTS. The playthrough checklist's last irreducible question is
"whether a roster is miserable to play for 40 hours", and it has always been
filed as pure human judgement. Most of it is, but a large part is measurable and
nobody had measured it in this repo.

The playability threshold already guarantees six fully-evolved obtainable
Pokemon, and the 10%% roster override guarantees you MEET your character's
Pokemon at a fixed rate everywhere. Neither answers the question that actually
decides whether a run drags: **when you walk into grass and something appears,
how often is it yours to keep?** That is the map's own encounter tables versus
the character's roster, and it is entirely in the data.

`natural%%` is the share of the game's wild encounter SLOTS whose species is on
that character's roster. It deliberately EXCLUDES the 10%% override, because the
override is the floor every character already has; what separates a comfortable
roster from a miserable one is what happens in the other 90%%.

⚠️ WHAT THIS IS NOT. It is not a verdict and must never become a gate. A low
score can be entirely fine (a character you play for the set pieces) and a high
one does not make a run fun. It is a flag for "check this one during the
playthrough" -- exactly what the checklist needs and what a suite cannot give.

⚠️ IT COUNTS SLOTS, NOT ENCOUNTER PROBABILITY. Slot 0 of a land table is 20%% of
that map's encounters and slot 11 is 1%%, so a roster that only matches rare
slots scores higher here than it plays. Weighting by the real slot chances is a
worthwhile refinement; it is not done, and this note is here so the number is
not read as more precise than it is. ROWE's version carries the same caveat.

⚠️ NO `early%%`. ROWE also reports the opening routes, using a hand-written list
of its starting maps. This repo has no map-progression data, and inventing one
by taking "the first N table records" would be a guess dressed as a measurement.
The comparable-and-honest signal here is ZERO-COVERAGE characters, reported
below.

LOCATING THE TABLE. gWildMonHeaders is an array of fixed-size records:
    u8 mapGroup; u8 mapNum; u16 pad; then N pointers to WildPokemonInfo
    struct WildPokemonInfo { u8 encounterRate; u8 pad[3]; const WildPokemon *; }
    struct WildPokemon     { u8 minLevel; u8 maxLevel; u16 species; }
terminated by mapGroup == 0xFF. The base, stride and field count below were
found by scanning for that shape and CONFIRMED by decoding the species: a real
table is dominated by Magikarp/Zubat/Tentacool, a false positive is not.

⚠️ THE STRIDE IS NOT THE SAME IN EVERY GAME. The two FireRed-family ports use
the vanilla 20-byte, 4-pointer header. The two Emerald-family ports use a
24-byte, 5-pointer header -- which is why a 20-byte scan finds nothing there at
all. That is corroborated independently by their own Battle Pyramid code, which
indexes its headers with `(i*3)<<3`.

Usage: roster_playability_report.py [--csv] [--all]
"""
import argparse
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

# ---- per-game constants (see LOCATING THE TABLE) --------------------------
ROM_PATH      = os.path.join(ROOT, "rom", "seaglass v3.0.gba")
TABLE_BASE    = 0x08A4E8B8
HEADER_STRIDE = 24
N_FIELDS      = 5
# Slot counts per pointer field, MEASURED from this ROM (not assumed).
FIELD_SLOTS   = [12, 5, 5, 3, 10]
FIELD_NAMES   = ["land", "water", "rock", "aux", "fishing"]
MAX_SPECIES   = 1500
# ⚠️ THE FIFTH FIELD IS DELIBERATELY NOT COUNTED. The Emerald-family header has
# a fifth pointer whose table is small and carries encounterRate 0 (Lazarus
# populates it in zero records, Seaglass in 23 with three entries each). It is
# most likely the expansion's hidden-encounter table, but "most likely" is not
# a measurement, so it is parsed and REPORTED and kept out of the metric rather
# than silently inflating it. Naming it "aux" is the honest label.
# Fields counted toward natural%: the four ways a player meets a wild Pokemon.
COUNTED       = {"land", "water", "rock", "fishing"}


def rd(d, o, n):
    return int.from_bytes(d[o:o + n], "little")


def read_slots():
    """[(mapGroup, mapNum, field, species)] for every wild slot in the game."""
    with open(ROM_PATH, "rb") as f:
        d = f.read()

    def ok(v):
        return 0x08000000 <= v < 0x08000000 + len(d)

    def at(a):
        return a - 0x08000000

    slots, recs, a = [], 0, TABLE_BASE
    while True:
        o = at(a)
        if o + HEADER_STRIDE > len(d):
            break
        grp, num = d[o], d[o + 1]
        if grp == 0xFF:
            break
        ptrs = [rd(d, o + 4 + 4 * i, 4) for i in range(N_FIELDS)]
        if not all(p == 0 or ok(p) for p in ptrs):
            break
        any_ok = False
        for i, p in enumerate(ptrs):
            if not p or not ok(p):
                continue
            mons = rd(d, at(p) + 4, 4)
            if not ok(mons):
                continue
            n = FIELD_SLOTS[i]
            entries = []
            for k in range(n):
                e = at(mons) + 4 * k
                if e + 4 > len(d):
                    entries = []
                    break
                lo, hi, sp = d[e], d[e + 1], rd(d, e + 2, 2)
                if not (1 <= lo <= 100 and 1 <= hi <= 100 and lo <= hi
                        and 0 < sp < MAX_SPECIES):
                    entries = []
                    break
                entries.append(sp)
            if entries:
                any_ok = True
                for sp in entries:
                    slots.append((grp, num, FIELD_NAMES[i], sp))
        if not any_ok:
            break
        recs += 1
        a += HEADER_STRIDE
    return recs, slots


def load_allowed():
    """{character: (set of allowed species ids, hidden)} from the EMITTED data
    the ROM actually enforces -- never from the research files."""
    with open(os.path.join(HERE, "characters_manifest.json")) as f:
        chars = json.load(f)["characters"]
    out = {}
    bm_path = os.path.join(HERE, "rosters_expanded.bin")
    if os.path.isfile(bm_path):
        with open(bm_path, "rb") as f:
            bm = f.read()
        stride = len(bm) // len(chars)
        for i, c in enumerate(chars):
            rec = bm[i * stride:(i + 1) * stride]
            allowed = {sp for sp in range(1, min(MAX_SPECIES, stride * 8))
                       if rec[sp >> 3] & (1 << (sp & 7))}
            out[c["character"]] = (allowed, bool(c.get("hidden")))
    else:
        # Unbound stores an explicit, already family-expanded species list.
        for c in chars:
            out[c["character"]] = (set(c["roster_species_ids"]),
                                   bool(c.get("hidden")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help="machine-readable rows")
    ap.add_argument("--all", action="store_true",
                    help="include characters the menu hides")
    args = ap.parse_args()

    recs, slots = read_slots()
    counted = [s for s in slots if s[2] in COUNTED]
    if not counted:
        raise SystemExit("no wild slots parsed -- the table constants are wrong")
    total = len(counted)
    allowed = load_allowed()

    rows = []
    for name, (aset, hidden) in allowed.items():
        if hidden and not args.all:
            continue
        hit = sum(1 for _, _, _, sp in counted if sp in aset)
        rows.append((100.0 * hit / total, hit, name))
    rows.sort()

    if args.csv:
        print("character,natural_pct,slots_matched,slots_total")
        for pct, hit, name in rows:
            print(f"{name},{pct:.2f},{hit},{total}")
        return 0

    by_field = {}
    for _, _, f, _ in slots:
        by_field[f] = by_field.get(f, 0) + 1
    print(f"wild table @ {TABLE_BASE:#x}: {recs} map records, "
          f"{len(slots)} slots ({by_field})")
    print(f"counted toward natural%: {total} slots from {sorted(COUNTED)}")
    print(f"characters scored: {len(rows)}"
          + ("" if args.all else " (menu-visible only)"))
    print()
    pcts = [r[0] for r in rows]
    mid = len(pcts) // 2
    median = pcts[mid] if len(pcts) % 2 else (pcts[mid - 1] + pcts[mid]) / 2
    zeros = [r[2] for r in rows if r[1] == 0]
    print(f"  median natural%: {median:.1f}%")
    print(f"  range:           {pcts[0]:.1f}% .. {pcts[-1]:.1f}%")
    print(f"  ZERO coverage:   {len(zeros)} character(s)"
          + (": " + ", ".join(zeros[:12]) if zeros else ""))
    print()
    print("  thinnest 12:")
    for pct, hit, name in rows[:12]:
        print(f"    {name:26s} {pct:5.1f}%  ({hit}/{total} slots)")
    print("  richest 5:")
    for pct, hit, name in rows[-5:][::-1]:
        print(f"    {name:26s} {pct:5.1f}%  ({hit}/{total} slots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
