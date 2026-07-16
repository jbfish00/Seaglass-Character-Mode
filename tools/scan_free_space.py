#!/usr/bin/env python3
"""Scan a GBA ROM for contiguous runs of a fill byte (free space).

Usage: scan_free_space.py <rom.gba> [--byte 0xFF] [--min 0x100]
"""
import argparse
import sys


def scan(data, fill_byte, min_len):
    runs = []
    start = None
    for i, b in enumerate(data):
        if b == fill_byte:
            if start is None:
                start = i
        else:
            if start is not None:
                length = i - start
                if length >= min_len:
                    runs.append((start, length))
                start = None
    if start is not None:
        length = len(data) - start
        if length >= min_len:
            runs.append((start, length))
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--byte", default="0xFF", help="fill byte to scan for (default 0xFF)")
    ap.add_argument("--min", default="0x100", help="minimum run length to report (default 0x100)")
    ap.add_argument("--top", type=int, default=30, help="show only the N largest runs")
    args = ap.parse_args()

    fill_byte = int(args.byte, 0)
    min_len = int(args.min, 0)

    with open(args.rom, "rb") as f:
        data = f.read()

    runs = scan(data, fill_byte, min_len)
    runs.sort(key=lambda r: -r[1])

    total_free = sum(r[1] for r in runs)
    print(f"ROM size: {len(data)} bytes ({len(data)/1024/1024:.2f} MiB)")
    print(f"Fill byte: 0x{fill_byte:02X}, min run length: 0x{min_len:X}")
    print(f"Total runs >= min: {len(runs)}")
    print(f"Total free bytes (this fill byte, this min size): {total_free} ({total_free/1024:.1f} KiB, {total_free/1024/1024:.2f} MiB)")
    print()
    print(f"Top {args.top} largest contiguous runs:")
    print(f"{'ROM offset':>12}  {'length (bytes)':>15}  {'length (hex)':>12}")
    for off, length in runs[: args.top]:
        print(f"0x{off:08X}  {length:15d}  0x{length:X}")


if __name__ == "__main__":
    main()
