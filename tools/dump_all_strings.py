#!/usr/bin/env python3
"""Exhaustively scan a GBA ROM for Gen3-charmap-encoded text runs and dump them all.

Unlike search_gametext.py (which looks for one known phrase), this walks the
whole ROM trying to decode a string starting at every offset, keeping runs
that look like real text (mostly known charmap bytes/control codes, reasonable
length, terminated by 0xFF). Useful for open-ended greps (e.g. "what menu
strings exist containing MODE or OPTION") when we don't know the exact wording
to search for.

Usage: dump_all_strings.py <rom.gba> [--min-len 6] [--charmap PATH] > dump.txt
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


# control codes and their operand-byte lengths (bytes to skip after the code byte)
CONTROL_CODES = {
    0xFF: (None, 0),      # string terminator
    0xFE: ("\\n", 0),
    0xFB: ("[PARA]", 0),
    0xFA: ("[PROMPT]", 0),
    0xFD: ("[CLEAR]", 0),
    0xF9: ("[F9]", 1),    # text speed / misc, 1 operand byte
    0xFC: ("[FC]", 1),    # color/highlight escape, 1 operand byte (placeholder codes etc use more, approximated)
}


def try_decode(data, start, table, min_len):
    out = []
    i = start
    n = len(data)
    letters = 0
    unknown = 0
    while i < n:
        b = data[i]
        if b == 0xFF:
            i += 1
            break
        if b in CONTROL_CODES:
            label, operand_len = CONTROL_CODES[b]
            if label:
                out.append(label)
            i += 1 + operand_len
            continue
        if b in table:
            ch = table[b]
            out.append(ch)
            if ch.isalnum() or ch == " ":
                letters += 1
            i += 1
            continue
        # unknown byte — bail, this isn't a clean text run
        unknown += 1
        break
    text = "".join(out)
    if unknown > 0:
        return None, start
    if letters < min_len:
        return None, i
    # require a decent letter ratio (avoid runs that are mostly control-code noise)
    if letters < len(text) * 0.4:
        return None, i
    return text, i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--min-len", type=int, default=6)
    ap.add_argument("--charmap", default="/home/jbfish00/Documents/Pokemon Rowe Alteration/charmap.txt")
    args = ap.parse_args()

    table = load_charmap(args.charmap)
    with open(args.rom, "rb") as f:
        data = f.read()

    i = 0
    n = len(data)
    found = 0
    while i < n:
        text, end = try_decode(data, i, table, args.min_len)
        if text:
            print(f"0x{i:08X}\t{text}")
            found += 1
            i = end
        else:
            i += 1

    import sys
    print(f"# {found} strings found", file=sys.stderr)


if __name__ == "__main__":
    main()
