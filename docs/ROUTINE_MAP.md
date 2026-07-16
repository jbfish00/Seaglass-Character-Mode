# Routine Map — seaglass v3.0.gba

The project's substitute for a public symbol table. Every finding is tagged:
- **CONFIRMED** — address verified by trace/patch-and-observe (code located and behavior proven).
- **CODE FOUND** — a literal pool or instruction stream was actually located and read (not just a data XREF), strongly implying the surrounding function, but not yet confirmed by disassembly/trace.
- **STRING ANCHOR** — a data string is located and its content strongly implies which subsystem/dialogue it belongs to; the *code* that reads/displays it is not yet located. Next step is Ghidra XREF analysis or an mGBA read-watchpoint.
- **LIKELY** — inferred from the pokeemerald-expansion donor's source shape, not yet verified against this binary at all.
- **UNKNOWN** — not yet investigated.

All offsets below are **file offsets** into `rom/seaglass v3.0.gba` (pinned to `rom.sha1`, see `docs/ROM_INFO.md`). GBA ROM is memory-mapped at `0x08000000`, so the in-emulator/Ghidra address = file offset + `0x08000000`.

Text was located with `tools/search_gametext.py` (Gen3-charmap string search, reusing ROWE's `charmap.txt`) and read with `tools/decode_gametext.py`. The charmap was sanity-checked against a known vanilla species name (`Bulbasaur`, title case) before trusting any hit. Pointer references found with `tools/find_pointer_refs.py` (raw 4-byte-LE pointer scan — GBA code/data reference strings via plain pointers in literal pools and data tables, so this works without needing disassembly).

## Ghidra setup (2026-07-12)

Reused Unbound's already-installed Ghidra 12.0.2 + `pudii/gba-ghidra-loader` (invoked directly from `Unbound-Character-Mode/tools/ghidra/support/analyzeHeadless` rather than re-downloading/copying the ~847 MB install — Ghidra's headless analyzer takes project/file paths as arguments and doesn't care where its own install lives). Imported with `-noanalysis` (fast — full auto-analysis on a similarly-sized ROM timed out for Unbound without reaching the regions of interest); analysis is entirely on-demand via `tools/ghidra_scripts/InspectRegions.java` (force-disassembles a window around a known address in Thumb mode and identifies/creates the containing function) and `DecompileFunc.java` (runs the decompiler on a function). Ghidra project lives at `ghidra_project/SeaglassCM.gpr` (gitignored).

**Important correction vs. Unbound's script usage comment**: addresses passed to both scripts must include the full `0x08000000` GBA base (e.g. `0811FFA4`, not `0011FFA4`) — Unbound's own script comments say "without the base" but that did not work here (produced empty disassembly/no function found every time); prefixing with the base worked immediately. Use the full address form.

## Script engine + flags/vars — CONFIRMED (2026-07-16, via the Lazarus feedback loop)

Found with `../Lazarus-Character-Mode/tools/find_script_cmd_table.py` (scans for
the donor ScriptContext-init signature: cmdTable and cmdTableEnd as two
adjacent literal-pool words, pointing at a dense run of odd Thumb pointers).
Single clean hit; entries 0x29/2A/2B are the classic 16-byte
setflag/clearflag/checkflag handler trio (decoy-proof). All ROM addresses
(subtract `0x08000000` for file offsets):

| Symbol | Address | Evidence |
|---|---|---|
| gScriptCmdTable | `0x0826D970`, 0xE7 (231) cmds, end `0x0826DD0C` | 4 literal-pool XREF pairs at file `0x1EF54C/0x1EF5DC/0x1EF654/0x1EF7B4` |
| ScriptReadHalfword | `0x081EF488` | called by all flag/var handlers |
| FlagSet | `0x0810D254` | bl target of setflag handler `0x081ED0C9` |
| FlagClear | `0x0810D304` | bl target of clearflag handler `0x081ED0D9` |
| FlagGet | `0x0810D35C` | bl target of checkflag handler `0x081ED0E9`; **live-verified**: entry/exit breakpoints predicted 61/61 return values from `sb1+0x13C0` (verify_flags_offset.lua, 2 savestates) |
| GetVarPointer | `0x0810D0C0` | from setvar handler `0x081ECC81` (cmd 0x16) |

**SaveBlock1 layout: flags at `+0x13C0` (0x12C bytes), vars at `+0x14EC`.**
Special flags (≥0x4000) at EWRAM `0x020055FC`. Both primitives deref
gSaveBlock1Ptr `0x030051B8`. Lazarus's offsets (`+0x12E8`/`+0x1414`) do NOT
transfer — same-author builds differ; the *method* transfers.

**Correction to the 2026-07-15 gate finding**: the bisection hit "flags base
+0x157E / flag 0x74 = byte +0x158C bit4" was actually **var 0x4050 |= 0x10**
(`0x158C = 0x14EC + 2*0x50`). The Littleroot north gate is a **coord trigger
keyed on var 0x4050** (fires while ==0) running an unconditional block script
@`0x0827DC4A` ("Um, um, um!" + applymovement push-back); the checkflag-0x74
script @`0x0827DBEF` is a different object's script and setting real flag 0x74
does NOT open the gate (live-tested: blocked with `sb1+0x13CE bit4` set, write
persisting to gate time). The game's own pass path sets var 0x4050 = 2.
`harness.lua` FLAG_BLOCK/VAR_BLOCK corrected; `goto_grass.lua` now uses
`H.setVar(0x4050, 2)`.

**Headless breakpoints now WORK** (this is what made the live verification
possible): stock `mgba-headless` never creates `core->debugger`, so
`emu:setBreakpoint` always returned -1 and silently never fired — every prior
breakpoint-based trace conclusion ("needs the GUI + a human") was built on a
dead API. Patched `tools/mgba_src/src/platform/headless-main.c` (2026-07-16)
to attach a module-less debugger when **`MGBA_HEADLESS_DEBUGGER=1`** is set;
rebuilt. Free while no breakpoints are armed; single-steps once they are.
**This unblocks `headless_catch_trace.lua` / the 6 catch candidates below.**

## Selection mechanism — cheat-code system LOCATED (2026-07-16; the Phase-4 character-select hook, per Lazarus's design)

Seaglass ships Nemo622's native **"CHEAT DEVICE" / "GIFT CODE"** system (same
family as Lazarus's Acrisia cheat codes) — the intended character-select hook:
replace one specials-table pointer to add character-name codes, everything else
additive free-space (Lazarus proved this exact route works).

| Piece | Address | Detail |
|---|---|---|
| **gSpecialsTable** | **`0x0826DD68`** | from `ScrCmd_special` (cmd 0x25 @ table) literal @`0x081EC89C`; special ID → slot `0x0826DD68 + 4*id` |
| Cheat-code entry script | `0x08311C32`+ | uses `special`/`specialvar` 0x1E5/0x1E6/0x1E7/0x1EC + a `compare VAR_RESULT(0x800D),k` match switch |
| Prompt/result text bank | `~0x00311A23`–`0x00311C20` | "turned on the CHEAT DEVICE! Prepare a GIFT CODE… enter a code?", "Please enter the code.", "The code was valid!/invalid!/already redeemed!", "[player] received a [item]!" (one code = show all in DexNav) |
| special 0x1E5 | `0x08215B24` | builds a caught/received-mon summary (GetPartyMon+GetMonData) — a display helper, NOT the matcher |
| special 0x1E7 | `0x08135BAC` | redeem-once guard (FlagGet→FlagSet) |

**Next (Phase-4 selection)**: parse the entry script fully to pin the
DoNamingScreen entry special + the StringCompare matcher + the code-string table
(Lazarus's were entry 0x221 / match 0x222 / table `0x087D9294` — IDs differ
here, same-author builds vary), then design the injection = overwrite the
matcher's specials-table slot with a CM function that (native match first, else
match our character-name codes → set CM char var + give signature starter). Full
template: `../Lazarus-Character-Mode/docs/SELECTION_MECHANISM.md`.

## Catch/give enforcement — CONFIRMED via live headless catch trace (2026-07-16, using Lazarus's method + the fixed headless breakpoints)

**This supersedes the "6 string-choice candidates" approach below.** The real
Character-Mode enforcement point is **GiveMonToPlayer** (the party-add function),
not the battle-string dispatcher. Found by the Lazarus recipe: give Poké Balls
(RAM), catch a wild mon fully headless, and set a **write-change watchpoint**
(`emu:setWatchpoint(cb, addr, 5)`, needs `MGBA_HEADLESS_DEBUGGER=1`) on
`gPlayerPartyCount` + party slot1. The catch fired both watchpoints and
`partyCount` went 1→2 (`catch_trace_sg.lua`, `after_catch.ss`).

| Symbol | Address | Evidence |
|---|---|---|
| **GiveMonToPlayer** | **`0x081AA5AC`** (Thumb; BL target) | disassembled: loads gSaveBlock2Ptr, SetMonData OT-id/name into the mon, scans 6 party slots for empty (GetMonData species==0), memcpy mon (stride 100), `strb ++count`. Literal pool self-confirms gPlayerParty `0x02019C20`, **gPlayerPartyCount `0x02019C1D`**, gSaveBlock2Ptr `0x030051BC` |
| SetMonData | `0x081A9CA0` | 3 calls in GiveMonToPlayer (OT_ID=7, OT_NAME=0x38, field 2) |
| GetMonData | `0x081A94AC` | empty-slot scan (species field 18) |
| CopyMon (memcpy) | `0x08368EF0` | mon copy into slot, r2=0x64; WP slot1 fired here |
| AddBagItem | `0x0814D2D0` | from ScrCmd_additem (cmd 0x44 @ table); pocket table EWRAM `0x0200B0B8` stride 8, Poké Ball=item id 1, slot {u16 id, u16 qty^key} — `give_pokeballs.lua` |

**The 3 (and only 3) callers of GiveMonToPlayer** — the complete catch/gift
enforcement audit surface (BL-scan; mirrors Lazarus's 3 exactly):

| Caller | Address | Role | Character-Mode action |
|---|---|---|---|
| **battle/catch** | **`0x080A6A46`** | `mon = r5 + slot*100; r0=mon; bl GiveMonToPlayer; cmp r0,#0; beq …` (return 0=party, else PC) | **PRIMARY HOOK** — gate here: if caught species ∉ active character's roster, redirect to PC / block |
| daycare/egg-hatch | `0x08188514` | egg-hatch give (field 22/38 reads) | exempt (grandfather/egg semantics, RR/Lazarus parity) |
| script-gift | `0x081F18DE` | ScriptGiveMon (sets field 52=IS_EGG before give) | gate in-game gift Pokémon |

This closes the highest-value Phase-1 unknown (catch enforcement) and gives the
exact Phase-4 hook site. Recorded in `harness.lua`.

## Catch mechanic (SUPERSEDED string-dispatcher investigation) — CODE FOUND, exact handler undetermined

File offset `~0x4C6918`–`0x4C69A8` decodes to the full vanilla-shaped Emerald catch-sequence string bank, contiguous and in the expected order:
```
Gotcha! [X] was caught!
Gotcha! [X] was caught! (variant — matches donor's STRINGID_GOTCHAPKMNCAUGHTWALLY, the scripted-tutorial-catch variant)
Give a nickname to the captured [X]?
[X] was sent to [Y]'s PC.  /  someone's  /  LANETTE's   <- "LANETTE" (not "Bill's") confirms Emerald, not FireRed
[X]'s data was added to the POKéDEX!
It is raining. / A sandstorm is raging.  (weather-affects-catch-rate flavor lines, same bank)
The BOX is full! You can't catch any more!
```
This is the same shape Unbound found for FireRed/CFRU, here confirmed Emerald-flavored (Lanette's PC, not Bill's). Good sign Seaglass's catch subsystem hasn't diverged from a vanilla/expansion-shaped compile at the message layer.

**Located the actual `gBattleStringsTable`-equivalent pointer table**: base `0x004C9A44`, end (exclusive) `0x004CA538`, **701 entries** (4-byte pointers, contiguous valid `0x08xxxxxx` range) — found by pointer-searching for XREFs to the "Gotcha!" string (`0x4C6918`) and its two neighbors, which landed at three consecutive table slots (`0x4C9E40`/`0x4C9E44`/`0x4C9E48`, i.e. table indices **255/256/257**). Cross-checked against the `pokeemerald_expansion_donor`'s `include/constants/battle_string_ids.h`: `STRINGID_GOTCHAPKMNCAUGHTPLAYER` is immediately followed by `STRINGID_GOTCHAPKMNCAUGHTWALLY` in that enum too — the adjacency matches, even though the donor's own numeric values won't necessarily equal 255/256 (fork divergence, expected — see `docs/DONOR_CROSSWALK.md`).

**XREFs to the table base** (`0x4C9A44`) — 8 call sites found:
```
0x00087108  0x00088268   <- two outliers, far from the rest
0x0011FFA4  0x00120364  0x00120594  0x00120934  0x00120D30  0x00120E18   <- dense cluster, ~3.5 KB span
```
**Disassembled and decompiled all 6 clustered call sites plus the 2 outliers.** All are real, coherent Thumb code with sensible control flow — no garbage/misaligned decode anywhere, a good general sign this region of the ROM is intact vanilla/expansion-shaped code. Key findings:
- `FUN_0811ff44`, `FUN_08120304`, `FUN_08120534`, `FUN_081208d4`, `FUN_08120cd0`, `FUN_08120db8` all index into what's consistently a **0x28-byte-stride struct array** (`unaff_rX * 0x28`, `unaff_rX + unaff_rY * 0x28`), each writing a small constant (`0xc`, `0xb`, `8`, ...) to offset `0x14` of the indexed record — this is the classic shape of a **"set next battle-string-choice index"** state machine (matches pret's `gBattleCommunication[MULTISTRING_CHOOSER]` pattern conceptually, though the exact struct isn't pret's — Seaglass/the underlying expansion has evidently repacked this).
- `FUN_08120534` and `FUN_08120cd0` both call **`func_0x08087328`** right before touching the string-choice index — this is almost certainly a shared "prepare/expand string placeholders" helper (pret's `PrepareStringFromBuffer`/`BattleStringExpandPlaceholders`-equivalent), called immediately before any of these battle strings gets displayed. Its address matches the "outlier" `0x08087108`/`0x08088268` XREF hits from the earlier pointer search — those outliers are XREFs to *this* shared helper being called from elsewhere in the same subsystem, not a separate catch-specific handler.
- Every one of these functions ends in an **unrecovered indirect jump table** (`Could not recover jumptable... Too many branches`) — meaning each is one **case** of a larger switch/dispatcher (very likely the real `HandleBattleScriptCommand` or `MULTISTRING_CHOOSER`-setting switch), not a standalone catch handler. Ghidra's targeted (`-noanalysis`) disassembly genuinely cannot recover a jump table without broader context (needs either full-ROM analysis or manual table-boundary annotation).
- **Still not narrowed down** which specific one of these 6+ cases is catch-success vs. a sibling battle-message case (faint/status-cured/etc. — this file clearly handles many message types, catch is just one). **Next step**: either (a) run Ghidra's jump-table recovery with a wider disassembly window around each function's dispatch point, or (b) skip static analysis entirely and use `mgba-qt`'s Lua console with a breakpoint at each of the 6 addresses + a live catch attempt to see which one actually fires — likely faster than continuing static analysis for this specific question.

## Mystery Gift — STRING ANCHOR + one CODE FOUND hit (2026-07-12 follow-up)

File offset `~0x30F550`+ decodes to Mystery Gift / Mystery Event dialogue and item-transfer messaging, contiguous with the vanilla Emerald "weird tree" Mystery Event (Route 111 Wailmer Pail event) and gift-Pokémon PC-transfer messages ("[X] was transferred to SOMEONE'S PC" / "LANETTE'S PC", "BOX '[Y]' was full"). A second, separate cluster at `~0x960880`+ has "MYSTERY GIFT" / "MYSTERY EVENTS" as title-screen menu option text (see next section) and Wireless Adapter warnings. A third cluster at `~0x9686A0`+ has multiplayer-specific Mystery Gift dialogue ("You can't send a MYSTERY GIFT to this TRAINER", "discard this NEWS item?", "You haven't received the GIFT").

**Pointer-searched all 13 exact string offsets in this bank** (`weird tree` x2, `was transferred to` x5, `MYSTERY GIFT` outside the title-menu table x3, `You haven't received the GIFT` cluster). **12 of 13 have no raw 4-byte pointer reference** — expected, not a dead end: Route 111's "weird tree" event and its transfer messages are field-map-script text, which Gen3 engines typically address via the script bytecode's own relative/indexed addressing rather than a literal-pool pointer, so a raw byte-pattern pointer scan won't find the referencing code (would need script-bytecode-aware search or a live watchpoint instead).

**One real hit**: the `You haven't received the GIFT` string (file offset `0x968850`) is referenced from `0x00171A98`, inside real, coherent function `FUN_08171a38` (`0x08171a38`-`0x08171a8c`, clean Thumb epilogue, no jump-table wall this time). Calls `func_0x081694c8` twice (looks like a "queue/send message" primitive, called with different small-int args each time) then `func_0x08008eac` and `func_0x08008f80` — the latter is the **same** `func_0x08008f80` seen in the PC-storage dispatcher below, reinforcing it's a shared low-level task/state-finalize helper used across subsystems, not something PC-storage-specific. Confirms the multiplayer Mystery Gift dialogue is live, wired-up code — useful as a secondary "gift Pokémon" injection path once the primary catch/starter paths are hooked, still not pointer-searched further (lower priority, unchanged from before).

## Title screen main menu — CODE FOUND, one real function confirmed (excellent lead for the mode-select hook)

Found the actual title-screen menu string bank at `~0x9608A4`+:
```
NEW GAME (0x9608A4) | CONTINUE (0x9608B0) | OPTION (0x9608BC) | MYSTERY GIFT (0x9608C4/0x9608D4) | MYSTERY EVENTS (0x9608E4)
```
also nearby: `BRENDAN / MAY / EGG / POKéMON / PROF. BIRCH` (character-select/save-file-summary labels) and Wireless Adapter / save-corruption warning text — this whole region is the title-screen-and-new-game-setup string bank.

**XREFs found two parallel option tables** (likely "save file present" vs. "no save file" title-screen states):
```
Table A: 0x00160DB8–0x00160DE8   Table B: 0x00160F00–0x00160F18
```
Raw dump of Table A shows a mixed struct: string pointers (`CONTINUE`, `NEW GAME`, `OPTION`, `MYSTERY GIFT`, `MYSTERY EVENTS`) interleaved with small integers (`0x861`, `0x547F` — likely ids/flags) and several other pointers. **Correction to the initial pass**: four of those other pointers (`0x08693020`, `0x086930C8`, `0x086930DC`, `0x08693030`) looked like function pointers at a glance but are **even addresses** — GBA Thumb function pointers are always odd (low bit set, for `BX`-mode calling), so these are actually **data pointers**, not code, and disassembling them produced garbage (repeated nonsense `lsl` instructions), confirming the correction. The **real** function pointers in the table are the two **odd**-addressed values: `0x08160F1D` and `0x0815E6A9` (table offsets `0x160DD0`/`0x160DEC`).

**Disassembled and decompiled `FUN_08160ebc` (real address for the `0x08160F1D` pointer, minus the Thumb tag bit)** — real, clean code:
```c
void FUN_08160ebc(undefined4 param_1, int param_2) {
    iVar1 = _DAT_08160f18;                      // base of a 4-element struct array
    func_0x08162f40(_DAT_08160f18,   param_2+0xff);
    func_0x08162f40(iVar1 + 8,       0x1d5);
    func_0x08162f40(iVar1 + 0x10,    0x1d5);
    func_0x08162f40(iVar1 + 0x18,    0x1d5);     // 4x identical calls, 8-byte stride
    *(undefined4 *)(unaff_r6 + (unaff_r5+unaff_r4)*8) = _DAT_08160dd0;  // stores a pointer
                                                                          // (= this table's own
                                                                          // 0x160DD0 slot) into
                                                                          // an 8-byte-stride array
}
```
Four repeated calls with an 8-byte stride is exactly the shape of "set up N menu items' highlight/cursor windows" — a strong match for the visible 4-item menu (CONTINUE / NEW GAME / MYSTERY GIFT-or-EVENTS / OPTION). The final store writes a pointer *back into the same table this function's own address came from* — consistent with a menu-item registering its own handler pointer, a real and expected pattern for menu-init code, not a coincidence.

**This is the strongest candidate hook point for Character Mode's opt-in menu.** `0x0815E6A9` (the other real function pointer, `FUN_0815e648`) was also disassembled but reads as unrelated bit-manipulation code (looks like tile/wallpaper or highlight-rect math, not obviously menu-item-specific) — lower priority. **Next step**: get the *full* body of `FUN_08160ebc` (its indirect jump table wasn't recoverable via targeted disassembly — same limitation as the catch-mechanic functions) to see what determines which menu item was chosen, then decide whether Character Mode hooks in as a 5th visible option here or as an inserted step inside whichever branch handles NEW GAME specifically.

## Trade — CODE FOUND (2026-07-12 follow-up: real dispatcher confirmed, same jump-table wall as catch)

File offset `~0xA48A00`+ decodes to real in-game Trainer-trade dialogue: "TRAINERS wishing to make a trade will be listed.", "Please choose the TRAINER with whom you would like to trade Pokémon.", "Would you like to ask [X] to make a trade?", "You have not registered a Pokémon for trading.", "You don't have a [type]-type Pokémon [...]" — this reads as the general in-game-trade NPC feature (not link-trade, not Mystery-Gift-item-transfer).

**Pointer-searched the 3 exact string offsets** (`wishing to make a trade` @ `0xA48A11`, `have not registered a` @ `0xA48AE0`, `Would you like to ask` @ `0xA48A84`). Only the last has a raw pointer hit, at `0x00220E54` — the other two are presumably reached the same script-bytecode-indexed way as most of the Mystery Gift bank above, not a literal-pool pointer.

`0x00220E54` sits in the literal pool immediately after `thunk_FUN_082206ac` (`0x08220df4`, a single `b 0x082206ac` branch). Decompiling the real target, `FUN_082206ac`, shows it's **the same shape as the catch-mechanic functions**: a bare indirect-jump dispatcher (`Could not recover jumptable... Too many branches`) with no other body. This is a useful confirmatory data point, not a new lead by itself — it means trade dialogue funnels through the *same kind* of central multistring-choice/battle-message dispatcher architecture as catch, title-menu-adjacent, and PC-storage code, all hitting Ghidra's `-noanalysis` jump-table recovery limit. Reinforces that **live mGBA tracing, not further static analysis, is the correct next tool** for any of these subsystems — see the new `tools/mgba_scripts/trace_catch_mechanic.lua` below. Lower priority than catch/menu for actually building Character Mode (trades are a narrower, opt-in player action), so no further tracing planned here unless catch/menu tracing reveals trade needs separate gating.

## PC Storage System — CODE FOUND (two real functions confirmed, dispatcher identified)

The PC-access flow's strings are clustered at `~0x963D90`–`0x963DE0`: `SOMEONE'S PC` / `LANETTE'S PC` / `[X]'s PC` (PC-type selection when interacting with a PC) immediately followed by `HALL OF FAME` (`0x963DC8`) / `LOG OFF` (`0x963DD8`) (PC main-menu options, alongside the presumably-adjacent WITHDRAW/DEPOSIT/MOVE/MAILBOX options this pass didn't isolate individually — those are intermixed with a much larger shared UI-string bank spanning contest ranks, Battle Frontier, and Secret Base decorations in the same `0x9615xx`–`0x965xxx` region, not yet fully mapped).

Pointer search on `HALL OF FAME`/`LOG OFF` found the referencing addresses (`0x1F0ADC`/`0x1F0AE0`) sitting inside a literal pool directly following real Thumb instruction bytes at `0x1F0AA0`+.

**Disassembled and decompiled the enclosing function, `FUN_081f0a40`** — small, clean, complete (proper Thumb epilogue: `add sp,#0x50 / pop {r4-r7} / pop {r0} / bx r0`):
```c
void FUN_081f0a40(void) {
    func_0x08168a88();
    func_0x08008eac();
    func_0x081f0418(0);   // hands off to the real dispatcher, with an initial mode/state of 0
}
```

**Followed the handoff to `0x81f0418`/`0x81f0420` and found what's very likely the actual PC-menu action dispatcher, `FUN_081f0420`** — decompiled cleanly:
```c
void FUN_081f0420(undefined4 param_1, uint param_2, undefined4 param_3, uint param_4) {
    uVar2 = param_4 >> 0x18;    // the selected menu action, as a byte code
    if (uVar2==0x4a || uVar2==0x4b || uVar2==0x4c || uVar2==0x4d || uVar2==0x4e || uVar2==0x4f) {
        *_DAT_081f0480 = 0xc;
    } else {
        *_DAT_081f0480 = 2;
    }
    // ... computes an index into a 0x28-byte-stride struct array (same stride seen in the
    // catch-mechanic functions — likely gTasks[] or a similar shared engine structure),
    // writes 4 param bytes into it, then:
    func_0x081f10d0(uVar2);   // hands the action code onward
}
```
**Six consecutive byte codes (`0x4A`–`0x4F`) checked together is a strong match for the 6 visible "Someone's/Lanette's/[X]'s PC" menu options** (Withdraw Pokémon / Deposit Pokémon / Move Pokémon / Move Items / Mailbox / Hall of Fame, or some ordering thereof — matches the count of options implied by the string cluster). This reads as the real menu-action dispatch point: every PC operation (including Withdraw, the one `CharacterMode_SweepPartyToPC()`-equivalent enforcement cares least about, and Deposit, which it cares most about) funnels through this one function before `func_0x081f10d0` does the actual work.

**This is a strong candidate hook point for `CharacterMode_SweepPartyToPC()`-equivalent enforcement** — though note Character Mode's actual need (auto-move off-roster party members to the PC on character switch) is a different operation than anything a *player-invoked* PC menu action does; this dispatcher is more useful as a map of "where does legitimate PC access funnel through" than as the injection point itself. The injection point for the sweep is more likely to be a new function called from the character-switch flow directly, calling into whatever lower-level "add Pokémon to a PC box" primitive `func_0x081f10d0`/its callees eventually reach.

**Traced `func_0x081f10d0` (2026-07-12 follow-up) — turned out to be a generic task-dispatch trampoline, not the storage primitive itself.** The containing function is `FUN_081f1070` (`0x081f1070`-`0x081f10b0`), small and clean:
```c
void FUN_081f1070(int param_1, int param_2, undefined1 param_3) {
    func_0x08167ecc(auStack_8, 0, /* two packed byte params */, param_3);
    uVar1 = func_0x08008bdc(auStack_8);   // returns a u8 — reads like CreateTask()
    func_0x08008f80(uVar1);               // shared finalize/dispatch helper (also seen
                                            // in the Mystery Gift function above)
    // ends in the same "pop {r1}; bx r1" epilogue shape Ghidra misreads as an
    // unrecovered indirect jump/call — this is very likely just a normal return,
    // not a real dispatcher, unlike the catch/trade cases above.
}
```
Reads as: pack a small event/task descriptor into an 8-byte stack struct, hand it to what looks like a `CreateTask`-equivalent (`func_0x08008bdc`, returns a task id), then call a shared finalize helper (`func_0x08008f80`) with that id. **This is one hop short of the actual storage write** — the real "add Pokémon to PC box" work is presumably inside whatever task function `func_0x08008bdc` registers, which isn't visible from this call site alone (its target is data, not something directly disassemblable without more context). Given diminishing returns from further static hops through generic task-engine plumbing, **this line of static tracing is paused here** — live mGBA tracing (watchpoint on a PC box's memory region during an actual Deposit) is likely to resolve this faster than continuing to chase task-engine internals statically. Not yet scripted (lower priority than catch-mechanic disambiguation, which blocks the higher-value starter/catch enforcement hook).

## Free space

See `docs/FREE_SPACE.md` — resolved, ~1.18 MiB confirmed free (0xFF-padded, one contiguous block), not a blocker.

## Species table

See `docs/SPECIES_CAP.md` — `gSpeciesInfo`-equivalent array located (base `0x008F07AC`, 208-byte stride, index = National Dex number for the Gen 1-3 block), full dump in `tools/character_mode/rom_species_table.json`. This directly feeds Stage B (`tools/character_mode/map_species.py`'s pending numeric-id pass) once a decision is made on when to run it (routine mapping and Stage B are independent — Stage B can run any time once someone wants real binaries).

## Toolchain status

See `CLAUDE.md`. **Full toolchain now set up (2026-07-12).** `arm-none-eabi-gcc` and `mgba-qt` were already system-installed (0.10.2, confirmed `liblua5.4`-linked). `tools/bin/armips` and `tools/bin/flips` are now present, copied verbatim (prebuilt portable ELF binaries, same reuse pattern as Ghidra) from `Unbound-Character-Mode/tools/bin/` — both run and print expected usage/version output. **Ghidra set up and used this session (still true)** — see "Ghidra setup" above; reused Unbound's install rather than re-downloading, imported with `-noanalysis`, all findings reached via targeted `InspectRegions.java`/`DecompileFunc.java` calls on specific known addresses (no full-ROM auto-analysis attempted — deliberately avoided given Unbound's hour-long timeout experience). `ghidra_project/SeaglassCM.gpr` now holds all work done so far (gitignored, regenerable by re-running the same `analyzeHeadless` commands documented above against `rom/seaglass v3.0.gba`). No code has been injected yet — toolchain being present just means the next phase (hook writing) is unblocked once a hook site is confirmed.

**New this session**: `tools/mgba_scripts/trace_catch_mechanic.lua` — a ready-to-run mGBA Lua script that arms breakpoints on all 6 catch-string-choice candidate addresses and logs hits (function name, PC, r0-r2) to the scripting console. API calls (`emu:setBreakpoint(callback, address, segment)`, `emu:readRegister(name)`, `console:log(str)`) were verified against the actual mGBA 0.10.2 source (`src/core/scripting.c` on GitHub), not guessed — high confidence they're correct, but this hasn't been execution-tested (needs the GUI + a live catch attempt, which is why it's handed off rather than run automatically — same reasoning as the rest of this section). **This still needs the user to actually sit down and play**: load the script via Tools → Scripting → Load script, battle a wild Pokémon, throw a Poke Ball, and watch which candidate(s) fire at "Gotcha!" vs. an ordinary battle message. This mirrors the exact same conclusion Unbound's project reached (live tracing "needs interactive gameplay... matching how ROWE's own testing worked") — confirmed here as still true, not re-litigated per session.

**Summary of what's CONFIRMED-adjacent (real code found and decompiled) vs. still open:**

| Subsystem | Status | Key function(s) |
|---|---|---|
| Catch mechanic | Code found, exact handler undetermined — **script ready for live trace** | `FUN_0811ff44`, `FUN_08120304/534/8d4/cd0/db8`, shared helper `func_0x08087328` |
| Title menu / mode-select | Code found, strong candidate | `FUN_08160ebc` |
| PC storage | Code found, dispatcher identified, one more hop traced (generic task trampoline, not the primitive itself) | `FUN_081f0a40` → `FUN_081f0420` → `FUN_081f1070` → task engine (untraced further, paused) |
| Trade | Code found — same unrecoverable jump-table dispatcher shape as catch | `thunk_FUN_082206ac` → `FUN_082206ac` |
| Mystery Gift | Code found for one hit (multiplayer dialogue); rest still string-anchor-only (likely script-bytecode-addressed, not pointer-addressed) | `FUN_08171a38` |

Every remaining "next step" above now converges on the same answer: **live mGBA tracing is the correct next tool**, not further static analysis — every subsystem investigated this session independently hit the same Ghidra `-noanalysis` jump-table recovery wall. `tools/mgba_scripts/trace_catch_mechanic.lua` is ready for the catch mechanic specifically; the same breakpoint-and-log pattern would generalize to PC storage/trade if needed later. Toolchain (`arm-none-eabi-gcc`, `armips`, `mgba-qt`, `flips`) is now fully set up — nothing left blocking hook-writing once a confirmed hook site exists.
