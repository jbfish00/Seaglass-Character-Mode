#!/usr/bin/env python3
"""Emit per-character allowed-species BITMAPS for the Character Mode shim.

The roster pipeline stores each character's roster as evolution-family BASE
stages (ROM species ids). Enforcement must allow the whole family (catching an
Ivysaur/Venusaur is fine if Bulbasaur is on the roster), so this expands each
base forward through the donor's evolution graph to all descendants, maps every
family member's display name back to this ROM's species id, and sets its bit.

Output: rosters_expanded.bin = record_count x BITMAP_STRIDE bytes (bit S set =>
species id S is catchable/keepable for that character). Index-aligned with
characters.bin. Feeds src/character_mode.c's onRoster() bit test.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map_species as M           # reuse the donor family parser + normalize
from map_species_stage_b import normalize

MANIFEST = os.path.join(HERE, "characters_manifest.json")
ROM_TABLE = os.path.join(HERE, "rom_species_table.json")
OUT = os.path.join(HERE, "rosters_expanded.bin")


def load_donor_forward():
    """const -> display name, and forward edges const -> {child consts}."""
    const_name, forward = {}, {}
    for fname in M.FAMILY_FILES:
        for const, name, children in M.parse_family_file(os.path.join(M.FAMILY_DIR, fname)):
            if name and const not in const_name:
                const_name[const] = name
            forward.setdefault(const, set())
            for ch in children:
                if ch != const:
                    forward[const].add(ch)
    return const_name, forward


def family_closure(base_const, forward):
    seen, stack = set(), [base_const]
    while stack:
        c = stack.pop()
        if c in seen:
            continue
        seen.add(c)
        stack.extend(forward.get(c, ()))
    return seen


def main():
    manifest = json.load(open(MANIFEST))
    rom_tbl = json.load(open(ROM_TABLE))["species"]  # {index(str): name}
    # ROM name -> lowest id (regional/alt forms reuse a base name; base wins)
    name_to_id = {}
    max_id = 0
    for idx_s, nm in rom_tbl.items():
        idx = int(idx_s)
        max_id = max(max_id, idx)
        key = normalize(nm)
        if key and (key not in name_to_id or idx < name_to_id[key]):
            name_to_id[key] = idx
    id_to_name = {int(i): nm for i, nm in rom_tbl.items()}

    name_to_const, _parent = M.load_donor()
    const_name, forward = load_donor_forward()

    stride = (max_id + 8) // 8          # bytes to cover ids 0..max_id
    records = manifest["characters"]
    blob = bytearray()
    stats = {"chars": 0, "bits_total": 0, "unresolved": 0}
    for c in records:
        bm = bytearray(stride)
        allowed = set()
        for base_id in c["roster_species_ids"]:
            allowed.add(base_id)                    # the base itself
            base_name = id_to_name.get(base_id)
            const = name_to_const.get(base_name) if base_name else None
            if not const:
                continue
            for member in family_closure(const, forward):
                mnm = const_name.get(member)
                if not mnm:
                    continue
                mid = name_to_id.get(normalize(mnm))
                if mid is not None:
                    allowed.add(mid)
                else:
                    stats["unresolved"] += 1
        for sid in allowed:
            if 0 <= sid <= max_id:
                bm[sid >> 3] |= 1 << (sid & 7)
        blob += bm
        stats["chars"] += 1
        stats["bits_total"] += len(allowed)

    open(OUT, "wb").write(blob)
    print("wrote %s: %d chars x %d bytes = %d B" % (OUT, len(records), stride, len(blob)))
    print("NUM_SPECIES(max id)=%d  BITMAP_STRIDE=%d  avg allowed/char=%.1f  fam-name-unresolved=%d"
          % (max_id, stride, stats["bits_total"] / max(1, stats["chars"]), stats["unresolved"]))
    # sanity: character 0 (Red) should allow Bulbasaur(1),Ivysaur(2),Venusaur(3)
    r0 = blob[0:stride]
    def has(sid): return (r0[sid >> 3] >> (sid & 7)) & 1
    print("Red allows Bulbasaur/Ivysaur/Venusaur:", has(1), has(2), has(3),
          " Charmander/Charmeleon/Charizard:", has(4), has(5), has(6))


if __name__ == "__main__":
    main()
