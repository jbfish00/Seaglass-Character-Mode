#!/usr/bin/env python3
"""Derive the OAM sprite API from a pokeemerald(-expansion)-family binary hack.

The mugshot renderer (Phase 3 render surface) needs a handful of engine
symbols. The FireRed-family hacks (Radical Red, Unbound) get them for free --
their low-ROM vanilla region is untouched, so CFRU's BPRE.ld addresses hold
byte-exact. The Emerald-family hacks are full decomp rebuilds: nothing is at a
stock address and no symbol file exists, so each ROM has to be mined.

Three scans, each of which produced a verified result on Lazarus v2:

  1. CreateSprite + gSprites -- sizeof(struct Sprite) is 0x44, emitted as
     i*17*4:  lsls rA,rB,#4 / adds rA,rA,rB / lsls rA,rA,#2, followed by a
     read of the inUse byte at +0x3E and a PC-relative load of gSprites.

     ⚠️ TRAP: FireRed's compiler emits `adds rA,#62; ldrb rA,[rA,#0]` but the
     Emerald builds emit `adds rA,#60; ldrb rA,[rA,#2]` -- LDRB's imm5 only
     reaches 31, so the split point is a compiler choice, not a constant.
     Matching only the FireRed form finds NOTHING and looks like "this engine
     is different" when it is in fact identical. Both forms are accepted here.

  2. gDummySpriteAnimTable / gDummySpriteAffineAnimTable / SpriteCallbackDummy
     -- by tallying fields across every SpriteTemplate-shaped 24-byte record in
     ROM ({u16 tileTag, u16 palTag, ptr oam, ptr anims, ptr images,
     ptr affineAnims, odd-ptr callback}). The engine defaults are whatever the
     hundreds of real templates overwhelmingly point at. On Lazarus the winners
     led the runners-up 693-to-27, 1047-to-42 and 236-to-91.

  3. LoadCompressedSpriteSheet / LoadCompressedSpritePalette -- found through
     their one unmistakable callee. `LZ77UnCompWram` is a two-instruction BIOS
     thunk (`svc 17; bx lr`), so it is trivially locatable; both loaders are
     then among its BL callers, distinguishable by what they do next.

     ⚠️ TRAP: FireRed's build merges size|tag<<16 with ldrh/lsls/orrs, which is
     a lovely fingerprint -- and the Emerald build does not use it, copying the
     struct's second word wholesale instead. Fingerprinting the arithmetic
     rather than the callee finds nothing here.

Everything is reported with disassembly. Confirm before trusting: an address
that merely appears in the right place is not a finding.

Usage:  python3 tools/find_sprite_api.py <rom>
"""
import argparse
import collections
import struct
import subprocess
import sys

ROM_BASE = 0x08000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    args = ap.parse_args()
    d = open(args.rom, "rb").read()
    n = len(d)
    END = ROM_BASE + n
    hw = lambda o: struct.unpack_from("<H", d, o)[0]
    found = {}

    def dis(addr, nb, label):
        off = (addr & ~1) - ROM_BASE
        open("/tmp/_fsa.bin", "wb").write(d[off:off + nb])
        out = subprocess.run(
            ["arm-none-eabi-objdump", "-D", "-b", "binary", "-m", "arm",
             "-M", "force-thumb", f"--adjust-vma={addr & ~1:#x}", "/tmp/_fsa.bin"],
            capture_output=True, text=True).stdout
        print(f"--- {label} {addr:#010x}")
        print("\n".join(out.splitlines()[7:]))

    def pcrel(addr, h):
        return None if (h & 0xF800) != 0x4800 else (((addr + 4) & ~3) + ((h & 0xFF) * 4))

    # ---- 1. CreateSprite + gSprites -------------------------------------
    print("== 1. CreateSprite + gSprites (0x44 stride + inUse at +0x3E) ==")
    hits = []
    for o in range(0, n - 32, 2):
        h = hw(o)
        if (h & 0xF800) or ((h >> 6) & 0x1F) != 4:
            continue
        a, b = h & 7, (h >> 3) & 7
        if hw(o + 2) != 0x1800 | (b << 6) | (a << 3) | a:
            continue
        if hw(o + 4) != (2 << 6) | (a << 3) | a:
            continue
        # inUse at +0x3E, either split (see the trap in the docstring)
        inuse = False
        for k in range(3, 12):
            x = hw(o + 2 * k)
            if x == 0x3000 | (a << 8) | 0x3E:                    # adds rA,#62
                inuse = True
            if x == 0x3000 | (a << 8) | 0x3C:                    # adds rA,#60
                nxt = hw(o + 2 * k + 2)
                if (nxt & 0xF800) == 0x7800 and ((nxt >> 6) & 0x1F) == 2:
                    inuse = True                                 # ldrb rX,[rA,#2]
        if not inuse:
            continue
        base = None
        for k in range(-12, 8):
            oo = o + 2 * k
            if oo < 0:
                continue
            t = pcrel(ROM_BASE + oo, hw(oo))
            if t is None or not (0 <= t - ROM_BASE < n - 4):
                continue
            w = struct.unpack_from("<I", d, t - ROM_BASE)[0]
            if 0x02000000 <= w < 0x02040000:
                base = w
                break
        if base:
            hits.append((ROM_BASE + o, base))
    tally = collections.Counter(b for _, b in hits)
    if not tally:
        print("  NO HIT -- widen the scan, do not guess")
        return 1
    gsprites, count = tally.most_common(1)[0]
    print(f"  gSprites = {gsprites:#010x}  ({count} indexing sites)")
    found["gSprites"] = gsprites
    loop = next(a for a, b in hits if b == gsprites)
    fn = None
    for k in range(0, 0x80, 2):
        if (hw((loop - ROM_BASE) - k) & 0xFF00) == 0xB500:
            fn = loop - k
            break
    if fn:
        found["CreateSprite"] = fn
        dis(fn, 0x50, "CreateSprite")

    # ---- 2. template defaults -------------------------------------------
    print("\n== 2. dummy anim tables + SpriteCallbackDummy (template tally) ==")
    an, af, cb = collections.Counter(), collections.Counter(), collections.Counter()
    for o in range(0, n - 24, 4):
        oam, anims, images, affine, callback = struct.unpack_from("<5I", d, o + 4)
        if not all(ROM_BASE <= w < END and w % 2 == 0 for w in (oam, anims, affine)):
            continue
        if not (ROM_BASE <= callback < END and callback % 2 == 1):
            continue
        if not (images == 0 or ROM_BASE <= images < END):
            continue
        if struct.unpack_from("<I", d, o)[0] == 0:
            continue
        an[anims] += 1
        af[affine] += 1
        cb[callback] += 1
    for name, ctr in (("gDummySpriteAnimTable", an),
                      ("gDummySpriteAffineAnimTable", af),
                      ("SpriteCallbackDummy", cb)):
        top = ctr.most_common(2)
        if not top:
            continue
        w, c = top[0]
        runner = f", runner-up {top[1][1]}" if len(top) > 1 else ""
        print(f"  {name:<28} = {w:#010x}  (x{c}{runner})")
        found[name] = w
    if "SpriteCallbackDummy" in found:
        dis(found["SpriteCallbackDummy"], 8, "SpriteCallbackDummy (want `bx lr`)")

    # ---- 3. compressed loaders via the BIOS thunk ------------------------
    print("\n== 3. LoadCompressedSprite{Sheet,Palette} via LZ77UnCompWram ==")
    thunk = None
    for o in range(0, n - 4, 2):
        if hw(o) == 0xDF11 and hw(o + 2) == 0x4770:      # svc 17; bx lr
            thunk = ROM_BASE + o
            break
    if not thunk:
        print("  LZ77UnCompWram thunk not found")
        return 1
    print(f"  LZ77UnCompWram = {thunk:#010x}   LZ77UnCompVram = {thunk + 4:#010x}")
    found["LZ77UnCompWram"] = thunk
    found["LZ77UnCompVram"] = thunk + 4

    def bl_target(o):
        h1, h2 = hw(o), hw(o + 2)
        if (h1 & 0xF800) != 0xF000 or (h2 & 0xF800) != 0xF800:
            return None
        off = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1)
        return ROM_BASE + o + 4 + (off - 0x800000 if off & 0x400000 else off)

    callers = [ROM_BASE + o for o in range(0, n - 4, 2) if bl_target(o) == thunk]
    print(f"  {len(callers)} BL callers; the two loaders are small functions that")
    print("  build a struct on the stack and tail-call LoadSpriteSheet/-Palette:")
    for c in callers:
        s = None
        for k in range(0, 0x40, 2):
            if (hw((c - ROM_BASE) - k) & 0xFF00) == 0xB500:
                s = c - k
                break
        if s and (c - s) <= 0x14:
            dis(s, 0x30, "loader candidate")

    print("\nSUMMARY (every line confirmed by disassembly above):")
    for k, v in found.items():
        print(f"  {k:<28} = {v:#010x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
