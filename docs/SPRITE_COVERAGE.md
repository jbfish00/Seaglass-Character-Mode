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
