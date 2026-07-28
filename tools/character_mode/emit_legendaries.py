#!/usr/bin/env python3
"""Emit legendaries.bin -- the data for the 1% legendary wild encounter rule.

Spec: ../../game_plans/legendary_encounters.md. If a legendary is on the active
character's roster there is a 1% chance to meet one in any area, rolled
independently of the existing 10% roster override, and each legendary is
OFFERED UNTIL CAUGHT.

⚠️ WHY FLAGS AND NOT THE POKEDEX. The spec tracks "already caught" with the
Pokedex caught bitmap, which costs zero new save state, and that is what the
other three games do. That accessor is NOT located in this ROM: four separate
probe strategies failed on 2026-07-27 and are recorded, with their tooling, in
game_plans/seaglass.md 5b. This uses the fallback the plan already sanctions --
one dedicated flag per distinct legendary -- which costs 20 bits of save state
instead of zero. If the dex is ever located, only the shim's `caught()` helper
has to change; this file and the data layout do not.

⚠️ THE FLAGS ARE NOT CONSECUTIVE, and the shim must not assume they are. There
is no run of 20 free flags anywhere in the valid space: the longest is 8. So the
flag id for each legendary is emitted as DATA and looked up, rather than being
FLAG_BASE + index.

Flag selection rules, all enforced below:
  * inside the flags array at all -- flags live at SB1+0x13C0..0x14EB (vars start
    at 0x14EC), so the space is 0x000..0x95F and nothing above 0x95F exists;
  * outside 0x000-0x01F, which ClearTempFieldEventData() wipes on every map load;
  * outside 0x920-0x95F, which ClearDailyFlags() wipes on every RTC day rollover
    -- that is the bug that silently switched Character Mode off at midnight
    (flag 0x945, fixed 2026-07-24), and the donor's FLAG_UNUSED_* list is mostly
    daily flags, which is exactly what caused it;
  * zero setflag/clearflag/checkflag operands anywhere in the ROM. That scan is
    CONSERVATIVE by construction: it counts raw byte matches, so it over-reports
    references and a zero result genuinely means unused.

Layout of legendaries.bin (little-endian):
    +0x00  u16 species_id[COUNT]     the distinct legendaries, ascending
    +0x28  u16 flag_id[COUNT]        the flag that records "caught", per index
    +0x50  u32 char_mask[NUM_CHARS]  bit i set = this character owns legendary i

Run after emit_characters.py --final:
    python3 tools/character_mode/emit_legendaries.py
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ROM = os.path.join(ROOT, "rom", "seaglass v3.0.gba")
OUT = os.path.join(HERE, "legendaries.bin")

FLAG_SPACE_END = 0x95F           # last flag that exists at all
TEMP_LO, TEMP_HI = 0x000, 0x01F  # ClearTempFieldEventData
DAILY_LO, DAILY_HI = 0x920, 0x95F  # ClearDailyFlags
FLAG_SEARCH_FROM = 0x2B1         # just past FLAG_CHARACTER_MODE (0x2B0)
SCR_SETFLAG, SCR_CLEARFLAG, SCR_CHECKFLAG = 0x29, 0x2A, 0x2B


def script_refs(rom, flag):
    return sum(rom.count(bytes([op]) + struct.pack("<H", flag))
               for op in (SCR_SETFLAG, SCR_CLEARFLAG, SCR_CHECKFLAG))


def pick_flags(rom, n):
    out = []
    f = FLAG_SEARCH_FROM
    while len(out) < n and f <= FLAG_SPACE_END:
        if not (TEMP_LO <= f <= TEMP_HI) and not (DAILY_LO <= f <= DAILY_HI) \
           and script_refs(rom, f) == 0:
            out.append(f)
        f += 1
    if len(out) < n:
        raise SystemExit("emit_legendaries: only found %d usable flags, need %d"
                         % (len(out), n))
    return out


def main():
    with open(os.path.join(HERE, "characters_manifest.json"), encoding="utf-8") as fh:
        chars = json.load(fh)["characters"]
    with open(os.path.join(HERE, "rom_species_table.json"), encoding="utf-8") as fh:
        names = json.load(fh)["species"]

    # Legendaries sit AFTER starter_count in roster_species_ids -- the same slice
    # convention emit_wildpool.py relies on to exclude them from the 10% pool.
    per_char = [c["roster_species_ids"][c["starter_count"]:] for c in chars]
    distinct = sorted({s for legs in per_char for s in legs})
    count = len(distinct)
    if not count:
        raise SystemExit("emit_legendaries: no legendaries found -- check that "
                         "starter_count is populated")
    if count > 32:
        raise SystemExit("emit_legendaries: %d legendaries but char_mask is a "
                         "u32 -- widen the mask before adding more" % count)
    index = {s: i for i, s in enumerate(distinct)}

    with open(ROM, "rb") as fh:
        rom = fh.read()
    flags = pick_flags(rom, count)
    assert len(set(flags)) == count, "duplicate flag assigned"

    blob = bytearray()
    for s in distinct:
        blob += struct.pack("<H", s)
    for fl in flags:
        blob += struct.pack("<H", fl)
    n_with = 0
    for legs in per_char:
        mask = 0
        for s in legs:
            mask |= 1 << index[s]
        if mask:
            n_with += 1
        blob += struct.pack("<I", mask)

    expect = count * 2 + count * 2 + len(chars) * 4
    assert len(blob) == expect, (len(blob), expect)
    with open(OUT, "wb") as fh:
        fh.write(blob)

    print("wrote %s: %d B (%d legendaries, %d characters)"
          % (OUT, len(blob), count, len(chars)))
    print("  %d of %d characters have at least one legendary"
          % (n_with, len(chars)))
    print("  flags: %s" % ", ".join("%#x" % f for f in flags))
    for i, s in enumerate(distinct):
        print("    [%2d] %-5d %-12s -> flag %#x"
              % (i, s, names.get(str(s), "?"), flags[i]))
    # Emitted so verify_artifacts can re-derive the same answer independently
    # rather than trusting the .bin it is checking.
    with open(os.path.join(HERE, "legendaries_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"count": count, "species": distinct, "flags": flags,
                   "characters_with_legendary": n_with,
                   "char_mask_offset": count * 4,
                   "_comment": "GENERATED by emit_legendaries.py -- do not hand-edit"},
                  fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main()
