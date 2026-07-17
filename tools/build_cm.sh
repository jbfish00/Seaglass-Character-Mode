#!/bin/sh
# Build the Character Mode enforcement patch for Seaglass v3.0 from source.
# Produces build/seaglass_cm.gba (patched ROM, gitignored) + build/seaglass_cm.bps
# (distributable patch). Reproducible: compile -> link -> extract -> inject -> patch.
#
# The shim is linked at 0x08ED2164; its CM_GiveMonToPlayerGated entry is read
# back from the ELF and must match the 0x08ED21A7 (|1) word in inject_cm.asm's
# trampoline. If the shim grows/moves, update that word.
set -e
cd "$(dirname "$0")/.."
mkdir -p build

arm-none-eabi-gcc -mthumb -mcpu=arm7tdmi -Os -fno-inline -ffreestanding \
    -fno-builtin -c src/character_mode.c -o build/cm.o
arm-none-eabi-ld -Ttext=0x08ED2164 build/cm.o -o build/cm.elf 2>/dev/null || \
    arm-none-eabi-ld -Ttext=0x08ED2164 build/cm.o -o build/cm.elf
arm-none-eabi-objcopy -O binary build/cm.elf build/cm.bin

ENTRY=$(arm-none-eabi-nm build/cm.elf | awk '/CM_GiveMonToPlayerGated/{print "0x"$1}')
echo "shim blob: $(stat -c%s build/cm.bin) bytes; CM_GiveMonToPlayerGated=$ENTRY (trampoline word must be entry|1)"

tools/bin/armips tools/patches/inject_cm.asm
tools/bin/flips --create --bps "rom/seaglass v3.0.gba" "build/seaglass_cm.gba" "build/seaglass_cm.bps" >/dev/null
echo "built build/seaglass_cm.gba + build/seaglass_cm.bps"
