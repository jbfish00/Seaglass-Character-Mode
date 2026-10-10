#!/usr/bin/env python3
"""Build the Character Mode patched ROM for Pokemon Emerald Seaglass v3.0.

Supersedes the enforcement-only tools/build_cm.sh: this injects the full
feature (selection + acquisition gate + script-gift gate). Trades are added by
task #4 (needs sIngameTrades). All addresses CONFIRMED for rom.sha1 — see
docs/ROUTINE_MAP.md.

Pipeline:
  1. emit_bitmaps.py -> rosters_expanded.bin (170 x 187 allowed-species) and
     emit_wildpool.py -> wildpool.bin (170 x 104 wild-encounter-override
     entries: species + canon min-level, non-legendary only). Both are
     pre-generated (not re-run automatically here); this script just reads
     the .bin outputs.
  2. Compile src/character_mode.c (6 entry points) at SHIM_ADDR in the big
     free block (ROM 0x08ED2164+). Referenced only via 32-bit pointers except
     the near-hook entries (catch/gift, marker, PC guard, wild stub), which
     share an 8-byte-slot block over a DEAD function at 0x081C3430 (see
     TRAMPOLINE_BLOCK; until 2026-09-29 they sat in a sprite frame). The wild
     stub hops to a 40-byte long-call veneer, src/wild_trampoline.c, because
     the main shim is out of Thumb BL range of its hook site.
  3. Splice payloads (shim/bitmaps/codes/starters/wildpool/entry+confirm
     script) into a ROM copy; the source ROM is never written.
  4. Patch (verify-original-first):
       - BG-event ptr (file 0x123ACC): 0x08311CCB -> CM entry script
         (yes/no -> CODE naming screen -> match -> confirm+give / invalid;
          NO keeps the original gift-code/easy-chat flow).
       - BL @0x0A6A46 (wild catch) and BL @0x1F18DE (small script-give fn):
         GiveMonToPlayer -> trampoline -> CM_GiveMonToPlayerGated.
       - 49 inline `callnative 0x081F2175` operands -> CM_NativeGiveGated.
       - BL @0x22BF36 (wild-encounter species/level roll's call into
         CreateMonWithIVs-simple): retargeted -> the wild trampoline, which
         calls CM_WildMonSpeciesGated then tail-jumps to the untouched
         original CreateMonWithIVs.
  5. Write build/seaglass_cm.gba + build/seaglass_cm.bps (BPS against the hack
     ROM, per the standing distribution rule).

Selection UX: at the cheat clipboard, choose "yes" to enter a Character Mode
code (character name, punctuation stripped, <=10 chars, case-insensitive).
Debug codes: CMDBGOFF, CMDBGGIVE1 (on-roster give), CMDBGGIVE2 (off-roster).
"""
import hashlib
import json
import re
import struct
import sys
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
ROM_IN = ROOT / "rom" / "seaglass v3.0.gba"
ROM_SHA1 = "b9f4d332d30fc88c379f9e037f9eae3b2755ead4"
BUILD = ROOT / "build"
CM = HERE / "character_mode"

def _resolve_charmap():
    """Path to this repo's vendored game-text charmap (tools/charmap.txt).

    This was a hardcoded absolute path into the unrelated "Pokemon Rowe
    Alteration" working tree, which made this repo unbuildable and
    unverifiable from a fresh clone. The charmap is now vendored here
    (byte-identical, md5 b31d142ca98103d64d707f9894fa42e3). Resolution is
    anchored to this file's own location, never the cwd.

    Override with the CM_CHARMAP environment variable.
    """
    import os
    from pathlib import Path
    override = os.environ.get("CM_CHARMAP")
    if override:
        p = Path(override)
        if not p.is_file():
            raise SystemExit("CM_CHARMAP=%s is not a file" % override)
        return p
    # Walk up to the REPO ROOT only. An unbounded walk would keep climbing past
    # the repo into ~ and could silently pick up an unrelated tools/charmap.txt
    # -- reading the wrong charmap presents as "this game encodes text
    # differently", not as a missing file. Bound it at the .git directory.
    for parent in Path(__file__).resolve().parents:
        cand = parent / "tools" / "charmap.txt"
        if cand.is_file():
            return cand
        if (parent / ".git").exists():
            break
    raise SystemExit(
        "charmap.txt not found. Expected it vendored at <repo>/tools/charmap.txt; "
        "set CM_CHARMAP to override.")

CHARMAP = _resolve_charmap()

# Derived, never hardcoded -- and passed on to the shim as -D. A hardcoded count
# in the C shim is the dangerous direction: too high and gateActive() trusts an
# out-of-range character index instead of rejecting it.
_MANIFEST = json.loads((HERE / "character_mode" / "characters_manifest.json").read_text())
NUM_CHARACTERS = len(_MANIFEST["characters"])
BITMAP_STRIDE = 187
CODE_LEN = 11

# Tobias gets the 1% legendary-inclusive wild rate (user spec 2026-07-23);
# everyone else 10%. Derived by NAME, because the id moved when Volo was
# inserted ahead of him on 2026-07-25 and the shim's hardcoded 182 -- now Volo --
# went with it unnoticed. 0 when he is not in the roster: ids are 1-based, so
# the branch goes dead rather than landing on whoever inherited the slot.
TOBIAS_CHAR_ID = next((i + 1 for i, c in enumerate(_MANIFEST["characters"])
                       if c["character"] == "Tobias"), 0)

# --- confirmed free-block layout (all verified 0xFF) ---
SHIM_ADDR      = 0x08ED2200
BITMAPS_ADDR   = 0x08EDA000        # 170*187 = 31790 B
CODES_ADDR     = 0x08EE2D00        # 193*11 = 2123 B (rebased 2026-07-25 for Volo: 193-char
                                   # bitmaps are 36,091 B and ended at 0x08EE2CFB, 123 B past
                                   # the old 0x08EE2C80. Every roster growth moves this.)
STARTERS_ADDR  = 0x08EE3600        # 193*2 = 386 B (rebased 2026-07-25: codes now end at
                                   # 0x08EE354B). Headroom to SCRIPT_ADDR is only ~126 B --
                                   # SCRIPT_ADDR CANNOT MOVE (naming_open.ss embeds a paused
                                   # script context pointing at it), so the next roster growth
                                   # must relocate CODES/STARTERS below BITMAPS, not above.
SCRIPT_ADDR    = 0x08EE3800        # entry + confirm script -- KEEP FIXED: naming_open.ss
                                   # embeds a paused script context pointing here
WILDPOOL_ADDR  = 0x08EE5000        # 193*176*4 = 135,872 B -> ends 0x08F062C0 (2026-07-25)
# 0x08F10000 is NOT free: tools/tests/build_trade_testrom.py uses it as its
# scratch script address. Placing the sprite table there built fine and only
# failed later, inside the trade e2e layer. Start above it.
CM_SPRITE_PTRS_ADDR  = 0x08f20000   # Phase 3, separate free run; additive table
CM_SPRITE_BLOBS_ADDR = 0x08f20800
# Mugshot renderer (src/character_sprite.c). Deliberately NOT in the main
# injection block: the 2026-07-25 rebase left only ~126 B of headroom below
# SCRIPT_ADDR, and SCRIPT_ADDR cannot move (naming_open.ss embeds a paused
# script context pointing at it). This sits past the sprite art in the same
# separate free run; splice()'s 0xFF precondition is what proves it clear.
# No BL-reach constraint: every engine call it makes goes through a function
# pointer, and the script reaches it by an absolute `callnative` operand.
#
# ⚠️ REBASED 2026-07-29: 0x08F42000 -> 0x08F60000. It was placed immediately
# past the sprite art with ~2 KB to spare, and staging four more portraits took
# the blob from 135,200 to 138,776 B -- ending at 0x08F42618, i.e. 1,560 B INTO
# the renderer. splice() caught it ("target not 0xFF @ 0x8f20800") rather than
# letting it corrupt anything, but the message names the blob, not the thing it
# collided with, so the assert below now says so directly.
# The whole run 0x08F20000..0x09000000 is 0xFF in the base ROM and holds nothing
# but our own regions, so this rebase costs nothing and buys ~120 KB of blob
# headroom -- the art would have to nearly double again to reach it.
CM_MUGSHOT_ADDR = 0x08F60000
FREE_END_ROM   = 0x09000000

# ⚠️⚠️ THE TRAMPOLINES USED TO LIVE IN A SPRITE FRAME. The "verified 64-byte
# 0xFF scavenge run" at 0x08470200 is a referenced 64-byte image:
# SpriteFrameImage {0x08470200, 0x40} at 0x0895ED54, used by the sprite
# template at 0x0895E894. The catch, wild and marker trampolines overwrote 56 B
# of it until 2026-09-29 (rowe_parity.md §13.53). A run of 0xFF is not free
# space unless nothing points at it.
#
# All four near-hook entries now share one block over the standalone
# IsRemovingLastPartyMon at 0x081C3430, which this build inlines at every call
# site (no BL callers, no pointer to its entry: verify_artifacts [22]):
#   +0  PC second guard   +8 catch/gift gate   +16 encounter marker
#   +24 wild ENTRY STUB (12 B: push {r3}; ldr r3,=veneer; bx r3; .word) --
#       the 40-byte wild veneer itself moved to the CM free block, since only
#       its entry must be in BL reach; it pops r3 back first thing.
TRAMPOLINE_BLOCK      = 0x081C3430
TRAMPOLINE_BLOCK_ORIG = bytes.fromhex("00b50a4b1b781b0600201b16012b03d1074b1b78002b01d002bc0847054b1878f7f7ccfc")   # 36 B of the dead function, base ROM
TRAMPOLINE_ADDR        = TRAMPOLINE_BLOCK + 8     # catch + gift gate
MARKER_TRAMPOLINE_ADDR = TRAMPOLINE_BLOCK + 16    # encounter marker (1.24 MB from its hook)
WILD_STUB_ADDR         = TRAMPOLINE_BLOCK + 24    # wild entry stub (the BL target)
# 100% catch for on-roster species (2026-10-09). The dead function runs past
# the 36 B above: its tail (b, nop) and literal pool reach 0x081C3467, and
# nothing outside it points or pc-loads into 0x081C3454..0x081C3467
# (verify_artifacts [26]). The veneer takes 0x081C3458..0x081C345F.
CATCH_VENEER_ADDR = 0x081C3458
CATCH_VENEER_ORIG = bytes.fromhex("f6e7c04674a10102")
CATCH_ODDS_SITE   = 0x0A6284          # Cmd_handleballthrow: mov r3,r9 ; cmp r3,#254
CATCH_ODDS_ORIG   = bytes.fromhex("4b46fe2b")
WILD_TRAMPOLINE_ADDR   = 0x08FA8000               # the wild veneer (src/wild_trampoline.c)
OLD_SPRITE_FRAME       = (0x08470200, 0x40)       # must stay byte-identical to the base
# The BL inside BufferStringBattle that every intro string funnels through:
#   ldr r0, =<one of several strings> ; b 0x08086EA8
#   0x08086EA8: ldr r1, =dst ; bl BattleStringExpandPlaceholders
MARKER_BL_SITE   = 0x086EAA
EXPAND_STRING    = 0x080876DC

# ROWE's second guard in the PC (src/character_mode.c CM_PSSLastMonGuard;
# docs/ROUTINE_MAP.md "PC second guard"). Every storage-system "is this the
# last party mon?" test calls CountPartyAliveNonEggMonsExcept; five inlined
# IsRemovingLastPartyMon sites and CanShiftMon's call are retargeted through ONE
# trampoline, written over the standalone IsRemovingLastPartyMon at 0x081C3430:
# this build inlines it at all five call sites, so the function has NO BL
# callers and no pointer to its entry (verify_artifacts [22] re-checks both on
# the base ROM). It sits right beside the patch sites.
# ⚠️ NOT the 0x08470200 "scavenge run": that is a referenced 64-byte SPRITE
# FRAME (SpriteFrameImage {0x08470200, 0x40} at 0x0895ED54, used by the
# template at 0x0895E894), not free space. See rowe_parity.md §13.53.
PSS_COUNT_ALIVE_EXCEPT = 0x081BADEC   # special 0x88's wrapper calls it (the anchor)
PSS_GUARD_BL_SITES = (0x1BC576, 0x1BC62C, 0x1BCB04, 0x1BCB3C, 0x1BCB6E)
PSS_CANSHIFT_BL    = 0x1C352C         # CanShiftMon (0x081C3508): bl Count
PSS_CANSHIFT_TAIL  = 0x1C3530         # cmp r0,#0 ; bne -> b <epilogue 0x081C3524> ; nop
PSS_GUARD_TRAMPOLINE_ADDR = TRAMPOLINE_BLOCK   # +0 of the block over the dead function
TEXT_WILD_APPEARED = 0x084C646C     # "Wild {FD}{06} appeared!{FB}"
# 193*64 = 12,352 B, in the run verified 0xFF from 0x08F0A000 to 0x08F1C000.
# ⚠️ NOT 0x08F10000: tools/tests/build_trade_testrom.py already writes its
# test script there, and it asserts the space is clear -- so the first choice
# broke the trade layer rather than corrupting anything. Kept as an assert
# below so the next allocation in this region cannot land on it silently.
MARKER_ADDR      = 0x08F12000
TRADE_TEST_SCRIPT_ADDR = 0x08F10000  # owned by tools/tests/build_trade_testrom.py
MARKER_STRIDE    = 64

# --- confirmed hook sites (docs/ROUTINE_MAP.md) ---
BL_SITE_CATCH = 0x0A6A46
BL_SITE_GIFT  = 0x1F18DE
GIVEMON_ADDR  = 0x081AA5AC

# --- egg-hatch sweep (../game_plans/rowe_parity.md §13.16/§13.18) ---
# The injected tail for the hatch script, 11 bytes, in a verified free run
# (0xFF in both the base ROM and every build). Script `goto` operands are
# absolute pointers, so there is no BL-reach constraint on where this lives.
# tools/character_mode/egg_hook.py carries the RE and the byte grammar.
EGG_TAIL_ADDR = 0x8fa0000

# --- PC-exit sweep (../game_plans/rowe_parity.md §13.24/§13.26c) ---
# Two 14-byte replayed tails, 0x20 apart, one per PC access script (they differ
# only in where their goto rejoins). Same verified free run as the egg tail --
# splice()'s 0xFF precondition is what actually proves it clear.
# tools/character_mode/pc_hook.py has the RE.
PC_TAIL_ADDR = 0x8fa1000

# --- in-game roster display (../game_plans/roster_display.md) ---
# The family ROOTS of every character's roster, so the list's per-row callback
# can map a ROW INDEX back to a species: dynmultichoice's script-pointer form
# sets items[i].id = i, so the callback is never handed a species.
# tools/character_mode/emit_roster_roots.py has the layout and the Rika note.
# Same verified free run as the egg and PC tails, past both; measured 385,024
# contiguous 0xFF bytes from here in the BASE ROM, and splice()'s 0xFF
# precondition is what actually proves it clear at build time.
# No BL-reach constraint: the shim reaches it through an absolute pointer.
ROSTER_ROOTS_ADDR = 0x08FA2000
_ROOTS_MANIFEST = json.loads(
    (HERE / "character_mode" / "roster_roots_manifest.json").read_text())
# Derived from the emitter's own manifest and passed to the shim as -D, never
# restated: roots[] starting at a different offset in the data than in the C is
# the WILDPOOL_STRIDE bug (104 vs 176) in a new costume.
ROSTER_ROOTS_OFF = _ROOTS_MANIFEST["roots_offset_bytes"]

# The dynamic multichoice callback table, RELOCATED so the roster display can
# own a callback set (../game_plans/roster_display.md, user decision
# 2026-09-27: relocate and repoint rather than write into the bytes after it).
# sDynamicListMenuEventCollections is 2 entries x {OnInit, OnSelectionChanged,
# OnDestroy} at 0x0895CC34 (docs/ROUTINE_MAP.md "Dynamic multichoice"). The
# bytes after it belong to whatever the linker put there, so the table is
# copied to free space with a reserved slot [2] and its three literal-pool
# references are repointed. The original stays where it is, unreferenced.
# ⭐ NONE is 0xFF in this ROM, NOT 2 as in the donor's enum: all four loads
# (0x081EFFB4, 0x081F0116, 0x081F01CC, 0x081F04DA) skip on `cmp r1, #255` and
# then on a NULL callback. So slot [2] is a real index, and while it holds
# zeros it is a no-op. verify_artifacts [20] pins all of this in the built ROM.
DYN_EVENT_TABLE_ORIG = 0x0895CC34
DYN_EVENT_TABLE_REFS = (0x1EFFF4, 0x1F02B0, 0x1F05C4)   # literal-pool file offsets
DYN_EVENT_ENTRY_SIZE = 12
DYN_EVENT_ORIG_ENTRIES = 2
DYN_EVENT_SLOTS = 3                  # [2] reserved for the roster display
# Past the roster roots (4,014 B, ending 0x08FA2FAE) with a page of headroom
# for roster growth; the same verified free run, and splice() proves it clear.
DYN_EVENT_TABLE_ADDR = 0x08FA4000
# The set the roster display owns. NONE is 0xFF here, so 2 is a real index.
ROSTER_CB_SET = 2
ROSTER_LIST_TOP = 6
# src/roster_display.c: its own compile unit and link address, like the
# mugshot renderer, so nothing in the main shim moves. 0x08FA5000 is left
# free on purpose: dyn_event_table_negative_test.py uses it as its stray target.
ROSTER_MENU_ADDR = 0x08FA6000
# The roster screen's header ("<name>'s roster", user ruling 2026-10-02 adds a
# second line saying evolutions count too). NUM_CHARACTERS x 16 B display names
# indexed by TABLE index, like Radical Red's. A page past the roster code
# (which is well under 4 KB: asserted below); splice() proves it clear.
ROSTER_NAMES_ADDR = 0x08FA7000
ROSTER_NAME_STRIDE = 16              # longest display name is 12 bytes + 0xFF
PRE_ROSTER_SCRIPT_LEN = 305

GIVE_NATIVE   = 0x081F2175         # callnative give fn (49 inline script ptrs)
GIVE_NATIVE_COUNT = 49

# Reusable TMs (2026-10-09). gItemsInfo records are 84 B with the name inline at
# +0; ITEM_NAME_BASE is item 1's (Poke Ball's) name. The importance bitfield byte
# is name+0x2C (HM01-08 carry 0x01 there, TM01-100 0x00; Lazarus's TMs 0x01).
ITEM_NAME_BASE = 0x0867E7D0
ITEM_STRIDE = 84
ITEM_IMPORTANCE_OFF = 0x2C
TM_FIRST_ID = 582        # TM01; TM100 = 681, contiguous
TM_COUNT = 100

# Wild-encounter species/level roll override (task #5). Found live via
# mgba-headless breakpoint tracing (docs/ROUTINE_MAP.md): the BL at this ROM
# file offset (0x0822BF36) is the wild-encounter roll's call into
# CreateMonWithIVs-simple, firing once per encounter with r0=gEnemyParty,
# r1=rolled species, r2=rolled level -- the single choke point shared by
# every wild-roll table (grass/cave, surf, rock smash, all fishing tiers).
WILD_BL_SITE          = 0x22BF36
CREATE_MON_WITH_IVS   = 0x081A7504
# Read from the emitter's own manifest, not restated here, and passed on to the
# shim as -DWILDPOOL_STRIDE. emit_wildpool.py's POOL_STRIDE is the one
# authoritative definition; three copies of it disagreeing with a fourth in the
# C shim is what shipped the 104-vs-176 bug.
WILDPOOL_STRIDE = json.loads(
    (HERE / "character_mode" / "wildpool_manifest.json").read_text())["pool_stride"]

# 1% legendary wild encounters. Its own free run: the wildpool ends at
# 0x08F062C0 and build_trade_testrom.py squats 0x08F10000, so this sits between
# them. splice()'s 0xFF precondition is what actually proves it clear.
LEGENDARY_ADDR = 0x08F08000
_LEG_MANIFEST = json.loads(
    (HERE / "character_mode" / "legendaries_manifest.json").read_text())
LEGENDARY_COUNT = _LEG_MANIFEST["count"]

BG_EVENT_PTR_OFF = 0x123ACC        # only ref to the clipboard script

# ⭐ SECOND ACTIVATION POINT (2026-09-19, user request): the CHEAT DEVICE in the
# player's bedroom, map 1.1 (Littleroot, player's house 2F), BG event 3 at
# tile (3,1). Measured from the live map: the bedroom's four interactables are
# the PC (0,1), the LEVEL CAPS settings sign (1,1), the wall clock (5,1) and
# this cheat device (3,1) -- there is NO notebook object here, though the
# vanilla notebook TEXT survives at 0x0829171F on an unreachable branch of the
# PC script. The cheat device is the bedroom's own code terminal ("turned on
# the CHEAT DEVICE! ... Would you like to enter a code?"), i.e. the exact
# analogue of Radical Red's bedroom game console, so Character Mode rides it
# the same way it rides the Oldale mart clipboard.
BEDROOM_BG_PTR_OFF = 0xA89A98      # map 1.1 BG event 3 -> script pointer
ORIG_CHEAT_DEVICE  = 0x0830FBC9    # the stock cheat-device script
ORIG_CLIPBOARD   = 0x08311CCB

# In-game trades (docs/ROUTINE_MAP.md): sIngameTrades 0x08A3DB30, stride 60,
# 4 entries (DOTS/PLUSES/SEASOR/MEOWOW), received species u16 @+14. The 4
# scripts share an identical 17-byte confirm junction; index arrives in 0x8008
# (junction order 2,0,1,3 vs table order). We overlay the first 5 bytes with a
# goto into a per-trade wrapper that asks CM_TradeCheck first.
TRADE_TABLE_ADDR = 0x08A3DB30
TRADE_STRIDE     = 60
TRADE_RECV_OFF   = 14
TRADE_COUNT      = 4
TRADE_JUNCTIONS  = (0x29CFF5, 0x2AF873, 0x2B01EF, 0x30129E)
TRADE_JUNCTION_BYTES = bytes([0x19,0x04,0x80,0x08,0x80, 0x19,0x05,0x80,0x0A,0x80,
                              0x25,0x00,0x01, 0x25,0x01,0x01, 0x27])
TRADE_SCRIPT_ADDR = 0x08EE3B00

# script/engine constants
YESNO_TEXT_ADDR = None             # our msg (in-script); built below
GStringVar2 = 0x0203AF24

FLAG_CHARACTER_MODE = 0x2B0
VAR_CM_CHAR    = 0x40E4
VAR_CM_STARTER = 0x40E5

# --- charmap ---
def load_charmap():
    table = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    with open(CHARMAP, encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.rstrip("\n"))
            if m and m.group(1) not in table:
                table[m.group(1)] = int(m.group(2), 16)
    return table


def enc_text(s, cm):
    out = bytearray()
    for ch in s:
        if ch == "\n":
            out.append(0xFE)
            continue
        if ch not in cm:
            raise ValueError(f"char {ch!r} not in charmap: {s!r}")
        out.append(cm[ch])
    out.append(0xFF)
    return bytes(out)


def thumb_bl(src, dst):
    off = dst - (src + 4)
    assert -0x400000 <= off < 0x400000, f"BL out of range: {off:#x}"
    off = (off >> 1) & 0x3FFFFF
    return struct.pack("<HH", 0xF000 | ((off >> 11) & 0x7FF), 0xF800 | (off & 0x7FF))


def code_for(display):
    n = unicodedata.normalize("NFKD", display)
    n = "".join(ch for ch in n if not unicodedata.combining(ch))
    return "".join(ch for ch in n if ch.isalnum())[:10]


# --- script opcodes (verified against this ROM's scripts / donor table) ---
def op_lockall():           return bytes([0x69])
def op_releaseall():        return bytes([0x6B])
def op_end():               return bytes([0x02])
def op_return():            return bytes([0x03])
def op_waitstate():         return bytes([0x27])
def op_callnative(fn):      return bytes([0x23]) + struct.pack("<I", fn | 1)
def op_compare(var, val):   return bytes([0x21]) + struct.pack("<HH", var, val)
def op_goto_if(cond, addr): return bytes([0x06, cond]) + struct.pack("<I", addr)
def op_goto(addr):          return bytes([0x05]) + struct.pack("<I", addr)
def op_setvar(var, val):    return bytes([0x16]) + struct.pack("<HH", var, val)
def op_copyvar(dst, src):   return bytes([0x19]) + struct.pack("<HH", dst, src)
def op_bufferspecies(buf, sp): return bytes([0x7D, buf]) + struct.pack("<H", sp)
def op_loadword(addr):      return bytes([0x0F, 0x00]) + struct.pack("<I", addr)
def op_callstd(n):          return bytes([0x09, n])
def op_msgbox_yesno(addr):
    # loadword 0 (text ptr) then callstd 5 (yes/no) -> VAR_RESULT 1=yes 0=no
    return op_loadword(addr) + op_callstd(5)
def op_dynmultichoice(cb_set, names):
    """dynmultichoice, script-pointer form: left 0, top 0, B allowed, default
    rows before scroll, unsorted, initial 0. Layout decoded from this ROM's
    handler (0x081EE0B1): E3 u16 u16 u8 u8 u8 u16 u8(set) u8(argc) u32[argc]."""
    return (bytes([0xE3]) + struct.pack("<HH", 0, 0) + bytes([0, 0xFF, 0])
            + struct.pack("<H", 0) + bytes([cb_set, len(names)])
            + b"".join(struct.pack("<I", n) for n in names))
def op_dynmultistack(cb_set, top=0):
    """The STACK form: argc 1 and a NULL word, which the handler peeks but does
    not consume, so it then runs as four `nop` (opcode 0x00 is a no-op here).
    top: CreateWindowFromRect adds 1, so top=6 puts the list at tile row 7."""
    return (bytes([0xE3]) + struct.pack("<HH", 0, top) + bytes([0, 0xFF, 0])
            + struct.pack("<H", 0) + bytes([cb_set, 1]) + struct.pack("<I", 0))
def op_givenative(species_var_or_id, fn):
    # the ROM's own give idiom: callnative <fn> + 10 inline arg bytes
    # (const 0x0600, species, level 5, 0, 0). species may be a var id (VarGet'd).
    # Our confirm-script give points at the wrapper (CM_NativeGiveGated) so the
    # starter is gated like every other give; it stays because roster[0] is
    # always on the character's own bitmap (emit invariant).
    return (bytes([0x23]) + struct.pack("<I", fn | 1)
            + struct.pack("<HHHHH", 0x0600, species_var_or_id, 5, 0, 0))


def build_scripts(cm):
    """Two free-space scripts: the entry script (repointed BG ptr) and the
    confirm/give tail. Returns (blob, entry_addr) with the entry at SCRIPT_ADDR.
    All internal pointers are resolved to absolute ROM addresses."""
    # text
    t_prompt  = enc_text("Enter a Character Mode code?", cm)
    t_on      = enc_text("Character Mode is now active!\nOff-roster catches go to the PC.", cm)
    t_off     = enc_text("Character Mode is now off.", cm)
    t_invalid = enc_text("That code is not valid.", cm)

    # We assemble in two passes: build with placeholder pointers, then fix up.
    # Layout: [entry][match_tail][text...]
    # ---- entry script ----
    # lockall
    # msgbox_yesno(prompt)
    # compare VAR_RESULT, 1 ; goto_if != -> goto ORIG_CLIPBOARD  (declined)
    # callnative CM_OpenCodeEntry
    # waitstate
    # callnative CM_MatchCode
    # goto match_tail
    # ---- match_tail ----
    # compare VAR_RESULT, 1 ; goto_if EQ -> give_block
    # compare VAR_RESULT, 2 ; goto_if EQ -> off_block
    # (else invalid) loadword invalid ; callstd 4 ; releaseall ; end
    # ---- give_block ----  (Result==1: character or dbg-give1/2)
    # loadword t_on ; callstd 4
    # copyvar 0x8000, VAR_CM_STARTER ; bufferspecies 0, 0x8000 ; setvar 0x4001,0x8000
    # setvar VAR_CM_STARTER, 0            (consume marker before give)
    # givenative(0x8000)
    # releaseall ; end
    # ---- off_block ----  (Result==2: dbg-off)
    # loadword t_off ; callstd 4 ; releaseall ; end
    HOOK = {}  # filled by caller via labels below; we need shim entry addrs

    t_view  = enc_text("View roster", cm)
    t_code  = enc_text("Character code", cm)
    t_quest = enc_text("Questionnaire", cm)
    t_gift  = enc_text("Gift code", cm)
    return dict(t_prompt=t_prompt, t_on=t_on, t_off=t_off, t_invalid=t_invalid,
                t_view=t_view, t_code=t_code, t_quest=t_quest, t_gift=t_gift)


def main():
    data = bytearray(ROM_IN.read_bytes())
    got = hashlib.sha1(data).hexdigest()
    if got != ROM_SHA1:
        raise SystemExit(f"ROM sha1 mismatch: {got}")

    cm = load_charmap()
    manifest = json.loads((CM / "characters_manifest.json").read_text())
    chars = manifest["characters"]
    assert len(chars) == NUM_CHARACTERS, len(chars)
    bitmaps = (CM / "rosters_expanded.bin").read_bytes()
    assert len(bitmaps) == NUM_CHARACTERS * BITMAP_STRIDE, len(bitmaps)
    wildpool = (CM / "wildpool.bin").read_bytes()
    assert len(wildpool) == NUM_CHARACTERS * WILDPOOL_STRIDE * 4, len(wildpool)
    legendaries = (CM / "legendaries.bin").read_bytes()
    assert len(legendaries) == LEGENDARY_COUNT * 4 + NUM_CHARACTERS * 4, (
        len(legendaries), LEGENDARY_COUNT, NUM_CHARACTERS)
    roster_roots = (CM / "roster_roots.bin").read_bytes()
    # Re-derived from the manifest rather than trusting the .bin's own length:
    # entry table + one u16 per root, with the character count derived as
    # everywhere else in this file.
    assert len(roster_roots) == (
        NUM_CHARACTERS * _ROOTS_MANIFEST["entry_size_bytes"]
        + _ROOTS_MANIFEST["total_roots"] * 2), (
        len(roster_roots), NUM_CHARACTERS, _ROOTS_MANIFEST["total_roots"])
    assert _ROOTS_MANIFEST["characters"] == NUM_CHARACTERS, (
        "roster_roots.bin was emitted for %d characters, this build has %d -- "
        "re-run emit_roster_roots.py"
        % (_ROOTS_MANIFEST["characters"], NUM_CHARACTERS))

    # --- code + starter tables ---
    #
    # THE PLAYABILITY THRESHOLD IS ENFORCED HERE, by poisoning the code slot of
    # every hidden character. Seaglass selects by typed code rather than by a
    # menu, so there is no list to filter and no shim change is needed -- an
    # unmatchable code slot IS the gate, and a hidden character's code is then
    # refused exactly like an unknown one.
    #
    # Why 11 non-terminator bytes rather than "a lead byte the screen cannot
    # produce" (which is what game_plans/seaglass.md suggested): that would
    # require knowing the CODE keyboard's exact character set, which we do not.
    # This is unmatchable by CONSTRUCTION instead. CM_OpenCodeEntry pre-clears
    # all CODE_LEN (11) bytes of gStringVar2 to 0xFF and the screen accepts at
    # most 10 characters, so entered[10] is ALWAYS 0xFF. codeEq() walks all 11
    # bytes and only returns a match on a simultaneous 0xFF, so a stored code
    # with no 0xFF anywhere can never match any reachable entry -- including 10
    # spaces, which is the closest a player could get.
    # 0xFE (newline) is used as the fill because it is also not producible on a
    # naming screen, so the property holds twice over for independent reasons.
    #
    # Hidden characters KEEP their index -- saves store the character INDEX, and
    # an already-selected hidden character keeps working. This blocks NEW
    # selection only.
    CODE_POISON = b"\xFE" * CODE_LEN
    codes = bytearray()
    seen = {}
    starters = []
    typed = []
    n_hidden = 0
    for c in chars:
        code = code_for(c["character"])
        key = code.upper()
        assert 1 <= len(code) <= 10, (c["character"], code)
        assert key not in seen, f"code collision: {code} ({c['character']} vs {seen[key]})"
        seen[key] = c["character"]
        if c.get("hidden"):
            n_hidden += 1
            typed.append(None)               # not offered; excluded from codes.txt
            codes += CODE_POISON
        else:
            typed.append(code)
            enc = enc_text(code, cm)
            assert len(enc) <= CODE_LEN
            assert 0xFF in enc + b"\xFF" * (CODE_LEN - len(enc)), code
            codes += enc + b"\xFF" * (CODE_LEN - len(enc))
        # ⚠️ An EMPTY roster needs its own branch here. Since 2026-08-20 a
        # character whose roster empties out keeps its table slot as a hidden
        # record rather than being dropped, because a save stores the character
        # INDEX and dropping one renumbers everyone behind it. Three characters
        # are in that state (Juniper, Rowan, Sonia). They are hidden, so no
        # starter of theirs can ever be granted -- but this line ran for every
        # record regardless and died on roster_species_ids[0].
        # ("Empty rosters need an explicit branch in every consumer" is a
        # standing trap in this project; this is that trap, in this file.)
        ids = c["roster_species_ids"]
        if c.get("has_signature") and c.get("signature_id"):
            sig = c["signature_id"]
        elif ids:
            sig = ids[0]
        else:
            assert c.get("hidden"), (
                "%s has an empty roster but is OFFERED -- it would grant "
                "SPECIES_NONE as a starter" % c["character"])
            sig = 0                          # SPECIES_NONE; unreachable slot
        starters.append(sig)
    assert n_hidden == sum(1 for c in chars if c.get("hidden"))
    print(f"threshold: {NUM_CHARACTERS - n_hidden} offered, {n_hidden} hidden "
          f"(code slots poisoned; indices unchanged)")
    starters_blob = b"".join(struct.pack("<H", s) for s in starters)

    # off-roster debug species for CMDBGGIVE2: lowest valid id not on char-1 bitmap
    sp_table = json.loads((CM / "rom_species_table.json").read_text())["species"]
    bm0 = bitmaps[0:BITMAP_STRIDE]
    def on0(sp): return (bm0[sp >> 3] >> (sp & 7)) & 1
    dbg_give2 = next(sp for sp in range(1, 1489)
                     if str(sp) in sp_table and not on0(sp)
                     and not sp_table[str(sp)].startswith("？"))
    print(f"CMDBGGIVE2 species (off-roster for {chars[0]['character']}): "
          f"{dbg_give2} ({sp_table[str(dbg_give2)]})")

    # --- compile shim ---
    BUILD.mkdir(exist_ok=True)
    obj, elf, binf = BUILD / "cm.o", BUILD / "cm.elf", BUILD / "cm.bin"
    subprocess.run(["arm-none-eabi-gcc", "-c", "-mthumb", "-mcpu=arm7tdmi",
                    "-O2", "-ffreestanding", "-fno-builtin", "-fno-jump-tables",
                    f"-DCODES_ADDR={CODES_ADDR:#x}",
                    f"-DSTARTERS_ADDR={STARTERS_ADDR:#x}",
                    f"-DBITMAPS_ADDR={BITMAPS_ADDR:#x}",
                    f"-DDBG_GIVE2_SPECIES={dbg_give2}",
                    f"-DTRADE_TABLE_ADDR={TRADE_TABLE_ADDR:#x}",
                    f"-DTRADE_STRIDE={TRADE_STRIDE}",
                    f"-DTRADE_RECV_OFF={TRADE_RECV_OFF}",
                    f"-DTRADE_COUNT={TRADE_COUNT}",
                    f"-DWILDPOOL_ADDR={WILDPOOL_ADDR:#x}",
                    f"-DMARKER_ADDR={MARKER_ADDR:#x}",
                    f"-DWILDPOOL_STRIDE={WILDPOOL_STRIDE}",
                    f"-DNUM_CHARACTERS={NUM_CHARACTERS}",
                    f"-DTOBIAS_CHAR_ID={TOBIAS_CHAR_ID}",
                    f"-DLEGENDARY_ADDR={LEGENDARY_ADDR:#x}",
                    f"-DLEGENDARY_COUNT={LEGENDARY_COUNT}",
                    f"-DROSTER_ROOTS_ADDR={ROSTER_ROOTS_ADDR:#x}",
                    f"-DROSTER_ROOTS_OFF={ROSTER_ROOTS_OFF}",
                    "-o", str(obj), str(ROOT / "src" / "character_mode.c")],
                   check=True)
    libgcc = subprocess.run(["arm-none-eabi-gcc", "-mthumb", "-mcpu=arm7tdmi",
                             "-print-libgcc-file-name"], check=True,
                            capture_output=True, text=True).stdout.strip()
    subprocess.run(["arm-none-eabi-ld", "-Ttext", f"{SHIM_ADDR:#x}",
                    "--entry", "CM_OpenCodeEntry",
                    "-o", str(elf), str(obj), libgcc], check=True)
    subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", str(elf), str(binf)],
                   check=True)
    shim = binf.read_bytes()
    sym_out = subprocess.run(["arm-none-eabi-nm", str(elf)], check=True,
                             capture_output=True, text=True).stdout
    syms = {m.group(2): int(m.group(1), 16)
            for m in re.finditer(r"^([0-9a-f]+) [Tt] (\w+)$", sym_out, re.M)}
    for need in ("CM_OpenCodeEntry", "CM_MatchCode", "CM_GiveMonToPlayerGated",
                 "CM_NativeGiveGated", "CM_TradeCheck", "CM_WildMonSpeciesGated",
                 "CM_CatchOddsStub", "CM_CatchOdds"):
        assert need in syms, f"missing symbol {need}"
    assert len(shim) <= BITMAPS_ADDR - SHIM_ADDR, f"shim too big: {len(shim)}"
    print(f"shim: {len(shim)} bytes @ {SHIM_ADDR:#x}")
    print(f"shim constants (derived, -D): NUM_CHARACTERS={NUM_CHARACTERS} "
          f"WILDPOOL_STRIDE={WILDPOOL_STRIDE} TOBIAS_CHAR_ID={TOBIAS_CHAR_ID}"
          f"{'' if TOBIAS_CHAR_ID else ' (Tobias not in roster -- 1%% branch dead)'}")

    hook_open   = syms["CM_OpenCodeEntry"]
    hook_match  = syms["CM_MatchCode"]
    hook_gate   = syms["CM_GiveMonToPlayerGated"] | 1
    hook_native = syms["CM_NativeGiveGated"]
    hook_wild   = syms["CM_WildMonSpeciesGated"]
    hook_marker = syms["CM_BattleStringGated"] | 1
    hook_sweep  = syms["CM_SweepPartyToPCNative"] | 1
    hook_pss_guard = syms["CM_PSSLastMonGuard"] | 1

    # --- mugshot renderer: separate compile unit + link address (see
    # CM_MUGSHOT_ADDR). Both entry points are resolved from the linked ELF
    # rather than assumed to be in source order -- gcc may emit them either
    # way and the `callnative` operands must be exact. ---
    mobj, melf, mbin = BUILD / "character_sprite.o", BUILD / "character_sprite.elf", BUILD / "character_sprite.bin"
    subprocess.run(["arm-none-eabi-gcc", "-c", "-mthumb", "-mcpu=arm7tdmi",
                    "-O2", "-ffreestanding", "-fno-builtin", "-Wall", "-Wextra",
                    f"-DSPRITE_PTRS_ADDR={CM_SPRITE_PTRS_ADDR:#x}",
                    f"-DNUM_CHARACTERS={NUM_CHARACTERS}",
                    "-o", str(mobj), str(ROOT / "src" / "character_sprite.c")], check=True)
    subprocess.run(["arm-none-eabi-ld", "-Ttext", f"{CM_MUGSHOT_ADDR:#x}",
                    "--entry", "CM_ShowCharacterMugshot",
                    "-o", str(melf), str(mobj)], check=True)
    subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", str(melf), str(mbin)], check=True)
    mugshot = mbin.read_bytes()
    _msym = subprocess.run(["arm-none-eabi-nm", str(melf)], check=True,
                           capture_output=True, text=True).stdout

    def _mug_sym(name):
        m = re.search(rf"^([0-9a-f]+) [Tt] {name}$", _msym, re.M)
        assert m, f"{name} not found in:\n{_msym}"
        a = int(m.group(1), 16)
        assert CM_MUGSHOT_ADDR <= a < CM_MUGSHOT_ADDR + len(mugshot), \
            f"{name} at {a:#x} outside the spliced blob"
        return a | 1                    # callnative operands carry the Thumb bit

    hook_mug_show = _mug_sym("CM_ShowCharacterMugshot")
    hook_mug_hide = _mug_sym("CM_HideCharacterMugshot")
    print(f"mugshot renderer: {len(mugshot)} bytes @ {CM_MUGSHOT_ADDR:#x} "
          f"(show {hook_mug_show:#x}, hide {hook_mug_hide:#x})")

    # --- in-game roster display: row pusher + dynmultichoice callback set 2
    # (src/roster_display.c). Separate unit and link address, same reasons as
    # the mugshot renderer; every entry point is resolved from the ELF. ---
    robj, relf, rbin = BUILD / "roster_display.o", BUILD / "roster_display.elf", BUILD / "roster_display.bin"
    subprocess.run(["arm-none-eabi-gcc", "-c", "-mthumb", "-mcpu=arm7tdmi",
                    "-O2", "-ffreestanding", "-fno-builtin", "-Wall", "-Wextra",
                    f"-DNUM_CHARACTERS={NUM_CHARACTERS}",
                    f"-DROSTER_ROOTS_ADDR={ROSTER_ROOTS_ADDR:#x}",
                    f"-DROSTER_ROOTS_OFF={ROSTER_ROOTS_OFF}",
                    f"-DROSTER_NAMES_ADDR={ROSTER_NAMES_ADDR:#x}",
                    f"-DROSTER_NAME_STRIDE={ROSTER_NAME_STRIDE}",
                    "-o", str(robj), str(ROOT / "src" / "roster_display.c")], check=True)
    subprocess.run(["arm-none-eabi-ld", "-Ttext", f"{ROSTER_MENU_ADDR:#x}",
                    "--entry", "CM_RosterPushRows",
                    "-o", str(relf), str(robj)], check=True)
    subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", str(relf), str(rbin)], check=True)
    roster_menu = rbin.read_bytes()
    assert ROSTER_MENU_ADDR + len(roster_menu) <= ROSTER_NAMES_ADDR, (
        f"roster display code ({len(roster_menu)} B) runs into the header names")
    # Header names, fixed stride, indexed by table index (VAR_CM_CHAR - 1).
    _names_bin = (CM / "names.bin").read_bytes()
    _cm_chars = json.loads((CM / "characters_manifest.json").read_text())["characters"]
    assert len(_cm_chars) == NUM_CHARACTERS
    roster_names = bytearray()
    for _c in _cm_chars:
        _nm = _names_bin[_c["name_offset"]:_names_bin.index(b"\xff", _c["name_offset"])]
        assert len(_nm) < ROSTER_NAME_STRIDE, (_c["character"], len(_nm))
        roster_names += _nm + b"\xff" * (ROSTER_NAME_STRIDE - len(_nm))
    _rsym = subprocess.run(["arm-none-eabi-nm", str(relf)], check=True,
                           capture_output=True, text=True).stdout

    def _roster_sym(name):
        m = re.search(rf"^([0-9a-f]+) [Tt] {name}$", _rsym, re.M)
        assert m, f"{name} not found in:\n{_rsym}"
        a = int(m.group(1), 16)
        assert ROSTER_MENU_ADDR <= a < ROSTER_MENU_ADDR + len(roster_menu), \
            f"{name} at {a:#x} outside the spliced blob"
        return a | 1

    hook_roster_push = _roster_sym("CM_RosterPushRows")
    roster_callbacks = (_roster_sym("CM_RosterMenu_OnInit"),
                        _roster_sym("CM_RosterMenu_OnSelectionChanged"),
                        _roster_sym("CM_RosterMenu_OnDestroy"))
    print(f"roster display: {len(roster_menu)} bytes @ {ROSTER_MENU_ADDR:#x} "
          f"(push {hook_roster_push:#x}, set {ROSTER_CB_SET} = "
          f"{', '.join(f'{c:#x}' for c in roster_callbacks)})")

    # --- overworld sprite (2026-10-03, ../game_plans/overworld_sprites.md):
    # the data is planned against the BASE ROM (all of it lands in OW_REGIONS,
    # Character Mode's own free block), then src/ow_sprite.c is linked at
    # OW_CODE_ADDR with the info table's address. Written after every other
    # splice, each byte re-checked 0xFF. ---
    sys.path.insert(0, str(CM))
    import seaglass_ow_player as owp
    ow_writes, ow_patches, ow_table, ow_ptrs, ow_sources = owp.build(bytes(data), chars)
    oobj, oelf, obin = BUILD / "ow_sprite.o", BUILD / "ow_sprite.elf", BUILD / "ow_sprite.bin"
    subprocess.run(["arm-none-eabi-gcc", "-c", "-mthumb", "-mcpu=arm7tdmi",
                    "-O2", "-ffreestanding", "-fno-builtin", "-Wall", "-Wextra",
                    f"-DOW_INFO_TABLE={ow_table:#x}",
                    f"-DNUM_CHARACTERS={NUM_CHARACTERS}",
                    f"-DGET_INFO_RESUME={(owp.GET_INFO + 8) | 1:#x}",
                    f"-DSWEEP_PARTY={hook_sweep:#x}",
                    "-o", str(oobj), str(ROOT / "src" / "ow_sprite.c")], check=True)
    subprocess.run(["arm-none-eabi-ld", "-Ttext", f"{owp.OW_CODE_ADDR:#x}",
                    "--entry", "CM_GetObjectEventGraphicsInfo",
                    "-o", str(oelf), str(oobj)], check=True)
    subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", str(oelf), str(obin)], check=True)
    ow_code = obin.read_bytes()
    assert len(ow_code) <= owp.OW_CODE_MAX, f"ow_sprite.c grew to {len(ow_code)} B"
    _osym = subprocess.run(["arm-none-eabi-nm", str(oelf)], check=True,
                           capture_output=True, text=True).stdout

    def _ow_sym(name):
        m = re.search(rf"^([0-9a-f]+) [Tt] {name}$", _osym, re.M)
        assert m, f"{name} not found in:\n{_osym}"
        a = int(m.group(1), 16)
        assert owp.OW_CODE_ADDR <= a < owp.OW_CODE_ADDR + len(ow_code), name
        return a | 1

    hook_ow_info = _ow_sym("CM_GetObjectEventGraphicsInfo")
    hook_ow_refresh = _ow_sym("CM_RefreshPlayerAvatar")
    hook_ow_sweep_refresh = _ow_sym("CM_SweepThenRefresh")
    print(f"overworld sprite: {len(ow_code)} B code @ {owp.OW_CODE_ADDR:#x}; "
          f"{sum(1 for v in ow_sources.values() if v == 'sheet')} sheets + "
          f"{sum(1 for v in ow_sources.values() if v == 'native')} native, "
          f"{sum(len(b) for _, b in ow_writes):,} B data; info table @ {ow_table:#x}")

    # --- compile + link the separate wild-encounter trampoline (long-call
    # veneer: its hook site is ~7.6 MiB from the main shim blob, out of Thumb
    # BL range, so it lives in its own tiny scavenged slot near both the hook
    # site and CreateMonWithIVs -- see src/wild_trampoline.c) ---
    wobj, welf, wbin = BUILD / "wtramp.o", BUILD / "wtramp.elf", BUILD / "wtramp.bin"
    subprocess.run(["arm-none-eabi-gcc", "-c", "-mthumb", "-mcpu=arm7tdmi",
                    "-O2", "-ffreestanding", "-fno-builtin",
                    f"-DGATED_FN_ADDR={hook_wild:#x}",
                    f"-DORIG_TARGET_ADDR={CREATE_MON_WITH_IVS:#x}",
                    "-o", str(wobj), str(ROOT / "src" / "wild_trampoline.c")],
                   check=True)
    subprocess.run(["arm-none-eabi-ld", "-Ttext", f"{WILD_TRAMPOLINE_ADDR:#x}",
                    "--entry", "CM_WildMonSpecies_Trampoline",
                    "-o", str(welf), str(wobj)], check=True)
    subprocess.run(["arm-none-eabi-objcopy", "-O", "binary", str(welf), str(wbin)],
                   check=True)
    wild_tramp = wbin.read_bytes()
    assert len(wild_tramp) <= 0x100, f"wild veneer grew to {len(wild_tramp)} B"
    # The stub must reach the veneer only by absolute address; the BL reach
    # constraint is on the stub, which the thumb_bl below asserts.
    print(f"wild trampoline: {len(wild_tramp)} bytes @ {WILD_TRAMPOLINE_ADDR:#x}")

    # --- assemble entry + confirm scripts (two-pass fixup) ---
    txt = build_scripts(cm)
    # compute block layout by building with zero pointers, measuring, then re-emit.
    def emit(addrs):
        e = bytearray()
        # entry
        e += op_lockall()
        e += op_msgbox_yesno(addrs["t_prompt"])
        e += op_compare(0x800D, 1)
        e += op_goto_if(5, ORIG_CLIPBOARD)        # != yes -> original flow
        # Everything from here on is the ACCEPTED path. The bedroom stub below
        # jumps straight to it, so the two entry points share one code path and
        # one set of strings -- a second copy would be a second thing to drift.
        addrs["accept_here"] = len(e)
        e += op_callnative(hook_open)
        e += op_waitstate()
        e += op_callnative(hook_match)
        e += op_goto(addrs["tail"])
        addrs["_entry_end"] = len(e)
        # tail
        addrs["tail_here"] = len(e)
        e += op_compare(0x800D, 1)
        e += op_goto_if(1, addrs["give"])
        e += op_compare(0x800D, 2)
        e += op_goto_if(1, addrs["off"])
        e += op_loadword(addrs["t_invalid"]) + op_callstd(4)
        e += op_releaseall() + op_end()
        # give block
        addrs["give_here"] = len(e)
        # mugshot bracket: show before the message, hide after callstd 4
        # returns (it blocks until the player presses A)
        e += op_callnative(hook_mug_show)
        e += op_loadword(addrs["t_on"]) + op_callstd(4)
        e += op_callnative(hook_mug_hide)
        e += op_copyvar(0x8000, VAR_CM_STARTER)
        e += op_bufferspecies(0, 0x8000)
        e += op_setvar(0x4001, 0x8000)
        e += op_setvar(VAR_CM_STARTER, 0)
        e += op_givenative(0x8000, hook_native)
        # Sweep AFTER the give, never before: beforehand a party holding only an
        # off-roster mon hits the never-empty rule and nothing is boxed.
        # ... then the player takes on the character's look (src/ow_sprite.c's
        # CM_SweepThenRefresh calls the same sweep first). One callnative, the
        # same 5 bytes as before: naming_open.ss pins this blob's length.
        e += op_callnative(hook_ow_sweep_refresh)
        e += op_releaseall() + op_end()
        # off block
        addrs["off_here"] = len(e)
        e += op_loadword(addrs["t_off"]) + op_callstd(4)
        e += op_releaseall() + op_end()
        # text
        addrs["t_prompt_here"] = len(e); e += txt["t_prompt"]
        addrs["t_on_here"]     = len(e); e += txt["t_on"]
        addrs["t_off_here"]    = len(e); e += txt["t_off"]
        addrs["t_invalid_here"]= len(e); e += txt["t_invalid"]
        # ---- bedroom cheat-device stub (second activation point) ----
        # Same question, same texts, same accepted path; only the DECLINED
        # target differs, because "No" must fall through to that object's own
        # stock script rather than the clipboard's.
        addrs["bedroom_here"] = len(e)
        e += op_lockall()
        e += op_msgbox_yesno(addrs["t_prompt"])
        e += op_compare(0x800D, 1)
        e += op_goto_if(5, ORIG_CHEAT_DEVICE)     # != yes -> stock cheat device
        e += op_goto(addrs["accept"])
        # ---- roster display entry (2026-09-27) ----
        # ⚠️ APPENDED, never inserted: naming_open.ss holds a paused script
        # context INSIDE the blob above, so no byte before this point may move.
        # The two BG-event pointers now land on these pre-entries instead; with
        # Character Mode OFF each one jumps straight to the unchanged entry
        # above, so the activation flow is byte-for-byte what it was.
        # With it ON: View roster / Character code / <the object's own use>.
        def pre_entry(orig_entry, stock, t_third):
            b = bytearray()
            b += bytes([0x2B]) + struct.pack("<H", FLAG_CHARACTER_MODE)  # checkflag
            b += op_goto_if(0, orig_entry)                               # unset -> as before
            b += op_lockall()
            b += op_dynmultichoice(0xFF, [addrs["t_view"], addrs["t_code"], t_third])
            b += op_compare(0x800D, 0) + op_goto_if(1, addrs["roster"])
            b += op_compare(0x800D, 1) + op_goto_if(1, addrs["accept"])
            b += op_compare(0x800D, 2) + op_goto_if(1, stock)           # as a declined prompt does
            b += op_releaseall() + op_end()                              # B
            return b
        addrs["clip_pre_here"] = len(e)
        e += pre_entry(base_entry, ORIG_CLIPBOARD, addrs["t_quest"])
        addrs["bed_pre_here"] = len(e)
        e += pre_entry(base_entry + addrs["bedroom_here"], ORIG_CHEAT_DEVICE, addrs["t_gift"])
        # shared list: push the active character's roots, then the stack form
        # of dynmultichoice with callback set ROSTER_CB_SET. VAR_RESULT == 0
        # (no rows) skips the menu rather than drawing an empty box.
        addrs["roster_here"] = len(e)
        e += op_callnative(hook_roster_push)
        e += op_compare(0x800D, 0) + op_goto_if(1, addrs["roster_end"])
        # top 6: list at rows 7-18 under the 4-row header window that
        # CM_RosterMenu_OnInit adds at rows 1-4 (frames 0-5 and 6-19).
        e += op_dynmultistack(ROSTER_CB_SET, ROSTER_LIST_TOP)
        addrs["roster_end_here"] = len(e)
        e += op_releaseall() + op_end()
        addrs["t_view_here"]  = len(e); e += txt["t_view"]
        addrs["t_code_here"]  = len(e); e += txt["t_code"]
        addrs["t_quest_here"] = len(e); e += txt["t_quest"]
        addrs["t_gift_here"]  = len(e); e += txt["t_gift"]
        return e

    base = SCRIPT_ADDR
    base_entry = SCRIPT_ADDR
    # pass 1: placeholder addrs -> measure block offsets
    ph = dict(t_prompt=base, t_on=base, t_off=base, t_invalid=base,
              tail=base, give=base, off=base, accept=base,
              roster=base, roster_end=base, t_view=base, t_code=base,
              t_quest=base, t_gift=base)
    tmp = emit(ph)
    A = base
    addrs = dict(
        tail   = A + ph["tail_here"],
        give   = A + ph["give_here"],
        off    = A + ph["off_here"],
        t_prompt = A + ph["t_prompt_here"],
        t_on     = A + ph["t_on_here"],
        t_off    = A + ph["t_off_here"],
        t_invalid= A + ph["t_invalid_here"],
        accept   = A + ph["accept_here"],
        roster     = A + ph["roster_here"],
        roster_end = A + ph["roster_end_here"],
        t_view   = A + ph["t_view_here"],
        t_code   = A + ph["t_code_here"],
        t_quest  = A + ph["t_quest_here"],
        t_gift   = A + ph["t_gift_here"],
    )
    script = emit(addrs)
    assert len(script) == len(tmp)
    BEDROOM_ENTRY = A + addrs["bedroom_here"]
    CLIPBOARD_PRE = A + addrs["clip_pre_here"]
    BEDROOM_PRE = A + addrs["bed_pre_here"]
    # The pre-roster blob must not change length: naming_open.ss holds a paused
    # context pointing INTO it, so every label before the appended roster
    # entry has to stay at its offset. 305 B measured on build d62f9d6b, the
    # last build before the roster entry was appended.
    assert addrs["clip_pre_here"] == PRE_ROSTER_SCRIPT_LEN, (
        f"the entry blob before the roster pre-entries is "
        f"{addrs['clip_pre_here']} B, expected {PRE_ROSTER_SCRIPT_LEN}: something "
        f"was INSERTED, which shifts the paused script in naming_open.ss")
    # The blob must stay inside its own region: the trade wrappers start at
    # TRADE_SCRIPT_ADDR and splice() would only notice a collision by accident.
    assert SCRIPT_ADDR + len(script) <= TRADE_SCRIPT_ADDR, (
        f"entry scripts ({len(script)} B) overrun into the trade wrappers "
        f"at {TRADE_SCRIPT_ADDR:#x}")
    print(f"scripts: {len(script)} bytes @ {SCRIPT_ADDR:#x} "
          f"(bedroom entry @ {BEDROOM_ENTRY:#x}, "
          f"{TRADE_SCRIPT_ADDR - (SCRIPT_ADDR + len(script))} B headroom)")

    # --- splice payloads ---
    def splice(rom_addr, payload, label):
        off = rom_addr - 0x08000000
        assert rom_addr + len(payload) <= FREE_END_ROM, f"{label} overruns ROM"
        seg = data[off:off + len(payload)]
        assert all(b == 0xFF for b in seg), f"{label}: target not 0xFF @ {rom_addr:#x}"
        data[off:off + len(payload)] = payload

    splice(SHIM_ADDR, shim, "shim")
    splice(BITMAPS_ADDR, bitmaps, "bitmaps")
    splice(CODES_ADDR, bytes(codes), "codes")
    splice(STARTERS_ADDR, starters_blob, "starters")
    splice(SCRIPT_ADDR, bytes(script), "scripts")
    splice(WILDPOOL_ADDR, wildpool, "wildpool")
    splice(LEGENDARY_ADDR, legendaries, "legendaries")
    splice(ROSTER_ROOTS_ADDR, roster_roots, "roster roots")
    splice(CM_MUGSHOT_ADDR, mugshot, "mugshot renderer")
    assert DYN_EVENT_TABLE_ADDR + DYN_EVENT_SLOTS * DYN_EVENT_ENTRY_SIZE <= ROSTER_MENU_ADDR
    splice(ROSTER_MENU_ADDR, roster_menu, "roster display code")
    splice(ROSTER_NAMES_ADDR, bytes(roster_names), "roster header names")

    # --- dynamic multichoice callback table: relocate + repoint ---
    assert ROSTER_ROOTS_ADDR + len(roster_roots) <= DYN_EVENT_TABLE_ADDR, (
        f"roster roots end at {ROSTER_ROOTS_ADDR + len(roster_roots):#x}, past "
        f"the relocated callback table at {DYN_EVENT_TABLE_ADDR:#x} -- move it up")
    assert DYN_EVENT_TABLE_ADDR % 4 == 0
    _dyn_orig_off = DYN_EVENT_TABLE_ORIG - 0x08000000
    _dyn_live = bytes(data[_dyn_orig_off:
                           _dyn_orig_off + DYN_EVENT_ORIG_ENTRIES * DYN_EVENT_ENTRY_SIZE])
    # Every copied word must be a Thumb ROM function pointer: a wrong
    # DYN_EVENT_TABLE_ORIG would otherwise copy some other object faithfully.
    for _w in struct.unpack(f"<{len(_dyn_live) // 4}I", _dyn_live):
        assert 0x08000000 <= _w < 0x0A000000 and _w & 1, (
            f"callback table at {DYN_EVENT_TABLE_ORIG:#x} holds {_w:#x}, not a "
            f"Thumb function pointer -- wrong address or wrong ROM")
    assert DYN_EVENT_SLOTS == ROSTER_CB_SET + 1 == DYN_EVENT_ORIG_ENTRIES + 1
    _dyn_table = _dyn_live + struct.pack("<III", *roster_callbacks)
    splice(DYN_EVENT_TABLE_ADDR, _dyn_table, "dynamic multichoice callback table")
    for _roff in DYN_EVENT_TABLE_REFS:
        _cur = struct.unpack_from("<I", data, _roff)[0]
        assert _cur == DYN_EVENT_TABLE_ORIG, (
            f"callback-table literal {_roff + 0x08000000:#x} holds {_cur:#x}, "
            f"expected {DYN_EVENT_TABLE_ORIG:#x} -- wrong ROM, or already patched")
        struct.pack_into("<I", data, _roff, DYN_EVENT_TABLE_ADDR)
    print(f"dynmultichoice callback table: {DYN_EVENT_SLOTS} slots @ "
          f"{DYN_EVENT_TABLE_ADDR:#x} (was {DYN_EVENT_TABLE_ORIG:#x}), "
          f"{len(DYN_EVENT_TABLE_REFS)} refs repointed")

    # --- egg-hatch sweep ---
    # The one enforcement hole reachable in ordinary play: eggs are exempt
    # everywhere by design so an egg event cannot block progress, and nothing
    # then looked at what the egg HATCHED INTO. This overlays the hatch
    # script's tail with a goto into a replayed tail that ends by calling the
    # activation sweep -- after the hatch's waitstate, so it sees the finished
    # Pokemon rather than the egg. docs/GIFT_EGGS.md lists the gift eggs this
    # covers; tools/character_mode/egg_hook.py has the RE.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "character_mode"))
    import egg_hook
    egg_entry = struct.unpack_from("<I", data, egg_hook.CALLER_POOL_OFF)[0]
    assert egg_entry == egg_hook.SCRIPT_ENTRY, (
        f"egg-hatch script pointer is {egg_entry:#x}, expected "
        f"{egg_hook.SCRIPT_ENTRY:#x} -- the hatch caller has moved")
    egg_tail, egg_patches = egg_hook.build(EGG_TAIL_ADDR, hook_sweep)
    splice(EGG_TAIL_ADDR, egg_tail, "egg-hatch tail")
    for _eoff, _eorig, _erepl in egg_patches:
        _eseg = bytes(data[_eoff:_eoff + len(_eorig)])
        assert _eseg == _eorig, (
            f"egg splice site {_eoff + 0x08000000:#x} holds {_eseg.hex()}, "
            f"expected {_eorig.hex()} -- wrong ROM, or already patched")
        data[_eoff:_eoff + len(_erepl)] = _erepl
    print(f"egg-hatch sweep: tail {len(egg_tail)} B @ {EGG_TAIL_ADDR:#x}, "
          f"splice @ {egg_hook.SPLICE_ROM_ADDR:#x} -> callnative {hook_sweep:#x}")

    # --- PC-exit sweep ---
    # Enforcement routes off-roster mons INTO the PC and, until 2026-09-07,
    # nothing re-enforced the roster afterwards -- so a mon the catch gate had
    # just boxed could be withdrawn straight back and kept, no exploit required
    # (rowe_parity.md §13.24). The PC is opened from a SCRIPT whose special
    # carries a waitstate, exactly like the egg hatch, so this is the same
    # splice pointed at a different tail: the sweep runs AFTER the waitstate,
    # once the storage UI has closed and the party is whatever the player left.
    # ⚠️ ROWE's Cb2_ExitPSS semantics -- UNDO ON EXIT, not prevention -- and it
    # deliberately does NOT reproduce ROWE's IsRemovingLastAllowedPartyMon.
    # See pc_hook.py's docstring.
    import pc_hook
    for _sr, _sf, _so, _txtoff in pc_hook.SITES:
        _t = struct.unpack_from("<I", data, _txtoff)[0]
        assert _t == pc_hook.PC_TEXT_PTR, (
            f"PC script @{_sr:#x} shows message {_t:#x}, expected "
            f"{pc_hook.PC_TEXT_PTR:#x} -- the PC access script has moved")
    pc_blobs, pc_patches = pc_hook.build(PC_TAIL_ADDR, hook_sweep)
    for _addr, _blob in pc_blobs:
        splice(_addr, _blob, "PC-exit tail")
    for _poff, _porig, _prepl in pc_patches:
        _pseg = bytes(data[_poff:_poff + len(_porig)])
        assert _pseg == _porig, (
            f"PC splice site {_poff + 0x08000000:#x} holds {_pseg.hex()}, "
            f"expected {_porig.hex()} -- wrong ROM, or already patched")
        data[_poff:_poff + len(_prepl)] = _prepl
    print(f"PC-exit sweep: {len(pc_blobs)} tails @ {PC_TAIL_ADDR:#x}, "
          f"splices @ {', '.join(f'{s[0]:#x}' for s in pc_hook.SITES)} "
          f"-> callnative {hook_sweep:#x}")

    # --- Phase 3 character sprites (2026-07-25) ---
    # Additive: this never touches the engine's own trainer-pic table, so
    # nothing the game already draws changes, and locating that table is not a
    # prerequisite. Blobs first, then a table of absolute ROM pointers.
    _spr_b = CM / "cm_sprite_blobs.bin"
    _spr_o = CM / "cm_sprite_offsets.bin"
    if _spr_b.is_file() and _spr_o.is_file():
        _blobs = _spr_b.read_bytes()
        _offs = _spr_o.read_bytes()
        assert len(_offs) == NUM_CHARACTERS * 8, (len(_offs), NUM_CHARACTERS)
        # Name the collision before splice() reports it as a bare 0xFF failure.
        # The art region is the only thing here that grows with the roster, and
        # it grew into the renderer once already (2026-07-29).
        _blob_end = CM_SPRITE_BLOBS_ADDR + len(_blobs)
        assert _blob_end <= CM_MUGSHOT_ADDR, (
            "sprite art overruns the mugshot renderer: blobs are %d B, ending at "
            "%#x, but CM_MUGSHOT_ADDR is %#x (over by %d B). Raise CM_MUGSHOT_ADDR "
            "-- the run is free to %#x -- and re-inject."
            % (len(_blobs), _blob_end, CM_MUGSHOT_ADDR,
               _blob_end - CM_MUGSHOT_ADDR, FREE_END_ROM))
        assert CM_MUGSHOT_ADDR < FREE_END_ROM, "CM_MUGSHOT_ADDR past the free run"
        _ptrs = bytearray()
        _wired = 0
        for _i in range(NUM_CHARACTERS):
            _g, _p = struct.unpack_from("<II", _offs, _i * 8)
            if _g == 0xFFFFFFFF:
                _ptrs += struct.pack("<II", 0, 0)
            else:
                _ptrs += struct.pack("<II", CM_SPRITE_BLOBS_ADDR + _g,
                                            CM_SPRITE_BLOBS_ADDR + _p)
                _wired += 1
        splice(CM_SPRITE_BLOBS_ADDR, _blobs, "character sprite blobs")
        splice(CM_SPRITE_PTRS_ADDR, bytes(_ptrs), "character sprite pointers")
        print(f"character sprites: {_wired}/{NUM_CHARACTERS} wired, "
              f"{len(_blobs):,} B @ {CM_SPRITE_BLOBS_ADDR:#x}, table @ {CM_SPRITE_PTRS_ADDR:#x}")


    # The trampoline block: prove it is still the base ROM's dead function,
    # then clear it so splice()'s 0xFF precondition covers it like free space.
    _tb = TRAMPOLINE_BLOCK - 0x08000000
    assert bytes(data[_tb:_tb + len(TRAMPOLINE_BLOCK_ORIG)]) == TRAMPOLINE_BLOCK_ORIG, (
        "the dead IsRemovingLastPartyMon is not at %#x -- re-derive before "
        "overwriting it" % TRAMPOLINE_BLOCK)
    data[_tb:_tb + len(TRAMPOLINE_BLOCK_ORIG)] = b"\xff" * len(TRAMPOLINE_BLOCK_ORIG)

    tramp = struct.pack("<HH", 0x4B00, 0x4718) + struct.pack("<I", hook_gate)
    assert TRAMPOLINE_ADDR % 4 == 0
    splice(TRAMPOLINE_ADDR, tramp, "trampoline")
    assert WILD_TRAMPOLINE_ADDR % 4 == 0
    splice(WILD_TRAMPOLINE_ADDR, wild_tramp, "wild veneer")
    # push {r3} ; ldr r3, [pc, #4] ; bx r3 ; nop ; .word veneer|1
    assert WILD_STUB_ADDR % 4 == 0
    splice(WILD_STUB_ADDR,
           struct.pack("<HHHHI", 0xB408, 0x4B01, 0x4718, 0x46C0, WILD_TRAMPOLINE_ADDR | 1),
           "wild entry stub")

    # --- encounter marker: per-character intro strings + its trampoline ---
    marker_blob = (CM / "marker_strings.bin").read_bytes()
    assert len(marker_blob) == NUM_CHARACTERS * MARKER_STRIDE, (
        f"marker_strings.bin is {len(marker_blob)} B, expected "
        f"{NUM_CHARACTERS * MARKER_STRIDE} for {NUM_CHARACTERS} characters "
        f"-- re-run emit_marker_strings.py")
    assert not (MARKER_ADDR <= TRADE_TEST_SCRIPT_ADDR
                < MARKER_ADDR + len(marker_blob)), (
        f"marker strings {MARKER_ADDR:#x}.."
        f"{MARKER_ADDR + len(marker_blob):#x} swallow the trade test script at "
        f"{TRADE_TEST_SCRIPT_ADDR:#x}")
    splice(MARKER_ADDR, marker_blob, "encounter marker strings")
    assert MARKER_TRAMPOLINE_ADDR % 4 == 0
    splice(MARKER_TRAMPOLINE_ADDR,
           struct.pack("<HH", 0x4B00, 0x4718) + struct.pack("<I", hook_marker),
           "marker trampoline")
    print(f"encounter marker: {len(marker_blob):,} B @ {MARKER_ADDR:#x}, "
          f"stride {MARKER_STRIDE}, trampoline @ {MARKER_TRAMPOLINE_ADDR:#x}")
    _of = OLD_SPRITE_FRAME[0] - 0x08000000
    assert all(x == 0xFF for x in data[_of:_of + OLD_SPRITE_FRAME[1]]), (
        "something wrote into the sprite frame at %#x again" % OLD_SPRITE_FRAME[0])

    # --- PC second guard: one trampoline, six retargeted BLs, one tail ---
    splice(PSS_GUARD_TRAMPOLINE_ADDR,
           struct.pack("<HH", 0x4B00, 0x4718) + struct.pack("<I", hook_pss_guard),
           "PC second-guard trampoline")
    for _site in PSS_GUARD_BL_SITES + (PSS_CANSHIFT_BL,):
        _cur = bytes(data[_site:_site + 4])
        _exp = thumb_bl(0x08000000 + _site, PSS_COUNT_ALIVE_EXCEPT)
        assert _cur == _exp, f"PC guard site {_site:#x}: {_cur.hex()} != {_exp.hex()}"
        data[_site:_site + 4] = thumb_bl(0x08000000 + _site, PSS_GUARD_TRAMPOLINE_ADDR)
    # CanShiftMon's `cmp r0,#0 ; bne 0x081C351E` becomes `b 0x081C3524 ; nop`:
    # the guard already returned the final answer, so go straight to the pop.
    _cur = bytes(data[PSS_CANSHIFT_TAIL:PSS_CANSHIFT_TAIL + 4])
    assert _cur == bytes.fromhex("0028f4d1"), f"CanShiftMon tail: {_cur.hex()}"
    data[PSS_CANSHIFT_TAIL:PSS_CANSHIFT_TAIL + 4] = struct.pack("<HH", 0xE7F8, 0x46C0)
    print(f"PC second guard: {len(PSS_GUARD_BL_SITES)} deposit/move/release sites + "
          f"CanShiftMon -> {hook_pss_guard:#x} via {PSS_GUARD_TRAMPOLINE_ADDR:#x}")

    # --- 100% catch for on-roster species (src/character_mode.c CM_CatchOddsStub) ---
    _cv = CATCH_VENEER_ADDR - 0x08000000
    assert bytes(data[_cv:_cv + 8]) == CATCH_VENEER_ORIG, (
        "the dead function's tail is not at %#x" % CATCH_VENEER_ADDR)
    assert CATCH_VENEER_ADDR % 4 == 0
    data[_cv:_cv + 8] = struct.pack("<HHI", 0x4B00, 0x4718, syms["CM_CatchOddsStub"] | 1)
    assert bytes(data[CATCH_ODDS_SITE:CATCH_ODDS_SITE + 4]) == CATCH_ODDS_ORIG, (
        "Cmd_handleballthrow's odds compare is not at %#x" % CATCH_ODDS_SITE)
    data[CATCH_ODDS_SITE:CATCH_ODDS_SITE + 4] = thumb_bl(0x08000000 + CATCH_ODDS_SITE,
                                                         CATCH_VENEER_ADDR)
    print(f"100% roster catch: odds compare @ {0x08000000 + CATCH_ODDS_SITE:#x} -> veneer "
          f"{CATCH_VENEER_ADDR:#x} -> {syms['CM_CatchOddsStub']:#x}")

    # --- patches (verify-then-write) ---
    for site in (BL_SITE_CATCH, BL_SITE_GIFT):
        cur = bytes(data[site:site + 4])
        expect = thumb_bl(0x08000000 + site, GIVEMON_ADDR)
        assert cur == expect, (f"BL site {site:#x}: {cur.hex()} != {expect.hex()}")
        data[site:site + 4] = thumb_bl(0x08000000 + site, TRAMPOLINE_ADDR)

    cur = bytes(data[WILD_BL_SITE:WILD_BL_SITE + 4])
    expect = thumb_bl(0x08000000 + WILD_BL_SITE, CREATE_MON_WITH_IVS)
    assert cur == expect, (f"wild BL site {WILD_BL_SITE:#x}: {cur.hex()} != {expect.hex()}")
    data[WILD_BL_SITE:WILD_BL_SITE + 4] = thumb_bl(0x08000000 + WILD_BL_SITE, WILD_STUB_ADDR)

    # The shim compares `src` against TEXT_WILD_APPEARED by hardcoded address,
    # so prove that address still holds that exact string before moving the BL.
    # Get this wrong and the marker simply never fires -- silently.
    _want = bytes.fromhex("d1dde0d800fd0600d5e4e4d9d5e6d9d8abfbff")
    _got = bytes(data[TEXT_WILD_APPEARED - 0x08000000:
                      TEXT_WILD_APPEARED - 0x08000000 + len(_want)])
    assert _got == _want, (
        f"TEXT_WILD_APPEARED {TEXT_WILD_APPEARED:#x}: {_got.hex()} != "
        f"{_want.hex()} -- the wild intro string moved")

    cur = bytes(data[MARKER_BL_SITE:MARKER_BL_SITE + 4])
    expect = thumb_bl(0x08000000 + MARKER_BL_SITE, EXPAND_STRING)
    assert cur == expect, (
        f"marker BL site {MARKER_BL_SITE:#x}: {cur.hex()} != {expect.hex()}")
    data[MARKER_BL_SITE:MARKER_BL_SITE + 4] = thumb_bl(
        0x08000000 + MARKER_BL_SITE, MARKER_TRAMPOLINE_ADDR)

    cur = struct.unpack_from("<I", data, BG_EVENT_PTR_OFF)[0]
    assert cur == ORIG_CLIPBOARD, f"BG ptr: {cur:#x} != {ORIG_CLIPBOARD:#x}"
    struct.pack_into("<I", data, BG_EVENT_PTR_OFF, CLIPBOARD_PRE)

    # second activation point: the bedroom cheat device
    cur = struct.unpack_from("<I", data, BEDROOM_BG_PTR_OFF)[0]
    assert cur == ORIG_CHEAT_DEVICE, (
        f"bedroom BG ptr: {cur:#x} != {ORIG_CHEAT_DEVICE:#x} -- the bedroom "
        f"map's BG event table has moved; re-derive BEDROOM_BG_PTR_OFF")
    struct.pack_into("<I", data, BEDROOM_BG_PTR_OFF, BEDROOM_PRE)
    print(f"bedroom cheat device -> CM pre-entry {BEDROOM_PRE:#x} "
          f"(was {ORIG_CHEAT_DEVICE:#x}); clipboard -> {CLIPBOARD_PRE:#x}")

    pat = struct.pack("<I", GIVE_NATIVE)
    sites = []
    i = data.find(pat)
    while i != -1:
        if data[i - 1] == 0x23:
            sites.append(i)
        i = data.find(pat, i + 1)
    assert len(sites) == GIVE_NATIVE_COUNT, f"expected {GIVE_NATIVE_COUNT} callnative sites, found {len(sites)}"
    for s in sites:
        struct.pack_into("<I", data, s, hook_native | 1)

    hook_trade = syms["CM_TradeCheck"]

    # --- trade gates: shared refuse + 4 per-trade wrappers; junction overlays ---
    txt_refuse = enc_text("Character Mode:\nthis trade is not in your roster.", cm)
    # refuse block: delay 0 ; loadword <txt> ; callstd 4 ; release ; end
    refuse = op_loadword(0) + op_callstd(4) + bytes([0x6C]) + op_end()
    blob = bytearray(refuse)
    wrapper_addrs = []
    for j in TRADE_JUNCTIONS:
        w_addr = TRADE_SCRIPT_ADDR + len(blob)
        wrapper_addrs.append(w_addr)
        resume = 0x08000000 + j + len(TRADE_JUNCTION_BYTES)
        w = bytearray()
        w += bytes([0x19, 0x04, 0x80, 0x08, 0x80])           # copyvar 0x8004,0x8008
        w += bytes([0x19, 0x05, 0x80, 0x0A, 0x80])           # copyvar 0x8005,0x800A
        w += op_callnative(hook_trade)                       # CM_TradeCheck -> VAR_RESULT
        w += op_compare(0x800D, 0)
        w += op_goto_if(1, TRADE_SCRIPT_ADDR)                # ==0 refuse
        w += bytes([0x25, 0x00, 0x01, 0x25, 0x01, 0x01, 0x27])  # special 0x100;0x101;waitstate
        w += op_goto(resume)
        blob += w
    txt_addr = TRADE_SCRIPT_ADDR + len(blob)
    blob += txt_refuse
    struct.pack_into("<I", blob, 2, txt_addr)                # refuse loadword ptr
    splice(TRADE_SCRIPT_ADDR, bytes(blob), "trade wrappers")

    for w_addr, j in zip(wrapper_addrs, TRADE_JUNCTIONS):
        cur = bytes(data[j:j + len(TRADE_JUNCTION_BYTES)])
        assert cur == TRADE_JUNCTION_BYTES, f"trade junction {j:#x}: {cur.hex()}"
        data[j:j + 5] = op_goto(w_addr)

    print(f"patched: 3 BL sites (2 catch/gift + 1 wild-encounter), BG-event ptr, "
          f"{len(sites)} callnative give ptrs, {len(TRADE_JUNCTIONS)} trade junctions "
          f"(wrappers @ {TRADE_SCRIPT_ADDR:#x})")

    # --- overworld sprite: code, data, word patches, entry trampoline ---
    splice(owp.OW_CODE_ADDR, ow_code, "overworld sprite code")
    for _off, _blob in ow_writes:
        splice(0x08000000 + _off, _blob, f"overworld data @ {_off:#x}")
    for _off, _old, _new in ow_patches:
        _cur = struct.unpack_from("<I", data, _off)[0]
        assert _cur == _old, f"overworld patch @{_off:#x}: {_cur:#x} != {_old:#x}"
        struct.pack_into("<I", data, _off, _new)
    _gi = owp.GET_INFO - 0x08000000
    assert bytes(data[_gi:_gi + 8]) == owp.GET_INFO_ORIG and _gi % 4 == 0
    # ldr r3,[pc,#0]; bx r3; .word hook -- r3 is overwritten by the original's
    # own third instruction, so it carries nothing in.
    data[_gi:_gi + 8] = struct.pack("<HHI", 0x4B00, 0x4718, hook_ow_info)
    print(f"overworld sprite: GetObjectEventGraphicsInfo @ {owp.GET_INFO:#x} -> "
          f"{hook_ow_info:#x}; {len(ow_patches)} palette-table literals repointed")

    # --- reusable TMs (user, 2026-10-09: every hack, CM on or off) ---
    # Seaglass's engine already has the mechanism: the teach path's
    # Task_LearnedMove removes the TM only when !GetItemImportance(item)
    # (pokeemerald-expansion's I_REUSABLE_TMS just sets .importance = 1 on
    # every TM). Seaglass shipped with I_REUSABLE_TMS off, so TM06 x36 went to
    # x35 when taught (measured live 2026-10-09); Lazarus, same engine, ships
    # it on. The fix is data only: set importance bit 0 on the 100 TM records.
    # HMs already carry it. Side effects are expansion's own for important
    # items (no quantity shown, can't toss or sell), as in Lazarus.
    for k in range(TM_COUNT):
        o = ITEM_NAME_BASE - 0x08000000 + (TM_FIRST_ID - 1 + k) * ITEM_STRIDE
        want = enc_text("TM%02d" % (k + 1), cm)
        assert bytes(data[o:o + len(want)]) == want, f"item {TM_FIRST_ID + k} is not TM{k + 1:02d}"
        b = o + ITEM_IMPORTANCE_OFF
        assert data[b] & 0x03 == 0, f"TM{k + 1:02d} importance byte {data[b]:#x}"
        data[b] |= 0x01
    print(f"reusable TMs: importance set on items {TM_FIRST_ID}-{TM_FIRST_ID + TM_COUNT - 1}")

    # --- outputs ---
    out_rom = BUILD / "seaglass_cm.gba"
    out_rom.write_bytes(data)
    print(f"wrote {out_rom} sha1={hashlib.sha1(data).hexdigest()}")
    flips = ROOT / "tools" / "bin" / "flips"
    bps = BUILD / "seaglass_cm.bps"
    r = subprocess.run([str(flips), "--create", "--bps", str(ROM_IN), str(out_rom), str(bps)],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if bps.exists():
        print(f"patch: {bps} ({bps.stat().st_size} bytes)")

    # Offered characters only -- a hidden character's code does not work, so
    # listing it would send a player to a code that gets refused. Lazarus's
    # codes.txt is the same shape (123 lines for 238 characters).
    _offered = [(code, c, s) for code, c, s in zip(typed, chars, starters)
                if code is not None]
    (BUILD / "codes.txt").write_text(
        "\n".join(f"{code}\t{c['character']}\tstarter={s}"
                  for code, c, s in _offered) + "\n")
    print(f"code list: {BUILD/'codes.txt'} "
          f"({len(_offered)} selectable of {len(typed)} characters)")
    print("Debug codes: CMDBGOFF, CMDBGGIVE1, CMDBGGIVE2 (case-insensitive)")


if __name__ == "__main__":
    main()
