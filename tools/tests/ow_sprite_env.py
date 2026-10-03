#!/usr/bin/env python3
"""Print `export` lines for cm_ow_sprite_test.lua, and write the expected art.

The 18 frames + 32-byte palette come from the SOURCE sheet
(sprites/ow_player/) or, for Brendan and May, from Seaglass's own player infos
in the BASE ROM -- never from the built ROM, so the live test cannot agree with
the build by construction.

Usage: eval "$(python3 tools/tests/ow_sprite_env.py <character name>)"
"""
import os
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "character_mode"))
import seaglass_ow_player as owp  # noqa: E402

name = sys.argv[1]
out = os.environ.get("CM_OW_EXPECT", "/tmp/sg_ow_expect.bin")
sheets = owp.sheets()
if name in owp.NATIVE:
    base = (ROOT / "rom" / "seaglass v3.0.gba").read_bytes()
    info = owp.info_ptr(base, owp.NATIVE[name])
    tag, = struct.unpack_from("<H", base, owp.R(info) + 2)
    images, = struct.unpack_from("<I", base, owp.R(info) + 0x1C)
    fb = struct.unpack_from("<H", base, owp.R(images) + 4)[0]
    frames = b"".join(base[owp.R(p):owp.R(p) + fb] for p in
                      (struct.unpack_from("<I", base, owp.R(images) + 8 * f)[0] for f in range(18)))
    pal = next(base[owp.R(p):owp.R(p) + 32] for p, t in owp.pal_entries(base) if t == tag)
elif name in sheets:
    e = sheets[name]
    fb = e["width"] * e["height"] // 2
    frames = (owp.SHEETS / f"{e['stem']}.4bpp").read_bytes()
    pal = (owp.SHEETS / f"{e['stem']}.gbapal").read_bytes()
else:
    sys.exit(f"ow_sprite_env: {name} has no overworld sprite")
Path(out).write_bytes(frames + pal)
print(f"export CM_OW_EXPECT={out} CM_OW_FRAME_BYTES={fb}")
print(f"export CM_OW_NATIVE_IMAGES={images:#x}" if name in owp.NATIVE else "unset CM_OW_NATIVE_IMAGES")
