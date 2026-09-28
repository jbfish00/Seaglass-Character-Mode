#!/usr/bin/env python3
"""Build a TEST-ONLY ROM that opens a dynamic multichoice from the mart
clipboard, so the RELOCATED callback table can be exercised live (never
shipped).

The roster display will drive `dynmultichoice` with its own callback set, so
the table the engine indexes must be the relocated one at
DYN_EVENT_TABLE_ADDR. Nothing in ordinary play opens a dynamic multichoice
with a callback set we can reach from a savestate, so -- exactly as
build_trade_testrom.py does for the trade junctions -- the mart clipboard's BG
event is repointed at a tiny script:

    lock
    dynmultichoice 0, 0, FALSE, 0xFF(default), FALSE, 0, <set>, 3 names
    release
    end

The three row names are species NAME fields in the base ROM (Bulbasaur,
Pikachu, Torchic), so no text needs injecting. Everything the engine runs
after the opcode -- the handler, the table loads, the callbacks -- is the
shipped build, unmodified.

Usage: python3 tools/tests/build_dynmenu_testrom.py <callback set, 0..254>
Writes build/seaglass_cm_dyntest.gba.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "build" / "seaglass_cm.gba"
TESTROM = ROOT / "build" / "seaglass_cm_dyntest.gba"
BG_EVENT_PTR_OFF = 0x123ACC          # mart clipboard BG event script pointer
CM_ENTRY_ADDR = 0x08EE3800           # shipped clipboard target (inject SCRIPT_ADDR)
# Free in the base ROM and in the build; clear of the trade test's 0x08F10000
# and the encounter markers at 0x08F12000.
TEST_SCRIPT_ADDR = 0x08F11000
# Species NAME fields (gSpeciesInfo 0x088F0780 + 44 + id*208), 0xFF-terminated.
NAME_BASE, STRIDE = 0x088F07AC, 208
ROWS = (1, 25, 255)                  # Bulbasaur, Pikachu, Torchic


def main():
    cb_set = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    assert 0 <= cb_set < 0xFF, "0xFF is NONE; pass a real set id"
    d = bytearray(SHIPPED.read_bytes())
    cur = struct.unpack_from("<I", d, BG_EVENT_PTR_OFF)[0]
    assert cur == CM_ENTRY_ADDR, f"clipboard BG ptr drifted: {cur:#x} != {CM_ENTRY_ADDR:#x}"
    off = TEST_SCRIPT_ADDR - 0x08000000
    assert all(b == 0xFF for b in d[off:off + 64]), "test-script free space not clear"
    for s in ROWS:
        nm = d[NAME_BASE - 0x08000000 + s * STRIDE:][:12]
        assert nm[0] not in (0x00, 0xFF) and 0xFF in nm, f"species {s} has no name"

    script = bytes([0x6A])                                   # lock
    script += bytes([0xE3]) + struct.pack("<HH", 0, 0)       # dynmultichoice left, top
    script += bytes([0, 0xFF, 0])                            # ignoreB, maxBeforeScroll, shouldSort
    script += struct.pack("<H", 0)                           # initialSelected
    script += bytes([cb_set, len(ROWS)])                     # callbackSet, argc
    script += b"".join(struct.pack("<I", NAME_BASE + s * STRIDE) for s in ROWS)
    script += bytes([0x6C, 0x02])                            # release ; end
    d[off:off + len(script)] = script
    struct.pack_into("<I", d, BG_EVENT_PTR_OFF, TEST_SCRIPT_ADDR)

    TESTROM.write_bytes(bytes(d))
    print(f"test ROM: clipboard -> dynmultichoice (callback set {cb_set}, "
          f"{len(ROWS)} rows) @ {TEST_SCRIPT_ADDR:#x}. Never distributed.")


if __name__ == "__main__":
    main()
