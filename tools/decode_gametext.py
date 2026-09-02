#!/usr/bin/env python3
"""Decode Gen3-charmap-encoded game text at given ROM offsets, with context.

Companion to search_gametext.py — once a hit offset is found, use this to
read the surrounding text and figure out what dialogue/menu it belongs to.

Usage: decode_gametext.py <rom.gba> <hex_offset...> [--before N] [--after N] [--charmap PATH]
"""
import argparse
import re


def load_charmap(path):
    table = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.rstrip("\n"))
            if m:
                table[int(m.group(2), 16)] = m.group(1)
    return table


CONTROL_CODES = {
    0xFF: "[END]",
    0xFE: "\\n",
    0xFB: "[PARA]",
    0xFA: "[PROMPT]",
    0xFD: "[CLEAR]",
}


def decode(data, table):
    out = []
    for byte in data:
        if byte in CONTROL_CODES:
            out.append(CONTROL_CODES[byte])
        elif byte in table:
            out.append(table[byte])
        else:
            out.append(f"[{byte:02X}]")
    return "".join(out)

def _resolve_charmap():
    """Path to this repo's vendored game-text charmap (tools/charmap.txt).

    This was a hardcoded absolute path into the unrelated "Pokemon Rowe
    Alteration" working tree, which made this repo unbuildable and
    unverifiable from a fresh clone. The charmap is now vendored here
    (byte-identical, md5 b31d142ca98103d64d707f9894fa42e3). Resolution is
    anchored to this file's own location, never the cwd.

    Override with the CM_CHARMAP environment variable.
    """
    import os
    from pathlib import Path
    override = os.environ.get("CM_CHARMAP")
    if override:
        p = Path(override)
        if not p.is_file():
            raise SystemExit("CM_CHARMAP=%s is not a file" % override)
        return p
    # Walk up to the REPO ROOT only. An unbounded walk would keep climbing past
    # the repo into ~ and could silently pick up an unrelated tools/charmap.txt
    # -- reading the wrong charmap presents as "this game encodes text
    # differently", not as a missing file. Bound it at the .git directory.
    for parent in Path(__file__).resolve().parents:
        cand = parent / "tools" / "charmap.txt"
        if cand.is_file():
            return cand
        if (parent / ".git").exists():
            break
    raise SystemExit(
        "charmap.txt not found. Expected it vendored at <repo>/tools/charmap.txt; "
        "set CM_CHARMAP to override.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("offsets", nargs="+", help="hex offsets, e.g. 0x1A6317")
    ap.add_argument("--before", type=int, default=20)
    ap.add_argument("--after", type=int, default=80)
    ap.add_argument("--charmap", default=str(_resolve_charmap()))
    args = ap.parse_args()

    table = load_charmap(args.charmap)
    with open(args.rom, "rb") as f:
        data = f.read()

    for off_str in args.offsets:
        off = int(off_str, 16)
        start = max(0, off - args.before)
        window = data[start : off + args.after]
        print(f"=== around 0x{off:08X} ===")
        print(decode(window, table))
        print()


if __name__ == "__main__":
    main()
