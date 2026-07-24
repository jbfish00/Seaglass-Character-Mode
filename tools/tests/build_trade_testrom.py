#!/usr/bin/env python3
"""Build a TEST-ONLY ROM variant for the in-situ trade-gate e2e (never shipped).

Real in-game trade NPCs sit deep in the game and the warp path is unusable
(same constraint Lazarus hit), so — exactly as Lazarus's run_trade_e2e does —
we repoint an *accessible* BG event (the mart clipboard, the one interaction
point we have a savestate for) to a tiny test entry script that hardcodes a
trade index and jumps straight into the REAL, already-overlaid trade junction:

    lock
    setvar 0x8008, <idx>
    goto   <junction[idx]>      ; == goto wrapper (the shipped overlay)

So the bytes actually exercised in the running ROM — the junction overlay, the
per-trade wrapper (copyvar 0x8008->0x8004, callnative CM_TradeCheck, compare
VAR_RESULT, refuse-vs-resume branch) — are the shipped ones, unmodified. The
clipboard's CM entry script (0x08EE2A00) is only *bypassed* in this variant, not
changed; build/seaglass_cm.gba is untouched.

Usage: python3 tools/tests/build_trade_testrom.py <idx 0..3>
Writes build/seaglass_cm_tradetest.gba.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "build" / "seaglass_cm.gba"
TESTROM = ROOT / "build" / "seaglass_cm_tradetest.gba"

BG_EVENT_PTR_OFF = 0x123ACC          # mart clipboard BG event script pointer
CM_ENTRY_ADDR    = 0x08EE3800        # shipped clipboard target (rebased 2026-07-23; must match inject_character_mode.SCRIPT_ADDR)
# Unused free space, clear of all CM data. Moved from 0x08EF0000 (task #5):
# the wild-encounter pool table now occupies 0x08EE4000-0x08EF5480 (170 x 104
# x 4B), which swallowed the old address.
TEST_SCRIPT_ADDR = 0x08F10000

# The junctions live at these addresses in *address* order, but each belongs to
# a trade index in the order (2, 0, 1, 3) — the setvar-0x8008 quirk documented
# in ROUTINE_MAP (verified: setvar 0x8008,2 sits 0x55 before 0x29CFF5, etc.).
# Map trade index -> its own junction so setvar and jump target agree.
JUNCTION_FOR_TRADE = {
    0: 0x082AF873,   # DOTS   -> receives Seedot 273
    1: 0x082B01EF,   # PLUSES -> receives Plusle 311
    2: 0x0829CFF5,   # SEASOR -> receives Horsea 116
    3: 0x0830129E,   # MEOWOW -> receives Meowth 52
}


def main():
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    assert 0 <= idx < 4, "idx must be 0..3"

    d = bytearray(SHIPPED.read_bytes())

    cur = struct.unpack_from("<I", d, BG_EVENT_PTR_OFF)[0]
    assert cur == CM_ENTRY_ADDR, f"clipboard BG ptr drifted: {cur:#x} != {CM_ENTRY_ADDR:#x}"

    off = TEST_SCRIPT_ADDR - 0x08000000
    assert all(b == 0xFF for b in d[off:off + 16]), "test-script free space not clear"

    junction = JUNCTION_FOR_TRADE[idx]
    # lock ; setvar 0x8008, idx ; goto junction (== the shipped goto-wrapper overlay)
    script = bytes([0x6A]) \
        + bytes([0x16, 0x08, 0x80, idx, 0x00]) \
        + bytes([0x05]) + struct.pack("<I", junction)
    d[off:off + len(script)] = script

    struct.pack_into("<I", d, BG_EVENT_PTR_OFF, TEST_SCRIPT_ADDR)

    TESTROM.write_bytes(bytes(d))
    print(f"test ROM: clipboard -> test trade entry (trade idx {idx}), "
          f"jumps into junction {junction:#x} (shipped overlay). "
          f"Never distributed.")


if __name__ == "__main__":
    main()
