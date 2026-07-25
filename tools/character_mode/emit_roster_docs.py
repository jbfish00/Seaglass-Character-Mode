#!/usr/bin/env python3
"""Generate ROSTERS.md / ROSTERS_SPRITES.md / sprites/gen_*.md from the data
the ROM actually enforces.

Why this exists: these docs used to be hand-maintained, and in the ROWE
reference project that produced a shipped doc promising 194 family bases the
catch gate refused while omitting ~2500 it already allowed. Here the docs are
derived from `rosters_expanded.bin` - the very allow-bitmaps `onRoster()` bit-
tests in the shim - so the doc cannot claim anything the ROM does not honour.

Inputs:
  rosters_expanded.bin      allow-bitmaps, one record per character
  characters_manifest.json  character order, names, generation, category
  rom_species_table.json    this ROM's species id -> display name
  the pokeemerald-expansion donor  evolution graph + national dex numbers
  docs/roster_provenance.json  the ᵃ/ᵍ provenance markers

"Final evolutions" = allowed species with nothing left to evolve into. The
donor's family files already exclude mega/gigantamax forms from `evolutions`,
so no method filtering is needed here. Cosmetic forms that cannot evolve
(the cap Pikachus) are NOT final stages of a family whose base still evolves,
and regional forms collapse onto their base species for display.

Run after emit_bitmaps.py:
    python3 tools/character_mode/emit_roster_docs.py
"""
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import map_species as M                     # noqa: E402  donor family parser
from map_species_stage_b import normalize   # noqa: E402

GAME_TITLE = "Pokémon Emerald Seaglass v3.0"
WIP_NOTE = ("> ⚠️ **Work in progress** — availability in this specific game "
            "may differ.")

CATEGORY_LABEL = {
    "protagonist": "Protagonist", "rival": "Rival", "gymleader": "Gym Leader",
    "elite4": "Elite Four", "champion": "Champion", "villain": "Villain",
    "anime": "Anime", "professor": "Professor",
}

SPRITE_URL = ("https://cdn.jsdelivr.net/gh/PokeAPI/sprites@master"
              "/sprites/pokemon/%d.png")
SPRITES_PER_ROW = 8


def species_blocks(text):
    """Yield (SPECIES_const, its full initializer block) by counting braces.

    A regex cannot do this: a species block nests several levels deep
    (.evolutions = EVOLUTION({...}, {...}), .formSpeciesIdTable, ...), and a
    one-level-nesting pattern silently matches nothing for the deeper entries.
    That bug shipped once already - every sprite URL came out as /0.png
    because .natDexNum was never found."""
    for m in re.finditer(r"\[(SPECIES_\w+)\]\s*=\s*\{", text):
        i = text.index("{", m.end() - 1)
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        yield m.group(1), text[i:j + 1]


def donor_species():
    """const -> {name, dex, children}, from the donor's gen_N_families.h."""
    info = {}
    for fname in M.FAMILY_FILES:
        path = os.path.join(M.FAMILY_DIR, fname)
        text = open(path, encoding="utf-8").read()
        dex_of = {}
        for const, block in species_blocks(text):
            m = re.search(r"\.natDexNum\s*=\s*(NATIONAL_DEX_\w+)", block)
            if m and const not in dex_of:
                dex_of[const] = m.group(1)
        for const, name, children in M.parse_family_file(path):
            rec = info.setdefault(const, {"name": name, "dex": dex_of.get(const),
                                          "children": set()})
            if name and not rec["name"]:
                rec["name"] = name
            rec["children"].update(c for c in children if c != const)
    # A few entries are macro-generated without a .natDexNum of their own
    # (SPECIES_FLORGES, whose colour forms carry it instead). Borrow the
    # number from a same-named sibling rather than rendering sprite id 0.
    dex_by_name = {}
    for rec in info.values():
        if rec["name"] and rec["dex"]:
            dex_by_name.setdefault(rec["name"], rec["dex"])
    for rec in info.values():
        if rec["name"] and not rec["dex"]:
            rec["dex"] = dex_by_name.get(rec["name"])
    return info


def dex_numbers():
    """NATIONAL_DEX_* -> number, from the donor's pokedex.h enum order."""
    text = open(os.path.join(M.DONOR, "include/constants/pokedex.h"),
                encoding="utf-8").read()
    # the enum is tagged (`enum NationalDexOrder {`), so allow a name here -
    # an untagged-only pattern matches nothing and every dex number silently
    # becomes 0
    body = re.search(r"enum\s+\w*\s*\{(.*?)\}\s*;", text, re.S).group(1)
    nums, n = {}, 0
    for line in body.splitlines():
        m = re.match(r"\s*(NATIONAL_DEX_\w+)\s*(?:=\s*(\d+))?\s*,", line)
        if not m:
            continue
        if m.group(2):
            n = int(m.group(2))
        nums[m.group(1)] = n
        n += 1
    return nums


TAG_MARKER = {"anime-only": "ᵃ", "single-game": "ᵍ"}


def load_markers():
    """character -> {final-evolution name: ᵃ/ᵍ}, from the repo's existing
    provenance archive (docs/roster_provenance.json, which also records WHICH
    game/anime the call came from). Absent entry = unclassified, not
    'multi-game': that research pass predates the roster additions."""
    path = os.path.join(TARGET, "docs/roster_provenance.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        archive = json.load(f)
    out = {}
    for char, species in archive.items():
        for name, info in species.items():
            mark = TAG_MARKER.get(info.get("tag"), "")
            if mark:
                out.setdefault(char, {})[name] = mark
    return out


def main():
    with open(os.path.join(HERE, "characters_manifest.json")) as f:
        manifest = json.load(f)["characters"]
    with open(os.path.join(HERE, "rosters_expanded.bin"), "rb") as f:
        bitmaps = f.read()
    with open(os.path.join(HERE, "rom_species_table.json")) as f:
        rom_names = {int(k): v for k, v in json.load(f)["species"].items()}
    markers = load_markers()

    stride = len(bitmaps) // len(manifest)
    if stride * len(manifest) != len(bitmaps):
        raise SystemExit("rosters_expanded.bin (%d bytes) is not a whole number "
                         "of records for %d characters - re-run emit_bitmaps.py"
                         % (len(bitmaps), len(manifest)))

    donor = donor_species()
    dexnum = dex_numbers()

    # normalized display name -> donor consts (a ROM species id resolves to its
    # donor entries by name, the same bridge emit_bitmaps.py uses)
    consts_by_name = defaultdict(list)
    for const, rec in donor.items():
        if rec["name"]:
            consts_by_name[normalize(rec["name"])].append(const)

    # canonical const per national dex number = the base-form entry
    canonical = {}
    for const in sorted(donor):
        d = donor[const]["dex"]
        if d:
            canonical.setdefault(d, const)

    def dex_of(const):
        d = donor[const]["dex"]
        if d:
            return dexnum.get(d, 0)
        # Last resort: derive the constant from the display name. Needed for
        # oddities like this donor's Eternal Floette, which carries the name
        # "Florges" and no .natDexNum of its own.
        name = (donor[const]["name"] or "").upper()
        return dexnum.get("NATIONAL_DEX_" + re.sub(r"[^A-Z0-9]", "", name), 0)

    def is_final(const):
        if donor[const]["children"]:
            return False
        base = canonical.get(donor[const]["dex"], const)
        return not donor[base]["children"]

    chars = []
    for i, rec in enumerate(manifest):
        bits = bitmaps[i * stride:(i + 1) * stride]
        finals = set()
        for sid, name in rom_names.items():
            if sid >= stride * 8 or not (bits[sid >> 3] & (1 << (sid & 7))):
                continue
            for const in consts_by_name.get(normalize(name), ()):
                if is_final(const):
                    finals.add(canonical.get(donor[const]["dex"], const))
        ordered = sorted(finals, key=lambda c: (dex_of(c), donor[c]["name"]))
        chars.append({
            "name": rec["character"],
            "gen": rec["generation"],
            "label": CATEGORY_LABEL.get(rec["category"], rec["category"].title()),
            "finals": [(donor[c]["name"], dex_of(c)) for c in ordered],
        })

    def marked(char, name):
        return name + markers.get(char, {}).get(name, "")

    by_gen = defaultdict(list)
    for c in chars:
        by_gen[c["gen"]].append(c)
    for g in by_gen:
        by_gen[g].sort(key=lambda c: c["name"])
    gens = sorted(by_gen)

    generated_note = ("GENERATED by `tools/character_mode/emit_roster_docs.py` "
                      "from `rosters_expanded.bin`, the same allow-bitmaps the "
                      "in-ROM shim tests — do not hand-edit, regenerate.")
    prov_note = ("> **Provenance:** ᵃ = only in the anime (never on this "
                 "character's team in a core game) · ᵍ = only in one core game. "
                 "Markers come from `docs/roster_provenance.json`; an entry "
                 "without one is unclassified rather than known to be "
                 "multi-game (that research pass predates the roster additions).")

    out = ["# Character Mode — Final-Evolution Rosters (%s)" % GAME_TITLE, "",
           "Every playable character and the **final evolutions** their complete "
           "roster resolves to, in **National Pokédex order**. Rosters were "
           "researched from Bulbapedia (union of all games, remakes, rematches, "
           "and anime) and cross-checked where possible. Regional/cosmetic forms "
           "show as their base species. Off-roster Pokémon are routed to your PC.",
           "", "Only species this ROM actually contains are listed: this hack ships a "
           "**curated dex** (see `docs/SPECIES_CAP.md`), so canon roster members the "
           "binary simply does not have are omitted rather than promised.",
           "", WIP_NOTE, "", prov_note, "",
           "**%d characters.** Sprite version: `ROSTERS_SPRITES.md`." % len(chars),
           "", generated_note, "", "## Contents"]
    for g in gens:
        out.append("- [Generation %d](#generation-%d)" % (g, g))
    out.append("")
    for g in gens:
        out += ["", "## Generation %d" % g, ""]
        for c in by_gen[g]:
            out.append("### %s — %s" % (c["name"], c["label"]))
            out.append("**Final evolutions (%d):**" % len(c["finals"]))
            out.append(", ".join(marked(c["name"], n) for n, _ in c["finals"]))
            out.append("")
    with open(os.path.join(TARGET, "ROSTERS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out).rstrip() + "\n")

    idx = ["# Character Mode — Roster Sprites (%s)" % GAME_TITLE, "",
           "Each character's **final-evolution** roster, in **National Pokédex "
           "order**, with sprites and names. Split by generation to keep pages "
           "fast. Regional/cosmetic forms show as base species. Sprites via "
           "[PokéAPI](https://github.com/PokeAPI/sprites). Text: `ROSTERS.md`.",
           "", "**%d characters.**" % len(chars), "", generated_note,
           "", "## Generations", ""]
    for g in gens:
        idx.append("- [Generation %d](sprites/gen_%d.md) — %d characters"
                   % (g, g, len(by_gen[g])))
    with open(os.path.join(TARGET, "ROSTERS_SPRITES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(idx).rstrip() + "\n")

    os.makedirs(os.path.join(TARGET, "sprites"), exist_ok=True)
    for g in gens:
        page = ["# %s — Roster Sprites (Generation %d)" % (GAME_TITLE, g), "",
                "Final-evolution rosters in National Pokédex order, sprites with "
                "names. [← back to index](../ROSTERS_SPRITES.md)", ""]
        for c in by_gen[g]:
            page.append("### %s — %s" % (c["name"], c["label"]))
            page.append("<table>")
            row = []
            for name, num in c["finals"]:
                row.append('<td align="center" width="80"><img width="56" src="%s">'
                           "<br><sub>%s</sub></td>"
                           % (SPRITE_URL % num, marked(c["name"], name)))
                if len(row) == SPRITES_PER_ROW:
                    page.append("<tr>" + "".join(row) + "</tr>")
                    row = []
            if row:
                page.append("<tr>" + "".join(row) + "</tr>")
            page += ["</table>", ""]
        with open(os.path.join(TARGET, "sprites/gen_%d.md" % g), "w",
                  encoding="utf-8") as f:
            f.write("\n".join(page).rstrip() + "\n")

    print("wrote ROSTERS.md, ROSTERS_SPRITES.md and %d sprites/gen_*.md: "
          "%d characters, %d final-evolution entries"
          % (len(gens), len(chars), sum(len(c["finals"]) for c in chars)))


if __name__ == "__main__":
    main()
