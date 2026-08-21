#!/usr/bin/env python3
"""Pick one trainer front pic per character and emit an injectable sprite table.

Phase 3 wiring. Until now `sprite_asset_id` has been 0xFFFF in every record --
a placeholder for art that did not exist. 754 sprites are now staged under
`sprites/donors/`, so this resolves each character to one of them and emits the
two blobs the injector places:

    cm_sprite_blobs.bin   every chosen sprite's LZ77 gfx + palette, concatenated
    cm_sprite_offsets.bin NUM_CHARACTERS x {u32 gfx_off, u32 pal_off}, relative
                          to the blob base; 0xFFFFFFFF for a character with no art

The injector turns those offsets into absolute ROM pointers, and
`emit_characters.py` writes `sprite_asset_id` = the character's own index (or
0xFFFF), so a reader can go character -> table entry -> gfx/palette in one hop.

Deliberately NOT touching gTrainerFrontPicTable's existing 148 slots. Repointing
those would replace the art of real opponents mid-playthrough; this table is
additive and changes nothing the game already draws. What renders it is a
separate question -- see docs/SPRITE_COVERAGE.md.

Source preference, best first. Rationale rather than taste:
  ashgray   already verbatim ROM-format LZ, and anime-specific art we cannot
            get elsewhere -- but only where it is that character's own pic,
            not an alternate
  rogue     the largest coherent set, one consistent style across Gen 1-9
  taar      per-author attribution is recoverable, the cleanest licence
  hns       HGSS-style, good Kanto/Johto coverage
  pokesho   anime-specific, fills gaps the game-art sets cannot
  platinum  weakest attribution (no per-sprite credit) -- last resort
"""
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DONORS = ROOT / "sprites" / "donors"

PREFERENCE = ["ashgray", "rogue", "taar", "hns", "pokesho", "dollsteak", "loulilie", "platinum"]

slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

# characters whose staged art is filed under a different stem
ALIAS = {
    # Tate has no front pic staged; Liza does (hns/liza_front) and matches on her
    # own name -- an earlier "tate_and_liza" alias for both silently blocked her.

    "Gary": "gary", "Ash": "ash", "Jessie": "jessie", "James": "jessie_james",
    "Lt. Surge": "lt_surge", "Crasher Wake": "crasher_wake",
    "Oak": "oak", "Samson Oak": None,
}


def candidates(character):
    """Every staged front pic for this character, best source first."""
    # ⚠️ STRIP " (anime)" FIRST, or the four Alola captains can never match.
    # `slug("Kiawe (anime)")` is `kiawe_anime`, and the staged art is
    # `kiawe_front` -- so before 2026-07-29 NO character whose display name
    # carried the suffix had a portrait in any repo, and all four sat in the
    # manifest's `missing` list looking like an art gap. It was a matcher gap.
    # Mirrors ROWE's import_donor_front_pics.py, which strips it already.
    # Checked before landing: the suffix appears on exactly four display names
    # per repo (Lillie, Kiawe, Lana, Mallow), none of the stripped stems
    # collides with another character, and no anime-styled alternate is
    # shadowed -- ashgray's `<name>_anime_front` files are reached by their own
    # stems, which are unaffected by this.
    base = character[:-len(" (anime)")] if character.endswith(" (anime)") else character
    stems = [slug(base)]
    a = ALIAS.get(character, ALIAS.get(base, ""))
    if a:
        stems.append(a)
    elif a is None:
        return []
    out = []
    for src in PREFERENCE:
        d = DONORS / src
        if not d.is_dir():
            continue
        for stem in stems:
            # the converted sets use <stem>_front[_N]; ashgray uses <stem>_front.lz
            for gfx in sorted(d.glob(f"{stem}_front*.4bpp.lz")):
                pal = gfx.with_name(gfx.name.replace(".4bpp.lz", ".gbapal.lz"))
                if pal.is_file():
                    out.append((src, gfx, pal))
            for gfx in sorted(d.glob(f"{stem}_front.lz")):
                pal = gfx.with_name(gfx.name.replace("_front.lz", "_frontpal.lz"))
                if pal.is_file():
                    out.append((src, gfx, pal))
    return out


def main():
    manifest = json.loads((HERE / "characters_manifest.json").read_text())
    chars = manifest["characters"]

    blobs = bytearray()
    offsets = bytearray()
    chosen, missing = [], []

    for c in chars:
        name = c["character"]
        cands = candidates(name)
        if not cands:
            offsets += struct.pack("<II", 0xFFFFFFFF, 0xFFFFFFFF)
            missing.append(name)
            continue
        src, gfx_p, pal_p = cands[0]
        gfx, pal = gfx_p.read_bytes(), pal_p.read_bytes()
        if gfx[0] != 0x10 or pal[0] != 0x10:
            # not an LZ77 stream -- refuse rather than inject something the
            # BIOS decompressor would choke on
            offsets += struct.pack("<II", 0xFFFFFFFF, 0xFFFFFFFF)
            missing.append(f"{name} (bad LZ header in {gfx_p.name})")
            continue
        g_off = len(blobs)
        blobs += gfx
        blobs += b"\x00" * (-len(blobs) % 4)          # keep entries word-aligned
        p_off = len(blobs)
        blobs += pal
        blobs += b"\x00" * (-len(blobs) % 4)
        offsets += struct.pack("<II", g_off, p_off)
        chosen.append({"character": name, "source": src, "file": gfx_p.name,
                       "gfx_off": g_off, "pal_off": p_off,
                       "gfx_bytes": len(gfx), "pal_bytes": len(pal)})

    # Patch sprite_asset_id in characters.bin rather than having
    # emit_characters.py compute it. emit_characters runs FIRST (this script
    # reads its manifest), so asking it to know which characters have art would
    # be circular. Record layout is 12 bytes; sprite_asset_id is the u16 at +8.
    cbin = HERE / "characters.bin"
    if cbin.is_file():
        data = bytearray(cbin.read_bytes())
        assert len(data) == len(chars) * 12, (len(data), len(chars))
        wired = 0
        for i in range(len(chars)):
            g_off, _ = struct.unpack_from("<II", offsets, i * 8)
            val = 0xFFFF if g_off == 0xFFFFFFFF else i
            struct.pack_into("<H", data, i * 12 + 8, val)
            wired += val != 0xFFFF
        cbin.write_bytes(bytes(data))
        print(f"characters.bin: sprite_asset_id set for {wired} characters "
              f"({len(chars) - wired} left 0xFFFF)")

    (HERE / "cm_sprite_blobs.bin").write_bytes(bytes(blobs))
    (HERE / "cm_sprite_offsets.bin").write_bytes(bytes(offsets))
    (HERE / "cm_sprite_manifest.json").write_text(json.dumps(
        {"count": len(chars), "with_art": len(chosen), "without_art": len(missing),
         "blob_bytes": len(blobs), "entries": chosen, "missing": missing}, indent=1))

    by_src = {}
    for e in chosen:
        by_src[e["source"]] = by_src.get(e["source"], 0) + 1
    print(f"sprite table: {len(chosen)}/{len(chars)} characters have a front pic")
    for s in PREFERENCE:
        if by_src.get(s):
            print(f"   {s:<10} {by_src[s]}")
    print(f"  cm_sprite_blobs.bin   {len(blobs):,} bytes")
    print(f"  cm_sprite_offsets.bin {len(offsets):,} bytes ({len(chars)} x 8)")
    if missing:
        print(f"  no art ({len(missing)}): {', '.join(missing[:12])}"
              + (" ..." if len(missing) > 12 else ""))


if __name__ == "__main__":
    main()
