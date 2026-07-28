#!/usr/bin/env python3
"""Union a sibling repo's roster_additions.json into this one.

The additions overlay records OWNERSHIP calls -- "this Pokemon is canonically
this character's" -- and ownership does not depend on which ROM is being built.
Stage B's dex filter is what decides whether a species survives here. So a
verdict reached in one repo is valid in all of them, exactly like the wave 5
audit verdicts, and the correct merge is a union rather than a copy.

Why it is needed: this repo's overlay was written before the 2026-07-26 Radical
Red pass, which found the audit surfaces UNDER-inclusions as well as
over-inclusions. Nate was missing an entire 36-species Battle Subway Multi Train
partner pool; Rosa and Hilbert were missing most of theirs.

⚠️ SEAGLASS NOTE (2026-07-27): unlike Lazarus, this repo's overlay carries
NOTHING the Radical Red one lacks -- it covers 29 characters and RR's covers the
same 29 plus 37 more, so here the union is in practice an adoption. It is still
run as a union rather than a copy, because that is the operation that stays
correct if this repo ever gains its own verdicts, and because a copy would
silently discard them if it did.

This mattered directly: the playability threshold judges characters on their
merged roster, and on the pre-union data it hid Nate on a roster missing 34 of
his species. Run this BEFORE derive_drops.py, not after.

    python3 tools/character_mode/port_sibling_additions.py \
        ../RadicalRed-Character-Mode/tools/character_mode/roster_additions.json

Re-run map_species.py onward afterwards.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MINE = os.path.join(HERE, "roster_additions.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sibling", help="path to another repo's roster_additions.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(MINE, encoding="utf-8") as f:
        mine = json.load(f)
    with open(args.sibling, encoding="utf-8") as f:
        theirs = json.load(f)
    a, b = mine["additions"], theirs["additions"]

    # Rows are EITHER a bare species name OR {species, source, owned_form} --
    # the same mixed shape that crashed map_species.py's merge_additions() once.
    # Key on the species name, and prefer whichever row carries a source, so
    # merging never downgrades a sourced row to a bare string.
    def name_of(row):
        return row if isinstance(row, str) else row["species"]

    def better(x, y):
        """y wins only if it says something x does not."""
        if isinstance(x, str):
            return y if isinstance(y, dict) else x
        if isinstance(y, dict) and not x.get("source") and y.get("source"):
            return y
        return x

    added_chars, grown = [], []
    for char, species in sorted(b.items()):
        if char not in a:
            a[char] = sorted(species, key=name_of)
            added_chars.append((char, len(species)))
            continue
        rows = {name_of(r): r for r in a[char]}
        new = 0
        for r in species:
            n = name_of(r)
            if n in rows:
                rows[n] = better(rows[n], r)
            else:
                rows[n] = r
                new += 1
        a[char] = [rows[n] for n in sorted(rows)]
        if new:
            grown.append((char, new))

    if not args.dry_run:
        with open(MINE, "w", encoding="utf-8") as f:
            json.dump(mine, f, indent=1, sort_keys=True, ensure_ascii=False)
            f.write("\n")

    print("%d characters gained an overlay entry, %d grew; %d species rows total"
          % (len(added_chars), len(grown), sum(len(v) for v in a.values())))
    for char, n in added_chars:
        print("   + %-14s %d species (no entry here before)" % (char, n))
    for char, n in sorted(grown, key=lambda t: -t[1]):
        print("     %-14s +%d" % (char, n))
    if args.dry_run:
        print("(dry run -- roster_additions.json not rewritten)")


if __name__ == "__main__":
    main()
