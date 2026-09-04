#!/usr/bin/env python3
"""Assemble the egg-hatch sweep hook (hatch-path enforcement).

THE GAP THIS CLOSES. Eggs are deliberately exempt from the catch gate, the gift
routing and the activation party sweep, so an egg event can never block
progress -- but nothing looked at what an egg HATCHED INTO. A gift egg of an
off-roster species therefore hatched into a permanent off-roster party member.
Breeding cannot reach that (a roster stores whole evolution families and only
on-roster parents can be kept, so offspring are on-roster by construction);
gift eggs are the way in.

⚠️ AND THERE ARE REACHABLE GIFT EGGS HERE. Measured 2026-09-03
(docs/GIFT_EGGS.md, ../game_plans/rowe_parity.md §13.18): 3 reachable `giveegg` sites -- the hot-spring EGG (Wynaut), the PALDEAN EGG from the Team Aqua grunt (off-roster for ALL 114 offered characters), and an Alolan Egg vendor selling for PINBALL POINTS whose entire 9-species pool is off-roster for all 114.

RE summary (2026-09-03). Hatching is SCRIPT-DRIVEN, which is what makes this
cheap. The field-control step handler runs the script at 0x0832EEEF when
`ShouldEggHatch` returns true -- its pointer sits in that caller's literal pool
at 0x08123DFC, and it decodes to:

    0x0832EEEF: 69                 lockall
              +1: 0F 00 <text>      loadword 0, "Huh?"
              +7: 09 04             callstd MSGBOX_DEFAULT
    0x0832EEF8: 25 C5 00           special EggHatch  <- performs the hatch
              +3: 27                 waitstate
              +4: 6B                 releaseall
              +5: 02                 end

⚠️⚠️ **THE DONOR SOURCE IS WRONG ABOUT THIS SCRIPT, AND BELIEVING IT WOULD HAVE
BROKEN THE HOOK.** `tools/pokeemerald_expansion_donor/data/scripts/day_care.inc`
has EventScript_EggHatch as `lockall; msgbox; special EggHatch; releaseall;
end` -- with **no waitstate**. On that shape, anything appended after the
special would run BEFORE the hatch scene, so the sweep would see an egg, the
sweep's own egg exemption would skip it, and the hook would be a silent no-op.
The ROM was disassembled instead of trusted, and it HAS the waitstate. **The
donor tree is a guess at the fork point, not this binary.**

The tail from `special EggHatch` is overlaid with a `goto` into an injected
tail that replays those four commands and then runs
`callnative CM_SweepPartyToPCNative`. The sweep runs AFTER the waitstate, so it
sees the finished Pokemon rather than the egg, and the egg exemption inside the
sweep no longer applies to it. With Character Mode off the sweep returns
immediately and never empties the party.

⭐ ALL FOUR PORTS SHARE THIS TAIL SHAPE. Radical Red and Unbound (FireRed/CFRU)
have `25 C2 00 27 6B 02` at 0x081BF54F; both Emerald hacks have `25 C5 00 27 6B
02`. Only the special's id differs. Six bytes, and a `goto` needs five, so the
displaced code is replayed rather than shortened and the sixth byte is padding
that is never executed.

Two facts that made this safe, both checked IN THIS ROM:

- **Nothing references the interior of the script.** An UNALIGNED u32 scan of
  the whole ROM finds 0x0832EEEF (the entry) exactly once -- the caller's literal pool at 0x08123DFC, and finds ZERO
  references to any byte of the six being overlaid. (⚠️ The scan must be
  unaligned: script pointers in this engine are not word-aligned, and an
  aligned-only scan reports a clean interior it never actually looked at.)
- **Six bytes are available**, asserted byte-for-byte before the overlay is
  applied, so a wrong ROM or a re-run over an already patched one fails loudly
  instead of writing opcodes into the middle of something else.

Byte grammar (all opcodes confirmed against this repo's donor command table):
    23 <u32>   callnative
    25 <u16>   special
    27         waitstate
    05 <u32>   goto
    02         end
"""
import struct

SCRIPT_ENTRY = 0x832eeef
CALLER_POOL_OFF = 0x123dfc          # file offset of the caller's literal pool
SPLICE_ROM_ADDR = 0x832eef8
SPLICE_FILE_OFF = 0x32eef8
SPLICE_ORIG = bytes.fromhex("25c500276b02")   # special EggHatch; waitstate; 6B; end
SPECIAL_HATCH = 0x00C5
OPCODE_RELEASEALL = 0x6B
OPCODE_CALLNATIVE = 0x23


def build(tail_rom_addr, sweep_thumb_addr):
    """Return (blob, patches): the tail-script blob to place at tail_rom_addr
    and a list of (file_off, orig_bytes, new_bytes) overlay patches.

    sweep_thumb_addr is CM_SweepPartyToPCNative WITH the Thumb bit, resolved
    from the built shim's own symbol table by the injector -- never hardcoded,
    because a stale address here would call into the middle of another routine
    on every egg hatch and would not fail any static check.
    """
    assert sweep_thumb_addr & 1, (
        "CM_SweepPartyToPCNative must carry the Thumb bit; %#x does not"
        % sweep_thumb_addr)
    tail = (bytes([0x25]) + struct.pack("<H", SPECIAL_HATCH)   # replay: the hatch
            + bytes([0x27])                                     # replay: waitstate
            + bytes([OPCODE_RELEASEALL])                        # replay: releaseall
            + bytes([OPCODE_CALLNATIVE])
            + struct.pack("<I", sweep_thumb_addr)               # NEW: sweep to PC
            + bytes([0x02]))                                    # replay: end
    new = bytes([0x05]) + struct.pack("<I", tail_rom_addr) + b"\x00"
    assert len(new) == len(SPLICE_ORIG), (
        "egg splice must be exactly %d bytes, got %d"
        % (len(SPLICE_ORIG), len(new)))
    return tail, [(SPLICE_FILE_OFF, SPLICE_ORIG, new)]


if __name__ == "__main__":
    blob, patches = build(0x8fa0000, 0x08000001)
    print("tail: %d bytes: %s" % (len(blob), blob.hex(" ")))
    for off, orig, new in patches:
        print("patch @%#010x: %s -> %s" % (off, orig.hex(" "), new.hex(" ")))
