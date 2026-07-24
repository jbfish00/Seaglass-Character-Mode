#!/usr/bin/env python3
"""Emit per-character WILD-ENCOUNTER OVERRIDE POOLS for the Character Mode
shim's new wild-encounter feature (species+level roll override).

Spec (see repo CLAUDE.md): on a wild encounter, after the normal species+level
roll, there's a 10% chance to override the result with a random member of the
active character's roster. Legendaries/mythicals are NEVER offered via this
path. Among the remaining eligible members, pick the evolution stage whose
canon level range best fits the rolled level (low level -> early stage, high
level -> evolved stage), nearest-stage fallback otherwise.

This reuses two things already built for the catch-gate bitmap
(emit_bitmaps.py):
  - characters_manifest.json's roster_species_ids[:starter_count] -- the
    non-legendary FAMILY-BASE species per character (legendary bases are
    ordered *after* starter_count and are simply never included here, which
    is how exclusion is enforced -- see build_rosters() in emit_characters.py).
  - the donor's per-species evolution edges (gen_N_families.h), same source
    map_species.py/emit_bitmaps.py already parse, but this script ALSO reads
    the evolution *parameter* (the level threshold for EVO_LEVEL-type edges)
    to build a canon "first-appears-at-level" estimate per family member:
      - the base stage's level = 1 (earliest obtainable)
      - a child reached via EVO_LEVEL, N with N>0 -> level = N
      - any other evolution method (item/trade/friendship/etc, or EVO_LEVEL,0
        e.g. friendship-gated) -> level = parent's level + a fixed step
        (16 for stage 1, 32 for stage 2, 45 for stage 3+) as a reasonable
        canon-ish default when no level is inherent to the method.

Output: wildpool.bin = NUM_CHARACTERS x POOL_STRIDE records of
  u16 species_id, u8 minLevel, u8 _pad
terminated within each character's slice by species_id == 0 (SPECIES_NONE,
never a real id). Feeds src/character_mode.c's CM_WildMonSpeciesGated().
"""
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map_species as M
from map_species_stage_b import normalize

MANIFEST = os.path.join(HERE, "characters_manifest.json")
ROM_TABLE = os.path.join(HERE, "rom_species_table.json")
OUT = os.path.join(HERE, "wildpool.bin")
MANIFEST_OUT = os.path.join(HERE, "wildpool_manifest.json")

NUM_CHARACTERS = 182  # 170 + 11 professors + Tobias (2026-07-23; Magnolia/Sada/Turo trimmed)
POOL_STRIDE = 176  # entries/character; raised 104->176 (2026-07-23 full-research rosters: max observed 160, Goh)
STEP_BY_DEPTH = {1: 16, 2: 32, 3: 45, 4: 55}
DEFAULT_STEP = 60

EVO_RE = re.compile(
    r"\{\s*(EVO_[A-Z0-9_]+)\s*,\s*([^,]+),\s*(SPECIES_[A-Z0-9_]+)")


def parse_family_file_with_levels(path):
    """Like map_species.parse_family_file but also returns, per child edge,
    the evolution type + raw param text (so EVO_LEVEL's numeric level can be
    used as the child's canon min-level)."""
    text = open(path, encoding="utf-8").read()
    starts = list(re.finditer(r"\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*\{", text))
    out = []
    for i, m in enumerate(starts):
        const = m.group(1)
        block_start = m.end()
        block_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[block_start:block_end]
        name_m = re.search(r'\.speciesName\s*=\s*_\("([^"]*)"\)', block)
        name = name_m.group(1) if name_m else None
        edges = []  # (evoType, paramText, childConst)
        evo_m = re.search(r"\.evolutions\s*=\s*EVOLUTION\(", block)
        if evo_m:
            captured = []
            for line in block[evo_m.end():].split("\n"):
                if line.strip().startswith(".") and "=" in line:
                    break
                captured.append(line)
            evo_text = "\n".join(captured)
            for tm in EVO_RE.finditer(evo_text):
                edges.append((tm.group(1), tm.group(2).strip(), tm.group(3)))
        out.append((const, name, edges))
    return out


def load_donor_forward_with_levels():
    """const -> display name, and forward edges const -> [(evoType, paramText, childConst), ...]."""
    const_name, forward = {}, {}
    for fname in M.FAMILY_FILES:
        for const, name, edges in parse_family_file_with_levels(
                os.path.join(M.FAMILY_DIR, fname)):
            if name and const not in const_name:
                const_name[const] = name
            forward.setdefault(const, [])
            for evo_type, param, child in edges:
                if child != const:
                    forward[const].append((evo_type, param, child))
    return const_name, forward


def levels_for_family(base_const, forward):
    """BFS from base_const (level=1) following forward edges, assigning each
    reached const the LOWEST level at which it's reachable (ties broken by
    BFS order -- fine, evolution trees are trees, not general DAGs)."""
    levels = {base_const: 1}
    stack = [(base_const, 1, 0)]
    while stack:
        c, lvl, depth = stack.pop()
        for evo_type, param, child in forward.get(c, ()):
            if evo_type == "EVO_LEVEL":
                try:
                    n = int(param, 0)
                except ValueError:
                    n = 0
                child_lvl = n if n > 0 else lvl + STEP_BY_DEPTH.get(depth + 1, DEFAULT_STEP)
            else:
                child_lvl = lvl + STEP_BY_DEPTH.get(depth + 1, DEFAULT_STEP)
            child_lvl = max(1, min(100, child_lvl))
            if child not in levels or child_lvl < levels[child]:
                levels[child] = child_lvl
                stack.append((child, child_lvl, depth + 1))
    return levels


def main():
    manifest = json.load(open(MANIFEST))
    rom_tbl = json.load(open(ROM_TABLE))["species"]
    name_to_id = {}
    for idx_s, nm in rom_tbl.items():
        idx = int(idx_s)
        key = normalize(nm)
        if key and (key not in name_to_id or idx < name_to_id[key]):
            name_to_id[key] = idx
    id_to_name = {int(i): nm for i, nm in rom_tbl.items()}

    name_to_const, _parent = M.load_donor()
    const_name, forward = load_donor_forward_with_levels()

    chars = manifest["characters"]
    assert len(chars) == NUM_CHARACTERS, len(chars)

    blob = bytearray()
    debug_manifest = []
    max_entries = 0
    total_unresolved = 0
    for c in chars:
        base_ids = c["roster_species_ids"][: c["starter_count"]]  # non-legendary only
        pool = {}  # species_id -> minLevel (lowest wins across overlapping families)
        for base_id in base_ids:
            base_name = id_to_name.get(base_id)
            const = name_to_const.get(base_name) if base_name else None
            if not const:
                continue
            levels = levels_for_family(const, forward)
            for member_const, lvl in levels.items():
                mnm = const_name.get(member_const)
                if not mnm:
                    continue
                mid = name_to_id.get(normalize(mnm))
                if mid is None:
                    total_unresolved += 1
                    continue
                if mid not in pool or lvl < pool[mid]:
                    pool[mid] = lvl

        entries = sorted(pool.items(), key=lambda kv: (kv[1], kv[0]))
        assert len(entries) <= POOL_STRIDE, (
            f"{c['character']}: pool has {len(entries)} entries, exceeds "
            f"POOL_STRIDE={POOL_STRIDE} -- raise POOL_STRIDE rather than "
            f"silently truncate a roster's wild-encounter pool")
        max_entries = max(max_entries, len(entries))

        rec = bytearray(POOL_STRIDE * 4)
        for i, (sid, lvl) in enumerate(entries):
            struct.pack_into("<HBB", rec, i * 4, sid, lvl, 0)
        blob += rec
        debug_manifest.append({
            "character": c["character"],
            "pool_size": len(entries),
            "pool": [{"species_id": sid, "species": id_to_name.get(sid, "?"), "min_level": lvl}
                     for sid, lvl in entries],
        })

    assert max_entries <= POOL_STRIDE, (
        f"POOL_STRIDE too small: need {max_entries}, have {POOL_STRIDE}")

    open(OUT, "wb").write(blob)
    json.dump({"pool_stride": POOL_STRIDE, "characters": debug_manifest},
               open(MANIFEST_OUT, "w"), indent=1)
    print(f"wrote {OUT}: {len(chars)} chars x {POOL_STRIDE} entries x 4B = {len(blob)} B")
    print(f"max pool entries used by any character: {max_entries} (stride={POOL_STRIDE})")
    print(f"family-name-unresolved (skipped) member lookups: {total_unresolved}")
    # sanity: character 0 (Red) should have Bulbasaur(1)@lvl1 ... Charizard family etc,
    # and NO legendary (Mewtwo not in pool despite being on Red's full roster).
    r0 = debug_manifest[0]
    print("Red pool sample:", r0["pool"][:6], "... size", r0["pool_size"])
    legend_names = {"Mewtwo", "Mew"}
    leaked = [e for e in r0["pool"] if e["species"] in legend_names]
    print("Red pool legendary leak-check (should be empty):", leaked)


if __name__ == "__main__":
    main()
