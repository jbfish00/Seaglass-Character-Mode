# Headless intro navigation — reaching a party state autonomously

Goal: drive Seaglass from a cold boot to a **party + wild battle** with no human
input, so we can (a) locate `gPlayerParty` (scan a real party — see
`docs/TESTING.md` Bootstrap) and (b) trace the catch-success handler at a live
wild battle. This is the self-service replacement for the "user provides a
savestate" plan.

Everything here was done with `tools/mgba_scripts/nav_coords.lua` (coordinate-
aware movement + live map detection) against `mgba-headless`, reading the
player's map position straight out of SaveBlock1 so navigation is driven by RAM
truth, not by eyeballing pixels.

## The key unlock: live coordinates + map id from SaveBlock1

`probe_saveblock.lua` disambiguated the confirmed IWRAM pointer trio by dumping
each target's header. **SaveBlock1 = `[0x030051B8]`** (its header reads as
`pos.x/pos.y` + `WarpData location`). Field offsets (vanilla pokeemerald
`struct SaveBlock1`, confirmed to hold here):

| field | offset | type |
|---|---|---|
| `pos.x`   | +0x00 | s16 |
| `pos.y`   | +0x02 | s16 |
| `mapGroup`| +0x04 | u8  |
| `mapNum`  | +0x05 | u8  |
| `warpId`  | +0x06 | u8  |

Full trio (also confirmed): `0x030051B8` = gSaveBlock1Ptr, `0x030051BC` =
gSaveBlock2Ptr (starts with the 8-byte playerName), `0x030051C0` =
gPokemonStoragePtr (all-zero at new game). Recorded in `harness.lua`.

Reading `(x, y, mapGroup, mapNum)` every frame makes navigation deterministic:
each queued move either changes the coords (walked) or doesn't (wall/NPC), and a
`mapGroup/mapNum` change means a warp fired — that's how every door/stair/edge
below was found without guessing tile geometry.

## Map ids seen (Seaglass, group.num)

| map | id | notes |
|---|---|---|
| Inside of truck | **25.40** | intro spawn; exit warp reached via the x=4 column, DOWN |
| Littleroot Town | **0.9**  | overworld |
| Player's house 1F | 1.0 | door at town (14→ own house ~(5,8)); stairs-up tile (8,2) |
| Player's house 2F | 1.1 | bedroom; wall clock, PC, game console; stairs-down tile (7,1) |
| Neighbor's house 1F | 1.2 | rival's mom + little sister |
| Prof. Birch's LAB | 1.4 | door approached from the south plaza (up into (7,15)); only aides inside — **Birch is out** |

## Route walked (checkpoints saved under tools/savestates/, all gitignored)

1. `intro_end.ss` — boot + A-mash intro (Birch speech, gender/name defaults) to
   the moving truck, frame ~9000. (`drive_intro.lua`)
2. Truck exit: from spawn (2,2), the walkable path is the **x=3→x=4 column**;
   DOWN off the truck at x=4 warps to Littleroot. Truck DOWN from spawn is
   blocked by a crate — the vanilla "walk straight down" does NOT apply here.
   → `littleroot_arrival.ss` (0.9 @ ~(4,10)).
3. Mom's greeting scripted-walks you into the house (→1.0).
4. Up the stairs (8,2) → 2F. **The wall clock is a hard gate** (verified: skip
   it and Mom's downstairs event sends you back up). Clock is on the top wall at
   ~(5,1); the game console at ~(4,1) is a decoy ("MOM might like this
   program"). Clock UI: A past two text boxes → clock face → A → "Is this the
   correct time?" **cursor defaults to NO** → press UP then A. → `clock_done.ss`.
5. Downstairs → TV event ("Come quickly!… PETALBURG GYM… he lives next door,
   go introduce yourself"). Long; close the last repeat-line with **B** (A
   re-triggers the adjacent NPC). Exit house → `outside_house.ss` (0.9).
6. Neighbor's (east) house door at (14,8): rival's little sister + mom. Mom's
   line: *"If he's not at his LAB, he's likely scrabbling about in grassy
   places."*
7. Birch's LAB (1.4): entered from the south plaza. Only wandering aides
   (fieldwork/trade-evo flavor) — **no starter here.** → `lab_interior.ss`.

## The blocker: north exit to Route 101 is flag-gated

The starter comes from the **vanilla Route 101 Birch rescue** — confirmed by
decoding the script text cluster at ROM 0x00284756–0x002847CE:

> "Hello! You over there! Please! Help! In my BAG! There's a POKé BALL!" …
> "PROF. BIRCH: I was in the tall grass studying wild POKéMON when I was
> jumped. You saved me!… come by my POKéMON LAB later, okay?"

But Littleroot's **north exit is gated**. Stepping north (e.g. onto ~(10,1))
fires a coordinate script that shows *"Um, um, um! If you go outside and go in
the grass, wild POKéMON will jump out!"* and walks you back. Decoded gate logic
(ROM script @0x0827DBEF, found via `find_pointer_refs.py` on the blocker text
0x0827E7A7):

```
checkflag 0x74 ; goto_if TRUE  -> "Are you going to catch POKéMON? Good luck!" (pass)
checkflag 0x52 ; goto_if TRUE  -> (other pass branch)
else           ->               "Um, um, um! … wild POKéMON will jump out!"  (block)
```

So **flag 0x74** = "player has a POKéMON". Center columns 9/10/11 at the top are
tree/NPC/tree — no walk-around gap was found. This is a genuine
chicken-and-egg by design intent (get a mon, *then* the grass opens), but the
mon is on Route 101 behind this gate — which in vanilla is opened because the
rescue is an on-Route-101 cutscene. Here the Littleroot-side gate preempts it.

## Next step (this is where the session stopped)

Two viable unblocks, in priority order:

1. **Set flag 0x74 via RAM** (the ROWE debug-menu "set flag" capability, and the
   cleanest fix). Needs the **flags-array offset inside Seaglass's SaveBlock1**,
   which is *not* vanilla's `+0x1270` — that region reads all-zero here
   (`set_flag_probe.lua` confirmed: setting flag 0x74 there did nothing).
   Seaglass is a pokeemerald-**expansion** fork, so the struct is relocated.
   Find the offset by disassembling `FlagGet` (the `checkflag` primitive embeds
   `offsetof(SaveBlock1, flags)` as an immediate), or by diffing SaveBlock1
   across a known flag toggle. `scan_saveblock.lua` dumps nonzero SB1 regions to
   help. Once found, record it in `harness.lua` (`H.FLAG_BLOCK`) — it also
   unlocks the catching-toggle and `VAR_CHARACTER_ID` equivalents.
2. Re-examine whether the gate is truly wall-flanked, or whether the intended
   trigger is a different Littleroot tile / an earlier missed story step that
   sets flag 0x74 or 0x52 legitimately.

Once past the gate → Route 101 → Birch rescue → **starter in party**, then run
`find_ram_anchors.lua` (resolves `gPlayerParty` + stride) and
`headless_catch_trace.lua` at the first wild battle (IDs the catch handler).

## Toolkit added this session (tools/mgba_scripts/)

- `nav_coords.lua` — coordinate-aware movement driver; edit `MOVES`, reads
  `(x,y,map)` from SaveBlock1 every frame, logs changes, screenshots + saves an
  out-state. The workhorse.
- `drive_intro.lua` — A-mash the boot intro to the truck.
- `wait_shot.lua` — load a state, no input, periodic screenshots (used to prove
  the truck does NOT auto-exit and the gate is coordinate-triggered).
- `probe_saveblock.lua` — dump/interpret the SaveBlock pointer trio headers.
- `set_flag_probe.lua` — set a flag at a candidate SB1 offset and test the gate.
- `scan_saveblock.lua` — dump nonzero SaveBlock1 rows to locate flags/vars.

Gotcha carried over from `docs/TESTING.md`: bound any periodic-screenshot loop
with `if f > END_FRAME then return end` — `H.finish()` does NOT halt the
emulator, and headless runs ~1800 fps, so an unbounded loop spews tens of
thousands of PNGs before the process timeout.
