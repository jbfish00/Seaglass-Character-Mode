#!/usr/bin/env python3
"""Port source labels from a sibling repo's roster_sources.json. Gap-fill only.

A source label says WHERE A CHARACTER OWNED a Pokemon -- "Anime — Pokemon
Origins PO01", "Emerald", "Battle Subway". That is an ownership fact about the
character, not a fact about which ROM you are playing, so it ports between
games unchanged. This is the same reasoning `push_rosters.md` records for
reusing wave 5's verdicts across repos ("the verdicts are ownership calls, not
per-game ones") and for copying ROWE's hand-made Frontier Brain labels rather
than re-deriving them (§5).

Radical Red reached 100% coverage by porting ROWE's hand attributions; this
brings the same labels here instead of re-researching them. Provenance is not
laundered: every ported row records `source_ported_from`, and a row that already
carries a source is never overwritten.

Idempotent. Run before emit_roster_docs.py.

Usage: port_sibling_sources.py [--dry-run] [--from PATH_TO_roster_sources.json]
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
DEFAULT_FROM = (WORKSPACE / "RadicalRed-Character-Mode" / "tools"
                / "character_mode" / "roster_sources.json")
SOURCES = HERE / "roster_sources.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from", dest="src", default=str(DEFAULT_FROM))
    args = ap.parse_args()

    src_path = Path(args.src)
    if not src_path.is_file():
        raise SystemExit("sibling source file not found: %s" % src_path)
    donor_label = src_path.parents[2].name

    donor = json.loads(src_path.read_text())["sources"]
    if SOURCES.is_file():
        doc = json.loads(SOURCES.read_text())
    else:
        # BOOTSTRAP. This repo has never had a roster_sources.json, so seed one
        # keyed by the characters it actually has. The seed is empty: nothing is
        # invented here, every label below comes from the donor and is stamped
        # with source_ported_from.
        mapped = json.loads((HERE / "rosters_mapped.json").read_text())
        doc = {"_comment": (
            "Per-character, per-species provenance labels. Bootstrapped from a "
            "sibling repo by port_sibling_sources.py; a source says WHERE A "
            "CHARACTER OWNED a Pokemon, which is an ownership fact and not a "
            "per-ROM one. Rows carrying source_ported_from were not researched "
            "here."),
            "sources": {c: {} for c in sorted(mapped)}}
        print("bootstrapped a new roster_sources.json for %d characters"
              % len(doc["sources"]))
    sources = doc["sources"]

    # Only characters this repo actually has -- porting a label for a character
    # that does not exist here would silently grow the file with dead rows.
    mine = {c for c in sources if not c.startswith("_")}

    added = filled = kept = skipped_char = 0
    for char, rows in donor.items():
        if char.startswith("_"):
            continue
        if char not in mine:
            skipped_char += 1
            continue
        target = sources[char]
        for species, info in rows.items():
            label = (info or {}).get("source")
            if not label:
                continue
            cur = target.get(species)
            ported = {
                "owned_form": (info or {}).get("owned_form") or species,
                "source": label,
                "source_ported_from": (info or {}).get("source_ported_from")
                or donor_label,
            }
            if cur is None:
                target[species] = ported
                added += 1
            elif not cur.get("source"):
                cur.update(ported)
                filled += 1
            else:
                kept += 1

    print("donor: %s (%d characters)" % (src_path, len(donor)))
    print("  %d new entries, %d null sources filled, %d existing labels kept, "
          "%d donor characters absent here" % (added, filled, kept, skipped_char))
    if args.dry_run:
        print("  (dry run -- nothing written)")
        return 0
    SOURCES.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    print("  wrote %s" % SOURCES.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
