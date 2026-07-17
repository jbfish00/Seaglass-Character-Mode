#!/bin/sh
# Build the Character Mode enforcement patch for Seaglass v3.0 from source.
# Produces build/seaglass_cm.gba (patched ROM, gitignored) + build/seaglass_cm.bps
# (distributable patch). Reproducible: emit bitmaps -> compile -> link -> extract
# -> inject -> patch. The shim entry is read from the ELF and fed to armips, so
# the shim can grow/move without hand-editing the trampoline.
#
# Free-block layout: shim @0x08ED2164, roster bitmap @0x08ED2400 (must not
# overlap; shim is <0x29C bytes). Trampoline @0x08470200 (0xFF scavenge).
set -e
cd "$(dirname "$0")/.."
mkdir -p build

python3 tools/character_mode/emit_bitmaps.py

arm-none-eabi-gcc -mthumb -mcpu=arm7tdmi -Os -fno-inline -ffreestanding \
    -fno-builtin -DBITMAPS_ADDR=0x08ED2400 \
    -c src/character_mode.c -o build/cm.o
arm-none-eabi-ld -Ttext=0x08ED2164 build/cm.o -o build/cm.elf 2>/dev/null || true
arm-none-eabi-objcopy -O binary build/cm.elf build/cm.bin

ENTRY=$(arm-none-eabi-nm build/cm.elf | awk '/ CM_GiveMonToPlayerGated$/{print "0x"$1}')
SHIM_SZ=$(stat -c%s build/cm.bin)
printf '.definelabel CM_ENTRY, %s\n' "$ENTRY" > build/cm_entry.asm
echo "shim blob: $SHIM_SZ bytes; CM_GiveMonToPlayerGated=$ENTRY"
[ "$SHIM_SZ" -lt 668 ] || { echo "ERROR: shim >= 0x29C, overlaps bitmap @0x08ED2400"; exit 1; }

tools/bin/armips tools/patches/inject_cm.asm
tools/bin/flips --create --bps "rom/seaglass v3.0.gba" "build/seaglass_cm.gba" "build/seaglass_cm.bps" >/dev/null
echo "built build/seaglass_cm.gba + build/seaglass_cm.bps"
