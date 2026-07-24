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
CHARMAP = Path("/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt")

NUM_CHARACTERS = 182  # 170 + 11 professors + Tobias (2026-07-23)
BITMAP_STRIDE = 187
CODE_LEN = 11

# --- confirmed free-block layout (all verified 0xFF) ---
SHIM_ADDR      = 0x08ED2200
BITMAPS_ADDR   = 0x08EDA000        # 170*187 = 31790 B
CODES_ADDR     = 0x08EE2800        # 182*11 = 2002 B (rebased 2026-07-23; bitmaps grew to 34,034 B)
STARTERS_ADDR  = 0x08EE3100        # 182*2 = 364 B
SCRIPT_ADDR    = 0x08EE3800        # entry + confirm script (rebased)
WILDPOOL_ADDR  = 0x08EE4000        # 182*176*4 = 128,128 B -> ends 0x08F03480 (2026-07-23)
FREE_END_ROM   = 0x09000000

TRAMPOLINE_ADDR      = 0x08470200  # 8B 0xFF scavenge, in BL range of both sites
WILD_TRAMPOLINE_ADDR = 0x08470208  # same 64B scavenge run, immediately after; 40B used

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
WILDPOOL_STRIDE       = 176

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
TRADE_SCRIPT_ADDR = 0x08EE3300

# script/engine constants
YESNO_TEXT_ADDR = None             # our msg (in-script); built below
GStringVar2 = 0x0203AF24

FLAG_CHARACTER_MODE = 0x945
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

    # --- code + starter tables ---
    codes = bytearray()
    seen = {}
    starters = []
    typed = []
    for c in chars:
        code = code_for(c["character"])
        key = code.upper()
        assert 1 <= len(code) <= 10, (c["character"], code)
        assert key not in seen, f"code collision: {code} ({c['character']} vs {seen[key]})"
        seen[key] = c["character"]
        typed.append(code)
        enc = enc_text(code, cm)
        assert len(enc) <= CODE_LEN
        codes += enc + b"\xFF" * (CODE_LEN - len(enc))
        sig = c["signature_id"] if c.get("has_signature") and c.get("signature_id") else c["roster_species_ids"][0]
        starters.append(sig)
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

    hook_open   = syms["CM_OpenCodeEntry"]
    hook_match  = syms["CM_MatchCode"]
    hook_gate   = syms["CM_GiveMonToPlayerGated"] | 1
    hook_native = syms["CM_NativeGiveGated"]
    hook_wild   = syms["CM_WildMonSpeciesGated"]

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
        e += op_loadword(addrs["t_on"]) + op_callstd(4)
        e += op_copyvar(0x8000, VAR_CM_STARTER)
        e += op_bufferspecies(0, 0x8000)
        e += op_setvar(0x4001, 0x8000)
        e += op_setvar(VAR_CM_STARTER, 0)
        e += op_givenative(0x8000, hook_native)
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

    tramp = struct.pack("<HH", 0x4B00, 0x4718) + struct.pack("<I", hook_gate)
    assert TRAMPOLINE_ADDR % 4 == 0
    splice(TRAMPOLINE_ADDR, tramp, "trampoline")
    assert WILD_TRAMPOLINE_ADDR % 2 == 0
    splice(WILD_TRAMPOLINE_ADDR, wild_tramp, "wild trampoline")

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

    (BUILD / "codes.txt").write_text(
        "\n".join(f"{code}\t{c['character']}\tstarter={s}"
                  for code, c, s in zip(typed, chars, starters)) + "\n")
    print(f"code list: {BUILD/'codes.txt'} ({len(typed)} characters)")
    print("Debug codes: CMDBGOFF, CMDBGGIVE1, CMDBGGIVE2 (case-insensitive)")


if __name__ == "__main__":
    main()
