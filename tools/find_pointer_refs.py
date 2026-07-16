#!/usr/bin/env python3
"""Find raw 4-byte little-endian pointer references to a ROM offset.

GBA code/data reference strings and sub-tables via plain 4-byte LE pointers
(literal pools in ARM/Thumb code work this way too — `ldr r0, [pc, #N]` loads
a pointer stored nearby as raw data). This lets us find what references a
known string's address WITHOUT needing Ghidra's disassembly at all: just
search the ROM bytes for the pointer value (file offset + 0x08000000, since
GBA ROM is mapped at 0x08000000).

Usage: find_pointer_refs.py <rom.gba> <hex_file_offset...>
"""
import argparse
import struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("offsets", nargs="+", help="hex file offsets, e.g. 0x3FD7A2")
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        data = f.read()

    for off_str in args.offsets:
        file_off = int(off_str, 16)
        rom_addr = 0x08000000 + file_off
        needle = struct.pack("<I", rom_addr)
        print(f"=== pointer refs to file offset 0x{file_off:08X} (ROM addr 0x{rom_addr:08X}) ===")
        start = 0
        hits = []
        while True:
            idx = data.find(needle, start)
            if idx == -1:
                break
            hits.append(idx)
            start = idx + 1
        if not hits:
            print("  (no raw pointer references found)")
        for h in hits:
            print(f"  0x{h:08X}  (ROM addr 0x{0x08000000+h:08X})")
        print()


if __name__ == "__main__":
    main()
