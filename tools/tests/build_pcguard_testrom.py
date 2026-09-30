#!/usr/bin/env python3
"""Build a TEST-ONLY ROM for the LIVE PC second-guard e2e (never shipped).

WHAT IT TESTS. CM_PSSLastMonGuard (src/character_mode.c): the storage system
must refuse to deposit the party's last ON-ROSTER mon when an off-roster one
would be left behind (ROWE's IsRemovingLastAllowedPartyMon). verify_artifacts
[22] proves the bytes; only a real deposit attempt proves the rule.

THE FIXTURE IS THE HARD PART, and every shortcut was measured useless:
  - the existing PC test ROM's `giveegg` anchor gives [starter, EGG]. An egg
    is never "alive", so VANILLA already refuses to deposit the starter and the
    guard would be invisible;
  - this fork has no scripted `givemon` (script command 0x79 is a stub that
    returns 0), and a mon synthesised from Lua would mean trusting a donor
    tree's substruct order and checksum;
  - the gift gate boxes an off-roster gift on the way in.
So the clipboard does TWO things, chosen by the PARTY SIZE (not the CM flag:
the CM-off control needs the second press to reach the PC too):

    getpartysize ; compare VAR_RESULT, 2            ; 2nd press (party of 2):
    goto_if >=, <PC script>                         ;   the PC
    giveegg 116 ; setvar 0x8004, 1                  ; 1st press (party of 1):
    goto EventScript_EggHatch                       ;   a REAL, alive Horsea

The Lua layer presses once with CM off (the hatch leaves [Torchic, Horsea]),
turns CM on for the character under test, and presses again. From the goto on,
every byte is SHIPPED: the PC overlay, special 0x3F, the storage system, the
six retargeted BLs and the guard.

`--no-guard` restores the six BL sites and CanShiftMon's tail to the BASE
ROM's bytes in the test ROM only: the layer's NEGATIVE CONTROL, which must
fail (the deposit goes through).

Usage: python3 tools/tests/build_pcguard_testrom.py [--no-guard]
Writes build/seaglass_cm_pcguard.gba (or ..._pcguard_noguard.gba).
"""
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIPPED = ROOT / "build" / "seaglass_cm.gba"
BASE = ROOT / "rom" / "seaglass v3.0.gba"
TESTROM = ROOT / "build" / "seaglass_cm_pcguard.gba"

BG_EVENT_PTR_OFF = 0x123ACC          # mart clipboard BG event script pointer
CM_ENTRY_ADDR    = 0x08EE3800        # shipped clipboard target
# Clear of the trade (0x08F10000), egg (0x08F11000) and PC (0x08F11800) test
# scripts and of the encounter markers at 0x08F12000.
TEST_SCRIPT_ADDR = 0x08F11C00
EGG_SPECIES      = 116               # Horsea: ON Misty's roster, OFF Brendan's
VAR_0x8004       = 0x8004

OP_GETPARTYSIZE, OP_COMPARE, OP_GOTO_IF, OP_GIVEEGG, OP_SETVAR, OP_GOTO = 0x43, 0x21, 0x06, 0x7A, 0x16, 0x05
VAR_RESULT, COND_GE = 0x800D, 4

_INJ = (ROOT / "tools" / "inject_character_mode.py").read_text()


def _inj(name):
    return int(re.search(rf"^{name}\s*=\s*(0x[0-9A-Fa-f]+)", _INJ, re.M).group(1), 16)


def _inj_tuple(name):
    body = re.search(rf"^{name}\s*=\s*\(([^)]*)\)", _INJ, re.M).group(1)
    return tuple(int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]+", body))


def main():
    no_guard = "--no-guard" in sys.argv
    sys.path.insert(0, str(ROOT / "tools" / "character_mode"))
    import egg_hook
    import pc_hook

    d = bytearray(SHIPPED.read_bytes())
    base = BASE.read_bytes()

    cur = struct.unpack_from("<I", d, BG_EVENT_PTR_OFF)[0]
    _o = cur - 0x08000000
    assert (d[_o:_o + 5] == bytes([0x2B, 0xB0, 0x02, 0x06, 0x00])
            and struct.unpack_from("<I", d, _o + 5)[0] == CM_ENTRY_ADDR), \
        f"clipboard BG ptr {cur:#x} is not the roster pre-entry for {CM_ENTRY_ADDR:#x}"

    # Both shipped splices must be in place, or this would test stock tails.
    pc_rom, pc_off, pc_orig = pc_hook.SITES[0][0], pc_hook.SITES[0][1], pc_hook.SITES[0][2]
    assert d[pc_off] == OP_GOTO, "the PC splice is NOT in this build -- run the injector"
    assert d[egg_hook.SPLICE_FILE_OFF] == OP_GOTO, "the egg splice is NOT in this build"

    sites = _inj_tuple("PSS_GUARD_BL_SITES") + (_inj("PSS_CANSHIFT_BL"),
                                                _inj("PSS_CANSHIFT_TAIL"))
    tramp = _inj("PSS_GUARD_TRAMPOLINE_ADDR")
    for s in sites[:-1]:
        hw1, hw2 = struct.unpack_from("<HH", d, s)
        off = ((hw1 & 0x7FF) << 12) | ((hw2 & 0x7FF) << 1)
        if off & 0x400000:
            off -= 0x800000
        assert 0x08000000 + s + 4 + off == tramp, \
            f"guard site {s:#x} does not call the trampoline -- run the injector"

    off = TEST_SCRIPT_ADDR - 0x08000000
    script = (bytes([OP_GETPARTYSIZE])
              + bytes([OP_COMPARE]) + struct.pack("<HH", VAR_RESULT, 2)
              + bytes([OP_GOTO_IF, COND_GE]) + struct.pack("<I", pc_rom)
              + bytes([OP_GIVEEGG]) + struct.pack("<H", EGG_SPECIES)
              + bytes([OP_SETVAR]) + struct.pack("<HH", VAR_0x8004, 1)
              + bytes([OP_GOTO]) + struct.pack("<I", egg_hook.SCRIPT_ENTRY))
    assert all(b == 0xFF for b in d[off:off + len(script) + 8]), \
        "test-script free space not clear"
    d[off:off + len(script)] = script
    struct.pack_into("<I", d, BG_EVENT_PTR_OFF, TEST_SCRIPT_ADDR)

    out = TESTROM
    if no_guard:
        for s in sites:
            d[s:s + 4] = base[s:s + 4]
        out = TESTROM.with_name(TESTROM.stem + "_noguard" + TESTROM.suffix)
        print("NEGATIVE CONTROL: the six guard BLs and CanShiftMon's tail restored "
              "to the base ROM -- the guard is absent here.")

    out.write_bytes(bytes(d))
    print(f"test ROM: {out.name}: clipboard -> party>=2 ? goto PC {pc_rom:#x} "
          f": giveegg {EGG_SPECIES} + hatch. Never distributed.")


if __name__ == "__main__":
    main()
