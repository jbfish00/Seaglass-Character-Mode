#!/usr/bin/env python3
"""Print the address of CM_TradeCheck's `strh r4,[r0]` (the VAR_RESULT store).

cm_trade_test.lua breakpoints that exact instruction to capture the gate's
decision from r4 before the allow path's `special 0x100/0x101` can overwrite
VAR_RESULT. The address is *inside* the compiled shim, so it moves whenever the
shim is recompiled (e.g. the 2026-07-24 flag-id change shifted it 0x08ED25BC ->
0x08ED25B6, which silently turned the breakpoint into a read of a garbage r4).
Deriving it from build/cm.elf at test time keeps the suite honest.

Usage: find_shim_store.py [symbol]   -> prints e.g. 0x08ED25B6
"""
import re
import subprocess
import sys
from pathlib import Path

ELF = Path(__file__).parent.parent.parent / "build" / "cm.elf"
STORE = re.compile(r"^\s*([0-9a-f]+):\s+8004\s+strh\s+r4,\s*\[r0")


def main():
    sym = sys.argv[1] if len(sys.argv) > 1 else "CM_TradeCheck"
    if not ELF.is_file():
        sys.exit(f"{ELF} missing -- build first: python3 tools/inject_character_mode.py")
    dis = subprocess.run(["arm-none-eabi-objdump", "-d", str(ELF),
                          f"--disassemble={sym}"],
                         capture_output=True, text=True, check=True).stdout
    for line in dis.splitlines():
        m = STORE.match(line)
        if m:
            print(f"0x{int(m.group(1), 16):08X}")
            return
    sys.exit(f"no `strh r4,[r0]` found in {sym} -- shim shape changed, "
             "update cm_trade_test.lua's capture point")


if __name__ == "__main__":
    main()
