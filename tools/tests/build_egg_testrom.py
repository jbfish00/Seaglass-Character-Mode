#!/usr/bin/env python3
"""Build a TEST-ONLY ROM variant for the LIVE egg-hatch e2e (never shipped).

WHY THIS EXISTS. ../game_plans/rowe_parity.md §13.20 closed the egg-hatch hole
in this repo -- the hatch script's tail is overlaid with a `goto` into an
injected tail that replays the hatch and then runs the activation party sweep,
so a gift egg of an off-roster species can no longer hatch into a permanent
off-roster party member. That hook is verified statically (five checks in
verify_artifacts.py, negative-tested 6/6 by egg_hook_negative_test.py) and by
every pre-existing live layer -- but **nobody had ever walked a hatch in an
emulator here**, which was §13.21's top open item.

The obstacle is reach: the three reachable gift eggs in this ROM
(docs/GIFT_EGGS.md) sit far past any savestate we hold, and hatching one needs
hundreds of steps afterwards. So -- exactly as build_trade_testrom.py does for
the trade gate -- we repoint the one interaction point we DO have a savestate
for (the Oldale mart clipboard) at a tiny test entry script:

    giveegg <species>          ; the game's OWN egg constructor
    setvar  0x8004, <slot>     ; the party index EggHatch/ScriptHatchMon reads
    goto    0x0832EEEF         ; == EventScript_EggHatch, WITH the shipped splice

⭐ Everything after the `goto` is shipped, unmodified bytes: the spliced tail,
the replayed `special EggHatch`/`waitstate`/`releaseall`, and the
`callnative CM_SweepPartyToPCNative`. Only the *entry* is a test shim, and
build/seaglass_cm.gba is never touched.

⚠️ WHY `giveegg` RATHER THAN A SYNTHESISED EGG. Writing an egg into gPlayerParty
from Lua means reproducing this engine's substruct order, XOR key and checksum
from a DONOR TREE -- and this repo has already been burned once by trusting the
donor about exactly this script (the donor's EventScript_EggHatch has no
`waitstate`; the ROM's does). `giveegg` is the ROM's own constructor, so the egg
under test is by construction the same object a real gift egg produces.

Usage: python3 tools/tests/build_egg_testrom.py <species> [slot] [--no-hook]
Writes build/seaglass_cm_eggtest.gba (or ..._eggtest_nohook.gba).

`--no-hook` reverts the splice to the stock tail in the test ROM only. That is
the live layer's NEGATIVE CONTROL: cm_egg_hatch_test.lua must FAIL on it. Without
it the layer proves the sweep works when it is called and says nothing about
whether the hatch calls it -- which is the entire claim being made.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "build" / "seaglass_cm.gba"
TESTROM = ROOT / "build" / "seaglass_cm_eggtest.gba"

BG_EVENT_PTR_OFF = 0x123ACC          # mart clipboard BG event script pointer
CM_ENTRY_ADDR    = 0x08EE3800        # shipped clipboard target (build_trade_testrom.py)
# Free space, clear of every CM region. 0x08F10000 is the trade test script's;
# take the next page so both test ROMs can be built from one tree without one
# silently overwriting the other's entry.
TEST_SCRIPT_ADDR = 0x08F11000

OP_GIVEEGG  = 0x7A
OP_SETVAR   = 0x16
OP_GOTO     = 0x05
VAR_0x8004  = 0x8004


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().splitlines()[-2])
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_hook = "--no-hook" in sys.argv
    species = int(argv[0], 0)
    slot = int(argv[1], 0) if len(argv) > 1 else 1
    assert 0 < species < 0x4000, "species must be a literal id, not a var ref"
    assert 0 <= slot < 6, "slot must be a party index"

    sys.path.insert(0, str(ROOT / "tools" / "character_mode"))
    import egg_hook

    d = bytearray(SHIPPED.read_bytes())

    cur = struct.unpack_from("<I", d, BG_EVENT_PTR_OFF)[0]
    assert cur == CM_ENTRY_ADDR, f"clipboard BG ptr drifted: {cur:#x} != {CM_ENTRY_ADDR:#x}"

    # The whole point of this ROM is to run the SHIPPED hook. If the splice is
    # not in place, the run would exercise the stock tail and report a green
    # "the mon stayed in the party" for the control cases while proving nothing
    # -- so refuse to build rather than test the wrong bytes.
    spliced = bytes(d[egg_hook.SPLICE_FILE_OFF:
                      egg_hook.SPLICE_FILE_OFF + len(egg_hook.SPLICE_ORIG)])
    assert spliced[0] == OP_GOTO, (
        "the egg-hatch splice is NOT in this build (%s) -- run the injector first"
        % spliced.hex(" "))
    tail = struct.unpack_from("<I", spliced, 1)[0]
    assert 0x08000000 <= tail < 0x0A000000, f"splice goto operand looks wrong: {tail:#x}"

    off = TEST_SCRIPT_ADDR - 0x08000000
    script = (bytes([OP_GIVEEGG]) + struct.pack("<H", species)
              + bytes([OP_SETVAR]) + struct.pack("<HH", VAR_0x8004, slot)
              + bytes([OP_GOTO]) + struct.pack("<I", egg_hook.SCRIPT_ENTRY))
    assert all(b == 0xFF for b in d[off:off + len(script) + 8]), \
        "test-script free space not clear"
    d[off:off + len(script)] = script

    struct.pack_into("<I", d, BG_EVENT_PTR_OFF, TEST_SCRIPT_ADDR)

    out = TESTROM
    if no_hook:
        o = egg_hook.SPLICE_FILE_OFF
        d[o:o + len(egg_hook.SPLICE_ORIG)] = egg_hook.SPLICE_ORIG
        out = TESTROM.with_name(TESTROM.stem + "_nohook" + TESTROM.suffix)
        print("NEGATIVE CONTROL: splice reverted to the stock tail "
              f"({egg_hook.SPLICE_ORIG.hex(' ')}) -- the hook is absent here.")

    out.write_bytes(bytes(d))
    print(f"test ROM: {out.name}: clipboard -> giveegg {species}, "
          f"setvar 0x8004={slot}, goto EventScript_EggHatch "
          f"{egg_hook.SCRIPT_ENTRY:#x} "
          + ("(STOCK tail -- no sweep)" if no_hook else f"(spliced -> tail {tail:#x})")
          + ". Never distributed.")


if __name__ == "__main__":
    main()
