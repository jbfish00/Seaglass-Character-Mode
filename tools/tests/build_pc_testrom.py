#!/usr/bin/env python3
"""Build a TEST-ONLY ROM variant for the LIVE PC-exit e2e (never shipped).

WHY THIS EXISTS. ../game_plans/rowe_parity.md §13.31 item 2: the PC-exit hook
shipped in four games verified STATICALLY only. The egg hook has a live layer
(4h); this one had none in any port, so "closing the PC calls the sweep" rested
entirely on reading bytes -- the exact position the hatch hook was in before
layer 4h existed, and the position §13.20 found four dead live layers hiding in.

The obstacle is the same one, and so is the answer: repoint the one interaction
point we hold a savestate for (the Oldale mart clipboard) at a tiny test entry
script, and let every byte after the `goto` be SHIPPED:

    giveegg <species>        ; an ANCHOR -- see below, this is load-bearing
    goto    0x0830E1E1       ; == the PC access script's spliced tail

⭐ Everything from that `goto` on is shipped, unmodified: the overlay itself,
the replayed `special 0x3F` + `waitstate` that opens the storage system and
waits for the player to close it, and the `callnative CM_SweepPartyToPCNative`
that runs when it does. Only the *entry* is a test shim, and
build/seaglass_cm.gba is never touched.

⚠️⚠️ THE EGG IS NOT DECORATION, AND WITHOUT IT THIS LAYER PROVES NOTHING. The
savestate's party holds exactly ONE Pokemon, the starter. `CM_SweepPartyToPCNative`
never empties the party: its pre-scan sets `kept` only if some mon is an egg or
on the roster, and when nothing qualifies the first off-roster mon is kept
anyway. So with a one-mon party the starter survives for EVERY character, the
"box" and "party" runs are identical, and the layer goes green while
discriminating nothing. `giveegg` supplies a second party member that the sweep
treats as a keeper (eggs are exempt AND set `kept`), so the starter's fate once
again depends on the roster. ⭐ This is the same trap Radical Red's egg layer
hit from the other side (§13.22: it needed a second, unhatched egg as an
anchor) -- the never-empty rule quietly makes a minimal fixture undiscriminating.

⚠️ WHY `giveegg` RATHER THAN A SYNTHESISED MON. Writing a Pokemon into
gPlayerParty from Lua means reproducing this engine's substruct order, XOR key
and checksum from a DONOR TREE -- and this repo has already been burned once by
trusting the donor about the PC/egg scripts. `giveegg` is the ROM's own
constructor. It also cannot be routed to the PC by the gift gate (eggs are
exempt everywhere by design), which is what makes it usable as an anchor at all:
an off-roster *gift* would be boxed on the way in and never reach the party.

Usage: python3 tools/tests/build_pc_testrom.py [species] [--no-hook]
Writes build/seaglass_cm_pctest.gba (or ..._pctest_nohook.gba).

`--no-hook` reverts BOTH PC splices to their stock tails in the test ROM only.
That is the live layer's NEGATIVE CONTROL: cm_pc_exit_test.lua must FAIL on it.
Without it the layer proves the sweep works when it is called and says nothing
about whether closing the PC calls it -- which is the entire claim.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "build" / "seaglass_cm.gba"
TESTROM = ROOT / "build" / "seaglass_cm_pctest.gba"

BG_EVENT_PTR_OFF = 0x123ACC          # mart clipboard BG event script pointer
CM_ENTRY_ADDR    = 0x08EE3800        # shipped clipboard target (build_trade_testrom.py)
# Free space, clear of every CM region AND of the other two test ROMs' entries
# (0x08F10000 trade, 0x08F11000 egg), so all three can be built from one tree
# without one silently overwriting another's script.
TEST_SCRIPT_ADDR = 0x08F11800

OP_GIVEEGG  = 0x7A
OP_GOTO     = 0x05


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_hook = "--no-hook" in sys.argv
    species = int(argv[0], 0) if argv else 116
    assert 0 < species < 0x4000, "species must be a literal id, not a var ref"

    sys.path.insert(0, str(ROOT / "tools" / "character_mode"))
    import pc_hook

    d = bytearray(SHIPPED.read_bytes())

    cur = struct.unpack_from("<I", d, BG_EVENT_PTR_OFF)[0]
    assert cur == CM_ENTRY_ADDR, f"clipboard BG ptr drifted: {cur:#x} != {CM_ENTRY_ADDR:#x}"

    # The whole point of this ROM is to run the SHIPPED hook. If the splice is
    # not in place the run would exercise the stock tail and report a green
    # "the mon stayed in the party" for the control cases while proving nothing
    # -- so refuse to build rather than test the wrong bytes.
    site_rom, site_off, site_orig = (pc_hook.SITES[0][0], pc_hook.SITES[0][1],
                                     pc_hook.SITES[0][2])
    spliced = bytes(d[site_off:site_off + len(site_orig)])
    assert spliced[0] == OP_GOTO, (
        "the PC splice is NOT in this build (%s) -- run the injector first"
        % spliced.hex(" "))
    tail = struct.unpack_from("<I", spliced, 1)[0]
    assert 0x08000000 <= tail < 0x0A000000, f"splice goto operand looks wrong: {tail:#x}"

    off = TEST_SCRIPT_ADDR - 0x08000000
    script = (bytes([OP_GIVEEGG]) + struct.pack("<H", species)
              + bytes([OP_GOTO]) + struct.pack("<I", site_rom))
    assert all(b == 0xFF for b in d[off:off + len(script) + 8]), \
        "test-script free space not clear"
    d[off:off + len(script)] = script

    struct.pack_into("<I", d, BG_EVENT_PTR_OFF, TEST_SCRIPT_ADDR)

    out = TESTROM
    if no_hook:
        # BOTH sites, not just the one under test: reverting only site 0 would
        # leave a build that still differs from "the hook is absent" in a way
        # nothing here would notice.
        for _r, _o, _orig, _txt in pc_hook.SITES:
            d[_o:_o + len(_orig)] = _orig
        out = TESTROM.with_name(TESTROM.stem + "_nohook" + TESTROM.suffix)
        print("NEGATIVE CONTROL: both PC splices reverted to their stock tails "
              "-- the hook is absent here.")

    out.write_bytes(bytes(d))
    print(f"test ROM: {out.name}: clipboard -> giveegg {species} (anchor), "
          f"goto PC script {site_rom:#x} "
          + ("(STOCK tail -- no sweep)" if no_hook else f"(spliced -> tail {tail:#x})")
          + ". Never distributed.")


if __name__ == "__main__":
    main()
