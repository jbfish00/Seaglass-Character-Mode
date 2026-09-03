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
     the two acquisition BLs (8-byte trampoline @0x08470200) and the wild-
     encounter species override (separate 40-byte long-call trampoline,
     src/wild_trampoline.c, @0x08470208 -- its hook site is ~7.6 MiB from the
     main shim, out of Thumb BL range, hence the manual long-call).
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

TRAMPOLINE_ADDR      = 0x08470200  # 8B 0xFF scavenge, in BL range of both sites
WILD_TRAMPOLINE_ADDR = 0x08470208  # same 64B scavenge run, immediately after; 40B used
# Encounter marker (../game_plans/rowe_parity.md §3). Third user of the same
# verified 64-byte 0xFF scavenge run at 0x08470200; the wild trampoline ends at
# 0x08470230, leaving 16 B. 4-aligned, and 3.91 MB from the hook site at
# 0x08086EAA -- inside the +-4 MB Thumb BL window, with no margin to spare, so
# check the reach again if either address ever moves.
MARKER_TRAMPOLINE_ADDR = 0x08470230
# The BL inside BufferStringBattle that every intro string funnels through:
#   ldr r0, =<one of several strings> ; b 0x08086EA8
#   0x08086EA8: ldr r1, =dst ; bl BattleStringExpandPlaceholders
MARKER_BL_SITE   = 0x086EAA
EXPAND_STRING    = 0x080876DC
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

GIVE_NATIVE   = 0x081F2175         # callnative give fn (49 inline script ptrs)
GIVE_NATIVE_COUNT = 49

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

    return dict(t_prompt=t_prompt, t_on=t_on, t_off=t_off, t_invalid=t_invalid)


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
                 "CM_NativeGiveGated", "CM_TradeCheck", "CM_WildMonSpeciesGated"):
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

    # --- mugshot renderer: separate compile unit + link address (see
    # CM_MUGSHOT_ADDR). Both entry points are resolved from the linked ELF
    # rather than assumed to be in source order -- gcc may emit them either
    # way and the `callnative` operands must be exact. ---
    mobj, melf, mbin = BUILD / "character_sprite.o", BUILD / "character_sprite.elf", BUILD / "character_sprite.bin"
    subprocess.run(["arm-none-eabi-gcc", "-c", "-mthumb", "-mcpu=arm7tdmi",
                    "-O2", "-ffreestanding", "-fno-builtin", "-Wall", "-Wextra",
                    f"-DSPRITE_PTRS_ADDR={CM_SPRITE_PTRS_ADDR:#x}",
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
    assert len(wild_tramp) <= TRAMPOLINE_ADDR + 64 - WILD_TRAMPOLINE_ADDR, (
        f"wild trampoline too big: {len(wild_tramp)} bytes, "
        f"only {TRAMPOLINE_ADDR + 64 - WILD_TRAMPOLINE_ADDR} available")
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
        e += op_callnative(hook_sweep)
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
        return e

    base = SCRIPT_ADDR
    # pass 1: placeholder addrs -> measure block offsets
    ph = dict(t_prompt=base, t_on=base, t_off=base, t_invalid=base,
              tail=base, give=base, off=base)
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
    )
    script = emit(addrs)
    assert len(script) == len(tmp)
    print(f"scripts: {len(script)} bytes @ {SCRIPT_ADDR:#x}")

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
    splice(CM_MUGSHOT_ADDR, mugshot, "mugshot renderer")

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


    tramp = struct.pack("<HH", 0x4B00, 0x4718) + struct.pack("<I", hook_gate)
    assert TRAMPOLINE_ADDR % 4 == 0
    splice(TRAMPOLINE_ADDR, tramp, "trampoline")
    assert WILD_TRAMPOLINE_ADDR % 2 == 0
    splice(WILD_TRAMPOLINE_ADDR, wild_tramp, "wild trampoline")

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
    assert MARKER_TRAMPOLINE_ADDR >= WILD_TRAMPOLINE_ADDR + len(wild_tramp), (
        f"marker trampoline at {MARKER_TRAMPOLINE_ADDR:#x} overlaps the wild "
        f"trampoline, which ends at "
        f"{WILD_TRAMPOLINE_ADDR + len(wild_tramp):#x}")
    splice(MARKER_TRAMPOLINE_ADDR,
           struct.pack("<HH", 0x4B00, 0x4718) + struct.pack("<I", hook_marker),
           "marker trampoline")
    print(f"encounter marker: {len(marker_blob):,} B @ {MARKER_ADDR:#x}, "
          f"stride {MARKER_STRIDE}, trampoline @ {MARKER_TRAMPOLINE_ADDR:#x}")

    # --- patches (verify-then-write) ---
    for site in (BL_SITE_CATCH, BL_SITE_GIFT):
        cur = bytes(data[site:site + 4])
        expect = thumb_bl(0x08000000 + site, GIVEMON_ADDR)
        assert cur == expect, (f"BL site {site:#x}: {cur.hex()} != {expect.hex()}")
        data[site:site + 4] = thumb_bl(0x08000000 + site, TRAMPOLINE_ADDR)

    cur = bytes(data[WILD_BL_SITE:WILD_BL_SITE + 4])
    expect = thumb_bl(0x08000000 + WILD_BL_SITE, CREATE_MON_WITH_IVS)
    assert cur == expect, (f"wild BL site {WILD_BL_SITE:#x}: {cur.hex()} != {expect.hex()}")
    data[WILD_BL_SITE:WILD_BL_SITE + 4] = thumb_bl(0x08000000 + WILD_BL_SITE, WILD_TRAMPOLINE_ADDR)

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
    struct.pack_into("<I", data, BG_EVENT_PTR_OFF, SCRIPT_ADDR)

    pat = struct.pack("<I", GIVE_NATIVE)
    sites = []
    i = bytes(data).find(pat)
    while i != -1:
        if data[i - 1] == 0x23:
            sites.append(i)
        i = bytes(data).find(pat, i + 1)
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
