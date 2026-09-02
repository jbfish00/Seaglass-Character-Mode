#!/usr/bin/env python3
"""Search a GBA Pokemon ROM for a string encoded via the Gen3 charmap.

Standard Gen3 (RS/E/FR/LG) text encoding is consistent across games for the
core Latin charset. Reuses the ROWE project's charmap.txt (same format pret
decomps use: `'X' = HH`) as the encoding table, since Seaglass's own charmap
is unknown/unpublished but should match its Emerald base for plain A-Z text.

Usage: search_gametext.py <rom.gba> <text...> [--charmap PATH] [--icase]
"""
import argparse
import re
import sys


def load_charmap(path):
    table = {}
    pat = re.compile(r"^'(.)'\s*=\s*([0-9A-Fa-f]{2})\s*$")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = pat.match(line.rstrip("\n"))
            if m:
                table[m.group(1)] = int(m.group(2), 16)
    return table


def encode(text, table):
    out = bytearray()
    for ch in text:
        if ch not in table:
            raise ValueError(f"character {ch!r} not in charmap")
        out.append(table[ch])
    return bytes(out)

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
    ap.add_argument("text", nargs="+")
    ap.add_argument("--charmap", default=str(_resolve_charmap()))
    ap.add_argument("--icase", action="store_true", help="also try Capitalized and lowercase variants")
    args = ap.parse_args()

    table = load_charmap(args.charmap)
    with open(args.rom, "rb") as f:
        data = f.read()

    query = " ".join(args.text)
    variants = {query, query.upper()}
    if args.icase:
        variants.add(query.capitalize())
        variants.add(query.lower())

    found_any = False
    for variant in variants:
        try:
            needle = encode(variant, table)
        except ValueError as e:
            print(f"skip {variant!r}: {e}")
            continue
        start = 0
        hits = []
        while True:
            idx = data.find(needle, start)
            if idx == -1:
                break
            hits.append(idx)
            start = idx + 1
        if hits:
            found_any = True
            print(f"{variant!r} ({len(needle)} bytes): {len(hits)} hit(s)")
            for off in hits[:20]:
                print(f"  0x{off:08X}")
            if len(hits) > 20:
                print(f"  ... and {len(hits) - 20} more")
        else:
            print(f"{variant!r}: no hits")

    if not found_any:
        sys.exit(1)


if __name__ == "__main__":
    main()
