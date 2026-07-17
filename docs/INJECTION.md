# Injection — Phase 4/5 (catch-enforcement PoC, live-tested)

**Status (2026-07-17): catch enforcement is INJECTED, LIVE-TESTED, and packaged
as a BPS.** This is the core Character-Mode mechanic working in a real patched
ROM. The roster check is a hardcoded PoC (Torchic line) pending the pipeline
bitmap step; the hook, gate, trampoline, build, and patch chain are production.

## What ships

`sh tools/build_cm.sh` → `build/seaglass_cm.gba` (patched, gitignored) +
`build/seaglass_cm.bps` (distributable patch; **created against
`rom/seaglass v3.0.gba`**, i.e. the hack ROM — end users apply it to their own
Seaglass ROM, never to clean Emerald). Round-trip verified byte-identical
(`flips --apply` reproduces the build).

## The shim (`src/character_mode.c`)

`CM_GiveMonToPlayerGated(mon)` — ROWE/RR acquisition semantics: when Character
Mode is ON (`FLAG 0x945` set + `VAR 0x40E4` != 0) and the caught mon is a
non-egg species not on the active character's roster, route it to the PC
(`CopyMonToPC`) instead of the party (`GiveMonToPlayer`); otherwise identical to
the original. Returns the same u8 the caller's `cmp r0,#0` expects.

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
3. **Hook**: retarget the wild-catch caller's BL `0x080A6A46`
   (GiveMonToPlayer → trampoline). `0x080A6A46` is 3.9 MB from `0x08470200` — in
   BL range. Total shipped-region edit: 4 bytes (one BL). Everything else is
   additive free space.

## Live test (`tools/mgba_scripts/cm_catch_test.lua`)

Same wild Zigzagoon (Nat-Dex 263, off the PoC Torchic-line roster), same catch,
toggling only the CM flag/var:

| Run | Setup | partyCount | Meaning |
|---|---|---|---|
| **control** | CM off | 1 → **2** | Zigzagoon caught to party (normal) |
| **enforcement** | CM on | 1 → **1** | same catch, off-roster mon **blocked → PC** |

The control proves the catch succeeds; the enforcement run proves the gate
redirects it. `battle_menu2.ss` (original-ROM state) loads fine on the patched
ROM.

## To reach a real playable build

1. **Roster bitmap emit** (pipeline): `rosters.bin` currently holds base-species
   *lists*; the shim needs a per-character allowed-species *bitmap* (base +
   evolution families → bitfield, like Lazarus's `rosters_expanded.bin`). Add an
   `emit_bitmaps.py` step; then `onRoster()` becomes a bit test and the hardcoded
   PoC roster is replaced.
2. **Selection mechanism**: hook the cheat-code matcher's specials-table slot
   (`gSpecialsTable 0x0826DD68`) so character-name codes set `FLAG 0x945` +
   `VAR 0x40E4` and deliver the signature starter — see `docs/ROUTINE_MAP.md`
   "Selection mechanism" + `../Lazarus-Character-Mode/docs/SELECTION_MECHANISM.md`.
3. **Gate the other 2 GiveMonToPlayer callers**: script-gift `0x081F18DE`
   (retarget its BL too); egg-hatch `0x08188514` stays original (eggs exempt).
4. Trades, sprites (Phase 3), regression suite, README — RR/Lazarus parity.
