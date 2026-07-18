#!/usr/bin/env python3
"""Lazarus Phase 3 sprite-coverage survey: cross-reference the final
179-character manifest against ROWE's sprite_report.txt (same methodology
as RadicalRed-Character-Mode/docs/SPRITE_COVERAGE.md)."""
import json, re, sys

MANIFEST = "/home/jbfish00/Documents/Character Hacks/Seaglass-Character-Mode/tools/character_mode/characters_manifest.json"
REPORT = "/home/jbfish00/Documents/Pokemon Rowe Alteration/tools/character_mode/sprite_report.txt"

chars = [c["character"] for c in json.load(open(MANIFEST))["characters"]]
gens = {c["character"]: c["generation"] for c in json.load(open(MANIFEST))["characters"]}
assert len(chars) == 170, len(chars)

report = {}
for line in open(REPORT):
    m = re.match(r"^(.*?)\s+ow=(\S+)\s+front=(\S+)\s+back=(\S+)\s*$", line)
    if not m:
        if line.strip():
            print("UNPARSED:", line.rstrip(), file=sys.stderr)
        continue
    name = m.group(1).strip()
    report[name] = {
        "ow": m.group(2) != "-",
        "front": m.group(3) != "-",
        "back": m.group(4) != "-",
    }

print(f"ROWE report entries: {len(report)}")

have_ow = have_front = have_back = have_any = 0
none_list, missing_from_report = [], []
for c in chars:
    r = report.get(c)
    if r is None:
        missing_from_report.append(c)
        none_list.append(c)
        continue
    have_ow += r["ow"]; have_front += r["front"]; have_back += r["back"]
    if r["ow"] or r["front"] or r["back"]:
        have_any += 1
    else:
        none_list.append(c)

n = len(chars)
print(f"\nSeaglass roster: {n} characters")
print(f"  ow candidate    : {have_ow:3d} ({100*have_ow//n}%)")
print(f"  front candidate : {have_front:3d} ({100*have_front//n}%)")
print(f"  back candidate  : {have_back:3d} ({100*have_back//n}%)")
print(f"  AT LEAST ONE    : {have_any:3d} ({100*have_any//n}%)")
print(f"  NO assets       : {len(none_list):3d} ({100*len(none_list)//n}%)")
print(f"\nNot in ROWE report at all ({len(missing_from_report)}): {missing_from_report}")
print(f"\nZero-coverage by generation:")
from collections import defaultdict
bygen = defaultdict(list)
for c in none_list:
    bygen[gens[c]].append(c)
for g in sorted(bygen):
    print(f"  Gen {g} ({len(bygen[g])}): {', '.join(bygen[g])}")
print(f"\nFull-coverage (ow+front+back):")
print("  " + ", ".join(c for c in chars if report.get(c, {}).get("ow") and report[c]["front"] and report[c]["back"]))
