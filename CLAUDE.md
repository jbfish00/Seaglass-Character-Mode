# CLAUDE.md — Pokemon Emerald Seaglass "Character Mode"

Guidance for Claude Code when working in this repo. Keep this file current at every pause — it's the handoff doc for a fresh instance picking this up cold.

## ⭐ COLD-START QUICK REFERENCE (read first; full detail in the dated Status entries below)

**Where we are (2026-07-17):** The **core Character-Mode mechanic works, is injected, live-tested, and packaged.** Catch + script-gift acquisition are gated by the real 170-character roster bitmap: an off-roster non-egg mon is routed to the PC instead of the party. Phases 0–2 done; Phase 1 RE fully confirmed (all addresses in `harness.lua` + `docs/ROUTINE_MAP.md`); Phase 4 (injection) + Phase 5 (BPS round-trip) done for enforcement.

**Build the patch** (reproducible from source): `sh tools/build_cm.sh` → `build/seaglass_cm.gba` + `build/seaglass_cm.bps` (both gitignored; BPS is the deliverable, created against the hack ROM). See `docs/INJECTION.md`.

**Test it** (headless; breakpoints need `MGBA_HEADLESS_DEBUGGER=1`):
```
# per-character catch enforcement (CM on): char 1 (Red) blocks Zigzagoon, char 39 (Brendan) allows it
CM_ON=1 CM_CHAR=1  ./tools/mgba_src/build/mgba-headless --script tools/mgba_scripts/cm_catch_test.lua -t tools/savestates/battle_menu2.ss build/seaglass_cm.gba
```
Key savestates (gitignored, one person's playthrough): `battle_menu2.ss` (wild Zigzagoon battle — the enforcement-test fixture), `have_starter.ss`, `oldale.ss`, `mart_inside.ss`. Original-ROM states load fine on the patched ROM.

**What's NEXT (task #15, in priority order):**
1. **Selection mechanism** — the biggest gap. CM flag/var are set via RAM in tests; players need an in-game way to pick a character. The native cheat-code system is LOCATED (`gSpecialsTable 0x0826DD68`, entry script `0x08311C32`, "CHEAT DEVICE/GIFT CODE" text `~0x00311A23`) but the exact matcher special + code-string table aren't pinned yet. **Lazarus completed this exact injection** — read `../Lazarus-Character-Mode/docs/SELECTION_MECHANISM.md` + its `src/character_mode.c` `CM_CheatDispatchHook` + `tools/inject_character_mode.py` as the template.
2. Trade gating, Phase 3 sprites (task #10, for select-UI portraits), regression suite, end-user README.

**The sibling `../Lazarus-Character-Mode/` (same author Nemo622, same engine) is FINISHED (Phase 6, shipped) and is the primary source of transferable methods** — offsets differ per-build but techniques/idioms transfer. Its CLAUDE.md Status + docs are worth re-reading before each new subsystem here (selection, trades, test suite). This session's wins (flags/vars offsets, headless-breakpoint fix, catch-trace recipe, give-item, injection template) all came from it.

## What this project is

Porting the "Character Mode" feature from the Pokemon ROWE project (`/home/jbfish00/Documents/Pokemon Rowe Alteration`) to Pokemon Emerald Seaglass (by Nemo622): an opt-in mode restricting the player to catching/keeping only one iconic Pokemon character's Bulbapedia-documented roster (evolution families included). See the full plan at `~/.claude/plans/similar-to-what-you-tranquil-crescent.md` for the research behind this scaffold.

**Critical difference from ROWE: Seaglass has no public source.** It's a closed binary hack (Nemo622), distributed only as a patch applied to a clean USA Emerald ROM (sold with bundled documentation via Ko-fi). No public repo for Nemo622's own fork was found despite thorough search. This project is classic binary ROM hacking — reverse-engineer a compiled ROM, inject new code/data into free space, output a patch (never redistribute the ROM) — the same category as `Unbound-Character-Mode/` in this workspace, not the source-editing ROWE precedent.

**Seaglass's own battle-engine changelog** ("Fairy type, Physical/Special split... from pokeemerald-expansion") indicates it's very likely privately forked from the public `rh-hideout/pokeemerald-expansion` project — used here as a donor reference (see below), the same role `Dynamic-Pokemon-Expansion` played for Unbound.

**Scope note**: Seaglass is marketed with a much larger species scope than Unbound turned out to have (all Gen 1-3 + cross-gen evolutions up to Gen 9, e.g. Weavile/Tinkaton/Annihilape confirmed catchable) — do NOT assume Unbound's "no Gen 9 content" finding carries over. The real species cap must be found empirically in Phase 1.

## Standing goal (set 2026-07-12, later session)

User's directive: **"Build and test until you have a playable rom with no bugs or glitches."** This supersedes the implicit "make progress on Character Mode" framing — the bar is a complete, injected, patched ROM that actually plays correctly, not just research/data artifacts. Treat this as the standing goal across sessions until the user says otherwise. See "Roadmap to playable" below for the concrete phase breakdown this implies.

## Standing rules (carried over from the ROWE/Unbound projects, user-confirmed pattern)

- **Checkpoint rule**: at every pause, update this file + the plan file for seamless handoff.
- **Ask questions until 95% confident** before making consequential decisions.
- Distribution: patch only (UPS/BPS via `tools/bin/flips`), never a prebuilt/redistributed ROM.
- **Never write to `rom/seaglass v3.0.gba` directly.** All ROM-mutating work (armips assembly, patch testing) targets a fresh copy or a `build/` output path — see the `.open "in","out",addr` two-filename armips form. The source ROM is the one fixed point everything else is pinned against by SHA1; treat it as read-only.
- Every located ROM address will be pinned to the exact SHA1 in `rom.sha1` once the ROM is supplied. Re-verify before trusting notes against any other copy.
- **Donor reference (`tools/pokeemerald_expansion_donor/`) is topology/name-only.** Never trust its numeric `SPECIES_*` values without Phase 1 confirmation against the real ROM — see `docs/DONOR_CROSSWALK.md`. Unlike Unbound's DPE donor (where donor-position-equaled-id held up under spot-checks), this donor's HEAD extends past `SPECIES_GLIMMORA_MEGA` (1572+, fan content) with no reason to expect alignment with Nemo622's private fork. **Superseded for numeric ids as of Stage B (2026-07-12)** — real ids now come from matching against `rom_species_table.json` (the ROM's own dumped name table) directly, not the donor; see `docs/SPECIES_CAP.md`.

## Repo layout

- `rom/` — will hold the extracted ROM + readme once supplied (gitignored, never commit).
- `rom.sha1` — checksum of the source ROM; all findings will be pinned to this (Phase 0).
- `docs/ROM_INFO.md` — ROM header/provenance notes (Phase 0, placeholder).
- `docs/FREE_SPACE.md` — free-space audit results (Phase 1, placeholder).
- `docs/ROUTINE_MAP.md` — located routine addresses + evidence (Phase 1, placeholder).
- `docs/SPRITE_COVERAGE.md` — sprite/trainer-pic asset survey (Phase 3, placeholder).
- `docs/SPECIES_CAP.md` — empirical species-cap finding (Phase 1, placeholder).
- `docs/DONOR_CROSSWALK.md` — documents the donor's per-gen-file layout, inline evolutions, and the ID-untrustworthiness caveat.
- `tools/scan_free_space.py`, `search_gametext.py`, `decode_gametext.py`, `find_pointer_refs.py`, `dump_all_strings.py`, `ghidra_scripts/find_xrefs.py` — copied verbatim from `Unbound-Character-Mode/tools/` (game-agnostic GBA ROM scanners).
- `tools/pokeemerald_expansion_donor/` — gitignored clone of `rh-hideout/pokeemerald-expansion`, used as species/evolution donor reference.
- `tools/character_mode/` — roster data pipeline (Phase 2, **fully done** as of 2026-07-12 — see Status below): `characters.txt`, `cache/` (Bulbapedia scrape cache, seeded from ROWE's), `scrape_rosters.py`, `map_species.py` (Stage A), `map_species_stage_b.py` (Stage B, new this session), `emit_characters.py`, `rom_species_table.json` (the real dumped ROM species table Stage B resolves against), and their outputs (`rosters_raw.json`, `rosters_mapped.json` + `rosters_mapped_stageA_backup.json`, `roster_review.csv`, `unmatched_names.txt`/`stageb_unmatched.txt`, `unresolved_ids.json`, `stageb_ambiguous.txt`, `names.bin`, `characters.bin`, `rosters.bin`, `characters_manifest.json`).

- `ghidra_project/SeaglassCM.gpr` — Ghidra project (gitignored), imported `-noanalysis`, all analysis done via targeted `tools/ghidra_scripts/InspectRegions.java`/`DecompileFunc.java`/`FindXrefs.java` calls (Java, ported from Unbound's).

- `tools/bin/armips`, `tools/bin/flips` — prebuilt portable binaries, reused verbatim from `Unbound-Character-Mode/tools/bin/` (see Toolchain).
- `docs/TESTING.md` — **the testing methodology**, ported from ROWE's in-game debug menu to a closed binary (read this before doing any testing work). Method-by-method mapping of what ports, what doesn't, and the mGBA-scripting harness that replaces it.
- `tools/mgba_scripts/harness.lua` — reusable test-harness library (input macros, RAM read/write, breakpoints, PASS/FAIL assertions) — the closed-binary equivalent of ROWE's `src/debug.c` debug menu. See `docs/TESTING.md`.
- `tools/mgba_scripts/find_ram_anchors.lua` — bootstrap tool: locates `gPlayerParty` (+ struct stride) by scanning EWRAM for real Pokémon structs. Needs a savestate with a party. Unlocks the state-mutation ("Give Pokémon", "set var") half of the harness.
- `tools/mgba_scripts/trace_catch_mechanic.lua` — mGBA Lua breakpoint script for live-tracing the catch mechanic in the real interactive GUI; ready for the user to run.
- `tools/mgba_scripts/headless_catch_trace.lua` — same trace, but for `mgba-headless` (no GUI): arms the same 6 breakpoints and scripts the button presses itself once loaded with a savestate positioned at "wild battle, bag open" (see Status below). This is the one this Claude instance can actually run itself.
- `tools/mgba_src/` — gitignored clone+build of `mgba-emu/mgba` from source (see Toolchain: built to get the headless frontend, which the packaged `mgba-qt` 0.10.2 doesn't have). `tools/mgba_src/build/mgba-headless` is the resulting binary.
- `tools/patches/test_toolchain_roundtrip.asm` — a harmless armips test patch (writes a marker string into free space) used once to validate the full armips→flips→boot-test pipeline; not part of Character Mode itself, kept as a working syntax reference for future `.asm` hook files.
- `build/` — gitignored scratch output for ROM-copy build artifacts (armips output, flips patches, boot-test roms). Never the canonical source ROM.

**Phase 4 injection (added 2026-07-17 — the working enforcement patch; see `docs/INJECTION.md`):**
- `src/character_mode.c` — the enforcement shim (`CM_GiveMonToPlayerGated`: off-roster non-egg catch → PC). Compiles to a position-independent Thumb blob.
- `tools/patches/inject_cm.asm` — armips injector: shim @`0x08ED2164`, roster bitmap @`0x08ED2400`, trampoline @`0x08470200`, retargets the two acquisition BLs (catch `0x080A6A46`, script-gift `0x081F18DE`).
- `tools/build_cm.sh` — one-command reproducible build (emit bitmaps → gcc → ld → objcopy → armips → flips). Reads the shim entry from the ELF into `build/cm_entry.asm` so the shim can move freely.
- `tools/character_mode/emit_bitmaps.py` → `rosters_expanded.bin` — per-character allowed-species bitmap (base rosters expanded through the donor evolution graph; 170×187 B).
- `tools/mgba_scripts/` (Phase 4/live-testing additions): `cm_catch_test.lua` (enforcement test), `catch_trace_sg.lua` (the watchpoint catch trace), `give_pokeballs.lua` (give-item), `nav_coords.lua` + the intro-nav suite (`drive_intro`, `reach_starter`, `win_battle`, `lab_out`, `trek_v3`, `walk_grass`, `grass_east`, `to_bag`, `buy_potion`, …), `probe_saveblock.lua`, `scan_saveblock.lua`, `boot_test.lua`. See `docs/INTRO_NAVIGATION.md` for the nav route.
- `docs/INJECTION.md` — the Phase 4/5 injection writeup (shim, hooks, bitmap, live-test table, build). `docs/INTRO_NAVIGATION.md` — headless intro nav + all savestate checkpoints.

## Toolchain

- `arm-none-eabi-gcc` (system) for new freestanding C — not `~/agbcc` (that's for byte-matching GameFreak's compiler in decomp recompilation, irrelevant here since any injected code is brand-new). System-installed, confirmed present.
- `armips` (built from `Kingcom/armips` source, no apt package) for hook/assembly injection. **Set up 2026-07-12** — `tools/bin/armips`, copied verbatim from `Unbound-Character-Mode/tools/bin/armips` (prebuilt portable ELF, same reuse pattern as Ghidra below). Runs, prints `armips assembler v0.11.0` usage banner.
- `flips` for the final UPS/BPS patch. **Set up 2026-07-12** — `tools/bin/flips`, copied verbatim from `Unbound-Character-Mode/tools/bin/flips`. Runs.
- `mgba-qt` (Lua-scriptable) for dynamic tracing, interactive/human use. System-installed, 0.10.2, confirmed `liblua5.4`-linked. `tools/mgba_scripts/trace_catch_mechanic.lua` is ready for the user to run in the GUI.
- **`mgba-headless` — built from source 2026-07-12, this Claude instance's own dynamic-testing tool.** The packaged `mgba-qt` 0.10.2 has no CLI script-autorun flag (`--script` was checked against the real `0.10.2` release tag source on GitHub and confirmed absent — only present in a newer unreleased build); `cmake --build`ing `BUILD_HEADLESS=ON` from a fresh `mgba-emu/mgba` clone (`tools/mgba_src/`, gitignored) produces `mgba-headless`, which does have `--script FILE` and needs no display/GUI/X server at all. Build deps installed via apt: `liblua5.4-dev`, `libsqlite3-dev`, `libzip-dev` (had to pass `-DUSE_LIBZIP=OFF` — the system's `libzip-dev` package is missing its `zipcmp` binary, breaks CMake's `find_package`; minizip is bundled and used instead, no functional loss). Configure: `cmake -B tools/mgba_src/build -S tools/mgba_src -DBUILD_HEADLESS=ON -DBUILD_QT=OFF -DBUILD_SDL=OFF -DCMAKE_BUILD_TYPE=Release -DUSE_LIBZIP=OFF`. **Empirically verified working** (not just read from source) against the real ROM this session: `emu:setBreakpoint(callback, addr)` fires correctly; `emu:addKey(n)`/`emu:clearKey(n)` genuinely drive the emulated GBA controller state (`getKeys()` bitmask observed changing `0→1→0`), fully independent of any host keyboard — this is a real TAS-style scripted-input mechanism, not host-input capture. `console:log()` routes through mGBA's normal logging and appears on stdout with the `Scripting:` prefix. GBA key bit indices (from `include/mgba/internal/gba/input.h`): A=0, B=1, SELECT=2, START=3, RIGHT=4, LEFT=5, UP=6, DOWN=7, R=8, L=9. Run via `./tools/mgba_src/build/mgba-headless --script <lua> [-t savestate] "rom/seaglass v3.0.gba"`; very verbose default BIOS/DMA/serial-IO logging, pipe through `grep` for a specific log prefix.
- Ghidra 12.0.2 + `pudii/gba-ghidra-loader` for static disassembly/decompilation. Set up and used (previous + this session) — reused `Unbound-Character-Mode/tools/ghidra/`'s already-installed copy directly (invoked its `support/analyzeHeadless` against this project's own `ghidra_project/`/ROM, rather than re-downloading/copying the ~847 MB install). No full-ROM auto-analysis run (deliberately — see `docs/ROUTINE_MAP.md`'s Ghidra setup section for why); everything is targeted, on-demand disassembly/decompilation of specific known addresses.

**Full toolchain is now set up AND the injection pipeline is empirically validated end-to-end (2026-07-12).** armips syntax for GBA (confirmed against the actual `tools/bin/armips` v0.11.0 build, not just docs): `.gba` sets the architecture, `.open "in.gba","out.gba",0x08000000` opens for output (two-filename form copies input→output first, leaving the source untouched), `.org <memory address>` seeks (GBA ROM maps 1:1 at `0x08000000`, so memory address = file offset + that base), `.ascii "text"`/`.db` for raw bytes (`.string` needs a `.loadtable`-loaded charmap first — plain ASCII should use `.ascii`), `.close` closes the file. Validated round-trip: wrote a marker string into free space via armips → `flips --create --bps` diffed it into a 74-byte patch → `flips --apply` to a fresh ROM copy reproduced a byte-identical file (SHA1-verified) → both the armips-built and patch-reapplied ROMs boot-tested cleanly via `mgba-headless` for 300 frames with identical CPU state, no crash. **Nothing left blocking hook-writing/patch-building once a confirmed hook site exists** — the remaining gap is knowledge (which exact address to hook), not tools, and that knowledge-gap-closing path (headless breakpoint+key-injection tracing) is now also self-service, gated only on one savestate (see Status).

## Status (2026-07-17 — PHASE 4/5: catch enforcement INJECTED + LIVE-TESTED + BPS)

**The core Character-Mode mechanic works in a real patched ROM.** Adapted
Lazarus's injection template (`src/character_mode.c`, `tools/inject_character_mode.py`)
to Seaglass's confirmed hook:
- `src/character_mode.c`: `CM_GiveMonToPlayerGated(mon)` — when CM on (FLAG 0x945
  + VAR 0x40E4) and the caught non-egg species isn't on the active roster, route
  to PC (`CopyMonToPC 0x081AA620`) instead of party (`GiveMonToPlayer 0x081AA5AC`).
  Compiles to a 180-byte position-independent Thumb blob.
- `tools/patches/inject_cm.asm` + `tools/build_cm.sh`: shim at free-space
  `0x08ED2164`; 8-byte **trampoline** at `0x08470200` (0xFF-padding scavenge, in
  BL range); retarget the wild-catch caller BL `0x080A6A46` → trampoline → shim.
  Total shipped-region edit = 4 bytes.
- **Live test (`cm_catch_test.lua`), same wild Zigzagoon, toggling only the CM
  flag**: CM off → caught to party (count 1→2); **CM on → same catch, off-roster
  mon blocked → PC (count stays 1)**. Controlled proof the gate works.
- `build/seaglass_cm.bps` created against the hack ROM, round-trip byte-identical.
  `sh tools/build_cm.sh` reproduces from source. Full writeup: `docs/INJECTION.md`.

**REAL 170-character roster now wired in** (`tools/character_mode/emit_bitmaps.py`
→ `rosters_expanded.bin`, base stages expanded through the donor evolution graph;
placed at ROM `0x08ED2400`; shim `onRoster()` = bit test). **Per-character
discrimination live-tested**: same wild Zigzagoon, CM on — char 1 (Red, off
roster) → blocked→PC (count 1); char 39 (Brendan, on roster) → party (count 2).
Remaining for a full playable game: **selection mechanism** (cheat-code
specials-table slot `0x0826DD68` → set CM flag/var + give signature starter),
then trades/sprites/tests/README. (Script-gift caller `0x081F18DE` now gated; egg-hatch `0x08188514` exempt.)

## Status (2026-07-16 — checkpoint #2 EXECUTED: catch enforcement hook CONFIRMED)

**The catch-handler question — Phase 1's highest-value unknown — is now SOLVED**,
by running Lazarus's recipe end-to-end on Seaglass:
- Gave Poké Balls via `give_pokeballs.lua` (AddBagItem `0x0814D2D0` → pocket table
  EWRAM `0x0200B0B8`, Poké Ball = item id 1) — the ROWE "give item" capability now
  works here.
- Caught a wild mon **fully headless** (weakened enemy to 1 HP + threw a ball;
  `catch_trace_sg.lua`, `MGBA_HEADLESS_DEBUGGER=1`), watchpoints on
  gPlayerPartyCount + slot1 fired and **partyCount went 1→2**.
- Pinned **GiveMonToPlayer = `0x081AA5AC`** (disasm self-confirms gPlayerParty
  `0x02019C20`, **gPlayerPartyCount `0x02019C1D`**, gSaveBlock2Ptr, memcpy
  `0x08368EF0`, SetMonData `0x081A9CA0`, GetMonData `0x081A94AC`).
- BL-scan → **exactly 3 callers** (matches Lazarus): **battle/catch `0x080A6A46`
  (PRIMARY Character-Mode hook)**, egg-hatch `0x08188514` (exempt), script-gift
  `0x081F18DE`. Full table + evidence in `docs/ROUTINE_MAP.md`; addresses in
  `harness.lua` (`H.GiveMonToPlayer`, `H.GiveMon_callers`).

This is the exact Phase-4 hook site. Remaining Phase-1-ish items: the selection
mechanism (check whether Seaglass has Nemo622's cheat-code system like Lazarus —
search game text for known codes), the `callnative` gift-site audit, and Phase 3
sprites. Then Phase 4 injection can begin against a confirmed hook.

## Status (2026-07-16 — Lazarus feedback checkpoint #1)

Four findings landed from the Lazarus sibling project (see `../Lazarus-Character-Mode/`):

1. **Headless breakpoints were never working — now fixed.** `emu:setBreakpoint` on stock `mgba-headless` returns -1 and never fires (`core->debugger` is never created; the "empirically verified" claim below covered callability only). Patched `tools/mgba_src/src/platform/headless-main.c` to attach a module-less debugger when **`MGBA_HEADLESS_DEBUGGER=1`**; rebuilt. Verified firing (61 FlagGet round-trips traced). **`headless_catch_trace.lua` / the 6 catch candidates are now runnable headlessly** — the "needs GUI + human" conclusion is obsolete. Env var only for trace runs (breakpoints armed = single-step slowdown).
2. **TRUE flags/vars offsets found and live-verified** (via the script command table, located with `../Lazarus-Character-Mode/tools/find_script_cmd_table.py`): **flags = SB1+0x13C0, vars = SB1+0x14EC**; FlagGet `0x0810D35C`, FlagSet `0x0810D254`, GetVarPointer `0x0810D0C0`, cmd table `0x0826D970` (0xE7 cmds). See `docs/ROUTINE_MAP.md`'s new "Script engine" section.
3. **Catch-trace recipe now PROVEN on Lazarus (checkpoint #2 ready here)**: don't chase the 6 string-anchor candidates — arm `emu:setWatchpoint(cb, gPlayerPartyCount, 5)` + slot-1 write watchpoints (`MGBA_HEADLESS_DEBUGGER=1`), catch a mon headlessly, and the faulting PC lands inside GiveMonToPlayer directly; then a whole-ROM Thumb BL scan enumerates every caller (Lazarus had exactly 3: battle-catch, daycare/hatch, ScriptGiveMon). Seaglass's gPlayerParty/count are already known (`0x02019C20`/stride 100 — count likely 3 bytes before, verify). Lazarus's ball-shortage fix also transfers: AddBagItem (via cmd-table entry 0x44) → pocket table + qty-XOR-key (SB2+offset) → Lua-write Poké Balls. See `../Lazarus-Character-Mode/docs/ROUTINE_MAP.md` + `tools/mgba_scripts/{catch_trace,give_pokeballs}.lua`.
4a. **(2026-07-16 later, Lazarus Phase 4 wins — more transferable methods.)** (i) **Donor specials.inc INDEX ordering transfers**: Lazarus's trade specials sat at exactly the donor's indices 0xFF/0x100/0x101 in the specials table (base found from cmd-0x25 handler literal; special ID = (slot−base)/4) → `sIngameTrades` from the create-fn's literal pool in minutes. Try the identical route here for trades and any other special. (ii) **Cheat-code system anatomy** (Seaglass may have one too — search game text for its known codes): string table → dispatcher special (StringCompare chain → VAR_RESULT) → script-side switch; specials-table slot replacement = perfect selection hook, no BL constraints. (iii) **Custom givemon lives behind `callnative`** on this engine family (vanilla cmd 0x79 re-tabled to nop): search u32 refs to the native fn to enumerate ALL script gift sites; gifts do NOT go through GiveMonToPlayer (native inserts into party directly) — enforcement needs a post-check wrapper on those callnative pointers. (iv) MON_DATA enum: SPECIES=18 matched the donor exactly on Lazarus (verify per-ROM via GiveMonToPlayer's slot-probe constant). See `../Lazarus-Character-Mode/docs/SELECTION_MECHANISM.md` + `docs/ROUTINE_MAP.md`.
4. **The 2026-07-15 gate finding was misattributed** (flags base 0x157E is wrong): the bisection's byte `+0x158C` bit4 was actually **var 0x4050 |= 0x10**, and the Littleroot gate is a coord trigger keyed on var 0x4050 == 0 (block script `0x0827DC4A` push-back), not flag 0x74 (live-disproven). All downstream results (starter, `gPlayerParty`, savestates) remain valid — the poke passed the gate for the right reason under the wrong name. `harness.lua` (FLAG_BLOCK/VAR_BLOCK + new `H.setVar/getVar`), `goto_grass.lua`, `reach_starter.lua` corrected.

## Status (2026-07-15)

**Phase 1 live-tracing prerequisites — big step this session: autonomous headless play now works, and the save-block trio is disambiguated.**

- **`emu:screenshot()` now works in headless** (patched `tools/mgba_src/src/platform/headless-main.c` to allocate a video buffer after `mArgumentsApply` — stock headless leaves it NULL and segfaults; rebuilt). This removed the dependency on a **user-provided savestate** — this Claude instance can now *see* the game and navigate it itself.
- **SaveBlock pointer trio DISAMBIGUATED** (`probe_saveblock.lua`): `0x030051B8` = **gSaveBlock1Ptr** (`+0x00 pos.x`, `+0x02 pos.y`, `+0x04 mapGroup`, `+0x05 mapNum`), `0x030051BC` = gSaveBlock2Ptr (playerName field first), `0x030051C0` = gPokemonStoragePtr. Recorded in `harness.lua`. Reading live `(x,y,map)` makes navigation deterministic.
- **Entire intro navigated headlessly** with checkpoints (`tools/savestates/*.ss`, gitignored): truck (25.40) → Littleroot (0.9) → house 1F/2F → **wall clock set** (full minigame; it IS a hard gate) → TV event → neighbor's house (1.2) → **Birch's LAB (1.4)**. Maps + exact route + tile geometry in **`docs/INTRO_NAVIGATION.md`** (new). New nav toolkit: `nav_coords.lua` (workhorse), `drive_intro.lua`, `wait_shot.lua`, `probe_saveblock.lua`, `set_flag_probe.lua`, `scan_saveblock.lua`.
- **Starter mechanic confirmed** = vanilla Route 101 Birch rescue (decoded script text at ROM 0x00284756–0x002847CE: "…In my BAG! There's a POKé BALL!" → "PROF. BIRCH: …You saved me!… come by my LAB later"). Birch is OUT (lab has only aides).
- **Gate cracked + STARTER OBTAINED autonomously.** Littleroot's north exit was flag-gated (decoded script @0x0827DBEF: `checkflag 0x74 → pass; checkflag 0x52 → pass; compare var 0x4050,0 → pass if !=0; else block "Um, um, um!"`). **Flags-array base found = SaveBlock1+0x157E** (flag N → byte 0x157E+N//8, bit N%8) by *bisecting the gate itself* (`gate_test.lua`: set bit4 across a byte range, walk to exit, check for map 0.16=Route 101; narrowed to byte 0x158C bit4 = flag 0x74). Empirical offset guesses + literal-pool disassembly both failed; gate-bisection was decisive. Set flag 0x74 → gate opens → Route 101 → **Birch rescue** → picked **Torchic** → won the Poochyena battle → Birch's lab. Checkpoints: `route101.ss`, `have_starter.ss`.
- **`gPlayerParty` = 0x02019C20** (stride **100**). Found by OT-ID match (SaveBlock2+0x0A = 0x99BDB9EF) then disambiguated by ROM literal-ref count (577 refs vs 3 for the two transient copies). `gEnemyParty` candidate = 0x02019E78 (adjacent, unverified). Recorded in `harness.lua` with `H.setFlag/getFlag` helpers. This unlocks the "Give Pokémon"/state-mutation half of the harness.
- **NEXT**: escape the lab aide-dialogue loop → free overworld → walk into Route 101 grass → wild battle → run `headless_catch_trace.lua` to ID the catch handler (the last Phase-1 unknown). Then Phase 3 (sprites) + Phase 4 (injection). See `docs/INTRO_NAVIGATION.md`.

## Status (2026-07-12)

**Phase 0/1 blocked — no ROM supplied yet.** Seaglass is distributed exclusively as a patch applied to a clean USA Emerald ROM; no ROM or patch file exists anywhere in this workspace as of this checkpoint. Do not attempt to source the ROM/patch on the user's behalf — wait for the user to place it at `rom/`.

**Phase 2 (roster data pipeline) — Stage A done, Stage B blocked on Phase 1.**
- `characters.txt`: 182 characters (full Gen 1-9 breadth, based on ROWE's list, not Unbound's trimmed copy).
- `scrape_rosters.py`: run cleanly against the seeded ROWE cache — 182/182 scraped, 0 missing pages, 0 empty rosters, effectively 0 new Bulbapedia requests.
- `map_species.py`: Stage A run cleanly — 182/182 characters mapped, **0 unmatched names, 0 empty rosters**, 505 distinct base-stage species resolved against the `pokeemerald_expansion_donor` clone's name/evolution-topology data. Every `species_id` is the literal string `"PENDING_PHASE1"` (Stage B not run — see `docs/DONOR_CROSSWALK.md`'s numeric-id caveat). Known limitation, documented in the script: a handful of macro-generated multi-form species (Scatterbug→Spewpa→Vivillon chain, some Flabébé/Floette/Florges color-form chains) don't fully reduce to their true evolutionary base — acceptable for provisional Stage A data, worth spot-checking in `roster_review.csv` before Stage B locks in real ids.
- `emit_characters.py`: `--dry-run` (default) validates roster completion/ordering and writes `names.bin` (final content) + `characters_manifest.json` — 182/182 validated, 0 skipped, 0 all-legendary warnings. Full Gen 1-9 `LEGENDARY_BASES` restored (verified: e.g. Pecharunt correctly appears in an emitted roster as a legendary, not a starter). `--final` mode is wired up and correctly refuses to run until Stage B fills in real ids (tested: errors out citing 506 pending species).

**Phase 0 — DONE.** ROM supplied by the user (`seaglass v3.0.zip`, a single raw `.gba`, already patched — not a base+patch pair). Extracted to `rom/seaglass v3.0.gba`, SHA1 `b9f4d332d30fc88c379f9e037f9eae3b2755ead4` (see `rom.sha1`, `docs/ROM_INFO.md`). Header confirms `POKEMON EMER` / `BPEE` / standard 16 MiB (unexpanded) Emerald USA base.

**Phase 1 — free space and species table located; routine mapping not started.**
- Free space: one contiguous 1.18 MiB 0xFF-padded block at `0x00ED2164`-EOF. See `docs/FREE_SPACE.md`. Not expected to be a bottleneck.
- **Major finding — species table located, revealed a scope problem, now resolved.** `gSpeciesInfo`-equivalent struct array found at base `0x008F07AC`, 208-byte stride, name field first in each record, array index = National Dex number for the whole Gen 1-3 contiguous block (verified). Full table dumped to `tools/character_mode/rom_species_table.json` (502 real species slots, indices 0-1488). **Seaglass has all of Gen 1-3 plus only a small curated set of later-gen additions (mostly cross-gen evolutions of Gen 1-3 species) — not anywhere near a full Gen 1-9 dex.** Cross-checking the original 182-character roster found only 39% of required species present, with 5 characters at 0 catchable species and 7 more at exactly 1. **User decision (2026-07-12): trim the 12 fully/nearly-broken characters, keep everyone else as-is.** `characters.txt` now has 170 characters; re-ran Stage A clean (0 empty rosters, 0 unmatched names); post-trim real-ROM cross-check shows 0 characters with ≤1 catchable species, 8/170 fully intact, 53.9% average completeness. Full writeup in `docs/SPECIES_CAP.md`.
- **Routine mapping — strong progress, Ghidra now set up and used.** Started with `search_gametext.py`/`decode_gametext.py`/`find_pointer_refs.py` to find string/pointer anchors, then installed-by-reuse Ghidra (see Toolchain) and disassembled/decompiled the specific candidate addresses:
  - **Catch mechanic**: `gBattleStringsTable`-equivalent located (base `0x4C9A44`, 701 entries), "Gotcha!" at table index 255/256 (matches donor's `STRINGID_GOTCHAPKMNCAUGHTPLAYER`/`WALLY` adjacency). All 8 XREF call sites disassembled+decompiled — all real, coherent code, consistently indexing a 0x28-byte-stride struct and setting a "next battle string" field, sharing a common helper `func_0x08087328`. Each ends in an unrecovered indirect jump table (one case of a larger dispatcher) — **exact catch-success case still not isolated**; next step is `mgba-qt` live tracing rather than more static analysis.
  - **Title screen / mode-select menu**: found the real `NEW GAME`/`CONTINUE`/`OPTION`/`MYSTERY GIFT`/`MYSTERY EVENTS` menu and two option-tables (`0x160DB8`, `0x160F00`). **Correction**: the 4 addresses that looked like function pointers (`0x8693020`-`0x8693030`) are actually even (data, not code — real Thumb function pointers are always odd); disassembling them produced garbage, confirming the mistake. The **real** function pointers are the odd-addressed `0x08160F1D`/`0x0815E6A9`. Decompiled `FUN_08160ebc` (the first): sets up 4 menu-item UI elements (8-byte stride) and stores a pointer back into the same table — strong, clean lead for the mode-select hook.
  - **PC storage**: traced the `HALL OF FAME`/`LOG OFF` literal pool to a real function `FUN_081f0a40`, which hands off to `FUN_081f0420` — decompiled and found it dispatches on 6 sequential byte codes (`0x4A`-`0x4F`, matching the 6 PC-menu options) before calling `func_0x081f10d0`. Real dispatcher found; the lower-level "add to PC box" primitive (`func_0x081f10d0`) is one more hop away, not yet traced.
  - **Trade**: found genuine NPC trainer-trade dialogue at `0xA48A00` (not yet pointer-searched).
  - **Mystery Gift**: found the dialogue bank at `0x30F550`+, tied to Route 111's "weird tree" event and gift-Pokémon PC-transfer messages (not yet pointer-searched).
  - Full detail, exact offsets, and decompiled code in `docs/ROUTINE_MAP.md`, including a status summary table. **Important note for future sessions**: addresses passed to `InspectRegions.java`/`DecompileFunc.java` need the full `0x08000000` GBA base prefix (Unbound's own script usage comment saying otherwise did not work here).
  - **2026-07-12 follow-up session**: traced `func_0x081f10d0` one more hop — turned out to be a generic task-dispatch trampoline (`FUN_081f1070`, likely a `CreateTask`-equivalent handoff), not the actual "add to PC box" primitive; that primitive is one more hop into task-engine internals not visible from this call site, and further static chasing was judged lower-value than switching to live tracing. Pointer-searched the Trade dialogue string anchor (`0xA48A00`+) — found one real XREF whose target, `FUN_082206ac`, hits the exact same unrecoverable-jump-table wall as the catch mechanic (useful confirmation these are all cases of the same underlying dispatcher architecture, not a new lead). Pointer-searched the Mystery Gift dialogue bank (13 exact string offsets) — 12/13 have no raw pointer reference (expected: likely field-map script-bytecode-addressed, not literal-pool-addressed), but the 1 hit (`You haven't received the GIFT`) led to a real, fully decompiled function (`FUN_08171a38`) confirming that dialogue path is live code. **Conclusion validated across every subsystem touched this session: static analysis has hit its ceiling; live mGBA tracing is the correct next tool for all of catch/trade/PC-storage disambiguation, not just catch.**
  - **Toolchain fully set up 2026-07-12**: `armips`/`flips` copied in from Unbound (same reuse pattern as Ghidra); `arm-none-eabi-gcc`/`mgba-qt` confirmed already system-installed. `tools/mgba_scripts/trace_catch_mechanic.lua` written — a ready-to-run breakpoint-and-log script for the 6 catch-mechanic candidates, using mGBA's real scripting API (verified against mGBA 0.10.2's own `src/core/scripting.c` source on GitHub, not guessed) — **not yet execution-tested**, since that needs the GUI and a live catch attempt.

**Phase 2 — FULLY DONE (2026-07-12, later session).** Stage A: 170/170 characters mapped, 0 unmatched, 0 empty rosters. **Stage B (new): 204/505 distinct species consts resolved to real ROM ids** by matching each species' canonical name directly against `rom_species_table.json`'s own dumped name table (not the donor's numeric ids — those remain untrusted per the standing rule). 301 species genuinely absent from this ROM (`stageb_unmatched.txt`) — count closely matches the earlier informal 197/505 estimate, cross-validating both. 13 species had multiple ROM-table matches (regional/alt forms); lowest index picked each time (spot-checked, all correct — matches the base/Kanto form every time). Re-checked per-character completeness after real resolution: **still 0 characters at 0-1 catchable species** — the earlier trim already anticipated this correctly, no further `characters.txt` changes needed. `emit_characters.py --final` now **builds successfully**: 170 characters, 0 skipped — `characters.bin` (2,040 B), `rosters.bin` (4,492 B), `names.bin` (1,110 B). `sprite_asset_id` still `0xFFFF` placeholder pending Phase 3. Full writeup in `docs/SPECIES_CAP.md`'s "Stage B — DONE" section.

**Phases 3-6: not started.** Phase 3 (sprite/trainer-pic coverage) and Phases 4-6 (actual code injection, patch assembly, playtesting) are the remaining work toward the standing "playable ROM" goal — see Roadmap below.

## Roadmap to playable (status as of 2026-07-17)

- **Phase 0 — ROM pinned. DONE.** (`rom.sha1`, `docs/ROM_INFO.md`.)
- **Phase 1 — RE. DONE (core confirmed).** Free space, species table, SaveBlock trio, flags/vars offsets (SB1+0x13C0 / +0x14EC), gPlayerParty/count/EnemyParty, and — the big one — **the catch/gift enforcement surface: GiveMonToPlayer `0x081AA5AC` + its 3 callers (battle/catch `0x080A6A46`, egg-hatch `0x08188514`, script-gift `0x081F18DE`), CopyMonToPC `0x081AA620`** — all live-verified. The selection mechanism (cheat-code system) is LOCATED but its matcher/code-table aren't pinned. All in `docs/ROUTINE_MAP.md` + `harness.lua`.
- **Phase 2 — roster pipeline. DONE.** 170 characters, real ROM ids, + `emit_bitmaps.py` → per-character allowed-species bitmap (base rosters expanded through evolution families).
- **Phase 3 — sprites. NOT STARTED (task #10).** Needed for character-select portraits; `sprite_asset_id` in `characters.bin` still a placeholder. Not blocking enforcement.
- **Phase 4 — injection. DONE for acquisition enforcement; selection remaining.** ✅ Catch + script-gift gated by the real roster bitmap, injected, **live-tested with per-character discrimination** (Red blocks Zigzagoon, Brendan allows it). ❌ **In-game selection UI** — CM flag/var (`FLAG 0x945`, `VAR_CM_CHAR 0x40E4`) are set via RAM in tests; still need to hook the cheat-code matcher's specials-table slot (`gSpecialsTable 0x0826DD68`) so character-name codes set them + give the signature starter (Lazarus's `CM_CheatDispatchHook` is the template). ❌ trade gating.
- **Phase 5 — BPS. DONE for the current build.** `build/seaglass_cm.bps` round-trips byte-identical; `sh tools/build_cm.sh` reproduces.
- **Phase 6 — regression suite + "no bugs" playtest. PARTIAL.** The enforcement path has a controlled live test (`cm_catch_test.lua`); a full suite (à la Lazarus's 4 layers: GDB unit tests, boot smoke, static artifact checks, live e2e) is not built. Once selection is injected, this becomes the gate to "playable." Lazarus found 2 real bugs in its equivalent step (stale activation marker; phantom nickname prompt on wrapper-boxed gives) — watch for the analogues here.

## Testing (read `docs/TESTING.md` before doing test work)

Testing methodology is a deliberate port of ROWE's, adapted for a closed binary. ROWE compiled an in-game debug menu (`src/debug.c`: Give Pokémon, set `VAR_CHARACTER_ID`, toggle `FLAG_SYS_NO_CATCHING`, warp, PC access) and drove it by hand via `mgba-qt`+`xdotool`+screenshots, with no automated harness. We can't compile a menu into a closed binary, so every debug-menu *capability* is reproduced from outside via mGBA scripting on `mgba-headless`: RAM read/write (= give Pokémon / set var / set flag), scripted controller input (= the human pressing buttons), plus breakpoints and assertions (which ROWE's menu could not do at all). Deterministic and repeatable, unlike ROWE's manual passes.

**Verified working** (empirically, against the real ROM — not assumed): `emu:addKey`/`clearKey` genuinely drive the emulated pad; `emu:read/write8/16/32` round-trip on live EWRAM; `emu:setBreakpoint` fires **only with `MGBA_HEADLESS_DEBUGGER=1`** (2026-07-16 correction: on stock headless it returns -1 and silently never fires — see Status). **Confirmed RAM anchor**: the save-block pointer trio at `0x030051B8`/`0x030051BC`/`0x030051C0` (the 3 most-referenced consecutive IWRAM words in the ROM; zero at boot, EWRAM pointers by frame ~240 — the expansion `gSaveBlock2Ptr`/`gSaveBlock1Ptr`/`gPokemonStoragePtr` shape; **which-is-which now pinned (2026-07-15): `0x030051B8`=gSaveBlock1Ptr, `0x030051BC`=gSaveBlock2Ptr, `0x030051C0`=gPokemonStoragePtr** — see 2026-07-15 Status).

**Critical**: vanilla Emerald's RAM map does NOT hold here — `gPlayerParty` (`0x020244EC`), `gSaveBlock1Ptr` (`0x03005D8C`) etc. have **zero** literal-pool references in this ROM. Never assume vanilla addresses; confirm empirically. `harness.lua` leaves unconfirmed addresses `nil` and fails loudly rather than poking a guess.

**Two hard-won gotchas**: (1) never pipe `mgba-headless` through `grep | head` — `timeout`-killing it loses all buffered output to SIGPIPE and looks like the script produced nothing; redirect to a file, then grep it. (2) Bulk-read RAM with `emu:readRange(addr, len)` (returns a Lua string); looping `emu:read8` over 256 KB of EWRAM stalls the emulator so hard the frame callback never returns.

NEXT (now fully self-service — no longer blocked on a user savestate, thanks to the headless-screenshot patch + coordinate navigation). Get a **starter into the party**, which unlocks catch-handler ID + `gPlayerParty` in one shot:

0. **Pass the Route 101 north gate** (the immediate blocker — see 2026-07-15 Status). Find Seaglass's SaveBlock1 **flags-array offset** (disassemble `FlagGet` / the `checkflag` primitive, whose immediate is `offsetof(SaveBlock1, flags)`; or diff SaveBlock1 across a known flag toggle — `scan_saveblock.lua` helps). Then `set_flag_probe.lua` sets flag 0x74 at that offset → gate says "Good luck!" → walk north to Route 101 → Birch rescue → **pick a starter**. Record the offset in `harness.lua` (`H.FLAG_BLOCK`); it also unlocks the catching-toggle + `VAR_CHARACTER_ID` equivalents. Resume from `tools/savestates/outside_house.ss` (or `lab_interior.ss`).
1. **`gPlayerParty` + struct stride** — once a starter exists, run
   `./tools/mgba_src/build/mgba-headless --script tools/mgba_scripts/find_ram_anchors.lua -t <state-with-party> "rom/seaglass v3.0.gba" > /tmp/a.log 2>&1; grep ANCHOR /tmp/a.log`
   (redirect, don't pipe — see gotcha). Unlocks the "Give Pokémon"-equivalent state mutation in `harness.lua`.
2. **Catch-handler identification** — navigate into Route 101 tall grass → wild battle → run `headless_catch_trace.lua` (same command shape). Identifies the real catch-success handler among the 6 candidates in `docs/ROUTINE_MAP.md`. Highest-value remaining Phase-1 unknown.

Parallel self-service work if the gate proves stubborn: Phase 3 (sprite/trainer-pic table location) — same static-analysis technique as Phase 1, no savestate needed.

**Commit note**: repo initialized + first commits made 2026-07-15 (per explicit user request). ROMs/savestates/third-party clones stay gitignored (`rom/*.gba`, `tools/savestates/`, `tools/mgba_src/`, etc.). Keep committing on explicit request only, per standing policy.
