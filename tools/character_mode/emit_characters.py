#!/usr/bin/env python3
"""Generate a flat binary character table from rosters_mapped.json.

Adapted from Unbound-Character-Mode's emit_characters.py (itself adapted
from ROWE's C-header generator), for the same reason: Seaglass has no
compile step to hook into, so this emits raw, position-independent POD data
matching ROWE's `struct CharacterInfo` semantics as three flat blobs, to be
injected into ROM free space and pointer-patched by a later insert script
once Phase 1 confirms real hook/table addresses:

  characters.bin  - fixed-size records, one per character (layout below)
  rosters.bin     - each character's roster: u16 species ids, SPECIES_NONE-
                    terminated, concatenated back to back
  names.bin       - each character's display name, Gen3-charmap-encoded,
                    0xFF-terminated, concatenated back to back
  characters_manifest.json - human-readable record of every field, for the
                    later insert step and for debugging

Record layout (12 bytes, native ROM byte order = little-endian), OFFSETS
ARE RELATIVE TO THE START OF THEIR OWN BLOB, not final ROM addresses:
    u32 name_offset      -- offset into names.bin
    u32 roster_offset     -- offset into rosters.bin
    u16 sprite_asset_id   -- PLACEHOLDER 0xFFFF ("TBD") until Phase 3 finds
                             Seaglass's OW/trainer-pic tables
    u8  generation
    u8  flags             -- bit0: hasSignature: signature ace is roster[0]

TWO MODES, unlike Unbound's single-pass emitter, because map_species.py's
Stage A deliberately does NOT borrow untrustworthy donor numeric ids (see
docs/DONOR_CROSSWALK.md) -- every species_id in rosters_mapped.json is the
literal string "PENDING_PHASE1" until a Stage B pass (gated on Phase 1)
fills in real, ROM-verified ids:

  --dry-run (default): validates roster completeness/ordering (starter vs.
      legendary split, signature placement, 0-empty-roster check) against
      names/topology only. Writes names.bin (fully known already) and
      characters_manifest.json (with SPECIES_* consts, not numeric ids,
      recorded for review), but deliberately does NOT write characters.bin
      or rosters.bin -- those would be meaningless without real species ids,
      and a stray placeholder-filled build is a real risk of being injected
      by accident.
  --final: requires every species referenced by every character's roster to
      have a real integer id (i.e. rosters_mapped.json must have been
      through Stage B first, not just Stage A) -- errors out otherwise.
      Writes all three binaries.
"""
import argparse
import json
import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
CHARMAP_PATH = "/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt"

# Legendary/mythical/Ultra Beast/Paradox evolution-family bases: kept on
# rosters (catchable) but never offered as starters. Full Gen 1-9 list,
# reused verbatim from ROWE (NOT Unbound's Gen-9-trimmed copy) -- Seaglass's
# confirmed cross-gen scope includes Gen 9 legendaries (Ogerpon, Koraidon/
# Miraidon, Terapagos, Pecharunt, etc.), unlike Unbound which has no Gen 9
# content at all.
LEGENDARY_BASES = {"SPECIES_" + s for s in """ARTICUNO ZAPDOS MOLTRES MEWTWO MEW
RAIKOU ENTEI SUICUNE LUGIA HO_OH CELEBI
REGIROCK REGICE REGISTEEL LATIAS LATIOS KYOGRE GROUDON RAYQUAZA JIRACHI DEOXYS
UXIE MESPRIT AZELF DIALGA PALKIA HEATRAN REGIGIGAS GIRATINA CRESSELIA PHIONE MANAPHY DARKRAI SHAYMIN ARCEUS
VICTINI COBALION TERRAKION VIRIZION TORNADUS THUNDURUS RESHIRAM ZEKROM LANDORUS KYUREM KELDEO MELOETTA GENESECT
XERNEAS YVELTAL ZYGARDE DIANCIE HOOPA VOLCANION
TYPE_NULL TAPU_KOKO TAPU_LELE TAPU_BULU TAPU_FINI COSMOG NECROZMA MAGEARNA MARSHADOW ZERAORA MELTAN
NIHILEGO BUZZWOLE PHEROMOSA XURKITREE CELESTEELA KARTANA GUZZLORD POIPOLE STAKATAKA BLACEPHALON
ZACIAN ZAMAZENTA ETERNATUS KUBFU ZARUDE REGIELEKI REGIDRAGO GLASTRIER SPECTRIER CALYREX ENAMORUS
WO_CHIEN CHIEN_PAO TING_LU CHI_YU KORAIDON MIRAIDON OKIDOGI MUNKIDORI FEZANDIPITI OGERPON TERAPAGOS PECHARUNT""".split()}

# SPECIES_* aliases used by LEGENDARY_BASES/MACRO_FORM_CONST_OVERRIDES that
# don't match this donor's base-form spelling for a couple of multi-form
# legendaries (Arceus/Genesect/Type: Null already resolve fine via their
# plain alias; kept here only for clarity that no extra mapping is needed).
CATEGORIES = ["protagonist", "rival", "gymleader", "elite4", "champion", "villain", "anime"]


def load_charmap(path):
    table = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.rstrip("\n"))
            if m:
                table[m.group(1)] = int(m.group(2), 16)
    return table


def encode_text(text, charmap):
    out = bytearray()
    for ch in text:
        if ch not in charmap:
            raise ValueError(f"character {ch!r} not in charmap (name: {text!r})")
        out.append(charmap[ch])
    out.append(0xFF)  # Gen3 string terminator
    return bytes(out)


def display_name(disp):
    if disp.endswith(" (anime)"):
        return disp[: -len(" (anime)")]
    return disp


def load_order(mapped):
    """Table order, with ALREADY-SHIPPED SLOTS PINNED.

    ⚠️ A save stores the character INDEX, not its name, so the position of every
    character already in characters_manifest.json is load-bearing and this
    function must never renumber one. The threshold has always honoured that --
    a character below it keeps its slot and is merely hidden -- but the roster
    pipeline did not: a character whose roster became EMPTY was dropped from the
    table entirely, silently shifting everyone after it.

    That is not hypothetical. Applying the audit's removals overlay on
    2026-08-20 emptied Rowan, Juniper and Sonia (slots 173, 174 and 178), which
    renumbered the 17 characters after them -- a save on any of those 17 would
    have loaded as a different character.

    So: every character already in the manifest keeps its slot, in its recorded
    order, even if its roster is now empty (it will simply be hidden). New
    characters are appended after them. characters.txt only decides the order of
    genuinely new arrivals.
    """
    shipped = []
    mpath = os.path.join(HERE, "characters_manifest.json")
    if os.path.isfile(mpath):
        with open(mpath, encoding="utf-8") as f:
            shipped = [c["character"] for c in json.load(f)["characters"]]

    order = list(shipped)
    seen = set(order)
    with open(os.path.join(HERE, "characters.txt")) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            disp = line.split("|")[0].strip()
            if disp in mapped and disp not in seen:
                order.append(disp)
                seen.add(disp)
    return order


def _signature_base_map():
    """Donor evolution topology: const -> its family-base const. Used to keep
    signatures whose ace is an evolved form (e.g. Red's Pikachu) when the
    roster stores only family bases (e.g. Pichu). Ported from Lazarus's
    emit_characters.py (found there as a real roster bug: Red was falling
    back to roster[0] instead of his Pikachu)."""
    from map_species import load_donor, first_stage_map
    _, parent = load_donor()
    return first_stage_map(parent)


def build_rosters(mapped, order):
    """Compute starter/legendary split + signature placement per character.
    Returns (per-character dict, skipped-empty list, warnings list) -- pure
    function of consts, independent of whether numeric ids exist yet."""
    base_of = _signature_base_map()
    built = {}
    skipped = []          # kept for the report's shape; nothing lands here now
    empty = []            # slots retained with an empty roster
    warnings = []
    for disp in order:
        info = mapped.get(disp, {"species": []})
        species = info["species"]
        if not species:
            # An empty roster no longer drops the character. It keeps its slot
            # (see load_order) and derive_drops.py will have it under the
            # threshold anyway, so it is emitted as a hidden record with an
            # empty roster rather than renumbering everyone behind it.
            built[disp] = {
                "category": info.get("category"),
                "generation": info.get("gen", 0) or 1,
                "ordered_consts": [],
                "starter_count": 0,
                "has_signature": False,
                "signature_const": None,
            }
            empty.append(disp)
            continue

        consts = [s["const"] for s in species]
        starters = [c for c in consts if c not in LEGENDARY_BASES]
        legends = [c for c in consts if c in LEGENDARY_BASES]

        sig = info.get("signature")
        has_signature = 0
        sig_const = None
        if sig:
            sig_const = sig["const"]
            if sig_const in starters:
                starters.remove(sig_const)
            elif sig_const in legends:
                legends.remove(sig_const)
            else:
                # Ace is an evolved form; roster stores family bases. Accept
                # when the ace's family base is on the roster -- the ace id
                # becomes roster[0] (the signature/starter give), and the
                # bitmap expansion covers the whole family either way.
                sig_base = base_of.get(sig_const, sig_const)
                if sig_base not in starters and sig_base not in legends:
                    warnings.append("%s: signature %s (base %s) not on roster, dropped"
                                    % (disp, sig_const, sig_base))
                    sig_const = None
            if sig_const:
                starters.insert(0, sig_const)
                has_signature = 1

        ordered_consts = starters + legends
        if not starters:
            warnings.append("%s: all-legendary roster, no starter to offer" % disp)

        built[disp] = {
            "category": info.get("category"),
            "generation": info.get("gen", 0) or 1,
            "ordered_consts": ordered_consts,
            "starter_count": len(starters),
            "has_signature": bool(has_signature),
            "signature_const": sig_const,
        }
    if empty:
        warnings.append("%d character(s) have an EMPTY roster and keep their "
                        "slot as hidden records: %s"
                        % (len(empty), ", ".join(sorted(empty))))
    return built, skipped, warnings


def cmd_dry_run(mapped, order):
    charmap = load_charmap(CHARMAP_PATH)
    built, skipped, warnings = build_rosters(mapped, order)

    names_blob = bytearray()
    manifest = []
    for disp in order:
        if disp in skipped:
            continue
        b = built[disp]
        name_off = len(names_blob)
        names_blob += encode_text(display_name(disp), charmap)
        manifest.append({
            "character": disp,
            "category": b["category"],
            "generation": b["generation"],
            "name_offset": name_off,
            "roster_species_consts": b["ordered_consts"],
            "starter_count": b["starter_count"],
            "has_signature": b["has_signature"],
            "signature_const": b["signature_const"],
            "sprite_asset_id": "TBD",
        })

    with open(os.path.join(HERE, "names.bin"), "wb") as f:
        f.write(names_blob)
    with open(os.path.join(HERE, "characters_manifest.json"), "w") as f:
        json.dump({"mode": "dry_run_names_topology_only",
                   "record_count": len(order) - len(skipped),
                   "skipped_empty_roster": skipped,
                   "warnings": warnings,
                   "characters": manifest}, f, indent=1)

    print("[dry-run] validated %d characters (%d skipped empty)" % (len(order) - len(skipped), len(skipped)))
    print("  names.bin: %d bytes (real, final content)" % len(names_blob))
    print("  characters.bin / rosters.bin: NOT written -- species ids are all")
    print("  PENDING_PHASE1; run with --final once Stage B fills in real ids.")
    if warnings:
        print("\nwarnings:")
        for w in warnings:
            print("  " + w)


def cmd_final(mapped, order):
    charmap = load_charmap(CHARMAP_PATH)
    built, skipped, warnings = build_rosters(mapped, order)

    # id lookup: const -> real numeric id, sourced from rosters_mapped.json's
    # per-species "id" field. Fail loudly if anything is still PENDING_PHASE1.
    const_to_id = {}
    unresolved = set()
    for info in mapped.values():
        for s in info["species"]:
            if s["id"] == "PENDING_PHASE1":
                unresolved.add(s["const"])
            else:
                const_to_id[s["const"]] = s["id"]
        sig = info.get("signature")
        if sig:
            if sig["id"] == "PENDING_PHASE1":
                unresolved.add(sig["const"])
            else:
                const_to_id[sig["const"]] = sig["id"]
    if unresolved:
        raise SystemExit(
            "--final requires Stage B ids for all species; %d species still "
            "PENDING_PHASE1 (e.g. %s). Run Stage B first."
            % (len(unresolved), ", ".join(sorted(unresolved)[:5])))

    # Playability threshold (user rule, 2026-07-25): fewer than six fully-evolved
    # Pokemon obtainable in THIS game's dex -> not offered, unless a legendary on
    # the roster exempts them. Hidden characters KEEP their table slot and their
    # index, because saves store the character INDEX -- dropping a row would
    # repoint every existing save at somebody else. Enforcement here is by
    # POISONED CODE in the injector, not by menu logic: Seaglass selects by typed
    # code, so a lead byte the naming screen cannot produce is a complete gate and
    # costs no shim changes. An already-selected hidden character keeps working,
    # which is the point of keeping the slot.
    # GENERATED by derive_drops.py from THIS repo's own rosters_mapped.json --
    # never from the audit scratchpad's answer, which predates the additions
    # overlay and drifts in both directions.
    drops_path = os.path.join(HERE, "character_drops.json")
    if not os.path.isfile(drops_path):
        raise SystemExit(
            "emit_characters: character_drops.json missing -- run "
            "derive_drops.py first (it MUST precede the emitters)")
    with open(drops_path, encoding="utf-8") as f:
        hidden_names = set(json.load(f)["unselectable"])

    names_blob = bytearray()
    rosters_blob = bytearray()
    records = bytearray()
    manifest = []
    hidden_bits = bytearray((len(order) - len(skipped) + 7) // 8)

    for disp in order:
        if disp in skipped:
            continue
        b = built[disp]
        name_off = len(names_blob)
        names_blob += encode_text(display_name(disp), charmap)

        roster_off = len(rosters_blob)
        for const in b["ordered_consts"]:
            rosters_blob += struct.pack("<H", const_to_id[const])
        rosters_blob += struct.pack("<H", 0)  # SPECIES_NONE terminator

        idx = len(manifest)                      # 0-based emitted index; charId = idx + 1
        hidden = disp in hidden_names
        if hidden:
            hidden_bits[idx >> 3] |= 1 << (idx & 7)

        flags = (int(b["has_signature"]) & 0x1) | (0x2 if hidden else 0)
        sprite_asset_id = 0xFFFF  # TBD -- Seaglass OW/trainer-pic table not yet located (Phase 1/3)
        records += struct.pack("<IIHBB", name_off, roster_off, sprite_asset_id, b["generation"], flags)

        sig_id = const_to_id[b["signature_const"]] if b["signature_const"] else None
        manifest.append({
            "character": disp, "category": b["category"], "generation": b["generation"],
            "name_offset": name_off, "roster_offset": roster_off,
            "roster_species_ids": [const_to_id[c] for c in b["ordered_consts"]],
            "starter_count": b["starter_count"], "has_signature": b["has_signature"],
            "signature_id": sig_id, "sprite_asset_id": "TBD", "hidden": hidden,
        })

    # A name in character_drops.json that matches NOTHING hides nobody, silently,
    # and ships a character the threshold was supposed to gate. Checked against
    # the SAME file derive_drops.py judged from (rosters_mapped.json, 196 entries)
    # rather than against the emitted set: Magnolia, Sada and Turo are real
    # characters that are dex-absent and were deliberately trimmed upstream of
    # characters.txt, so they are legitimately named here and never emitted. A
    # typo or a renamed character matches neither and is what this catches.
    emitted = {r["character"] for r in manifest}
    with open(os.path.join(HERE, "rosters_mapped.json")) as f:
        judged = set(json.load(f))
    unmatched = sorted(hidden_names - judged)
    if unmatched:
        raise SystemExit(
            "emit_characters: %d name(s) in character_drops.json match no character "
            "in rosters_mapped.json -- they would hide NOBODY: %s"
            % (len(unmatched), ", ".join(unmatched)))
    trimmed_upstream = sorted(hidden_names - emitted)
    if trimmed_upstream:
        print("  (%d hidden name(s) trimmed upstream, never emitted: %s)"
              % (len(trimmed_upstream), ", ".join(trimmed_upstream)))
    n_hidden = sum(1 for r in manifest if r["hidden"])

    with open(os.path.join(HERE, "hidden.bin"), "wb") as f:
        f.write(hidden_bits)
    with open(os.path.join(HERE, "characters.bin"), "wb") as f:
        f.write(records)
    with open(os.path.join(HERE, "rosters.bin"), "wb") as f:
        f.write(rosters_blob)
    with open(os.path.join(HERE, "names.bin"), "wb") as f:
        f.write(names_blob)
    with open(os.path.join(HERE, "characters_manifest.json"), "w") as f:
        json.dump({"mode": "final", "record_count": len(order) - len(skipped),
                   "record_size_bytes": 12, "skipped_empty_roster": skipped,
                   "hidden_count": n_hidden,
                   "selectable_count": len(manifest) - n_hidden,
                   "warnings": warnings, "characters": manifest}, f, indent=1)

    print("[final] emitted %d characters (%d skipped empty)" % (len(order) - len(skipped), len(skipped)))
    print("  threshold: %d offered, %d hidden (kept their table slot)"
          % (len(manifest) - n_hidden, n_hidden))
    print("  characters.bin: %d bytes (%d records x 12)" % (len(records), len(records) // 12))
    print("  rosters.bin:    %d bytes" % len(rosters_blob))
    print("  names.bin:      %d bytes" % len(names_blob))
    print("\nsprite_asset_id is a PLACEHOLDER (0xFFFF) for every record -- Phase 3 fills")
    print("this in once Seaglass's OW/trainer-pic tables are located (Phase 1).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true",
                     help="emit real binaries (requires Stage B ids); default is --dry-run")
    args = ap.parse_args()

    with open(os.path.join(HERE, "rosters_mapped.json")) as f:
        mapped = json.load(f)
    order = load_order(mapped)

    if args.final:
        cmd_final(mapped, order)
    else:
        cmd_dry_run(mapped, order)


if __name__ == "__main__":
    main()
