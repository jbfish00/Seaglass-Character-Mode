#!/usr/bin/env python3
"""Build TEST-ONLY ROMs for the live relearner layer (QoL 2026-10-17: the relearner also teaches egg moves).

The mart clipboard (savestate mart_inside.ss) is repointed at
    special ChooseMonForMoveRelearner (0xDE) ; waitstate ; releaseall ; end
so the REAL party-menu path runs: picking the lead sets VAR_0x8005 = GetNumberOfRelearnableMoves(lead), which the
shipped ROM answers through CM_NumRelearnable (level-up list + egg moves). The control ROM is the same build with
CM_NO_EGGRELEARN=1 (the vanilla count). Writes build/seaglass_cm_reltest.gba (from build/seaglass_cm.gba) or, with
--control, build/seaglass_cm_reltest_ctl.gba from a CM_NO_EGGRELEARN injector run, or, with --anylevel-control (QoL A2,
2026-10-24), build/seaglass_cm_reltest_lv.gba from a CM_NO_ANYLEVEL run (the relearner keeps the level cut). Never
distributed.
"""
import os, shutil, struct, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BG_EVENT_PTR_OFF = 0x123ACC          # mart clipboard BG event script pointer (build_egg_testrom.py)
TEST_SCRIPT_ADDR = 0x08F11400        # next to the other test entries, clear of each
SCRIPT = bytes([0x25, 0xDE, 0x00, 0x27, 0x6B, 0x02])


def main():
    control = "--control" in sys.argv
    lvctl = "--anylevel-control" in sys.argv
    src = ROOT / "build" / "seaglass_cm.gba"
    if control or lvctl:
        keep = {f: f.read_bytes() for f in (src, src.with_suffix(".bps")) if f.exists()}
        subprocess.run([sys.executable, str(ROOT / "tools" / "inject_character_mode.py")], check=True, cwd=ROOT,
                       env=dict(os.environ, **({"CM_NO_ANYLEVEL": "1"} if lvctl else {"CM_NO_EGGRELEARN": "1"})),
                       stdout=subprocess.DEVNULL)
        d = bytearray(src.read_bytes())
        # the control injection also rewrote the ELF/symbols/report in build/: rebuild the shipping set so later checks
        # never read the control's (verify_artifacts did once, 2026-10-24); then the ROM + BPS bytes are restored as before
        subprocess.run([sys.executable, str(ROOT / "tools" / "inject_character_mode.py")], check=True, cwd=ROOT,
                       stdout=subprocess.DEVNULL)
        for f, b in keep.items():                   # the shipping ROM + BPS stay the shipping ones
            f.write_bytes(b)
    else:
        d = bytearray(src.read_bytes())
    off = TEST_SCRIPT_ADDR - 0x08000000
    assert all(b == 0xFF for b in d[off:off + len(SCRIPT) + 8]), "test-script space not clear"
    d[off:off + len(SCRIPT)] = SCRIPT
    struct.pack_into("<I", d, BG_EVENT_PTR_OFF, TEST_SCRIPT_ADDR)
    out = ROOT / "build" / ("seaglass_cm_reltest_ctl.gba" if control else "seaglass_cm_reltest_lv.gba" if lvctl
                            else "seaglass_cm_reltest.gba")
    out.write_bytes(bytes(d))
    print("test ROM:", out.name, "(CM_NO_EGGRELEARN control)" if control else "(CM_NO_ANYLEVEL control)" if lvctl else "")


if __name__ == "__main__":
    main()
