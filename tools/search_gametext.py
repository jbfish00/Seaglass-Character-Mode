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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("text", nargs="+")
    ap.add_argument("--charmap", default="/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt")
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
