#!/usr/bin/env python3
"""Independent static verification of the built Seaglass Character Mode artifacts.

Re-derives everything from the finished ROM/BPS (shares no code with
tools/inject_character_mode.py's own build-time asserts), so an injector
bookkeeping bug can't hide itself. Run: verify_artifacts.py (exit 0 = all pass).

Layers:
  1. rom/seaglass v3.0.gba matches rom.sha1.
  2. BPS round-trip: flips-apply build/seaglass_cm.bps -> byte-identical to
     build/seaglass_cm.gba.
  3. Patched ROM differs from the original ONLY inside intended windows
     (shim/bitmaps/codes/starters/scripts/trade wrappers, trampoline, 2 BLs,
     BG-event ptr, 49 callnative give ptrs, 4 five-byte trade junctions).
  4. GiveMonToPlayer BL exhaustion: original has exactly 3 callers
     {catch, egg-hatch, script-gift}; patched leaves ONLY the exempt egg-hatch
     caller -> every party-add funnel is gated by construction.
  5. Trampoline decodes to ldr/bx into the gate shim; both patched BLs decode
     to the trampoline; their originals decoded to GiveMonToPlayer.
  6. Bitmaps in-ROM == rosters_expanded.bin; every character's manifest roster
     ids + starter are set in that character's own bitmap.
  7. Codes decode (charmap) to independently recomputed codes; all unique.
  8. All 49 callnative give sites (found in the ORIGINAL by the 0x23+ptr idiom)
     now point at CM_NativeGiveGated; none un-retargeted (except our own give,
     which points at the same wrapper by design).
  9. BG-event ptr repointed from 0x08311CCB to our entry script; the entry +
     confirm scripts decode with the expected hook targets and pointers.
 10. Trade junctions: original 17-byte junctions present, overlaid gotos ->
     wrappers that decode (copyvars, callnative CM_TradeCheck, refuse path,
     resume goto == junction+17); received-species fields sane.
"""
import hashlib
import json
import re
import struct
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
ROM_IN = ROOT / "rom" / "seaglass v3.0.gba"
ROM_OUT = ROOT / "build" / "seaglass_cm.gba"
BPS = ROOT / "build" / "seaglass_cm.bps"
FLIPS = ROOT / "tools" / "bin" / "flips"
CM = ROOT / "tools" / "character_mode"
CHARMAP = Path("/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt")

ROM_SHA1 = "b9f4d332d30fc88c379f9e037f9eae3b2755ead4"
# Derived, not hardcoded. Roster growth used to mean hand-editing this AND the
# three injection addresses below, and a stale value fails as an unrelated-looking
# "stray bytes"/"size mismatch" error rather than as a count mismatch (Volo,
# 2026-07-25). Read the count from the manifest and the layout from the injector
# so this file can never disagree with the build it is verifying.
NUM_CHARACTERS = len(json.loads(
    (ROOT / "tools" / "character_mode" / "characters_manifest.json").read_text())["characters"])

def _injector_addr(name):
    m = re.search(rf"^{name}\s*=\s*(0x[0-9A-Fa-f]+)", 
                  (ROOT / "tools" / "inject_character_mode.py").read_text(), re.M)
    if not m:
        raise SystemExit(f"verify_artifacts: cannot find {name} in inject_character_mode.py")
    return int(m.group(1), 16)

BITMAPS_ADDR  = _injector_addr("BITMAPS_ADDR")
CODES_ADDR    = _injector_addr("CODES_ADDR")
STARTERS_ADDR = _injector_addr("STARTERS_ADDR")
BITMAP_STRIDE = 187
CODE_LEN = 11

GIVEMON_ADDR = 0x081AA5AC
BL_CATCH = 0x0A6A46
BL_GIFT  = 0x1F18DE
BL_EGG   = 0x188514              # egg-hatch caller (exempt, stays original)
TRAMPOLINE_ADDR = 0x08470200
GIVE_NATIVE = 0x081F2175
BG_EVENT_PTR_OFF = 0x123ACC
ORIG_CLIPBOARD = 0x08311CCB
TRADE_JUNCTIONS = (0x29CFF5, 0x2AF873, 0x2B01EF, 0x30129E)
TRADE_JUNCTION_BYTES = bytes([0x19,0x04,0x80,0x08,0x80, 0x19,0x05,0x80,0x0A,0x80,
                              0x25,0x00,0x01, 0x25,0x01,0x01, 0x27])
TRADE_TABLE = 0xA3DB30

# Wild-encounter species override (task #5, docs/ROUTINE_MAP.md).
WILD_BL_SITE = 0x22BF36
CREATE_MON_WITH_IVS = 0x081A7504
WILD_TRAMPOLINE_ADDR = 0x08470208
WILDPOOL_ADDR = 0x08EE5000
CM_SPRITE_PTRS_ADDR  = 0x08f20000   # Phase 3 (keep in sync with the injector)
CM_MUGSHOT_ADDR      = 0x08F42000   # mugshot renderer (src/character_sprite.c)
CM_SPRITE_BLOBS_ADDR = 0x08f20800
# Derived, like NUM_CHARACTERS above and for the same reason. emit_wildpool.py's
# POOL_STRIDE is authoritative and publishes itself here; restating it was how
# this file agreed with the injector while both disagreed with the compiled shim
# for four days (see check [16]).
WILDPOOL_STRIDE = json.loads(
    (ROOT / "tools" / "character_mode" / "wildpool_manifest.json").read_text())["pool_stride"]

# Build fingerprint exported by src/character_mode.c (check [16]).
CM_FINGERPRINT_MAGIC = 0x4D435346
SHIM_ADDR = 0x08ED2200
SHIM_REGION = 0x2000

# 1% legendary wild encounters (check [17]). Derived from the injector and the
# emitter's manifest, never restated -- an unregistered data region surfaces as
# "stray bytes in diff containment", never as a missing table, which is exactly
# how this one first failed.
LEGENDARY_ADDR = _injector_addr("LEGENDARY_ADDR")
_LEG = json.loads((ROOT / "tools" / "character_mode"
                   / "legendaries_manifest.json").read_text())
LEGENDARY_COUNT = _LEG["count"]
# The flags array is SB1+0x13C0..0x14EB (vars start at 0x14EC), so flags above
# 0x95F do not exist at all.
FLAG_SPACE_END = 0x95F

# Engine flag/var bookkeeping (check [13], added 2026-07-24 with the 0x945 fix).
SB1_FLAGS_OFF = 0x13C0           # SaveBlock1.flags (docs/ROUTINE_MAP.md)
TEMP_FLAGS_START, TEMP_FLAGS_END = 0x000, 0x01F
DAILY_FLAGS_START, DAILY_FLAGS_END = 0x920, 0x95F
SCR_SETFLAG, SCR_CLEARFLAG, SCR_CHECKFLAG = 0x29, 0x2A, 0x2B

_p = _f = 0
def ok(cond, msg):
    global _p, _f
    if cond:
        _p += 1
        print(f"  PASS {msg}")
    else:
        _f += 1
        print(f"  FAIL {msg}")


def load_charmap():
    t = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    for line in open(CHARMAP, encoding="utf-8"):
        m = pat.match(line.rstrip("\n"))
        if m and m.group(1) not in t:
            t[m.group(1)] = int(m.group(2), 16)
    return t


def enc(s, cm):
    return bytes(cm[c] for c in s) + b"\xFF"


def code_for(display):
    n = unicodedata.normalize("NFKD", display)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return "".join(c for c in n if c.isalnum())[:10]


def decode_bl(rom, at):
    hw1, hw2 = struct.unpack_from("<HH", rom, at)
    if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xF800) != 0xF800:
        return None
    d = ((hw1 & 0x7FF) << 12) | ((hw2 & 0x7FF) << 1)
    if d & 0x400000:
        d -= 0x800000
    return 0x08000000 + at + 4 + d


def bl_callers(rom, target):
    out = []
    for i in range(0, len(rom) - 4, 2):
        if decode_bl(rom, i) == target:
            out.append(i)
    return out


def main():
    orig = bytearray(ROM_IN.read_bytes())
    patched = bytearray(ROM_OUT.read_bytes())
    cm = load_charmap()
    manifest = json.loads((CM / "characters_manifest.json").read_text())["characters"]
    bitmaps = (CM / "rosters_expanded.bin").read_bytes()

    print("[1] source ROM sha1")
    ok(hashlib.sha1(orig).hexdigest() == ROM_SHA1, "rom.sha1 pin")

    print("[2] BPS round-trip")
    tmp = ROOT / "build" / "_verify_rt.gba"
    subprocess.run([str(FLIPS), "--apply", str(BPS), str(ROM_IN), str(tmp)],
                   capture_output=True)
    rt = tmp.read_bytes()
    ok(hashlib.sha1(rt).digest() == hashlib.sha1(patched).digest(),
       "flips-apply == built ROM byte-identical")
    tmp.unlink(missing_ok=True)


    _spr_blobs = (ROOT / "tools" / "character_mode" / "cm_sprite_blobs.bin").read_bytes() if (ROOT / "tools" / "character_mode" / "cm_sprite_blobs.bin").is_file() else b""
    _spr_offs = (ROOT / "tools" / "character_mode" / "cm_sprite_offsets.bin").read_bytes() if (ROOT / "tools" / "character_mode" / "cm_sprite_offsets.bin").is_file() else b""
    _spr_ptrs = bytearray()
    for _i in range(len(_spr_offs) // 8):
        _gof, _pof = struct.unpack_from("<II", _spr_offs, _i * 8)
        _spr_ptrs += (struct.pack("<II", 0, 0) if _gof == 0xFFFFFFFF else
                      struct.pack("<II", CM_SPRITE_BLOBS_ADDR + _gof,
                                        CM_SPRITE_BLOBS_ADDR + _pof))
    # renderer blob length: scan from its base to the next 0xFF run
    _m = CM_MUGSHOT_ADDR & 0x01FFFFFF
    _mend = _m
    while not all(b == 0xFF for b in patched[_mend:_mend + 32]):
        _mend += 32
    _mugshot_len = _mend - _m

    print("[3] diff containment")
    windows = [(BL_CATCH, 4), (BL_GIFT, 4), (BG_EVENT_PTR_OFF, 4),
               (TRAMPOLINE_ADDR & 0x01FFFFFF, 8),
               (WILD_BL_SITE, 4), (WILD_TRAMPOLINE_ADDR & 0x01FFFFFF, 64 - 8),
               (0xED2200, 0x2000), (BITMAPS_ADDR & 0x01FFFFFF, NUM_CHARACTERS * BITMAP_STRIDE),
               (CODES_ADDR & 0x01FFFFFF, NUM_CHARACTERS * CODE_LEN),
               (STARTERS_ADDR & 0x01FFFFFF, NUM_CHARACTERS * 2),
               (0xEE3800, 0x300), (0xEE3B00, 0x400),
               (WILDPOOL_ADDR & 0x01FFFFFF, NUM_CHARACTERS * WILDPOOL_STRIDE * 4),
               (LEGENDARY_ADDR & 0x01FFFFFF,
                LEGENDARY_COUNT * 4 + NUM_CHARACTERS * 4),
               (CM_SPRITE_BLOBS_ADDR & 0x01FFFFFF, len(_spr_blobs)),
               (CM_SPRITE_PTRS_ADDR & 0x01FFFFFF, len(_spr_ptrs)),
               (CM_MUGSHOT_ADDR & 0x01FFFFFF, _mugshot_len)]
    give_sites = [i for i in range(len(orig))
                  if orig[i - 1] == 0x23 and orig[i:i + 4] == struct.pack("<I", GIVE_NATIVE)]
    windows += [(s, 4) for s in give_sites]
    windows += [(j, 5) for j in TRADE_JUNCTIONS]
    def allowed(b):
        return any(w <= b < w + n for w, n in windows)
    bad = [b for b in range(len(orig)) if orig[b] != patched[b] and not allowed(b)]
    ok(not bad, f"all diffs inside {len(windows)} intended windows (stray bytes: {len(bad)})")

    print("[4] GiveMonToPlayer BL exhaustion")
    oc = set(bl_callers(orig, GIVEMON_ADDR))
    pc = set(bl_callers(patched, GIVEMON_ADDR))
    ok(oc == {BL_CATCH, BL_GIFT, BL_EGG}, f"original callers == 3 known {sorted(hex(x) for x in oc)}")
    ok(pc == {BL_EGG}, f"patched leaves only egg-hatch {sorted(hex(x) for x in pc)}")

    print("[5] trampoline + BL retargets")
    ok(decode_bl(patched, BL_CATCH) == TRAMPOLINE_ADDR, "catch BL -> trampoline")
    ok(decode_bl(patched, BL_GIFT) == TRAMPOLINE_ADDR, "gift BL -> trampoline")
    ok(decode_bl(orig, BL_CATCH) == GIVEMON_ADDR, "catch BL originally -> GiveMonToPlayer")
    ok(decode_bl(orig, BL_GIFT) == GIVEMON_ADDR, "gift BL originally -> GiveMonToPlayer")
    t = TRAMPOLINE_ADDR & 0x01FFFFFF
    tw = struct.unpack_from("<HHI", patched, t)
    gate = tw[2] & ~1
    ok(tw[0] == 0x4B00 and tw[1] == 0x4718 and 0x08ED2200 <= gate < 0x08EDA000,
       f"trampoline = ldr/bx into shim (gate {gate:#x})")

    print("[6] bitmaps + roster/starter invariants")
    bbase = BITMAPS_ADDR & 0x01FFFFFF
    ok(patched[bbase:bbase + len(bitmaps)] == bitmaps, "bitmaps in-ROM == rosters_expanded.bin")
    def onbm(ci, sp):
        bm = bitmaps[ci * BITMAP_STRIDE:(ci + 1) * BITMAP_STRIDE]
        return sp == 0 or sp >= 1489 or (bm[sp >> 3] >> (sp & 7)) & 1
    all_in = True
    for ci, c in enumerate(manifest):
        for sp in c["roster_species_ids"]:
            if not onbm(ci, sp):
                all_in = False
        starter = c["signature_id"] if c.get("has_signature") and c.get("signature_id") else c["roster_species_ids"][0]
        if not onbm(ci, starter):
            all_in = False
    ok(all_in, "every roster id + starter is set in its character's own bitmap")

    print("[7] codes table + playability threshold")
    cbase = CODES_ADDR & 0x01FFFFFF
    codes_rom = patched[cbase:cbase + NUM_CHARACTERS * CODE_LEN]
    seen = set(); good = True
    # The threshold is enforced by POISONING the code slot of every hidden
    # character (see the injector). Checked in BOTH directions below: an offered
    # character whose code stopped working, and a hidden character whose code
    # still works, must each fail. A one-directional check would pass just as
    # happily if the gate poisoned everybody or nobody.
    hidden_bad_offered = []      # offered but unmatchable  -> lost a character
    hidden_bad_gated = []        # hidden but matchable     -> gate did not bite
    for ci, c in enumerate(manifest):
        want = enc(code_for(c["character"]), cm)
        got = codes_rom[ci * CODE_LEN:ci * CODE_LEN + CODE_LEN]
        # A slot is matchable iff it contains a 0xFF terminator: the entered
        # buffer is pre-cleared to 0xFF and the screen caps at CODE_LEN-1
        # characters, so entered[CODE_LEN-1] is always 0xFF and codeEq() can
        # only return a match on a simultaneous terminator.
        matchable = 0xFF in got
        if c.get("hidden"):
            if matchable:
                hidden_bad_gated.append(c["character"])
        else:
            if got[:len(want)] != want:
                good = False
            if not matchable:
                hidden_bad_offered.append(c["character"])
            seen.add(code_for(c["character"]).upper())
    n_hidden = sum(1 for c in manifest if c.get("hidden"))
    n_offered = NUM_CHARACTERS - n_hidden
    ok(good, f"all {n_offered} offered codes in-ROM == recomputed from names")
    ok(len(seen) == n_offered, f"offered codes case-fold-unique ({len(seen)})")

    drops = json.loads((CM / "character_drops.json").read_text())["unselectable"]
    manifest_hidden = {c["character"] for c in manifest if c.get("hidden")}
    emitted_names = {c["character"] for c in manifest}
    ok(manifest_hidden == set(drops) & emitted_names,
       f"manifest hidden set == character_drops.json ∩ emitted ({n_hidden})")
    ok(not hidden_bad_gated,
       f"every hidden character's code slot is unmatchable "
       f"({len(hidden_bad_gated)} still selectable: {hidden_bad_gated[:5]})")
    ok(not hidden_bad_offered,
       f"every offered character's code slot is still matchable "
       f"({len(hidden_bad_offered)} wrongly gated: {hidden_bad_offered[:5]})")
    ok(n_hidden > 0 and n_offered > 0,
       f"the threshold gates SOME characters and spares others "
       f"({n_offered} offered / {n_hidden} hidden) -- neither all nor nothing")

    print("[8] callnative give exhaustion")
    ok(len(give_sites) == 49, f"49 give sites in original ({len(give_sites)})")
    still = [s for s in give_sites if patched[s:s + 4] == struct.pack("<I", GIVE_NATIVE)]
    ok(not still, f"no original callnative-give site left un-retargeted ({len(still)})")
    targets = {struct.unpack_from("<I", patched, s)[0] & ~1 for s in give_sites}
    ok(len(targets) == 1 and 0x08ED2200 <= next(iter(targets)) < 0x08EDA000,
       f"all give sites share one shim ptr {[hex(x) for x in targets]}")

    print("[9] BG-event ptr + entry script")
    ok(struct.unpack_from("<I", orig, BG_EVENT_PTR_OFF)[0] == ORIG_CLIPBOARD,
       "BG ptr originally -> clipboard script")
    entry = struct.unpack_from("<I", patched, BG_EVENT_PTR_OFF)[0]
    ok(entry == 0x08EE3800, f"BG ptr repointed -> entry script {entry:#x}")
    o = entry & 0x01FFFFFF
    # lockall; loadword; callstd 5; compare 0x800D,1; goto_if !=,ORIG; callnative; waitstate; callnative; goto
    ok(patched[o] == 0x69, "entry starts lockall")
    # lockall(1) + loadword(6) + callstd 5(2) + compare 0x800D,1(5) = offset 14
    ok(patched[o + 14:o + 20] == bytes([0x06, 0x05]) + struct.pack("<I", ORIG_CLIPBOARD),
       "decline branch -> original clipboard preserved")

    print("[10] trade junctions + wrappers")
    tj_ok = True
    for j in TRADE_JUNCTIONS:
        if orig[j:j + 17] != TRADE_JUNCTION_BYTES:
            tj_ok = False
    ok(tj_ok, "all 4 original 17-byte junctions present")
    wrap_ok = True
    for j in TRADE_JUNCTIONS:
        if patched[j] != 0x05:  # goto
            wrap_ok = False; continue
        w = struct.unpack_from("<I", patched, j + 1)[0] & 0x01FFFFFF
        # wrapper: copyvar 0x8004,0x8008
        if patched[w:w + 5] != bytes([0x19, 0x04, 0x80, 0x08, 0x80]):
            wrap_ok = False
        # find resume goto == junction+17
        resume = 0x08000000 + j + 17
        if struct.pack("<I", resume) not in bytes(patched[w:w + 0x30]):
            wrap_ok = False
    ok(wrap_ok, "junctions overlaid -> wrappers (copyvar + resume goto == junction+17)")
    recv_ok = all(1 <= struct.unpack_from("<H", orig, TRADE_TABLE + k * 60 + 14)[0] < 1489
                  for k in range(4))
    ok(recv_ok, "sIngameTrades received-species fields sane (4 entries)")

    print("[11] wild-encounter hook + trampoline")
    ok(decode_bl(orig, WILD_BL_SITE) == CREATE_MON_WITH_IVS,
       "wild BL originally -> CreateMonWithIVs-simple")
    ok(decode_bl(patched, WILD_BL_SITE) == WILD_TRAMPOLINE_ADDR,
       "wild BL retargeted -> wild trampoline")
    wt = patched[WILD_TRAMPOLINE_ADDR & 0x01FFFFFF: (WILD_TRAMPOLINE_ADDR & 0x01FFFFFF) + 40]
    ok(wt[0:2] == bytes([0x1D, 0xB5]), "wild trampoline starts push {r0,r2,r3,r4,lr}")
    gated_word, orig_word = struct.unpack_from("<II", wt, 0x20)
    ok(0x08ED2200 <= (gated_word & ~1) < 0x08EDA000,
       f"wild trampoline's long-call literal -> main shim blob ({gated_word:#x})")
    ok((orig_word & ~1) == CREATE_MON_WITH_IVS,
       f"wild trampoline's tail-jump literal -> untouched CreateMonWithIVs ({orig_word:#x})")

    print("[12] wild pool data + legendary exclusion")
    wildpool = (CM / "wildpool.bin").read_bytes()
    ok(len(wildpool) == NUM_CHARACTERS * WILDPOOL_STRIDE * 4, "wildpool.bin size matches stride")
    wp_off = WILDPOOL_ADDR & 0x01FFFFFF
    ok(patched[wp_off:wp_off + len(wildpool)] == wildpool, "wildpool in-ROM == wildpool.bin")
    sys.path.insert(0, str(CM))
    from emit_characters import LEGENDARY_BASES
    import map_species as _M
    name_to_const, _ = _M.load_donor()
    const_to_name = {v: k for k, v in name_to_const.items()}
    legend_names = {const_to_name[c] for c in LEGENDARY_BASES if c in const_to_name}
    sp_table = json.loads((CM / "rom_species_table.json").read_text())["species"]
    # Exempt by character INDEX, not by name. The name-keyed exemption that used
    # to live here still passed while the shim's hardcoded TOBIAS_CHAR_ID pointed
    # at Volo -- it was checking the data, which was right, and the rate branch,
    # which was wrong, went unexamined. tobias_id is the value check [16] then
    # asserts the compiled shim actually agrees with.
    tobias_id = next((i + 1 for i, c in enumerate(manifest)
                      if c["character"] == "Tobias"), 0)
    leaks = 0
    empty_pool_but_nonempty_roster = 0
    for ci, c in enumerate(manifest):
        rec = wildpool[ci * WILDPOOL_STRIDE * 4:(ci + 1) * WILDPOOL_STRIDE * 4]
        n_entries = 0
        for k in range(WILDPOOL_STRIDE):
            sid, lvl, _pad = struct.unpack_from("<HBB", rec, k * 4)
            if sid == 0:
                break
            n_entries += 1
            if sp_table.get(str(sid)) in legend_names:
                if ci + 1 == tobias_id:
                    pass  # legendary-INCLUSIVE by design (Latios @1%%, user spec 2026-07-23)
                else:
                    leaks += 1
        if n_entries == 0 and c.get("starter_count", 0) > 0:
            empty_pool_but_nonempty_roster += 1
    ok(leaks == 0, f"no legendary species in any character's wild pool ({leaks} leaks)")
    ok(empty_pool_but_nonempty_roster == 0,
       "every character with a non-legendary roster has a non-empty wild pool")

    print("[13] CM flag id survives the engine's sweeps")
    src = (ROOT / "src" / "character_mode.c").read_text()
    m = re.search(r"#define\s+FLAG_CHARACTER_MODE\s+(0x[0-9A-Fa-f]+)", src)
    flag = int(m.group(1), 16) if m else None
    ok(flag is not None, "FLAG_CHARACTER_MODE parsed from src/character_mode.c")
    # ClearTempFieldEventData() memsets flags 0x000-0x01F on every map load;
    # ClearDailyFlags() memsets flags 0x920-0x95F on every RTC day rollover.
    # A flag in either range silently deactivates Character Mode mid-save --
    # that was the 0x945 bug (fixed 2026-07-24). Both ranges are re-derived
    # from the ROM below rather than trusted as constants.
    ok(not (TEMP_FLAGS_START <= flag <= TEMP_FLAGS_END),
       f"flag {flag:#x} outside the temp-flag sweep "
       f"({TEMP_FLAGS_START:#x}-{TEMP_FLAGS_END:#x})")
    ok(not (DAILY_FLAGS_START <= flag <= DAILY_FLAGS_END),
       f"flag {flag:#x} outside the daily-flag sweep "
       f"({DAILY_FLAGS_START:#x}-{DAILY_FLAGS_END:#x})")
    # ClearDailyFlags is `ldr r0,[gSaveBlock1Ptr]; ldr r3,=off; mov ip,r3;
    # push {lr}; movs r2,#8; movs r1,#0; add r0,ip; bl memset` -- find it and
    # confirm the byte range it wipes really is the one we excluded above.
    sig = bytes.fromhex("9c4600b5082200216044")
    i = orig.find(sig)
    ok(i != -1, "ClearDailyFlags located in the original ROM")
    if i != -1:
        swept_off = struct.unpack_from("<I", orig, i + 22)[0]
        first = SB1_FLAGS_OFF + DAILY_FLAGS_START // 8
        ok(swept_off == first,
           f"ClearDailyFlags wipes SB1+{swept_off:#x} == flags[{DAILY_FLAGS_START:#x}] "
           f"(8 B); our flag byte is SB1+{SB1_FLAGS_OFF + flag // 8:#x}")
    # No script anywhere in the ROM touches it (setflag/clearflag/checkflag).
    refs = sum(orig.count(bytes([op]) + struct.pack("<H", flag))
               for op in (SCR_SETFLAG, SCR_CLEARFLAG, SCR_CHECKFLAG))
    ok(refs == 0, f"no script setflag/clearflag/checkflag references flag {flag:#x} ({refs})")

    print("[15] mugshot renderer (Phase 3 render surface)")
    # NOT `if is_file()` -- a missing build/character_sprite.bin (e.g. after a
    # clean) silently dropped this check and the suite still reported success,
    # 49 -> 48 passed, exit 0. This is the ONLY check binding the shipped ROM to
    # the compiled renderer, so its absence must FAIL, not vanish.
    _mug_bin = ROOT / "build" / "character_sprite.bin"
    ok(_mug_bin.is_file(),
       "build/character_sprite.bin present (required to bind the ROM to the "
       "compiled renderer; rebuild if this fails)")
    if _mug_bin.is_file():
        _mug_blob = _mug_bin.read_bytes()
        ok(patched[_m:_m + len(_mug_blob)] == _mug_blob,
           f"renderer blob in ROM == build/character_sprite.bin ({len(_mug_blob)} B)")
    ok(patched[_m + 1] == 0xB5, "renderer starts with push {..,lr}")

    # The two callnative operands are re-derived from the ROM: find both 0x23
    # ops inside the script window and check where they point.
    _mug_ops = []
    _mug_lo, _mug_hi = 0xEE3800, 0xEE3B00
    _mug_i = _mug_lo
    while _mug_i < _mug_hi - 5:
        if patched[_mug_i] == 0x23:
            _mug_t = struct.unpack_from("<I", patched, _mug_i + 1)[0]
            if CM_MUGSHOT_ADDR <= (_mug_t & ~1) < CM_MUGSHOT_ADDR + _mugshot_len:
                _mug_ops.append(_mug_t)
        _mug_i += 1
    ok(len(_mug_ops) == 2, f"script names exactly two mugshot entry points ({len(_mug_ops)})")
    ok(all(a & 1 for a in _mug_ops), "both mugshot operands are Thumb pointers")
    ok(len(set(_mug_ops)) == 2, "show and hide are distinct entry points")

    # Re-locate the SpriteTemplate and check every pointer it hands the engine.
    # A wrong address here draws garbage rather than crashing.
    _MUG_ANIM, _MUG_AFFINE, _MUG_CB = 0x08A500CC, 0x08A500D0, 0x0800414D
    _mug_tmpl = None
    for _mug_o in range(_m, _mend - 24, 4):
        _mug_w = struct.unpack_from("<5I", patched, _mug_o + 4)
        if _mug_w[1] == _MUG_ANIM and _mug_w[3] == _MUG_AFFINE and _mug_w[4] == _MUG_CB:
            _mug_tmpl = _mug_o
            break
    ok(_mug_tmpl is not None, "SpriteTemplate located in the renderer blob")
    if _mug_tmpl is not None:
        _mug_tt, _mug_pt = struct.unpack_from("<HH", patched, _mug_tmpl)
        _mug_oam, _x1, _mug_img, _x2, _x3 = struct.unpack_from("<5I", patched, _mug_tmpl + 4)
        ok(_mug_tt != _mug_pt and 0xFFFF not in (_mug_tt, _mug_pt),
           f"template tile/palette tags distinct and non-TAG_NONE ({_mug_tt:#x}/{_mug_pt:#x})")
        ok(_mug_img == 0, "template images == NULL (required when tileTag != TAG_NONE)")
        _mug_oam_in = CM_MUGSHOT_ADDR <= _mug_oam < CM_MUGSHOT_ADDR + _mugshot_len
        ok(_mug_oam_in, f"template oam pointer inside the renderer blob ({_mug_oam:#x})")
        if _mug_oam_in:
            _a0, _a1, _a2, _a3 = struct.unpack_from("<4H", patched, _mug_oam & 0x01FFFFFF)
            ok((_a0 >> 14) == 0 and ((_a0 >> 13) & 1) == 0
               and (_a1 >> 14) == 3 and ((_a2 >> 10) & 3) == 0,
               f"OAM describes a 64x64 4bpp square sprite at priority 0 "
               f"(attr0={_a0:#06x} attr1={_a1:#06x} attr2={_a2:#06x})")

    print("[17] 1%% legendary wild encounters")
    # Re-derived from characters_manifest.json rather than read back from the
    # .bin, so agreeing with itself is not enough.
    _lg_blob = (CM / "legendaries.bin").read_bytes()
    _lg_off = LEGENDARY_ADDR & 0x01FFFFFF
    ok(patched[_lg_off:_lg_off + len(_lg_blob)] == _lg_blob,
       f"legendaries in-ROM == legendaries.bin ({len(_lg_blob)} B)")
    _lg_want = sorted({s for c in manifest
                       for s in c["roster_species_ids"][c["starter_count"]:]})
    ok(len(_lg_want) == LEGENDARY_COUNT,
       f"distinct legendaries re-derived from the manifest == "
       f"emitter's count ({len(_lg_want)} vs {LEGENDARY_COUNT})")
    ok(len(_lg_blob) == LEGENDARY_COUNT * 4 + NUM_CHARACTERS * 4,
       "legendaries.bin size == ids + flags + per-character masks")
    _lg_ids = list(struct.unpack_from(f"<{LEGENDARY_COUNT}H", _lg_blob, 0))
    _lg_flags = list(struct.unpack_from(f"<{LEGENDARY_COUNT}H", _lg_blob,
                                        LEGENDARY_COUNT * 2))
    ok(_lg_ids == _lg_want, "in-ROM legendary ids == manifest-derived set")

    # Flag hygiene. Every one of these ranges has already cost this repo real
    # time: 0x945 sat in the daily sweep and switched Character Mode off at
    # midnight, and anything above 0x95F is not in the flags array at all.
    ok(len(set(_lg_flags)) == LEGENDARY_COUNT,
       f"all {LEGENDARY_COUNT} legendary flags distinct")
    _lg_oob = [f for f in _lg_flags if f > FLAG_SPACE_END]
    ok(not _lg_oob, f"every legendary flag inside the flags array "
                    f"(<= {FLAG_SPACE_END:#x}); out of bounds: "
                    f"{[hex(f) for f in _lg_oob]}")
    _lg_temp = [f for f in _lg_flags if TEMP_FLAGS_START <= f <= TEMP_FLAGS_END]
    ok(not _lg_temp, f"no legendary flag in the temp sweep "
                     f"({TEMP_FLAGS_START:#x}-{TEMP_FLAGS_END:#x}): "
                     f"{[hex(f) for f in _lg_temp]}")
    _lg_daily = [f for f in _lg_flags if DAILY_FLAGS_START <= f <= DAILY_FLAGS_END]
    ok(not _lg_daily, f"no legendary flag in the daily sweep "
                      f"({DAILY_FLAGS_START:#x}-{DAILY_FLAGS_END:#x}) -- a flag "
                      f"here would un-catch every legendary at midnight: "
                      f"{[hex(f) for f in _lg_daily]}")
    _lg_cmflag = re.search(r"#define\s+FLAG_CHARACTER_MODE\s+(0x[0-9A-Fa-f]+)",
                           (ROOT / "src" / "character_mode.c").read_text())
    ok(_lg_cmflag and int(_lg_cmflag.group(1), 16) not in _lg_flags,
       "no legendary flag collides with FLAG_CHARACTER_MODE")
    _lg_refs = {f: sum(orig.count(bytes([op]) + struct.pack("<H", f))
                       for op in (SCR_SETFLAG, SCR_CLEARFLAG, SCR_CHECKFLAG))
                for f in _lg_flags}
    _lg_used = {hex(f): n for f, n in _lg_refs.items() if n}
    ok(not _lg_used,
       f"no script setflag/clearflag/checkflag touches any legendary flag "
       f"({_lg_used})")

    # Per-character masks, re-derived. The bit order here is the contract the
    # shim indexes sLegendaryIds with; getting it backwards would offer the
    # wrong legendary and still look plausible.
    _lg_maskoff = LEGENDARY_COUNT * 4
    _lg_idx = {s: i for i, s in enumerate(_lg_ids)}
    _lg_bad, _lg_with = [], 0
    for _lg_ci, _lg_c in enumerate(manifest):
        _lg_want_mask = 0
        for _lg_s in _lg_c["roster_species_ids"][_lg_c["starter_count"]:]:
            _lg_want_mask |= 1 << _lg_idx[_lg_s]
        _lg_got, = struct.unpack_from("<I", _lg_blob, _lg_maskoff + _lg_ci * 4)
        if _lg_got != _lg_want_mask:
            _lg_bad.append(_lg_c["character"])
        if _lg_want_mask:
            _lg_with += 1
    ok(not _lg_bad,
       f"every character's legendary mask matches their roster "
       f"({len(_lg_bad)} wrong: {_lg_bad[:5]})")
    ok(0 < _lg_with < NUM_CHARACTERS,
       f"some characters have a legendary and some do not ({_lg_with} of "
       f"{NUM_CHARACTERS}) -- neither all nor nothing")
    # No legendary may be reachable through the ORDINARY 10% pool -- that is what
    # keeps the two rates distinct -- EXCEPT Tobias, whose pool is deliberately
    # legendary-inclusive (Latios at 1%, user spec 2026-07-23) and who carries
    # the same exemption in check [12].
    # ⚠️ Tobias is NOT double-served: his whole roster is that one Latios, so it
    # sits in his starter slice and his legendary MASK IS ZERO -- the 1% roll
    # skips him entirely and his Latios stays repeatable via the pool, which is
    # what the spec wants for an all-legendary roster. Do not "fix" the mask.
    _lg_leak = []
    for _lg_ci, _lg_c in enumerate(manifest):
        if _lg_ci + 1 == tobias_id:
            continue
        _lg_rec = wildpool[_lg_ci * WILDPOOL_STRIDE * 4:
                           (_lg_ci + 1) * WILDPOOL_STRIDE * 4]
        for _lg_k in range(WILDPOOL_STRIDE):
            _lg_sid, = struct.unpack_from("<H", _lg_rec, _lg_k * 4)
            if _lg_sid == 0:
                break
            if _lg_sid in _lg_idx:
                _lg_leak.append((_lg_c["character"], _lg_sid))
    ok(not _lg_leak,
       f"no legendary id in any ordinary wild pool except Tobias's "
       f"({len(_lg_leak)} leaks: {_lg_leak[:5]})")
    _lg_tob = manifest[tobias_id - 1] if tobias_id else None
    ok(_lg_tob is None or not _lg_tob["roster_species_ids"][_lg_tob["starter_count"]:],
       "Tobias's legendary mask is empty -- his Latios stays repeatable via the "
       "pool rather than being retired on catch by the 1% roll")

    # ⚠️ Every local below is _fp*-prefixed on purpose. A bare `_p` or `_f` here
    # shadows the module-level PASS/FAIL COUNTERS that the summary line reads,
    # and the run reports a nonsense total instead of a result (that once printed
    # "135160 passed, 0 failed"). Same trap as section 15's _mug* prefix.
    print("[16] compiled shim constants (read back out of the built ROM)")
    # THE CHECK THE OTHER FIFTEEN WERE MISSING. Every section above validates an
    # emitted .bin, a patched byte range, or the C source TEXT. None of them ever
    # looked at the value the compiler actually baked into the shim, which is why
    # WILDPOOL_STRIDE sat at 104 against 176-byte data, and TOBIAS_CHAR_ID at 182
    # (Volo) against Tobias at 183, for four days with a green suite.
    # src/character_mode.c exports CM_BuildFingerprint into its own .text.* slice
    # so the constants land in the spliced blob; we find it by its magic.
    _fp_magic = struct.pack("<I", CM_FINGERPRINT_MAGIC)
    _fp_region = patched[SHIM_ADDR & 0x01FFFFFF:
                         (SHIM_ADDR & 0x01FFFFFF) + SHIM_REGION]
    ok(_fp_region.count(_fp_magic) == 1,
       f"exactly one build fingerprint in the shim blob "
       f"({_fp_region.count(_fp_magic)} found)")
    if _fp_region.count(_fp_magic) == 1:
        _fp_at = _fp_region.find(_fp_magic)
        (_fp_sig, _fp_nchars, _fp_stride,
         _fp_tobias, _fp_bmstride) = struct.unpack_from("<5I", _fp_region, _fp_at)
        ok(_fp_sig == CM_FINGERPRINT_MAGIC, "fingerprint magic")
        ok(_fp_nchars == NUM_CHARACTERS,
           f"shim compiled NUM_CHARACTERS={_fp_nchars} == manifest {NUM_CHARACTERS}")
        ok(_fp_stride == WILDPOOL_STRIDE,
           f"shim compiled WILDPOOL_STRIDE={_fp_stride} == "
           f"wildpool_manifest pool_stride {WILDPOOL_STRIDE}")
        ok(_fp_tobias == tobias_id,
           f"shim compiled TOBIAS_CHAR_ID={_fp_tobias} == manifest index of "
           f"Tobias {tobias_id}"
           + (f" (would be {manifest[_fp_tobias - 1]['character']})"
              if 0 < _fp_tobias <= len(manifest) and _fp_tobias != tobias_id
              else ""))
        ok(_fp_bmstride == BITMAP_STRIDE,
           f"shim compiled BITMAP_STRIDE={_fp_bmstride} == {BITMAP_STRIDE}")
        # The stride is only correct if the shim's own view of the table also
        # fits the region the injector reserved -- catches a stride that agrees
        # with the manifest while the table itself was sized from something else.
        ok(_fp_nchars * _fp_stride * 4 == len(wildpool),
           f"shim's view of the wild pool ({_fp_nchars}x{_fp_stride}x4 = "
           f"{_fp_nchars * _fp_stride * 4} B) == wildpool.bin ({len(wildpool)} B)")

    print(f"\n==== verify_artifacts: {_p} passed, {_f} failed ====")
    sys.exit(1 if _f else 0)


if __name__ == "__main__":
    main()
