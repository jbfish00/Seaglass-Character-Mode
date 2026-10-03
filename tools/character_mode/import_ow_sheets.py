#!/usr/bin/env python3
"""Vendor the player-grade overworld sheets this repo's characters use.

The sheets are ROWE's built overworld art (pokeemerald player layout: stand and
walk in frames 0-8, run frames 9-17, 4bpp + one 16-colour palette each), as the
Radical Red port already imported them. This copies the ones whose character is
in this repo's characters_manifest.json into sprites/ow_player/, with a manifest
holding only those, so the build never reads outside this repo.

The source directory is an ARGUMENT (the Radical Red port's sprites/ow_player/),
never a literal path: check_repo_selfcontained.py forbids a sibling path here.

    python3 tools/character_mode/import_ow_sheets.py <source sprites/ow_player dir>
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "sprites" / "ow_player"
CHAR_MANIFEST = ROOT / "tools" / "character_mode" / "characters_manifest.json"


def main(src):
    src = Path(src)
    m = json.loads((src / "manifest.json").read_text())
    names = {c["character"] for c in json.loads(CHAR_MANIFEST.read_text())["characters"]}
    keep = {n: e for n, e in m["characters"].items() if n in names}
    DEST.mkdir(parents=True, exist_ok=True)
    for e in keep.values():
        for ext in (".4bpp", ".gbapal", ".png"):
            shutil.copy2(src / f"{e['stem']}{ext}", DEST / f"{e['stem']}{ext}")
    out = {"source": m["source"], "frames": m["frames"], "count": len(keep),
           "characters": dict(sorted(keep.items()))}
    (DEST / "manifest.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(keep)} sheets -> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
