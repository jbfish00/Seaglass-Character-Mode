# Testing methodology — ported from Pokemon ROWE

Seaglass's testing approach is a deliberate port of the one used on **Pokemon
ROWE** (`/home/jbfish00/Documents/Pokemon Rowe Alteration`), adapted to the
fact that ROWE has full C source and Seaglass is a closed binary. This doc
records the method-by-method mapping: what ports, what doesn't, and what
replaces it.

## What ROWE did

ROWE is a `pret/pokeemerald` decomp fork, so it could **compile a debug menu
into the ROM**:

- `src/debug.c` (~2900 lines), entry `Debug_ShowMainMenu()`, enabled
  unconditionally via `#define DEBUG_MENU` in `include/debug.h`. Opened
  in-game from **Start → Select**.
- Submenus: **Utilities** (`DebugAction_Util_HealParty`, `_Util_Fly`,
  `_Util_Warp_Warp`, `_Util_CheckSaveBlock`, wall-clock/trainer-id setters),
  **Flags** (`DebugAction_Flags_FlagsSelect` to set any flag,
  `_Flags_CatchingOnOff` toggling `FLAG_SYS_NO_CATCHING`, `_CollisionOnOff`,
  `_EncounterOnOff`, badge/fly toggles), **Vars** (`DebugAction_Vars_SetValue`
  to set any var — this is how the active Character Mode character was
  selected, via `VAR_CHARACTER_ID`, which `GetActiveCharacter()` reads at
  `src/character_mode.c:30`), and **Give** (`DebugAction_Give_PokemonSimple` /
  `_PokemonComplex` full IV/EV/nature/ability/move/shiny builder,
  `_Give_Item`, `GiveAllTMs`, `DebugAction_AccessPC`, and a `Debug_CheatStart`
  script that warps straight into content).
- **No automated test harness at all** — no `test/` dir, no `mgba-rom-test`,
  no CI. Verification was entirely manual: drive `mgba-qt` with `xdotool`
  keydown/keyup (ROWE's `CLAUDE.md` notes ≥0.4 s holds were needed for the
  real GUI to register presses), take `import` screenshots to confirm each
  step, and log the results by hand ("Systems test pass", "7 of 7 PROVEN").
- Temporary test grants (a stocked party, badges) were **patched into the C
  source**, built into a throwaway ROM, then reverted and rebuilt clean.

## Why it can't be copied literally

Seaglass has **no source**. There is no build step to `#define DEBUG_MENU`
into, no `src/debug.c` to add, and no C in which to write a menu. Injecting a
whole interactive debug-menu UI into a closed binary via `armips` would be a
large sub-project in its own right — and, crucially, it would be *testing
infrastructure that itself needs testing*, built out of exactly the same
risky hand-written ARM hooks whose correctness is the thing in question.

## What we do instead — an external harness with the same capabilities

Every capability the ROWE debug menu provided is a form of **(a) mutate game
state, (b) drive input, (c) observe state**. All three are available from
*outside* a closed ROM through mGBA's scripting API, which we reach with the
`mgba-headless` binary built from source (see `CLAUDE.md`'s Toolchain section
for why the packaged `mgba-qt` 0.10.2 can't do this — no `--script` flag).

`tools/mgba_scripts/harness.lua` is the reusable library. The mapping:

| ROWE debug-menu capability | Seaglass equivalent | Status |
|---|---|---|
| Give Pokémon (`_Give_PokemonComplex`) | `H.wr8/wr16/wr32` into `gPlayerParty` | **RAM write verified** (EWRAM round-trip proven); needs `gPlayerParty` address — see Bootstrap below |
| Set `VAR_CHARACTER_ID` (Vars menu) | poke the vars block | pending vars-block address; **also moot until Character Mode is actually injected** — nothing to select yet |
| Toggle catching (`FLAG_SYS_NO_CATCHING`) | poke the flags block | pending flags-block address |
| Heal party / Access PC / Warp | poke party HP / drive input to a PC / poke map+coords | pending; savestates cover most of the need more cheaply |
| Human pressing buttons (xdotool, ≥0.4 s holds, screenshots) | `H.press` / `H.sequence` / `H.mash` — drives the **emulated pad directly** | **verified working** (`emu:addKey`/`clearKey`; `getKeys()` observed `0→1→0`) |
| *(not possible in ROWE)* | `H.breakpoint(name, addr)` — halt on any ROM address, dump `pc`/`r0`-`r2` | **verified working** |
| *(not possible in ROWE)* | `H.assertEq` / `H.finish` — PASS/FAIL assertions, headless & repeatable | implemented |

Two things this port gains over the original:

1. **Determinism.** ROWE's tests were manual GUI playthroughs; frame timing was
   approximate and flaky enough that its own notes warn some debug dialogs were
   unreliable. Here input is scheduled in exact frames on the emulated pad, with
   no host window focus, no screenshots to eyeball, and no `xdotool` timing
   guesswork. The same script produces the same result every run.
2. **Breakpoints and memory watch.** An in-game menu cannot tell you *which ROM
   routine* fired. This is the core tool for the Phase 1 reverse-engineering
   that a source-available project like ROWE never needed to do at all.

The thing this port *loses*: ROWE could exercise state via real, in-engine code
paths (`GiveMon()` builds a legitimate Pokémon through the game's own
constructor). Poking RAM from outside is blunter — write a malformed struct and
you get a "bug" that is entirely your own fault. This is why `harness.lua`
leaves every unconfirmed address `nil` and fails loudly rather than poking a
guessed address, and why we confirm addresses empirically instead of assuming
vanilla Emerald's memory map — which **demonstrably does not hold here**:

> Verified: vanilla Emerald's `gPlayerParty` (`0x020244EC`), `gSaveBlock1Ptr`
> (`0x03005D8C`) and `gSaveBlock2Ptr` (`0x03005D90`) have **zero** literal-pool
> references anywhere in this ROM. Seaglass's memory map is its own.

## Bootstrap: finding the RAM anchors

`tools/mgba_scripts/find_ram_anchors.lua` is the step that unlocks the
state-mutation half of the table above.

**Confirmed so far** (empirically, on `rom/seaglass v3.0.gba` @ `rom.sha1`):

- **Save-block pointer trio: `0x030051B8` / `0x030051BC` / `0x030051C0`.**
  These are the three most-referenced consecutive IWRAM words in the entire
  ROM (1885/902/666 literal-pool hits). All three read `0x00000000` at boot and
  hold EWRAM pointers by frame ~240 — runtime-initialized pointers into EWRAM,
  exactly the shape of pokeemerald-expansion's `gSaveBlock2Ptr` /
  `gSaveBlock1Ptr` / `gPokemonStoragePtr` trio.
  **DISAMBIGUATED** (via `probe_saveblock.lua` on the truck state — dumped each
  target's header):
  - `0x030051B8` → **gSaveBlock1Ptr** (header = `pos.x/pos.y` + `WarpData
    location`; read x=2 y=2 map=25.40 = the truck)
  - `0x030051BC` → **gSaveBlock2Ptr** (starts with the 8-byte playerName field)
  - `0x030051C0` → **gPokemonStoragePtr** (all-zero at new game = empty PC)

  SaveBlock1 field offsets confirmed vanilla: `+0x00 s16 pos.x`, `+0x02 s16
  pos.y`, `+0x04 u8 mapGroup`, `+0x05 u8 mapNum`, `+0x06 u8 warpId`. These give
  **live player coords + current map** — the robust nav/scene-detection signal
  (see `docs/INTRO_NAVIGATION.md`). The flags and vars arrays live inside save
  block 1; the **flags-array offset is NOT vanilla's `+0x1270`** (that region
  reads all-zero here — expansion relocated it) and is the next thing to pin
  down, as it unlocks the catching-toggle and `VAR_CHARACTER_ID` equivalents.

**Still needed: `gPlayerParty`.** Found by scanning EWRAM for the *plaintext
tail* of Gen 3 `struct Pokemon` records (`+0x54` level, `+0x56` hp, `+0x58`
maxHP, with nonzero personality/otId), looking for consecutive records at a
consistent stride. The stride is **discovered, not assumed** — expansion forks
change `struct Pokemon`'s size, so the scanner tries 100–128 bytes.

This requires a savestate that actually **has a party**. Rather than depend on
a human-provided "wild battle" savestate, we now reach that state
autonomously: `mgba-headless`'s `emu:screenshot()` (after the local
headless-main.c video-buffer patch) plus coordinate-aware navigation
(`nav_coords.lua`) drive the intro headlessly. See
**`docs/INTRO_NAVIGATION.md`** for the full route + checkpoints. Current status:
the entire intro is navigated (truck → house → clock → town → neighbor → lab),
blocked only at the flag-gated Route 101 north exit (needs flag 0x74 set, i.e.
the flags-array offset). Validation of the scanner against a fresh boot (no
party) behaves exactly as it should: after tightening the heuristic, **zero**
multi-record runs and only 10 scattered single-record false positives from
title-screen graphics data — so when a real party exists it will stand out
unmistakably as the sole multi-record run.

```bash
./tools/mgba_src/build/mgba-headless \
  --script tools/mgba_scripts/find_ram_anchors.lua \
  -t /path/to/savestate.ss1 \
  "rom/seaglass v3.0.gba" > /tmp/anchors.log 2>&1
grep ANCHOR /tmp/anchors.log
```

`gPlayerParty` and `gEnemyParty` look identical to this scan — disambiguate by
comparing the reported level/HP against what the savestate actually shows on
screen (your mon vs the wild mon), then record the winner in `harness.lua`'s
`H.gPlayerParty` and here.

## Gotcha: don't pipe mgba-headless through `head`

`mgba-headless` emits an enormous amount of BIOS/DMA/serial-I/O logging, and
`timeout`-killing it while piped into `grep | head` loses the buffered output
entirely (SIGPIPE) — it looks like the script silently produced nothing when it
actually ran fine. **Redirect to a file first**, then grep the file. This cost
real debugging time; it is not a bug in the scripts.

Also: bulk-read memory with `emu:readRange(addr, len)` (returns a plain Lua
string) rather than looping `emu:read8`. Scanning 256 KB of EWRAM one byte at a
time crosses the C/Lua marshalling boundary ~200k times and stalls the emulator
so hard the frame callback never returns.

## Test matrix (2026-07-17 — full feature injected)

Run the automated layers: `sh tools/tests/run_tests.sh`.

| Layer | What | Status |
|---|---|---|
| **3 — static artifacts** (`tools/tests/verify_artifacts.py`) | Re-derives everything from the built ROM/BPS, shares no code with the injector. 24 checks: sha1 pin, **BPS round-trip byte-identical**, **diff containment to 63 intended windows**, **GiveMonToPlayer BL exhaustion** (orig 3 callers → patched leaves only the exempt egg-hatch caller), trampoline/BL decode, bitmaps == rosters_expanded.bin, roster+starter on-bitmap invariant, 170 codes round-trip + unique, **49 callnative-give sites all retargeted**, BG-ptr repoint + entry-script decode, 4 trade-junction overlays + wrapper decode. | **24/24 GREEN** |
| **2 — boot smoke** (`boot_test.lua`) | Patched ROM boots and runs. | **GREEN** |
| **4a/b — live catch gate** (`cm_catch_test.lua`) | Same wild Zigzagoon, toggling only the CM flag: CM on + char 1 (Red, off-roster) → blocked→PC (party stays 1); CM off → caught to party (control). Per-character discrimination previously verified (char 39 Brendan allows Zigzagoon). | **GREEN** |
| **1 — GDB shim unit tests** | Not built for Seaglass. Would exercise the shim's branch table (flag off / empty party / on-roster / off-roster→PC / egg exemption / per-char bitmap) in isolation à la Lazarus's `shim_unit_test.py`. The static on-bitmap invariants + live catch gate + the 4c–4f e2e now cover this seam's main paths; optional hardening only. | Not built (optional) |
| **4c–4f — real-UI activation e2e** (`cm_ui_activate.lua`) | **DONE (2026-07-17 later).** From `naming_open.ss` (CODE naming screen open at the mart clipboard), types a code via 40-frame-spaced cursor taps, commits (START→A), dismisses the dialogue, then **asserts** on flag/char/party/starter-var. Four suite layers: **4c** RED → char 1 + starter to party; **4d** MISTY → char 10 (discrimination); **4e** ZZZ → rejected, nothing set; **4f** CMDBGOFF with CM preset → flag+char cleared, starter var = 0xFFFF off-marker. | **GREEN (all 4)** |
| **4g — in-situ trade gate** (`cm_trade_test.lua` on the test-only ROM) | **DONE (2026-07-17 latest).** From `mart_inside.ss` we navigate to the clipboard and trigger a test-ROM entry script (`lock; setvar 0x8008,idx; goto junction[idx]`) that lands on the **shipped** junction overlay → the shipped per-trade wrapper. Breakpoints CM_TradeCheck's store (`0x08ED25BC`) and reads the decision from r4. Three cases on idx2 (SEASOR, receives Horsea 116): **RED** (off-roster) → 0 refuse + refusal msg renders + party unchanged; **MISTY** (on-roster) → 1 allow (per-character discrimination); **CM off** → 1 allow (control). | **GREEN (all 3)** |
| **5a/b — wild-encounter override** (`cm_wild_test.lua`, `cm_wild_stage_test.lua`, `tools/tests/verify_wild_override.py`) | **DONE (task #5, wild-mon override).** From `at_8_8.ss`, walks into Route 101 grass; two breakpoints on the wild trampoline (`0x08470208` entry, `0x08470218` post-call) observe the rolled species/level going in and the (possibly overridden) species coming out. **5a**: CM off → trampoline fires (proving the hook is live) but never overrides (inert requirement). **5b** (`verify_wild_override.py`): forces the rolled level to 45 via `emu:writeRegister` and retries across `START_DELAY`s until the 10% gate fires → asserts the resulting species is a real, non-legendary member of the active character's pool with no closer-fitting stage available; separately samples 20 unforced low-level (2–3) rolls, asserting every override observed is a valid pool member and the empirical rate is in a plausible band for p=0.10. Comprehensive **offline** legendary-exclusion + rate-math checks (not emulator-dependent) also passed: `wildpool_manifest.json`'s 4889 entries across all 170 characters contain zero legendary species; an exhaustive sweep of the `wildSeed()` formula over ~346k (species,level,vcount,keys) combinations landed at exactly 10.00%. | **GREEN** |

**What's proven about selection:** the selection script + shim are statically
verified end-to-end, **and the naming-screen UI seam is now live-verified**
(4c–4f above: type→commit→match→confirm+give / reject / deactivate, all
asserted against real RAM state). The enforcement half is live-verified
(catch gate on/off; the 49-site callnative-give hole closed by exhaustion).
**Trade gating is now live-verified too** (4g: the real overlaid junction
wrapper + CM_TradeCheck, refuse and allow both exercised, per-character
discrimination on one trade). The only remaining live gap is the **full human
playthrough**.

**In-situ trade e2e — how it works and what it cost (2026-07-17 latest):**
Real trade NPCs are deep in the game and the warp path is unusable (same wall
Lazarus hit), so we reuse Lazarus's *test-only ROM* trick:
`tools/tests/build_trade_testrom.py <idx>` copies `build/seaglass_cm.gba` and
repoints the mart-clipboard BG event (file `0x123ACC`) from the CM entry script
to a tiny `lock; setvar 0x8008,idx; goto junction` shim in unused free space
(`0x08EF6000` — moved from `0x08EF0000` when task #5's wild-encounter pool
table, `0x08EE4000`-`0x08EF5440`, grew into the old address). The junction it jumps to is the **shipped** overlay, so the
per-trade wrapper under test is unmodified; the shipped ROM is never touched and
the variant is never distributed. Three hard-won gotchas that cost real time:
1. **The junction/setvar order is (2,0,1,3), not table order** (documented in
   the trades section): trade index N's junction is *not* `TRADE_JUNCTIONS[N]`.
   The builder maps index→junction explicitly (`JUNCTION_FOR_TRADE`). Verify:
   `setvar 0x8008,2` sits 0x55 before junction `0x29CFF5`.
2. **A log-only "pass" is worthless — and RED is a decoy.** Horsea is off
   *every* roster we'd test, so a RED-only refuse result confirms nothing about
   whether the right trade index was read. The MISTY-vs-RED pair on the *same*
   trade is the load-bearing check. Always breakpoint CM_TradeCheck to prove it
   ran, and read the decision from r4/the store, not from a frame poll — the
   ALLOW path's `special 0x100/0x101` overwrite VAR_RESULT before any later
   frame sees it.
3. **gSpecialVar_Result is at `0x020055F0`, not `0x020055F2`** — an old computed
   note was off by 2; reading GetVarPointer(0x800D)'s own store address settled
   it. The test now reads r4 directly (address-independent).
4. **The clipboard interacts on a LEFT-facing A at (0,5)** (LEFT till blocked,
   UP till blocked, an A-up probe, then face-LEFT + A) — the older `LEFT×3,UP×2`
   cadence no longer reaches it and a saved "facing" state didn't reproduce the
   trigger; the reactive walk in `cm_trade_test.lua` is the reliable route.

**Two e2e gotchas (hard-won, 2026-07-17 later):**
1. **Tests must assert, not just log.** `H.finish()` prints `RESULT: PASS`
   whenever the assert-failure list is empty — a script that only `H.log`s its
   observations *always* "passes" the runner's grep. `cm_catch_test.lua` had
   exactly this bug (green while vacuous); it now asserts the party count, and
   `H.finish` also `os.exit`s with a real status (nonzero on failure), which
   ends the emulator immediately instead of idling out the runner's timeout.
2. **Don't over-mash A after the commit.** The player is still standing at the
   clipboard, so a long post-commit A-mash re-triggers the BG event, reopens
   the code entry, and can commit a stray invalid code that overwrites
   `VAR_CM_STARTER` (this made the off-marker assert fail intermittently and
   left a reopened naming screen in end screenshots). The mash window is ~9
   presses (`commit+80 .. commit+500`) — enough for one msgbox, too few to
   drive prompt→naming→commit again.

**Fixture note:** `naming_open.ss` embeds the paused script context (the
`waitstate` inside the injected entry script), so it is build-layout-specific —
if `SCRIPT_ADDR` or the entry-script layout ever moves, regenerate it with
`capture_naming.lua` (drives mart_inside.ss → clipboard → "yes" → naming
screen, saves the state ~90 frames after the DoNamingScreen breakpoint).
