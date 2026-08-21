#!/usr/bin/env python3
"""Re-derive character_drops.json from THIS repo's own roster data.

The rule (user, 2026-07-25): a character with fewer than six fully-evolved
Pokemon obtainable in this game is not offered here -- unless a legendary or
mythical is on the roster, which exempts them. They keep their table slot and
are hidden from the menu, because saves store the character INDEX and deleting
a row would repoint every existing save at a different character.

Why this exists rather than using the audit's own answer: the drop list was
first computed by the audit's `per_game_threshold.py`, which reads the audit's
`final_rosters.json`. That file does not include this repo's
`roster_additions.json` overlay or wave 5, so its answer drifts from what the
ROM actually enforces in BOTH directions -- applied verbatim to ROWE it left 20
Legends: Arceus wardens selectable with a single final evolution each, while
hiding 5 characters who clear the bar once their overlay adds are counted.

Ported from Radical Red's copy but REWRITTEN against this repo's own modules:
Seaglass expands families with `emit_bitmaps.family_closure()` and judges final
stages with `emit_roster_docs`'s donor tables, so the numbers here come from the
very code that builds the injected allow-bitmaps and writes the doc rows. The
threshold, the bitmaps and the docs therefore cannot disagree about who is thin.

⚠️ Reads `rosters_mapped.json`, which is the STAGE B output: its ids are real
ROM indices and species this ROM does not carry have already been dropped. So a
species Seaglass lacks cannot inflate anyone's count. Run derive_drops AFTER
map_species_stage_b.py and BEFORE emit_characters.py.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emit_bitmaps
import emit_roster_docs
from emit_characters import LEGENDARY_BASES

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="report only; do not rewrite character_drops.json")
    args = ap.parse_args()

    const_name, forward = emit_bitmaps.load_donor_forward()
    donor = emit_roster_docs.donor_species()

    canonical = {}
    for const in sorted(donor):
        d = donor[const]["dex"]
        if d:
            canonical.setdefault(d, const)

    def is_final(const):
        """emit_roster_docs' rule verbatim: a cosmetic form that cannot itself
        evolve is NOT a final stage of a family whose base still evolves."""
        rec = donor.get(const)
        if rec is None or rec["children"]:
            return False
        base = canonical.get(rec["dex"], const)
        return not donor.get(base, rec)["children"]

    def shown_row(const):
        """The doc row this final collapses onto: a regional form keeps its own
        row, everything else folds onto the base sharing its dex number."""
        rec = donor.get(const)
        if rec is None or not rec["dex"]:
            return const
        return canonical.get(rec["dex"], const)

    with open(os.path.join(HERE, "rosters_mapped.json")) as f:
        mapped = json.load(f)

    dropped, kept, exempt = [], [], []
    for char, info in sorted(mapped.items()):
        # ⚠️ Use the roster's OWN key, verbatim. This used to strip a trailing
        # " (anime)", which made the emitted name unmatchable: every consumer
        # (emit_characters, verify_artifacts) looks these up against
        # rosters_mapped.json / the manifest, where the key IS "Kiawe (anime)".
        # A stripped name therefore hides NOBODY -- silently, because a name
        # that matches nothing simply never fires. It went unnoticed only
        # because no (anime) character had ever fallen under the threshold;
        # applying the audit's removals overlay put Kiawe, Lillie and Mallow
        # under it and emit_characters' "matches no character" guard caught it
        # immediately. Same shape as the audit's page-name-vs-menu-name trap
        # that blanked the Source column for all four Alola captains.
        name = char
        consts = [s["const"] for s in info["species"]]
        if any(c in LEGENDARY_BASES for c in consts):
            exempt.append(name)
            kept.append(name)
            continue
        allowed = set()
        for c in consts:
            allowed |= emit_bitmaps.family_closure(c, forward)
        finals = {shown_row(c) for c in allowed if is_final(c)}
        if len(finals) < 6:
            dropped.append((name, len(finals)))
        else:
            kept.append(name)

    path = os.path.join(HERE, "character_drops.json")
    old = set()
    if os.path.isfile(path):
        with open(path) as f:
            old = set(json.load(f).get("unselectable", []))
    new = sorted(n for n, _ in dropped)

    if not args.dry_run:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_comment": "Characters that keep their table slot (saves "
                                   "store the INDEX) but fall under the "
                                   "six-fully-evolved threshold in this game's "
                                   "dex, with no legendary to exempt them. "
                                   "GENERATED by derive_drops.py -- do not "
                                   "hand-edit.",
                       "unselectable": new}, f, indent=1, sort_keys=True,
                      ensure_ascii=False)
            f.write("\n")

    print(f"{len(kept)} selectable ({len(exempt)} exempted by a legendary), "
          f"{len(dropped)} under the threshold")
    added = sorted(set(new) - old)
    removed = sorted(old - set(new))
    if added:
        print(f"  newly hidden ({len(added)}): {', '.join(added[:12])}"
              + (" ..." if len(added) > 12 else ""))
    if removed:
        print(f"  no longer hidden ({len(removed)}): {', '.join(removed[:12])}"
              + (" ..." if len(removed) > 12 else ""))
    thin = sorted(dropped, key=lambda t: t[1])[:8]
    if thin:
        print("  thinnest: " + ", ".join(f"{n} ({c})" for n, c in thin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
