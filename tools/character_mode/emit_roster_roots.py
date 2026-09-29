#!/usr/bin/env python3
"""Emit roster_roots.bin -- the family ROOTS of each character's roster, in
authored order, for the in-game roster display.

Spec: ../../../game_plans/roster_display.md. The screen shows ONE ROW PER FAMILY
ROOT for the ACTIVE character only, each row a species name plus a bordered
species icon. This file emits the roots; the names come from the ROM's own
species table and are never copied.

⚠️⚠️ WHY THIS BLOB EXISTS AT ALL. Nothing else in the ROM holds a character's
roots in order. The allow-bitmap is a SET of every species in every family
(every stage, no order), and the ROM has no cheap way to walk a family back to
its root at run time. So the ordered roots are emitted here, once, from the
audited roster.

The shim (src/roster_display.c) pushes one row per root with the STACK form of
dynmultichoice, and each row's id is the SPECIES. (An earlier design used the
script-pointer form, which sets `items[i].id = i` and would have needed this blob
to map a row index back to a species. That design was abandoned.) So
`OnSelectionChanged` gets the species directly. docs/ROUTINE_MAP.md "Dynamic
multichoice" has the RE.

⭐ ROWE's trap, recorded here because the stack form is what keeps it away:
`moveCursorFunc`'s first parameter is the item's ID, not its index. Indexing
the item array with it drew Scyther for Pikachu, and because Scyther is green
it read as a palette bug and cost two rebuilds "fixing" a palette that was never
broken. Here the id IS the species, so nothing indexes the item array at all.

WHAT IS IN THE LIST. `roster_species_ids` verbatim, whole: the signature species
first (84 of 84 characters with a signature have it at [0]), then the rest of
the non-legendary roots, then the legendaries -- which sit after `starter_count`
in the same slice convention emit_wildpool.py uses to EXCLUDE them from the 10%
pool. Nothing is filtered or re-sorted here. Re-resolving roster names against
the target ROM's dex is the one thing this pipeline must never do (the Platinum
finding: a smaller dex silently loses cross-generation family links), so this
consumes the already-mapped, already-audited ids and only checks them.

⚠️ NAMES ARE NOT EMITTED. Every root is asserted to resolve in the ROM's own
species table (rom_species_table.json, base 0x008F07AC, stride 208, name at
offset 0; that base is gSpeciesInfo 0x088F0780 + 44, the NAME field). The shim
copies each name out of that table into a heap buffer, because the engine
Free()s every row name when the list closes (FreeListMenuItems), and a pointer
into ROM would be freed. An id with no name there would draw a blank row, so a
miss is a hard error here rather than something to notice on the screen later.

⭐ ONE CHARACTER'S ROOTS COLLAPSE, AND THE DISPLAY IS THE ONLY THING THAT CARES.
Rika's roster holds both Wooper (-> Quagsire) and Clodsire, whose root is
Paldean Wooper. `SPECIES_WOOPER` and `SPECIES_WOOPER_PALDEA` are two distinct
constants that both resolve to ID 194 in THIS ROM, because Seaglass's curated
dex has no separate Paldean Wooper -- so the regional form collapses onto the
base species. That is correct behaviour of the mapper, not a scraper defect, and
it is measured: she is the ONLY one of the 193 characters it happens to, and she
is OFFERED, so a real player can reach this screen.

Enforcement never noticed because the allow-bitmap is a SET -- setting a bit
twice is setting it once. A LIST is not, so the screen would print "Wooper"
twice. Deduplicated here, first occurrence kept (which preserves the signature
at [0]; hers IS the Paldean one). This costs Rika one displayed row, 6 -> 5, and
that number is honest: the ROM really does have only five distinct roots for
her. Nothing about enforcement, the wild pool or the playability threshold
changes -- none of them reads this file.

⚠️ THREE CHARACTERS HAVE AN EMPTY ROSTER (Rowan, Juniper, Sonia) and are hidden
by the playability threshold, so no player can select them. They still get a
record -- count 0 -- because records are indexed by character id and a missing
one would shift every character after it. A consumer MUST branch on count == 0
rather than assuming at least one row: "empty rosters need an explicit branch in
every consumer" is already a recorded trap in this workspace.

Layout of roster_roots.bin (little-endian):
    +0x0000  entry[NUM_CHARACTERS]    u16 first_root, u16 root_count  (4 B each)
    +0x0304  u16 roots[TOTAL_ROOTS]   all characters' roots, concatenated

`first_root` is an INDEX INTO roots[], not a byte offset -- the byte address of
a character's first root is ROOTS_ADDR + entry.first_root * 2.

⭐ There is deliberately NO STRIDE. A fixed-stride table would need a constant
shared between this emitter and the C shim, and that is precisely the shape of
this repo's worst shipped bug: WILDPOOL_STRIDE was 104 in the shim and 176 in
the data, so every character except #1 read a misaligned slice of somebody
else's pool, and a 49-check verifier and a 14-layer live suite both passed it.
An offset+count table has no such constant to disagree about.

Run after emit_characters.py --final:
    python3 tools/character_mode/emit_roster_roots.py
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "roster_roots.bin")

ENTRY_SIZE = 4   # u16 first_root, u16 root_count


def main():
    with open(os.path.join(HERE, "characters_manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    chars = manifest["characters"]
    # Derived, never hardcoded: a stale literal character count is the most
    # repeated bug in this workspace and it never presents AS a count error.
    n_chars = len(chars)
    assert n_chars == manifest["record_count"], (n_chars, manifest["record_count"])

    with open(os.path.join(HERE, "rom_species_table.json"), encoding="utf-8") as fh:
        table = json.load(fh)
    names = table["species"]

    entries = bytearray()
    roots = bytearray()
    cursor = 0
    empty = []
    max_count = 0

    collapsed = []

    for c in chars:
        raw = c["roster_species_ids"]
        # Deduplicate, keeping first occurrence -- see the Rika note in the
        # module docstring. Recorded per character rather than silently dropped,
        # because a NEW collapse appearing here is a real signal about the dex.
        ids = list(dict.fromkeys(raw))
        if len(ids) != len(raw):
            collapsed.append({"character": c["character"],
                              "was": len(raw), "now": len(ids)})
        for s in ids:
            # A root with no name in this ROM would draw a blank row. Fail here
            # instead, where the id is still attributable to a character.
            assert str(s) in names, (
                "%s: root species %d has no name in the ROM species table"
                % (c["character"], s))
            assert 0 < s <= 0xFFFF, (c["character"], s)
        assert len(set(ids)) == len(ids), (
            "%s: dedup failed" % c["character"])
        if not ids:
            empty.append(c["character"])
        max_count = max(max_count, len(ids))
        assert cursor <= 0xFFFF and len(ids) <= 0xFFFF, (c["character"], cursor)
        entries += struct.pack("<HH", cursor, len(ids))
        for s in ids:
            roots += struct.pack("<H", s)
        cursor += len(ids)

    total_roots = cursor
    blob = bytes(entries) + bytes(roots)
    expect = n_chars * ENTRY_SIZE + total_roots * 2
    assert len(blob) == expect, (len(blob), expect)
    # The emitter's own claim about where roots[] starts, checked rather than
    # asserted in a comment -- the shim is given this as -DROSTER_ROOTS_OFF.
    roots_off = n_chars * ENTRY_SIZE
    assert blob[roots_off:roots_off + 2] == struct.pack(
        "<H", chars[0]["roster_species_ids"][0]), "roots[] does not start where claimed"

    with open(OUT, "wb") as fh:
        fh.write(blob)

    # Emitted so verify_artifacts can re-derive the same answer independently
    # rather than trusting the .bin it is checking.
    with open(os.path.join(HERE, "roster_roots_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "characters": n_chars,
            "total_roots": total_roots,
            "entry_size_bytes": ENTRY_SIZE,
            "roots_offset_bytes": roots_off,
            "blob_size_bytes": len(blob),
            "max_roots_per_character": max_count,
            "empty_roster": empty,
            "collapsed_duplicate_roots": collapsed,
            "species_table_base": table["table_base_offset"],
            "species_table_stride": table["stride_bytes"],
            "_comment": "GENERATED by emit_roster_roots.py -- do not hand-edit",
        }, fh, indent=1)
        fh.write("\n")

    print("wrote %s: %d B (%d characters, %d roots, roots[] at +%#x)"
          % (OUT, len(blob), n_chars, total_roots, roots_off))
    print("  longest roster %d roots; %d empty (%s)"
          % (max_count, len(empty), ", ".join(empty) if empty else "none"))
    for cd in collapsed:
        print("  collapsed duplicate root: %s %d -> %d rows"
              % (cd["character"], cd["was"], cd["now"]))


if __name__ == "__main__":
    main()
