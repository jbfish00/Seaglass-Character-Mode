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

### FULLY DECODED 2026-07-17 — Lazarus's design does NOT transfer; new design pinned

**The entry chain was fully script-decoded (2026-07-17). Key discovery: Seaglass's
GIFT CODE flow has NO text matcher to hook — it's the vanilla Easy Chat
QUESTIONNAIRE flow** (the Mauville-style clipboard), with phrase matching done
natively inside the easy-chat screen. Character-name codes cannot ride it
(Easy Chat only offers vocabulary words, no free text). Full chain:

| Piece | Address | Detail |
|---|---|---|
| Main BG-event script | `0x08311CCB` | lockall → yes/no msgbox `0x0830F7D4` ("enter a code?") → decline goto `0x08311DAD` (releaseall,end) |
| Easy-chat launcher sub | `0x0830E247` | `fadescreen 1; special 0x62; fadescreen 0` — donor INDEX 0x62 = **ShowEasyChatScreen**; type set by `setvar 0x8004, 0x14` = EASY_CHAT_TYPE_QUESTIONNAIRE |
| Post-entry dispatch | `0x08311CEB`+ | `specialvar 0x8008, 0x1EC` (mart-employee obj id, donor-INDEX match) then `compare 0x8004,1→0x8311D1D`, `0x8004,2→0x8311D65`, `0x800D,0→end`, `0x800D,1→0x8311DAF` (invalid msg `0x830F80D`) — i.e. **0x8004 = matched-phrase index (set inside easy chat), 0x800D = 0 canceled / 1 confirmed-no-match** |
| Reward branches | `0x08311D1D` / `0x08311D65` | both gated on flag `0x861`; redeem-once flags `0x8AC` / `0x8DB`; msg-only rewards (DexNav-show-all etc.) — only TWO live codes |
| Single BG-event ref | file **`0x123ACC`** | the ONLY pointer to `0x08311CCB` in the ROM (bg_event struct base `0x123AC4`) — one clipboard, at a mart (0x1EC + `mart_inside.ss` savestate) |

**But the perfect entry UI exists anyway, unused: Seaglass compiles the
expansion's CODE naming-screen template.** DoNamingScreen internals (all
byte-confirmed in-ROM 2026-07-17):

| Piece | Address | Detail |
|---|---|---|
| **DoNamingScreen** | **`0x08174415`** (Thumb) | vanilla sig: `(u8 template, u8* dest, u16 species, u16 gender, u32 personality, MainCallback cb)` — proven by ChangePokemonNickname special (donor INDEX 0xA1 → Seaglass fn `0x08215A69`) and DoWaldaNamingScreen (INDEX 0x200 → `0x0822A7C1`), both BL it |
| sNamingScreenTemplates | `0x0869DFD0` | 7 entries; **template 5 = CODE: struct `0x0869E320`, maxChars=10, no icon/gender, title "Enter Gift Code:" (`0x08967D24`)** — compiled but unused by the hack (v3 gift codes use easy chat instead) |
| Resume callback | **`0x08179AFD`** | CB2_ReturnToFieldContinueScriptPlayMapMusic-equivalent — Walda's exit cb (`0x0822A7F5`) stores match result to `gSpecialVar_0x8004` then `SetMainCallback2(0x08179AFD)`; resumes a `waitstate`-paused script |
| SetMainCallback2 | `0x08000685` (Thumb) | `gMain = 0x030014B4`, callback2 at +4, clears byte +0x438 |
| gSpecialVar_0x8004 | `0x020055E0` | from ChangePokemonNickname/Walda disasm |
| gStringVar2 | `0x0203AF24` | Walda's dest buffer — safe transient dest for ours |
| givemon cmd 0x79 | handler `0x081EC84D` | **re-tabled to nop1's handler (movs r0,#0; bx lr) — same as Lazarus**; script gives happen elsewhere (see callnative audit) |

**DoNamingScreen ABI (byte-decoded from ChangePokemonNickname 0x08215A69,
2026-07-17):** `DoNamingScreen(r0=templateNum, r1=destBuf, r2=species,
r3=gender, [sp+0]=personality(u32), [sp+4]=returnCallback)`. returnCallback is
a CB2; Walda's exit cb chains to **`0x08179AFD`** (CB2_ReturnToField…, resumes
a `waitstate`-paused field script) — confirmed a real function. `GetVarPointer
0x0810D0C0`, FlagSet `0x0810D254`, FlagClear `0x0810D304`, FlagGet
`0x0810D35C` (all re-confirmed from cmd-table handlers). **gSpecialVars base
`0x020055D8`**. gSpecialVar_Result (0x800D) is at **`0x020055F0`** — verified
2026-07-17 by reading r0 at CM_TradeCheck's `strh` store (the game's own
GetVarPointer(0x800D) return). NOTE: the earlier "= 0x020055F2" here was a naive
base + 0xD*2 computation and is **wrong by 2** (GetVarPointer's special-var
indexing isn't a flat 0x8000-based array); always read GetVarPointer(0x800D) /
the store address rather than hardcoding, and if you must hardcode use
`0x020055F0`.

**Injection design (final, replaces the Lazarus slot-hook plan since Seaglass
has no text matcher to hook):** repoint the single BG-event ptr (file
`0x123ACC`, currently → `0x08311CCB`) → our free-space entry script:
`lockall; yesnobox "Enter a Character Mode code?"` → NO: `goto 0x08311CCB`
(original gift-code/easy-chat flow 100% untouched) → YES:
`callnative CM_OpenCodeEntry` (calls `DoNamingScreen(5=CODE, gStringVar2
0x0203AF24, 0, 0, 0, cb=0x08179AFD)`) → `waitstate` → `callnative
CM_MatchCode` (folds gStringVar2 vs our 170-code table + 3 debug codes; on
match sets VAR_CM_CHAR/FLAG_CM/VAR_CM_STARTER + gSpecialVar_Result; else
Result=0) → `compare 0x800D` branch → confirm-msgbox + starter give (via the
native-give idiom, VAR_CM_STARTER as species) OR invalid-msgbox → releaseall.
Passing `0x08179AFD` directly as the return cb (not a custom processing cb like
Walda's) lets the match happen in the post-waitstate callnative, so **our C
never calls SetMainCallback2**. Shipped-region edit for selection = 4 bytes
(one pointer). Lazarus bug lessons applied: reset VAR_CM_STARTER before the
give; `goto` (never `call`) any releaseall-terminated tail; native-give wrapper
sets Result=1 when it boxes.

## Callnative give audit — ENFORCEMENT HOLE FOUND + SURFACE CLOSED BY EXHAUSTION (2026-07-17)

**Lazarus lesson (iii) confirmed on Seaglass: script gifts do NOT go through
GiveMonToPlayer.** The engine's script-give surface:

| Piece | Address | Detail |
|---|---|---|
| **Give native (the hole)** | **`0x081F2175`** | reached via `callnative` at **49 script sites** (pattern `23 75 21 1F 08`); reads 10 bytes of inline args: hw0=`0x0600` const, hw1=species (literal or var id — VarGet'd; one site passes `0x800D`), hw2=level, hw3/hw4 usually 0. Simple-site idiom: `0006 <species> 0500 0000 0000` |
| Give core | `0x081F1D64` | called ONLY from inside the native (2 BLs: `0x1F2124`, `0x1F2362`); **writes gPlayerParty/gPlayerPartyCount directly, boxes via CopyMonToPC `0x081AA620` when party full — never BLs GiveMonToPlayer** → bypasses the injected CM gate |
| Arg readers | `0x081EF488` / `0x081EF49C` | ScriptReadHalfword / ScriptReadWord; species/level resolved via VarGet `0x0810D104` |
| Coverage proof | — | `0x081F2175` has ZERO Thumb-BL callers and ZERO non-callnative u32 refs ROM-wide; give core has only the 2 internal BLs → **wrapping the 49 callnative operands closes the entire script-gift surface by exhaustion** |
| Gated BL `0x081F18DE` (context) | fn `0x081F18BC` | small fn (SetMonData + GiveMonToPlayer + `0x081AA76C`), single BL caller `0x1EE80E` (ScrCmd-handler region — the giveegg-family path). Keeping it gated is correct but it is NOT the main gift path |
| Other frequent natives (ruled out) | `0x0810F20D` ×25, `0x0810F3B9` ×9 | var/flag EWRAM utilities (`0x02005654` etc.), no party writes — not gives |
| Post-give script flow | e.g. site `0x281CCF` | `setvar 0x4001,<species>` (msg buffer) → callnative+args → fanfare + "received!" msgbox; **no VAR_RESULT branching, no nickname prompt** → wrapper needs no Result semantics; off-roster boxing is silent (matches catch UX) |

**Fix (Phase 4b)**: `CM_NativeGiveGated(ctx)` — snapshot gPlayerPartyCount, call
the original native, and if the count grew while the gate is active, post-check
the new tail slot: non-egg off-roster → CopyMonToPC, zero the 100-byte slot,
count-- (only if the copy succeeded, per the Lazarus wrapper-boxing bug). Patch
all 49 callnative operands → wrapper. The same native idiom (species via a CM
var) delivers the selection starter from the confirm script.

## In-game trades — GATED (2026-07-17; donor specials.inc INDEX ordering, exactly Lazarus's recipe)

Donor trade specials at indices 0xFF/0x100/0x101 (GetInGameTradeSpeciesInfo /
CreateInGameTradePokemon / DoInGameTradeScene) → Seaglass gSpecialsTable
`0x0826DD68` slots resolve to `0x0820AA3D` / `0x0820AD35` / `0x0820B1C5`.
GetInGameTradeSpeciesInfo's literal pool → **sIngameTrades `0x08A3DB30`,
stride 60, 4 entries, received species u16 @+14** (identical layout to
Lazarus):

| idx | nick | receives | wants |
|---|---|---|---|
| 0 | DOTS | Seedot 273 | Ralts 280 |
| 1 | PLUSES | Plusle 311 | Volbeat 313 |
| 2 | SEASOR | Horsea 116 | Bagon 371 |
| 3 | MEOWOW | Meowth 52 | Skitty 300 |

All 4 scripts share an identical 17-byte confirm junction
(`copyvar 0x8004,0x8008; copyvar 0x8005,0x800A; special 0x100; special 0x101;
waitstate`); the trade index arrives in **0x8008** (junction order 2,0,1,3 vs
table order — same quirk Lazarus found). Junctions: `0x29CFF5`(idx2),
`0x2AF873`(idx0), `0x2B01EF`(idx1), `0x30129E`(idx3). Injector overlays the
first 5 bytes of each with `goto` → per-trade wrapper at `0x08EE3000` that
`copyvar`s the index, `callnative CM_TradeCheck` (received species @+14 vs the
active bitmap → VAR_RESULT 1/0), then either the polite refusal or the original
17-byte junction body + `goto` resume. CM_TradeCheck compiled behind
`-DTRADE_TABLE_ADDR=0x08A3DB30 -DTRADE_STRIDE=60 -DTRADE_RECV_OFF=14
-DTRADE_COUNT=4`.

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

## Wild-encounter species/level roll — CreateMonWithIVs-simple choke point CONFIRMED (task #5, wild-mon override)

Found live via `mgba-headless` breakpoint tracing from `tools/savestates/at_8_8.ss`
(clean overworld a few tiles from Route 101's tall grass) — the same
"give Poké Balls, weaken, watch a watchpoint fire" methodology as the
GiveMonToPlayer discovery, but climbing the call chain via `emu:setBreakpoint`
at each successive candidate entry (reading its own `lr` register) rather than
static disassembly, since every subsystem here (like the earlier catch
mechanic / trade / PC storage investigations) hits Ghidra's `-noanalysis`
jump-table wall — the mon-construction code is a deeply shared, jump-table
dispatched `SetMonData`-style core reused for dozens of unrelated fields, and
static backward-tracing through it repeatedly dead-ends. Breakpointing actual
candidate function entries and reading `lr` (not watching memory writes,
which land deep inside the shared dispatcher with a stale/generic caller)
was the technique that actually worked.

| Symbol | Address | Evidence |
|---|---|---|
| **CreateMonWithIVs-simple** | **`0x081A7504`** (Thumb) | disasm-confirmed signature: `(mon, u16 species, u8 level, u8 fixedIV, ...)` — masks r1 to u16, r2 to u8, writes r2 (level) directly to `mon+0x54` (the same plaintext level field `enemyLv()` readers already used), calls a sibling `CreateBoxMon`-shaped helper (`0x081A6E44`) which itself calls the giant SetMonData-driven field-init montage (species set via `SetMonData(mon, MON_DATA_SPECIES=18, &species)` inside it, confirmed by breakpointing `SetMonData`@`0x081A9CA0` with `r0==gEnemyParty` filter and watching `r1` cycle through the exact field-id sequence donor's CreateBoxMon writes) |
| **Wild-encounter hook site (the BL retargeted)** | **ROM file offset `0x22BF36`** (`0x0822BF36`) | `emu:setBreakpoint` at `0x081A7504`'s entry fired **exactly once per wild encounter** with `r0=gEnemyParty (0x02019E78)`, `r1=`rolled species, `r2=`rolled level, `lr=0x0822BF3B` — i.e. the BL instruction at file offset `0x22BF36` is the wild-roll's own call into CreateMonWithIVs-simple. A full-ROM BL-scan for direct callers of `0x081A7504` found exactly **5** static sites: 4 clustered at `0x81F19xx`/`0x81F1Fxx` (the give-native region — confirmed unrelated, script gifts use fixed species) and this **1** at `0x0822BF36` — the sole wild-roll caller, matching the donor's architecture where `TryGenerateWildMon`/`GenerateFishingWildMon`/`SetUpMassOutbreakEncounter` all fan into ONE shared `CreateWildMon(species, level)` which itself makes exactly one call into `CreateMonWithIVs` — i.e. **this single BL is the shared choke point for every wild-roll table type** (grass/cave land, surfing, rock smash, all 3 fishing rod tiers, and mass outbreaks), exactly mirroring how `GiveMonToPlayer`'s 3 callers were the acquisition choke point. |

**Coverage — what is live-proven vs analysis-only (updated 2026-07-17 latest++):**

*Live-proven (grass/cave LAND path, the only wild type reachable from any
existing savestate):* `tools/mgba_scripts/prove_wild_chokepoint.lua` (suite
layer 5c), run on the **original unpatched ROM** across 5 land encounters with
different rolled species/levels, asserts every run:
1. the BL instruction at `0x0822BF36` genuinely **executes** (breakpoint on the
   site fires during the encounter), and
2. **every** `CreateMonWithIVs`-for-the-wild-mon call (r0==gEnemyParty) returns
   to **exactly one** address, `0x0822BF3B` (= the return addr of the BL at
   `0x0822BF36`) — i.e. there is no second wild-construction path on the
   reachable route.
Plus the patched-ROM side: `cm_wild_test.lua`/`cm_wild_stage_test.lua` (layers
5a/5b) show the *retargeted* land encounter routing through the trampoline at
`0x08470208` (the only BL in the ROM pointing there) into
`CM_WildMonSpeciesGated` and back, with the override firing/not-firing
correctly.

*Analysis-only (surf / rock smash / all fishing tiers / mass outbreaks):* NOT
walked into live — no Surf HM, fishing rod, or badge exists in any savestate
(every state is pre-5th-gym early game: bag + badge dump confirmed 0 badges,
no rods/HMs), and those wild types are unreachable this session. Their
coverage rests on: (a) the donor architecture — `TryGenerateWildMon`
(land/water/rock), `GenerateFishingWildMon` (fishing), and
`SetUpMassOutbreakEncounter` all funnel into ONE shared
`CreateWildMon`→`CreateMonWithIVs` call; and (b) `verify_artifacts.py`'s
full-ROM BL-scan finding **exactly one** wild-related caller of `0x081A7504`
(the other 4 are the unrelated give-native region) — if surf/rock/fishing used
a different `CreateMonWithIVs` site, the scan would have found a second caller.
This is now "the *same* BL that we empirically proved is the sole caller on the
land path, and the ROM has no other wild caller" rather than pure static
inference — but the non-land types themselves have not been observed executing.

**Hook design**: since the hook site (`0x0822BF36`) is ~7.6 MiB from the main
Character Mode shim blob (`~0x08ED2200`) and ~0.5 MiB from CreateMonWithIVs
itself, retargeting the BL directly to the far shim is out of Thumb BL range
(±4 MiB). Fix: a tiny second trampoline (`src/wild_trampoline.c`, 40 bytes)
placed in the *same* 64-byte 0xFF scavenge run as the existing catch-gate
trampoline (`0x08470200`), immediately after it at `0x08470208` — in range of
both the hook site and CreateMonWithIVs. It shuffles species/level into the
call ABI, reaches the far `CM_WildMonSpeciesGated` via the classic ARMv4T
long-call idiom (manually build a Thumb return address into `lr`, `bx` to an
absolute literal — this CPU has no BLX), then tail-jumps (plain `bx`, not
`bl`) to the untouched original CreateMonWithIVs so its own return goes
straight back to the real caller, invisibly. See `src/character_mode.c`'s
`CM_WildMonSpeciesGated` doc comment and `tools/character_mode/emit_wildpool.py`
for the per-character override-pool data (non-legendary roster bases,
expanded through the donor evolution graph, each member tagged with a canon
"first appears at this level" estimate from the donor's `EVO_LEVEL` params).
