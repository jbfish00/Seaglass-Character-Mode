#!/usr/bin/env python3
"""Stage B: fill in real numeric ROM species ids for rosters_mapped.json.

Stage A (map_species.py) resolves Bulbapedia roster names to SPECIES_*
constants and evolution-family bases using the pokeemerald-expansion donor,
but deliberately leaves every species_id as the placeholder string
"PENDING_PHASE1" -- see docs/DONOR_CROSSWALK.md for why the donor's own
numeric ids can't be trusted for this ROM.

Phase 1 has since located and dumped the REAL species table straight out of
the Seaglass ROM itself (tools/character_mode/rom_species_table.json: ROM
index -> in-game display name, SHA1-pinned to rom.sha1). This script uses
THAT -- not the donor -- as the source of truth for numeric ids: for each
species_id/roster the donor is only ever used to get a species's canonical
(Bulbapedia-matching) display name; that name is then matched directly
against the ROM's own dumped name table to find its real numeric id.

This is more reliable than assuming any positional/numeric alignment with
the donor (which docs/DONOR_CROSSWALK.md explicitly warns against for this
project, unlike Unbound's DPE donor where donor-position-equals-id held up).

Name matching handles two real wrinkles found in the ROM dump:
  - Gen3-charmap-decoded punctuation doesn't round-trip to plain ASCII for
    a few characters (e.g. "-" decodes as the fullwidth "ー", "." as "。",
    a mid-name space as U+3000) -- normalize() maps these back before
    comparing.
  - A handful of species appear at MULTIPLE ROM indices sharing the same
    base name (regional forms: Alolan/Galarian Rattata, Raichu, etc., and
    Unown/Deoxys/Castform's per-form entries all reuse the base name in this
    dump). Since every roster species here is a plain evolution-family base
    (no roster ever needs "Alolan X" specifically -- see map_species.py's
    first_stage_map()), the LOWEST matching index is used (matches the
    established finding that index = National Dex number for the base/
    non-regional table region, and regional/alt forms are appended at much
    higher indices) -- every such pick is logged to stageb_ambiguous.txt for
    manual review, not silently trusted.

Modern-mechanic form suffixes that don't exist on a GBA-engine ROM at all
(Gigantamax, Mega, regional-form consts the donor carries for Switch-era
games) are stripped from the SPECIES_* constant name before name lookup,
since the donor's own speciesName for these still resolves to a name a
GBA-hack table might plausibly have under its plain (non-Gmax/Mega) form --
if the plain form doesn't exist in this ROM either, it correctly falls
through to unmatched rather than being guessed.

Writes:
  - rosters_mapped.json           updated in place with real integer ids
  - rosters_mapped_stageA_backup.json   pre-Stage-B backup (only written once)
  - stageb_ambiguous.txt          every multi-match pick, for manual review
  - stageb_unmatched.txt          species that matched NO ROM table entry
                                   (name genuinely absent from this ROM --
                                   same category that drove the characters.txt
                                   trim in docs/SPECIES_CAP.md; more trimming
                                   may be needed if this is non-empty)
"""
import json
import os
import re
import shutil

from map_species import load_donor

HERE = os.path.dirname(os.path.abspath(__file__))

# Modern-only form/mechanic suffixes the donor encodes as part of the
# SPECIES_* constant that have no meaning on this GBA-engine ROM -- stripped
# before falling back to the plain species name.
STRIP_SUFFIXES = [
    "_MEGA_X", "_MEGA_Y", "_MEGA", "_GMAX", "_GIGANTAMAX",
    "_ALOLA", "_ALOLAN", "_GALAR", "_GALARIAN", "_HISUI", "_HISUIAN",
    "_PALDEA", "_PALDEAN",
]


def normalize(s):
    s = s.replace("ー", "-").replace("。", ".").replace("　", " ")
    s = s.strip().lower()
    s = re.sub(r"[^\w♀♂]+", "", s)
    return s


def plain_const(const):
    for suf in STRIP_SUFFIXES:
        if const.endswith(suf):
            return const[: -len(suf)]
    return const


def main():
    name_to_const, _parent = load_donor()
    const_to_name = {}
    for name, const in name_to_const.items():
        const_to_name.setdefault(const, name)

    with open(os.path.join(HERE, "rom_species_table.json")) as f:
        rom_table = json.load(f)
    rom_species = rom_table["species"]

    by_norm_name = {}
    for idx_str, name in rom_species.items():
        idx = int(idx_str)
        by_norm_name.setdefault(normalize(name), []).append(idx)
    for idx_list in by_norm_name.values():
        idx_list.sort()

    mapped_path = os.path.join(HERE, "rosters_mapped.json")
    backup_path = os.path.join(HERE, "rosters_mapped_stageA_backup.json")
    if not os.path.exists(backup_path):
        shutil.copy(mapped_path, backup_path)

    with open(mapped_path) as f:
        mapped = json.load(f)

    ambiguous = []
    unmatched = set()
    resolved_cache = {}

    def resolve_id(const):
        if const in resolved_cache:
            return resolved_cache[const]
        name = const_to_name.get(const) or const_to_name.get(plain_const(const))
        result = None
        if name:
            key = normalize(name)
            matches = by_norm_name.get(key)
            if matches:
                result = matches[0]
                if len(matches) > 1:
                    ambiguous.append((const, name, matches))
        if result is None:
            unmatched.add(const)
        resolved_cache[const] = result
        return result

    dropped_total = 0
    for disp, info in mapped.items():
        for entry in info.get("species", []):
            sid = resolve_id(entry["const"])
            if sid is not None:
                entry["id"] = sid
        sig = info.get("signature")
        if sig:
            sid = resolve_id(sig["const"])
            if sid is not None:
                sig["id"] = sid

        # Drop roster entries that still have no real id: those species
        # genuinely don't exist in this ROM (see stageb_unmatched.txt), same
        # category that already drove the characters.txt trim in
        # docs/SPECIES_CAP.md -- a roster can't reference a nonexistent
        # species id, so the placeholder must be removed, not left dangling,
        # for emit_characters.py --final to build. This does not remove any
        # CHARACTER (that was the user's earlier, separate decision) -- only
        # individual already-known-uncatchable species within a kept
        # character's roster.
        before = len(info.get("species", []))
        info["species"] = [e for e in info.get("species", []) if e["id"] != "PENDING_PHASE1"]
        dropped_total += before - len(info["species"])
        if sig and sig["id"] == "PENDING_PHASE1":
            del info["signature"]

    with open(mapped_path, "w") as f:
        json.dump(mapped, f, indent=1, sort_keys=True)

    with open(os.path.join(HERE, "stageb_ambiguous.txt"), "w") as f:
        for const, name, matches in sorted(ambiguous):
            f.write("%s (%r) -> picked index %d, other matches: %s\n"
                    % (const, name, matches[0], matches[1:]))

    with open(os.path.join(HERE, "stageb_unmatched.txt"), "w") as f:
        f.write("\n".join(sorted(unmatched)) + ("\n" if unmatched else ""))

    empty_after = [d for d, i in mapped.items() if not i.get("species")]

    print("STAGE B: resolved %d/%d distinct species consts (%d ambiguous, %d unmatched)"
          % (len(resolved_cache) - len(unmatched), len(resolved_cache), len(ambiguous), len(unmatched)))
    print("dropped %d unresolved roster entries (species not present in this ROM)" % dropped_total)
    if empty_after:
        print("WARNING: %d characters now have an empty roster after Stage B: %s"
              % (len(empty_after), ", ".join(empty_after)))
    if unmatched:
        print("See stageb_unmatched.txt -- these species genuinely don't exist "
              "in this ROM's species table (same category that drove the "
              "characters.txt trim in docs/SPECIES_CAP.md).")
    if ambiguous:
        print("See stageb_ambiguous.txt -- %d const(s) matched multiple ROM "
              "indices (regional/alt forms); lowest index was picked for each, "
              "spot-check before trusting." % len(ambiguous))


if __name__ == "__main__":
    main()
