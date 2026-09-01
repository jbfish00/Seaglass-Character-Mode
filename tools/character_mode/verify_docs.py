#!/usr/bin/env python3
"""Prove ROSTERS.md and README.md describe exactly what the BUILT ROM offers.

⭐ Why this file exists. rowe_parity.md §9 measured that Seaglass was the ONLY
port with no verify_docs.py -- "the only one whose ROSTERS.md is checked against
nothing" -- and it acquired that gap at the worst possible moment, having just
rewritten every roster (153 offered -> 114).

`emit_roster_docs.py` generates the docs from `rosters_expanded.bin`, so docs
and build agree BY CONSTRUCTION: a bug in the generator makes them agree with
each other and still disagree with the game. This closes that loop by reading
the enforcement data back out of `build/seaglass_cm.gba`, at the addresses the
injector actually wrote it to, and re-deriving every claim from those bytes.

Checks:
  0. the ROSTERS.md parse itself worked (see parse_doc)
  1. the allow-bitmaps in the built ROM == rosters_expanded.bin
  2. the offered/hidden split read out of the ROM's own code table == the
     manifest's hidden flag == character_drops.json, in BOTH directions
  3. every character in ROSTERS.md is offered by the ROM, and every character
     the ROM offers is in ROSTERS.md
  4. every Pokemon listed under a character is genuinely allowed by that
     character's in-ROM bitmap
  5. every final evolution the in-ROM bitmap allows is actually listed
  6. the sprite pages mirror ROSTERS.md character for character, row for row
  7. the character counts the docs advertise agree with what the ROM offers
  8. every code in README.md matches the code table in the ROM, byte for byte,
     and no hidden character's code is documented

⚠️ This game hides a character by POISONING its 11-byte code slot with bytes
containing no 0xFF terminator, not by a hidden bitmap -- the entered buffer is
pre-cleared to 0xFF and the screen caps at CODE_LEN-1 characters, so a slot is
matchable if and only if it contains a terminator. Check 2 reads that, so it is
testing the mechanism the ROM actually uses rather than a flag beside it.

Addresses are parsed out of tools/inject_character_mode.py rather than copied:
a rebase there (CM_MUGSHOT_ADDR moved once already, and six checks then failed
as "stray bytes" rather than as a stale constant) cannot leave this file reading
the wrong bytes.

Exit 1 on any mismatch. Run after emit_roster_docs.py, on a built ROM.
"""
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import emit_roster_docs as erd             # noqa: E402
from map_species_stage_b import normalize   # noqa: E402

BUILT = os.path.join(ROOT, "build", "seaglass_cm.gba")
INJECTOR = os.path.join(ROOT, "tools", "inject_character_mode.py")
CHARMAP = "/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt"
BITMAP_STRIDE = 187
CODE_LEN = 11


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def injector_addr(name):
    m = re.search(r"^%s\s*=\s*(0x[0-9A-Fa-f]+)" % name, read(INJECTOR), re.M)
    if not m:
        raise SystemExit("could not parse %s out of inject_character_mode.py"
                         % name)
    return int(m.group(1), 16)


def code_for(display):
    """Mirrors tools/inject_character_mode.py's code_for exactly."""
    n = unicodedata.normalize("NFKD", display)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return "".join(ch for ch in n if ch.isalnum())[:10]


def parse_doc(text):
    """{character: [listed Pokemon names]} from a ROSTERS.md-shaped file.

    ROSTERS.md lists one Pokemon per table row -- `| Name | Source |`. Reading
    it as anything else makes every roster parse as EMPTY, which then reports
    as the docs omitting everything rather than as a parse failure; that is
    exactly how the sibling repo's copy of this file sat red for weeks. Check 0
    below turns that failure mode back into what it is.
    """
    out, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^### (.+?) — ", line)
        if m:
            cur = m.group(1).strip()
            out[cur] = []
            continue
        m = re.match(r"^\| (.+?) \| (.*?) \|$", line)
        if m and cur is not None and m.group(1) not in ("Pokémon", "---"):
            out[cur].append(m.group(1).strip())
    return out


def main():
    fails = []

    if not os.path.isfile(BUILT):
        print("no built ROM at %s -- run tools/inject_character_mode.py first"
              % os.path.relpath(BUILT, ROOT))
        return 1
    with open(BUILT, "rb") as f:
        rom = f.read()

    with open(os.path.join(HERE, "characters_manifest.json")) as f:
        manifest = json.load(f)["characters"]
    with open(os.path.join(HERE, "rosters_expanded.bin"), "rb") as f:
        bitmaps = f.read()
    with open(os.path.join(HERE, "rom_species_table.json")) as f:
        rom_names = {int(k): v for k, v in json.load(f)["species"].items()}

    n = len(manifest)
    bitmaps_addr = injector_addr("BITMAPS_ADDR")
    codes_addr = injector_addr("CODES_ADDR")

    # --- 1. the bitmaps the ROM carries are the ones we emitted -------------
    boff = bitmaps_addr & 0x01FFFFFF
    in_rom = rom[boff:boff + n * BITMAP_STRIDE]
    if in_rom != bitmaps:
        fails.append("allow-bitmaps in the built ROM differ from "
                     "rosters_expanded.bin -- the ROM is not this data")

    # --- 2. offered/hidden, read out of the ROM's own code table -----------
    cm = {}
    for line in read(CHARMAP).splitlines():
        m = re.match(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$", line)
        if m and m.group(1) not in cm:
            cm[m.group(1)] = int(m.group(2), 16)
    decode = {v: k for k, v in cm.items()}

    coff = codes_addr & 0x01FFFFFF
    codes_rom = rom[coff:coff + n * CODE_LEN]
    rom_hidden, rom_codes = set(), {}
    for i, rec in enumerate(manifest):
        slot = codes_rom[i * CODE_LEN:(i + 1) * CODE_LEN]
        # Matchable iff it carries a terminator; see the module docstring.
        if 0xFF not in slot:
            rom_hidden.add(rec["character"])
            continue
        rom_codes[rec["character"]] = "".join(
            decode.get(b, "?") for b in slot[:slot.index(0xFF)] if b != 0xFF)

    in_table = {r["character"] for r in manifest}
    man_hidden = {r["character"] for r in manifest if r.get("hidden")}
    # ⚠️ character_drops.json is computed over the ROSTER data, which is wider
    # than the character TABLE: Magnolia, Sada and Turo were trimmed out of
    # characters.txt as dex-absent, so they have no slot, no code and no bitmap.
    # Intersecting is not papering over a mismatch -- a character that is not in
    # the table cannot be "hidden in the ROM" in either direction, and comparing
    # it would report three permanent failures that no build could ever clear.
    drops = set(json.loads(
        read(os.path.join(HERE, "character_drops.json")))["unselectable"])
    drops &= in_table
    for who, what in (("the manifest", man_hidden),
                      ("character_drops.json", drops)):
        for c in sorted(rom_hidden - what):
            fails.append("%s: unmatchable in the ROM but not hidden per %s"
                         % (c, who))
        for c in sorted(what - rom_hidden):
            fails.append("%s: hidden per %s but its code still matches in the "
                         "ROM -- the threshold did not bite" % (c, who))

    # --- per-character allow sets, straight from the ROM's bytes -----------
    donor = erd.donor_species()
    dexnum = erd.dex_numbers()
    canonical = {}
    for const in sorted(donor):
        d = donor[const]["dex"]
        if d:
            canonical.setdefault(d, const)

    def is_final(const):
        if donor[const]["children"]:
            return False
        base = canonical.get(donor[const]["dex"], const)
        return not donor[base]["children"]

    consts_by_name = defaultdict(list)
    for const, rec in donor.items():
        if rec["name"]:
            consts_by_name[normalize(rec["name"])].append(const)

    rom_allowed, rom_finals = {}, {}
    for i, rec in enumerate(manifest):
        bits = in_rom[i * BITMAP_STRIDE:(i + 1) * BITMAP_STRIDE]
        allowed = {rom_names[s] for s in rom_names
                   if s < BITMAP_STRIDE * 8 and bits[s >> 3] & (1 << (s & 7))}
        rom_allowed[rec["character"]] = allowed
        finals = set()
        for nm in allowed:
            for const in consts_by_name.get(normalize(nm), []):
                if is_final(const):
                    finals.add(donor[const]["name"])
        rom_finals[rec["character"]] = finals

    doc = parse_doc(read(os.path.join(ROOT, "ROSTERS.md")))

    # --- 0. the parse itself worked ---------------------------------------
    # An offered character always has at least six fully-evolved Pokemon --
    # that is the threshold rule deciding it is offered at all -- so a heading
    # with no rows under it cannot be a real roster, only a bad parse.
    empty = sorted(c for c, rows in doc.items() if not rows)
    if not doc or empty:
        print("verify_docs: PARSE FAILURE -- %d of %d headings in ROSTERS.md "
              "yielded no rows (%s). parse_doc no longer matches the file's "
              "shape; fix the parser before reading anything below."
              % (len(empty), len(doc), ", ".join(empty[:6]) or "no headings"))
        return 1

    # --- 3. offered <-> documented, both directions ------------------------
    for char in doc:
        if char not in rom_allowed:
            fails.append("%s: in ROSTERS.md but not in characters_manifest.json"
                         % char)
    for char in rom_allowed:
        if char in rom_hidden:
            if char in doc:
                fails.append("%s: hidden from selection but still listed in "
                             "ROSTERS.md -- re-run emit_roster_docs.py" % char)
            continue
        if char not in doc:
            fails.append("%s: offered by the ROM but missing from ROSTERS.md"
                         % char)

    # --- 4/5. every listed row allowed, every allowed final listed ---------
    for char, listed in doc.items():
        if char not in rom_allowed:
            continue
        allowed_norm = {normalize(x) for x in rom_allowed[char]}
        bare = {re.sub(r"[ᵃᵍ]", "", m) for m in listed}
        for mon in sorted(bare):
            if normalize(mon) not in allowed_norm:
                fails.append("%s: doc lists %s, which its in-ROM bitmap does "
                             "not allow" % (char, mon))
        missing = {normalize(x) for x in rom_finals[char]} - {
            normalize(x) for x in bare}
        if missing:
            fails.append("%s: in-ROM bitmap allows %d final evolution(s) the "
                         "doc omits (%s)"
                         % (char, len(missing), ", ".join(sorted(missing)[:6])))

    # --- 6. the sprite pages mirror ROSTERS.md ----------------------------
    sprite_chars = {}
    sprites_dir = os.path.join(ROOT, "sprites")
    for path in sorted(os.listdir(sprites_dir)):
        if not re.match(r"gen_\d+\.md$", path):
            continue
        cur = None
        for line in read(os.path.join(sprites_dir, path)).splitlines():
            m = re.match(r"^### (.+?) — ", line)
            if m:
                cur = m.group(1).strip()
                sprite_chars[cur] = 0
                continue
            if cur is not None:
                sprite_chars[cur] += len(re.findall(r"<sub>([^<]+)</sub>", line))
    for char, listed in doc.items():
        if char not in sprite_chars:
            fails.append("%s: in ROSTERS.md but missing from the sprite pages"
                         % char)
        elif sprite_chars[char] != len(listed):
            fails.append("%s: %d rows in ROSTERS.md but %d sprite cells"
                         % (char, len(listed), sprite_chars[char]))
    for char in sprite_chars:
        if char not in doc:
            fails.append("%s: on a sprite page but not in ROSTERS.md" % char)

    # --- 7. the counts the docs advertise ---------------------------------
    offered = n - len(rom_hidden)
    for fname, pat in (
            ("README.md", r"\*\*(\d+) selectable characters\*\*"),
            ("ROSTERS.md", r"\*\*(\d+) characters\.\*\*"),
            ("ROSTERS_SPRITES.md", r"\*\*(\d+) characters\.\*\*")):
        path = os.path.join(ROOT, fname)
        if not os.path.isfile(path):
            continue
        m = re.search(pat, read(path))
        if not m:
            fails.append("%s: no character count found" % fname)
        elif int(m.group(1)) != offered:
            fails.append("%s says %s characters; the ROM offers %d"
                         % (fname, m.group(1), offered))

    # --- 8. README codes == the ROM's own code table ----------------------
    readme_codes = set(re.findall(r"^\| `([^`]+)` \|",
                                  read(os.path.join(ROOT, "README.md")), re.M))
    for char, code in rom_codes.items():
        expected = code_for(char)
        if code != expected:
            fails.append("%s: code table in the ROM says %r, the naming rule "
                         "says %r" % (char, code, expected))
        if readme_codes and code not in readme_codes:
            fails.append("%s: offered, but its code `%s` is missing from "
                         "README.md" % (char, code))
    for char in sorted(rom_hidden):
        if code_for(char) in readme_codes:
            fails.append("%s: hidden, but its code `%s` is documented in "
                         "README.md" % (char, code_for(char)))

    if fails:
        print("verify_docs: %d FAILURE(S)" % len(fails))
        for f in fails:
            print("  FAIL " + f)
        return 1
    print("verify_docs: ALL PASS -- %d characters in the table, %d offered, "
          "%d hidden; %d doc rows re-derived from the built ROM"
          % (n, offered, len(rom_hidden), sum(len(v) for v in doc.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
