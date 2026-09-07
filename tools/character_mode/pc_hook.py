#!/usr/bin/env python3
"""Assemble the PC-exit sweep hook (withdraw-path enforcement).

THE GAP THIS CLOSES. Enforcement deliberately routes off-roster Pokemon INTO
the PC -- the catch gate, the gift routing, the activation sweep and the
egg-hatch hook all box what the roster does not allow. Nothing then looked at
the PC's own WITHDRAW, so a mon the catch gate had just boxed could be taken
straight back out and kept for the rest of the run. No exploit was required: it
is what happens if you open the PC and take the mon back.
../game_plans/rowe_parity.md §13.24 has the measurement; §13.26c has this RE.

⭐ THE FINDING THAT MADE THIS CHEAP, AND IT IS THE EGG HOOK AGAIN. The PC is
opened FROM A SCRIPT, and the special that opens it carries a `waitstate`, so
the script RESUMES after the storage UI closes:

    0x0830E1DB: 0F 00 <0x0830EA7B>  loadword 0, "POKeMON Storage System opened."
              +6: 09 04              callstd MSGBOX_DEFAULT
    0x0830E1E1: 25 3F 00             special 0x3F   <- opens the storage system
              +3: 27                 waitstate      <- returns here when it closes
              +4: 05 <0x0830E162>    goto (back to the PC main menu)
              +9: 02                 end (unreachable)

That is the SAME SHAPE as the egg-hatch tail this repo already splices
(egg_hook.py: `25 C5 00 27 6B 02`), so this hook is that technique pointed at a
different script -- already shipped, negative-tested 6/6, and proven live in an
emulator (rowe_parity.md §13.22). ⭐ And there is MORE room here: nine
contiguous replayable bytes where a `goto` needs five; the egg hook had six.

⭐ TWO SITES, and both are hooked. They differ ONLY in where their `goto`
returns to, which is why each gets its own tail rather than sharing one -- a
shared tail would have to pick one return address and would silently send the
other caller to the wrong place. ✅ Both are confirmed to be PC scripts by the
same message pointer, `0x0830EA7B`.

✅ TWO IS THE WHOLE COUNT IN THIS ROM, measured rather than assumed: a
whole-ROM scan for the byte sequence `25 3F 00 27` finds exactly these two.
⚠️ There is a THIRD `special; waitstate` in the same PC menu, at `0x0830E1B9`,
and it is deliberately NOT hooked: its special is `0xFD`, and the dialogue
above it decodes as "Accessed <player>'s PC." -- the item storage PC, which
cannot move Pokemon into the party.

HOW THE SPECIAL ID WAS FOUND (0x3F), and it was NOT guessed. Counting
`def_special` entries in the donor's `data/specials.inc` puts `EggHatch` at
0xC5 -- EXACTLY the id egg_hook.py already uses in this ROM -- which validates
the whole index space, and `ShowPokemonStorageSystemPC` reads off as 0x3F.
✅ Independently confirmed by decoding the dialogue immediately above each
splice: "POKeMON Storage System opened."

⚠️ WHAT THIS GIVES, AND WHAT IT DOES NOT. This is ROWE's `Cb2_ExitPSS`
semantics: UNDO ON EXIT, not prevention. The player may withdraw an off-roster
mon and carry it inside the PC UI; it is boxed again the moment the PC closes.
🔴 It does NOT give ROWE's SECOND guard, `IsRemovingLastAllowedPartyMon`. The
sweep's never-empty rule KEEPS an off-roster mon when the roster allows nothing
else, so "deposit your only on-roster mon, withdraw an off-roster one, exit"
still leaves the player holding it. ROWE closes that inside the PSS's own
"can this mon be removed" check, which is a real RE job in a closed binary and
is deliberately NOT attempted here. Do not describe this hook as closing the
withdraw hole completely.

Two facts checked IN THIS ROM before either overlay is applied:

- **Nothing references the interior of either spliced region.** An UNALIGNED
  u32 scan of the whole ROM finds ZERO words pointing anywhere into
  0x0830E1E1..0x0830E1EA or 0x0830E22B..0x0830E234 -- the entries included,
  since each script falls into its own from the msgbox above rather than being
  jumped to. (⚠️ The scan MUST be unaligned: script pointers in this engine are
  not word-aligned, and an aligned-only scan reports a clean interior it never
  actually looked at.)
- **The nine original bytes at each site are asserted byte-for-byte** before
  anything is written, so a wrong ROM, or a re-run over an already-patched
  build, fails loudly instead of writing opcodes into the middle of something
  else.

Byte grammar (all opcodes confirmed in this ROM):
    23 <u32>   callnative
    25 <u16>   special
    27         waitstate
    05 <u32>   goto
"""
import struct

SPECIAL_PC = 0x003F
OPCODE_CALLNATIVE = 0x23

# The message both PC access scripts show, and the file offset of each script's
# pointer to it. Asserted by the injector, so a moved script fails loudly
# instead of being spliced at the wrong address.
PC_TEXT_PTR = 0x0830EA7B

# (rom_addr, file_off, original 9 bytes, text-pointer file offset)
SITES = [
    (0x0830E1E1, 0x0030E1E1,
     bytes.fromhex("253f00270562e13008"), 0x0030E1DB),
    (0x0830E22B, 0x0030E22B,
     bytes.fromhex("253f002705fde13008"), 0x0030E225),
]
# Kept for the checkers, which pin the primary site by name.
SPLICE_ROM_ADDR = SITES[0][0]
SPLICE_FILE_OFF = SITES[0][1]
SPLICE_ORIG = SITES[0][2]
TAIL_LEN = 14


def build(tail_base_addr, sweep_thumb_addr, spacing=0x20):
    """Return (blobs, patches).

    blobs is [(rom_addr, bytes)] -- one replayed tail per PC access script;
    patches is [(file_off, orig_bytes, new_bytes)] -- the overlays.

    sweep_thumb_addr is CM_SweepPartyToPCNative WITH the Thumb bit, resolved
    from the built shim's own symbol table by the injector -- never hardcoded,
    because a stale address here would call into the middle of another routine
    every time the player closes the PC, and would not fail any static check.
    """
    assert sweep_thumb_addr & 1, (
        "CM_SweepPartyToPCNative must carry the Thumb bit; %#x does not"
        % sweep_thumb_addr)
    blobs, patches = [], []
    for i, (rom_addr, file_off, orig, _txt) in enumerate(SITES):
        # The original tail's own goto target -- each site rejoins its OWN
        # caller. Read from the original bytes rather than hardcoded, so the
        # two can never be transposed.
        ret = struct.unpack_from("<I", orig, 5)[0]
        tail_addr = tail_base_addr + i * spacing
        tail = (bytes([0x25]) + struct.pack("<H", SPECIAL_PC)  # replay: open PC
                + bytes([0x27])                                 # replay: waitstate
                # NEW, and the ORDER IS THE FEATURE: the sweep runs AFTER the
                # waitstate, i.e. once the storage UI has closed and the party
                # is whatever the player left it as. Run before it and the
                # sweep would see the party as it was on the way IN -- a silent
                # no-op that still passes any "the callnative is present" check.
                + bytes([OPCODE_CALLNATIVE])
                + struct.pack("<I", sweep_thumb_addr)
                + bytes([0x05]) + struct.pack("<I", ret))       # rejoin
        assert len(tail) == TAIL_LEN, len(tail)
        new = bytes([0x05]) + struct.pack("<I", tail_addr)
        new += b"\x00" * (len(orig) - len(new))
        assert len(new) == len(orig), (
            "PC splice must be exactly %d bytes, got %d" % (len(orig), len(new)))
        blobs.append((tail_addr, tail))
        patches.append((file_off, orig, new))
    return blobs, patches


if __name__ == "__main__":
    blobs, patches = build(0x08FA1000, 0x08F00001)
    for a, b in blobs:
        print("tail @%#010x: %d bytes: %s" % (a, len(b), b.hex(" ")))
    for off, orig, new in patches:
        print("patch @%#010x: %s -> %s" % (off, orig.hex(" "), new.hex(" ")))
