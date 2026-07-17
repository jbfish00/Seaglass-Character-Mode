# Injection — Phase 4/5 (catch enforcement, real rosters, live-tested)

**Status (2026-07-17): catch enforcement is INJECTED with the REAL 170-character
roster bitmap, LIVE-TESTED with per-character discrimination, and packaged as a
BPS.** The core Character-Mode mechanic works in a real patched ROM for every
character. Remaining for a full game: the in-game selection UI (currently the CM
flag/var are set via RAM), script-gift/trade gating, sprites.

## What ships

`sh tools/build_cm.sh` → `build/seaglass_cm.gba` (patched, gitignored) +
`build/seaglass_cm.bps` (distributable patch; **created against
`rom/seaglass v3.0.gba`**, i.e. the hack ROM — end users apply it to their own
Seaglass ROM, never to clean Emerald). Round-trip verified byte-identical
(`flips --apply` reproduces the build).

## The shim (`src/character_mode.c`)

`CM_GiveMonToPlayerGated(mon)` — ROWE/RR acquisition semantics: when Character
Mode is ON (`FLAG 0x945` set + `VAR 0x40E4` in 1..170) and the caught mon is a
non-egg species not on the active character's roster, route it to the PC
(`CopyMonToPC`) instead of the party (`GiveMonToPlayer`); otherwise identical to
the original. `onRoster()` is an O(1) bit test into the per-character bitmap.

## The roster bitmap (`tools/character_mode/emit_bitmaps.py` → `rosters_expanded.bin`)

The pipeline stores each character's roster as evolution-family **base stages**;
enforcement must allow the whole family. `emit_bitmaps.py` expands each base
forward through the donor's evolution graph, maps every member's display name
back to this ROM's species id, and sets its bit → 170 × 187-byte bitmaps
(index-aligned with `characters.bin`, bit S = species id S catchable). 0 family
names unresolved; avg 29.8 species/char. Verified: Red allows the full
Bulbasaur+Charmander families; Brendan allows Zigzagoon, Red does not.

Confirmed addresses used (all live-verified, `docs/ROUTINE_MAP.md`):
GiveMonToPlayer `0x081AA5AC`, CopyMonToPC `0x081AA620`, GetMonData `0x081A94AC`,
FlagGet `0x0810D35C`, GetVarPointer `0x0810D0C0`, gPlayerPartyCount `0x02019C1D`.
MON_DATA SPECIES=18, IS_EGG=52. Position-independent blob (intra-object calls
PC-relative, engine calls via absolute-pointer literals) — placeable anywhere.

## The injection (`tools/patches/inject_cm.asm`)

1. Shim blob (`build/cm.bin`, linked at `0x08ED2164`, entry `0x08ED21A6`)
   `.incbin` into the big free block.
2. **Trampoline** at `0x08470200` (8 bytes into a 64-byte 0xFF-padding scavenge
   spot; the free block is >4 MB from the caller, out of Thumb BL range):
   `ldr r3,[pc,#0]; bx r3; .word 0x08ED21A7` (entry|1). `bx` preserves `lr`, so
   the shim returns straight to the caller.
3. **Hooks**: retarget the two acquisition BLs to the trampoline (both in BL
   range of it): wild-catch `0x080A6A46` (3.9 MB) and script-gift `0x081F18DE`
   (2.6 MB). The egg-hatch caller `0x08188514` is left original (eggs exempt).
   Total shipped-region edit: 8 bytes (two BLs). Everything else is additive
   free space.

## Live test (`tools/mgba_scripts/cm_catch_test.lua`)

Same wild Zigzagoon (Nat-Dex 263), same catch, varying only the CM state:

| Run | Setup | partyCount | Meaning |
|---|---|---|---|
| control | CM off | 1 → **2** | Zigzagoon caught to party (normal) |
| enforce, char 1 (Red) | Zigzagoon **off** Red's roster | 1 → **1** | **blocked → PC** |
| enforce, char 39 (Brendan) | Zigzagoon **on** Brendan's roster | 1 → **2** | **allowed → party** |

Per-character discrimination on an identical catch — the real bitmap works. The
control proves the catch succeeds; Red proves the gate redirects off-roster;
Brendan proves on-roster is untouched. `battle_menu2.ss` (original-ROM state)
loads fine on the patched ROM.

## To reach a full playable game

1. **Roster bitmap** — DONE (`emit_bitmaps.py`, wired into the shim, tested).
2. **Selection mechanism**: hook the cheat-code matcher's specials-table slot
   (`gSpecialsTable 0x0826DD68`) so character-name codes set `FLAG 0x945` +
   `VAR 0x40E4` and deliver the signature starter — see `docs/ROUTINE_MAP.md`
   "Selection mechanism" + `../Lazarus-Character-Mode/docs/SELECTION_MECHANISM.md`.
3. **Remaining acquisition gates** — DONE (script-gift `0x081F18DE` gated;
   egg-hatch `0x08188514` intentionally exempt — eggs).
4. Trades, sprites (Phase 3), regression suite, README — RR/Lazarus parity.
