#!/usr/bin/env python3
"""Generate ENCOUNTERS.md -- what each character can actually meet in the wild.

rowe_parity.md §9 listed this as a gap the parity table never carried: ROWE and
Radical Red generate this document, Unbound writes its own, and Lazarus and
Seaglass had nothing -- so two of four ports did not document what a character
can meet in the wild.  That is the document the playability work makes most
useful: in this game the median offered character matches only ~4.3% of the
game's own wild slots, so the 10% roster override does most of the work of
building a team.

Same principle as emit_roster_docs.py: derived from the data the ROM itself
reads, never hand-written, so it cannot drift from the patch.  Sources are the
EMITTED artifacts -- `wildpool_manifest.json` (published by emit_wildpool.py
alongside the `wildpool.bin` the shim reads) and `legendaries.bin` -- and
deliberately NOT `rosters_mapped.json`, which sits upstream of the per-game dex
filter and would promise species this ROM cannot spawn.

⚠️ This game's pool records carry a species and a MINIMUM level only; there is
no per-stage upper band and no family grouping in the data, unlike the sibling
ports.  The document says what the data supports and no more -- inventing an
upper bound here would be a claim about the ROM that nothing checks.

The 1% legendary roll is read from `legendaries.bin`'s per-character u32 mask,
the same bytes the shim tests.

⚠️ Unlike its siblings, this game does NOT retire a caught legendary via the
Pokédex -- its dex accessor is unlocated after six failed probe strategies -- so
it uses 20 dedicated flags instead.  A character whose roster is ENTIRELY
legendary is excluded from the roll rather than added to it, which keeps its
legendary repeatable through the ordinary pool instead of retiring it.

Hidden characters are excluded, for the same reason ROSTERS.md excludes them:
the CODE screen refuses them, so their pools are not something a player reaches.

Run after emit_wildpool.py and emit_legendaries.py:
    python3 tools/character_mode/emit_encounter_docs.py
"""
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "ENCOUNTERS.md")

GAME_TITLE = "Pokémon Emerald Seaglass v3.0"
LEGENDARY_CHANCE_PCT = 1     # keep in sync with the injected shim
OVERRIDE_CHANCE_PCT = 10

CATEGORY_LABEL = {"protagonist": "Protagonist", "rival": "Rival",
                  "gymleader": "Gym Leader", "elite4": "Elite Four",
                  "champion": "Champion", "villain": "Villain",
                  "anime": "Anime", "professor": "Professor",
                  "warden": "Warden", "other": "Other"}


def load_json(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    manifest = load_json("characters_manifest.json")["characters"]
    pools = {c["character"]: c["pool"]
             for c in load_json("wildpool_manifest.json")["characters"]}
    legman = load_json("legendaries_manifest.json")
    with open(os.path.join(HERE, "legendaries.bin"), "rb") as f:
        legblob = f.read()

    names = {int(k): v
             for k, v in load_json("rom_species_table.json")["species"].items()}
    mask_off, n_leg_species = legman["char_mask_offset"], legman["count"]
    leg_species = legman["species"]
    want = mask_off + 4 * len(manifest)
    if len(legblob) != want:
        raise SystemExit("legendaries.bin is %d bytes, expected %d for %d "
                         "characters -- re-run emit_legendaries.py"
                         % (len(legblob), want, len(manifest)))

    rows = []
    for i, rec in enumerate(manifest):
        if rec.get("hidden"):
            continue
        mask = struct.unpack_from("<I", legblob, mask_off + 4 * i)[0]
        legs = [leg_species[b] for b in range(n_leg_species) if mask >> b & 1]
        pool = pools.get(rec["character"], [])
        rows.append({
            "name": rec["character"],
            "gen": rec.get("generation", 1) or 1,
            "cat": CATEGORY_LABEL.get(rec.get("category"), "Other"),
            "pool": sorted(pool, key=lambda e: (e["min_level"], e["species"])),
            "legs": [names.get(s, "species %d" % s) for s in legs],
            # A roster that is ENTIRELY legendary is excluded from the 1% roll,
            # so its legendary stays repeatable through the ordinary pool.
            "repeatable": bool(legs) and not pool,
        })

    n_with_leg = sum(1 for r in rows if r["legs"])
    n_repeat = sum(1 for r in rows if r["repeatable"])
    n_none = sum(1 for r in rows if not r["legs"] and not r["pool"])
    gens = sorted({r["gen"] for r in rows})

    out = []
    w = out.append
    w("# Character Mode — Wild Encounters (%s)\n" % GAME_TITLE)
    w("What each character can meet **in the wild**, on top of the game's own "
      "encounter tables. Two independent rolls replace the species the area "
      "would normally produce; the level is always the area's own rolled "
      "level.\n")
    w("```\nroll %d%%   -> a legendary from this character's roster\n"
      "else roll %d%% -> a non-legendary roster member\n"
      "else          -> the game's own wild table\n```\n"
      % (LEGENDARY_CHANCE_PCT, OVERRIDE_CHANCE_PCT))
    w("The two rolls are **independent**. They are derived from one seed, so "
      "the shim decorrelates them deliberately; without that step the "
      "legendary hit would be a strict subset of the roster override rather "
      "than an independent event, at an unchanged 1% headline rate.\n")
    w("**Legendaries retire once caught** — recorded with 20 dedicated flags "
      "rather than the Pokédex, which is unlocated in this ROM. A character "
      "whose roster is *entirely* legendary is excluded from the 1% roll "
      "instead, leaving its legendary **repeatable** through the ordinary "
      "pool; those are marked below.\n")
    w("Each pool entry carries a **minimum level** only — this game's pool "
      "records have no upper band and no family grouping, so none is claimed "
      "here.\n")
    w("GENERATED by `tools/character_mode/emit_encounter_docs.py` from "
      "`wildpool_manifest.json` and `legendaries.bin`, the same data the "
      "injected shim reads — do not hand-edit, regenerate.\n")
    w("### Coverage\n")
    w("- **%d characters** (the ones the CODE screen accepts; hidden "
      "characters are not listed, same as `ROSTERS.md`)." % len(rows))
    w("- **%d have a legendary pool** (%d%%); **%d** of those are repeatable."
      % (n_with_leg, round(100 * n_with_leg / max(len(rows), 1)), n_repeat))
    w("- **%d characters can meet nothing at all** — both pools empty.\n"
      % n_none)
    w("## Contents")
    for g in gens:
        w("- [Generation %d](#generation-%d)" % (g, g))
    w("")

    for g in gens:
        w("\n## Generation %d\n" % g)
        for r in sorted((x for x in rows if x["gen"] == g),
                        key=lambda x: x["name"]):
            w("### %s — %s" % (r["name"], r["cat"]))
            legpct = LEGENDARY_CHANCE_PCT if (r["legs"] and not r["repeatable"]) else 0
            rospct = OVERRIDE_CHANCE_PCT if r["pool"] else 0
            w("**Effective rates:** %d%% legendary · %d%% roster · %d%% the "
              "game's own tables\n" % (legpct, rospct, 100 - legpct - rospct))
            if r["legs"]:
                w("**Legendary pool (%d):** %s%s\n"
                  % (len(r["legs"]), ", ".join(r["legs"]),
                     " — **repeatable** (roster is entirely legendary)"
                     if r["repeatable"] else ""))
            else:
                w("**Legendary pool:** none — no legendary on this "
                  "character's roster.\n")
            if r["pool"]:
                w("**Roster pool (%d entries):**\n" % len(r["pool"]))
                w("| Pokémon | Appears from |")
                w("|---|---|")
                for e in r["pool"]:
                    w("| %s | L%d |" % (e["species"], e["min_level"]))
                w("")
            else:
                w("**Roster pool:** none — nothing on this character's roster "
                  "can spawn in this game.\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("wrote %s: %d characters, %d with a legendary pool (%d repeatable), "
          "%d with nothing"
          % (os.path.relpath(OUT, ROOT), len(rows), n_with_leg, n_repeat,
             n_none))


if __name__ == "__main__":
    main()
