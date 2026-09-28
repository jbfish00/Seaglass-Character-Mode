#!/usr/bin/env python3
"""Print `export` lines for cm_roster_menu_test.lua: the roster display's entry
points read from the BUILT ELFs, and the expected rows for a character derived
from characters_manifest.json (deduplicated, first occurrence kept -- the same
rule the emitter applies, re-applied here rather than read back out of the
blob, so the live test cannot agree with the blob by construction).

Usage: eval "$(python3 tools/tests/roster_menu_env.py <character id, 1-based>)"
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"


def sym(elf, name):
    out = subprocess.run(["arm-none-eabi-nm", str(BUILD / elf)], check=True,
                         capture_output=True, text=True).stdout
    m = re.search(rf"^([0-9a-f]+) [Tt] {name}$", out, re.M)
    if not m:
        sys.exit(f"roster_menu_env: {name} not in {elf}")
    return int(m.group(1), 16)


char = int(sys.argv[1]) if len(sys.argv) > 1 else 10
man = json.loads((ROOT / "tools" / "character_mode" / "characters_manifest.json")
                 .read_text())["characters"]
roots = list(dict.fromkeys(man[char - 1]["roster_species_ids"]))
if len(roots) < 2:
    sys.exit(f"roster_menu_env: character {char} has {len(roots)} roots; the "
             f"test needs >= 2 to prove a cursor move changes the icon")
print(f"export CM_ROSTER_ONINIT={sym('roster_display.elf', 'CM_RosterMenu_OnInit'):#x}")
print(f"export CM_ROSTER_ONSEL={sym('roster_display.elf', 'CM_RosterMenu_OnSelectionChanged'):#x}")
print(f"export CM_ROSTER_ONDESTROY={sym('roster_display.elf', 'CM_RosterMenu_OnDestroy'):#x}")
print(f"export CM_OPEN_CODE_ENTRY={sym('cm.elf', 'CM_OpenCodeEntry'):#x}")
print(f"export CM_EXPECT_ROOTS={','.join(map(str, roots))}")
print(f"# {man[char - 1]['character']}: {len(roots)} rows", file=sys.stderr)
