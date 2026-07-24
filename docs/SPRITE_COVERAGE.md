# SPRITE_COVERAGE — Seaglass Character Mode (Phase 3 survey)

Survey run 2026-07-17 via `tools/character_mode/sprite_coverage_survey.py`:
cross-references the **final 170-character manifest**
(`tools/character_mode/characters_manifest.json`) against ROWE's already-built
sprite report (`/home/jbfish00/Documents/Pokemon Rowe Alteration/tools/character_mode/sprite_report.txt`)
— same methodology as the Lazarus / RadicalRed / Unbound surveys, since the
Gen 1–8 slice of this roster is the same real-world characters ROWE already
sourced donor art for. All 170 characters appear in ROWE's 182-entry report.

## Coverage summary

| | count | % of 170 |
|---|---|---|
| Have an overworld sprite candidate | 96 | 56% |
| Have a trainer front-pic candidate | 70 | 41% |
| Have a battle back-pic candidate | 12 | 7% |
| Have AT LEAST ONE asset | 96 | 56% |
| Have NO assets in ROWE's tree | 74 | 43% |

Full ow+front+back coverage (12): Red, Leaf, Ethan, Kris, Brendan, May,
Steven, Wally, Lucas, Dawn, Barry, Hilbert.

## Zero-coverage pattern (matches the Lazarus/RR/Unbound precedent exactly)

The 74 zero-coverage characters, by generation:

- **Gen 1–4 anime-only (9)**: Ritchie, Tracey, Jessie, James, Lyra, Drew,
  Paul, Zoey, Nando — ROWE's own notes already flagged these as never sourced.
- **Gen 6 (16)**: Calem, Serena, Diantha, Malva, Siebold, Wikstrom, Viola,
  Grant, Korrina, Ramos, Clemont, Valerie, Shauna, Lysandre, Alain, Sawyer.
- **Gen 7 (20)**: Elio, Selene, Kukui, Hau, Molayne, Kahili, Acerola, Hala,
  Olivia, Nanu, Hapu, Gladion, Guzma, Plumeria, Lusamine, Lillie (anime),
  Kiawe (anime), Lana (anime), Mallow (anime), Sophocles.
- **Gen 8 (15)**: Leon, Milo, Nessa, Kabu, Bea, Allister, Opal, Gordie,
  Raihan, Hop, Bede, Marnie, Rose, Goh, Chloe.
- **Gen 9 (14)**: Nemona, Rika, Poppy, Hassel, Katy, Brassius, Iono, Kofu,
  Larry, Ryme, Tulip, Grusha, Arven, Penny.

Same underlying reason established across every sibling port: GBA-style pixel
art genuinely doesn't exist (official or fan-made) for 3D-model-era characters.

## Decision: v1 SHIPS WITHOUT SPRITES — Phase 3 closed as survey-done

Per the standing "sprites never block" policy and matching the shipped Lazarus
and Radical Red precedents (both shipped with `sprite_asset_id = 0xFFFF`
everywhere and list sprite installation as cosmetic-only future work):

- Character Mode on Seaglass is **text-first by design**: selection is a typed
  character code at the cheat clipboard, and no shipped UI surface renders a
  character sprite. Sprites are purely cosmetic polish.
- `characters.bin`'s `sprite_asset_id` stays `0xFFFF` in every record; the
  field exists so a future sprite pass needs no schema change.
- 56% coverage with a hard 43% floor of impossible characters means sprites
  could only ever be partial — a deliberate post-ship cosmetic pass, never a
  ship gate.

## If sprites are ever installed (future work, not queued)

Seaglass's OW/trainer-pic ROM tables were **never located** (nothing in Phase 1
needed them; the enforcement + selection paths use none). A future pass would
hunt `gTrainerFrontPicTable` / `gTrainerBackPicTable` / palette tables and the
overworld `gObjectEventGraphicsInfoPointers` equivalent (verify byte-exact,
beware decoy copies via `find_pointer_refs.py`), LZ77-compress donor tiles from
ROWE's tree into the big free block, and repoint table entries. Same
`CREDITS.md` donor discipline as ROWE/Lazarus/RR.

## 2026-07-23 — Ash Gray donor sourcing (anime-only gap partially closed)

Pokemon Ash Gray v4.5.3 (metapod23) was built locally — BPS patch (RAPatches
mirror) onto a byte-matching pret/pokefirered build — and its sprites ripped
(`RadicalRed-Character-Mode/tools/rip_frlg_sprites.py`). **19 anime-character
trainer front pics** now staged as verbatim LZ77 blobs in
`sprites/donors/ashgray/` (64x64 4bpp + 32 B palette — the same format this
engine family consumes; see that directory's README for provenance).

Coverage delta for the "never sourced" anime-only list: **Ritchie ✓,
Tracey ✓, Jessie ✓ + James ✓ (as a duo pic)** — plus new-to-us Duplica, Todd,
Giselle, A.J., Otoshi, Samurai, Damian, Gary, Cissy, Danny, Rudy, Jessiebelle,
and anime-style Brock/Misty/Oak/Giovanni alternates. Ash overworld
(walk/bike/fishing) + back-pic sheet also ripped.

**Still missing** (web-archive survey 2026-07-23 found no GBA-style front
pics): Drew, Paul, Zoey, Nando, Trip, Lyra; Gen 6-9 policy unchanged
(portrait-only). Candidate OW-only source if ever needed: spherical-ice's
"Accurate FireRed Overworld Sprite Resource" (DeviantArt) — has some anime OW
sprites; The Spriters Resource search is JS-only (not scriptable).

**Pilot injection result (RadicalRed, 2026-07-23)**: all 19 donors injected
at 0x08CF0000 (15,364 B) by `tools/inject_sprites_pilot.py` (RR repo);
decode-back from the built ROM byte-exact; `gTrainerFrontPicTable`
consumption confirmed (12 literal-pool code refs incl. battle engine); the
all-slots test build boots to free-roam. The blob-copy + table-repoint
technique transfers to this project once its own table addresses are located.
