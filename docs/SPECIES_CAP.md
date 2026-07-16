# Species Cap — findings (Phase 1, 2026-07-12)

## Summary

Seaglass does **not** have a clean generational cutoff like Unbound (which stopped cleanly at Gen 8). Instead it has **all of Gen 1-3 (National Dex order, contiguous) plus a small, curated set of later-gen additions** — mostly cross-gen evolutions of Gen 1-3 species (Steelix, Crobat, Blissey, Kingdra, Weavile, Sylveon, etc.), plus a handful of wholly new post-Gen3 species that have no Gen 1-3 lineage at all (Wyrdeer, Kleavor, Ursaluna, Dipplin, Hydrapple, Farigiraf, Dudunsparce, Annihilape, Tinkatink/Tinkatuff/Tinkaton, Dondozo, Gimmighoul, Ogerpon, Terapagos — but conspicuously **not** Gholdengo, despite its pre-evolution Gimmighoul being present).

This is a materially different, harder situation than assumed when `characters.txt` was built from ROWE's full Gen 1-9 list: **most Gen 4-9 signature/roster Pokemon that aren't evolutions of a Gen 1-3 base species simply don't exist in this ROM.**

## Method

1. Located the actual species data table: `gSpeciesInfo`-style struct array, **base offset `0x008F07AC`, stride 208 bytes**, name field at the start of each 208-byte record. Verified by walking the first 10 entries and confirming exact National Dex order (Bulbasaur, Ivysaur, Venusaur, Charmander... Caterpie), then spot-checked known Gen 3 species (Milotic, Salamence, Metagross, Absol, Sceptile, Blaziken, Gardevoir, etc. — all present at their exact National Dex index) and known Gen 1→Gen 2+ cross-gen evolutions (Crobat #169, Steelix #208, Kingdra #230, Blissey #242 — all present at their real dex numbers) to confirm the table walk is sound, not a methodology artifact.
2. Walked indices 0-1488 (`table_end_index` in `tools/character_mode/rom_species_table.json`), decoding each 208-byte record's name field via the Gen3 charmap. Beyond index ~1488 the data stops decoding as plausible species names (Japanese kana fragments, clearly unrelated ROM content) — this is the real end of the array. Within 0-1488 there are large blocks of blank/reserved slots (e.g. index ~494-898 is almost entirely unused/reserved, then real content resumes at index 899 with PLA-derived evolutions Wyrdeer/Kleavor/Ursaluna).
3. Result: **502 real (non-blank) species slots** across the 0-1488 range, saved to `tools/character_mode/rom_species_table.json` (index → name, `rom_sha1`-pinned).
4. Cross-referenced this master list (by name) against every base-stage species required by `tools/character_mode/rosters_mapped.json` (505 distinct species across all 182 characters' rosters).

## Result

- **197 / 505 (39%) of required base-stage species are present.** 308 are absent.
- Per-character impact (computed by checking how many of each character's mapped roster species are actually catchable):
  - **5 characters have ZERO catchable species** (fully broken as currently scoped): Bianca (rival), Geeta (champion), Ghetsis (villain), Piers (gymleader), Trip (anime).
  - **7 more have exactly 1 catchable species** (Alder, Drasna, Hilda, Melony, Olympia, Rosa, Wulfric) — essentially unplayable as a distinct character.
  - Only **8 of 182 characters have their full roster intact.**
  - Average roster completeness across all 182 characters: **50.8%.**

## Why this happened

`characters.txt` and `map_species.py`'s `SIGNATURES` dict were built from ROWE's full Gen 1-9 roster (per the approved plan, justified at the time by Seaglass's marketing claiming "cross-generation evolutions up to Generation 9"). That marketing claim is accurate but narrower in practice than it reads: it describes evolution-chain extensions bolted onto a Gen 1-3 catchable base, not a broad multi-generation dex. Characters whose Bulbapedia-documented roster or signature leans heavily on Gen 4-9-native base species (not evolutions of Gen 1-3 Pokemon) lose most or all of their roster once reduced against what's actually in this ROM.

## Resolution (2026-07-12, user decision)

User chose: **trim the fully/nearly-broken characters, keep everyone else as-is even if thinner than originally scraped.** Removed from `characters.txt` (12 total — the 5 zero-species + 7 one-species characters found above): Bianca, Alder, Hilda, Rosa, Ghetsis, Trip, Drasna, Olympia, Wulfric, Melony, Piers, Geeta.

Re-ran the full Stage A pipeline (`scrape_rosters.py` → `map_species.py` → `emit_characters.py --dry-run`) against the trimmed 170-character list and re-checked every remaining character's roster against `rom_species_table.json`:

- **170/170 characters mapped, 0 unmatched names, 0 empty rosters** (Stage A, name/topology level).
- **0 characters with zero or one catchable species** (down from 5 + 7).
- **8/170 characters still have a fully intact roster.**
- **Average roster completeness across all 170 characters: 53.9%** (up from 50.8% pre-trim, as expected since only the worst offenders were removed — most remaining characters still have a meaningfully reduced roster vs. what was originally scraped from Bulbapedia, just not degenerate).

This is the accepted baseline going into Stage B. No further characters.txt changes are planned unless new evidence emerges (e.g. a secondary catchable-species data structure Phase 1 hasn't found yet).

## Stage B — DONE (2026-07-12, later session)

`tools/character_mode/map_species_stage_b.py` (new script this session) resolves
real numeric ROM species ids by matching each species' canonical (donor-derived,
Bulbapedia-spelling) display name directly against `rom_species_table.json`'s own
dumped in-ROM name table — not by trusting any donor/ROM positional alignment.
Handles two real wrinkles: Gen3-charmap punctuation that doesn't round-trip to
plain ASCII in the dump (`-` → `ー`, `.` → `。`, mid-name space → U+3000), and
13 species with multiple ROM-table matches (regional/alt forms sharing a base
name — Rattata, Meowth, Pikachu, Diglett, etc.) where the lowest index (the
base/Kanto form, matching the established index-is-National-Dex-number pattern)
is picked and logged to `stageb_ambiguous.txt` for review — every pick spot-
checked, all correct (base form each time, higher indices consistently the
regional/alt variants).

**Result: 204/505 distinct species consts resolved to real ids, 301 unmatched**
(species genuinely absent from this ROM's table — see `stageb_unmatched.txt`;
count closely matches this doc's earlier informal 197/505-resolved finding,
cross-validating both). Per-character re-check after resolution: **0 characters
dropped to 0 or 1 catchable species** (same as the post-trim baseline above —
the earlier trim already correctly anticipated this), so **no further
characters.txt changes were needed**. Unresolved roster entries (1,577 across
all characters) were dropped from `rosters_mapped.json` (mechanical cleanup of
the already-accepted trim, not a new subjective call — a roster can't reference
a nonexistent species id).

`emit_characters.py --final` then built successfully: **170 characters, 0
skipped, 0 empty rosters** — `characters.bin` (2,040 B), `rosters.bin` (4,492
B), `names.bin` (1,110 B), well within the 1.18 MiB free-space budget.
`sprite_asset_id` is still the `0xFFFF` placeholder pending Phase 3. **Phase 2
(roster data pipeline) is now fully done.**
