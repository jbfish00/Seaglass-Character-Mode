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

## RESOLVED (2026-07-15): gate bypassed, starter obtained, party located

> **2026-07-16 CORRECTION (Lazarus feedback loop — read before reusing the
> numbers below):** the "flags-array base = SaveBlock1 + 0x157E" finding is
> WRONG. The true bases are **flags = SB1+0x13C0, vars = SB1+0x14EC** (static
> disasm of FlagGet/FlagSet/GetVarPointer via the script command table, plus
> 61/61 live FlagGet round-trip matches — `docs/ROUTINE_MAP.md`). The
> bisection's byte `+0x158C` bit4 was actually **var 0x4050 |= 0x10**, and the
> gate is a coord trigger keyed on var 0x4050 == 0 (its block script
> `0x0827DC4A` shows "Um, um, um!" and pushes the player back
> unconditionally); real flag 0x74 does NOT open it (live-disproven). Every
> downstream result below (Route 101, Torchic, gPlayerParty, savestates)
> remains valid — the poke set the right memory under the wrong name.

The flag-gated north exit (below) was cracked and the full rescue completed
**autonomously**:

- **Flags-array base = SaveBlock1 + 0x157E** (flag N -> byte 0x157E + N//8, bit
  N%8). Found by *bisection against the gate itself*: `gate_test.lua` sets bit4
  across a byte range, walks to the exit, and checks whether the map becomes
  0.16 (Route 101). Narrowed to byte 0x158C bit 4 = flag 0x74. (Empirical guesses
  and literal-pool disassembly had both failed; the gate-bisection was decisive.
  The write-read path was verified: gSaveBlock1Ptr is stable and the poked byte
  persisted.) Recorded in `harness.lua` as `H.FLAG_BLOCK` + `H.setFlag/getFlag`.
- Setting **flag 0x74** opens the gate -> walk north -> **Route 101 (0.16)**.
- Continuing north into the tall grass triggers the **Prof. Birch rescue**:
  `reach_starter.lua` reaches it, `win_battle.lua` confirms the starter
  (**Torchic**), A-mashes the wild-Poochyena battle, and Birch warps you to his
  lab (1.4). Checkpoints: `route101.ss`, `after_rescue.ss`, `have_starter.ss`.
- **gPlayerParty = 0x02019C20** (stride 100). Found by scanning EWRAM for a
  Pokemon record whose OT-ID matches the player's (SaveBlock2+0x0A =
  0x99BDB9EF), then disambiguating the 3 hits by ROM literal-ref count: this
  address has 577 refs (the real global); the two transient copies have 3 each.
  Recorded in `harness.lua`. This unlocks the "Give Pokemon" state-mutation half
  of the harness and the `find_ram_anchors.lua`/catch-trace path.

Escaping the lab: the post-rescue lab has aide NPCs; A-mashing re-triggers them
in a loop (same as the neighbor's-house mom). **Escape with B** (closes dialogue
without re-interacting), then walk away — `escape_lab.lua` / the B-mash in
`nav_coords.lua`. After that, walking out and back north to Route 101 works
(the gate is now legitimately open — obtaining Torchic set flag 0x74 for real).
`route101_party.ss` = on Route 101 with Torchic; `have_starter.ss` = free
overworld with the party.

**Catch-trace status (2026-07-16 update): wild battles WORK; blocked only on
obtaining Poké Balls.** The full pipeline is proven end-to-end headlessly:
clean rescue (clear flag 0x74 on Route 101 so Birch despawns —
`reach_starter.lua`) → escape lab (B, not A — `escape_lab.lua`/`lab_out.lua`) →
Route 101 **tall grass** (the encounter grass is the dark spiky tiles east of
~(11,10), NOT the light tufted ground; sprite legs stay visible either way in
this tileset, so identify grass by the tile art, not the sprite) → **wild
battle confirmed** (`battle_bag_oneshot.lua`; `gEnemyParty` **VERIFIED** at
0x02019E78 — the wild mon materializes there). Battle input gotcha: the GBC-paced
intro ("Wild X appeared!" / "Go! <name>!") swallows early presses — wait ~1500
frames for the real command menu; state-loads mid-battle drop single key edges,
so drive menus with `H.mash` (repeated edges) or run the whole encounter in one
script. The **bag is EMPTY** (all 4 pockets checked — `pockets.lua`), so we
can't throw a ball yet. Reached **Oldale Town** (map 0.10, connection at Route
101 top-edge **column 8**) and the **Oldale Mart** (map 2.4) via a
whiteout-proof auto-healing trek (`trek_v3.lua`/`probe_north.lua` poke
gPlayerParty+0x56 = maxHP each frame). The Oldale Mart clerk **shop menu was opened** (`shop.lua`; talk from tile
**(1,5)** facing up — the counter is at the top-LEFT, the front tile is 1 west of
where geometry first suggested), MONEY ¥3000. **But it stocks only medicine**
(Potion/Antidote/Paralyze Heal/Awakening) — **no Poké Balls**. In the vanilla
Emerald flow (which Seaglass follows here), marts don't sell Poké Balls until you
have the **Pokédex**, and **Birch gives the Pokédex + 5 Poké Balls only AFTER the
Route 103 rival battle**, not right after the rescue. Verified: the post-rescue
lab speech is short — control returns by ~frame 800 (then A-mashing just loops a
tall-grass aide) — and leaves the **bag empty**. So the path to a throwable ball
(and thus the catch trace) is:

  Route 101 → **Oldale (0.10)** → north to **Route 103** → meet + battle the
  rival (Torchic can win; auto-heal keeps us alive) → return to **Birch's lab
  (1.4)** → receive Pokédex + 5 Poké Balls → wild battle → throw → catch trace.

Alternative (faster, and the ROWE "give item" capability we want anyway):
**RAM-write Poké Balls** into the bag's Poké-Ball pocket. Needs three unknowns
pinned in this fork's SaveBlock1: the pocket offset, ITEM_POKE_BALL's id (vanilla
4), and the encryption key (gSaveBlock2->encryptionKey; item *quantities* are
XOR'd with its low 16 bits, item *IDs* are plain). Easiest to locate by buying a
Potion (¥200, we have ¥3000) and diffing SaveBlock1 to find the Items pocket +
key behavior, then writing itemId=4/qty=(N XOR key) into the Poké-Ball pocket.

Checkpoints: `wild_battle.ss`, `oldale.ss`, `mart_inside.ss`, `shop.ss`,
`have_starter2.ss` (post-full-lab-speech).

**Earlier catch-trace note (superseded — kept for context):** With flag 0x74 set to
bypass the gate, the Route 101 **rescue cleanup did not fully run**: Prof. Birch
and his bag still linger on the map, and no encounter-triggering *tall grass* was
reachable in the immediate rescue zone (`walk_grass.lua` walked many steps with
no wild encounter; the map appears stuck in a partial rescue state). The likely
fix is to pass the gate **without the flag-0x74 lie** — either poke `var 0x4050`
(= vars[0x50]; needs the vars-array base pinned, candidate 0x156E, unverified) or
**clear flag 0x74 immediately after passing the gate** so the rescue's own
completion sets the correct end-state and re-enables encounters. Alternatively,
traverse further north past the rescue zone to Oldale-side tall grass. Everything
else for the trace is ready: `gPlayerParty` known, Route 101 reachable with a
party, and `headless_catch_trace.lua` armed on the 6 catch candidates — it just
needs a savestate positioned in a real wild battle.

## The blocker (original analysis): north exit to Route 101 is flag-gated

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
