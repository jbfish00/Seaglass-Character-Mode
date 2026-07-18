#!/bin/sh
# Seaglass Character Mode automated regression suite.
# Runs the layers that need no human input; see docs/TESTING.md for the full
# matrix (incl. the remaining real-UI activation e2e). Exit 0 = all green.
set -e
cd "$(dirname "$0")/../.."
ROM="build/seaglass_cm.gba"
MGBA="./tools/mgba_src/build/mgba-headless"
[ -f "$ROM" ] || { echo "build first: python3 tools/inject_character_mode.py"; exit 1; }

echo "=== Layer 3: static artifact verification ==="
python3 tools/tests/verify_artifacts.py

echo
echo "=== Layer 2: boot smoke (patched ROM) ==="
timeout 45 "$MGBA" --script tools/mgba_scripts/boot_test.lua "$ROM" > /tmp/sg_boot.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_boot.log && echo "  PASS boot smoke" \
    || { echo "  FAIL boot smoke (see /tmp/sg_boot.log)"; exit 1; }

echo
echo "=== Layer 4a: catch gate ON (char 1 Red blocks Zigzagoon -> PC) ==="
timeout 100 env CM_ON=1 CM_CHAR=1 "$MGBA" --script tools/mgba_scripts/cm_catch_test.lua \
    -t tools/savestates/battle_menu2.ss "$ROM" > /tmp/sg_gate_on.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_gate_on.log && echo "  PASS catch gate ON" \
    || { echo "  FAIL catch gate ON (see /tmp/sg_gate_on.log)"; exit 1; }

echo
echo "=== Layer 4b: catch gate OFF (control: mon caught to party) ==="
timeout 100 env CM_ON=0 "$MGBA" --script tools/mgba_scripts/cm_catch_test.lua \
    -t tools/savestates/battle_menu2.ss "$ROM" > /tmp/sg_gate_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_gate_off.log && echo "  PASS catch gate OFF" \
    || { echo "  FAIL catch gate OFF (see /tmp/sg_gate_off.log)"; exit 1; }

echo
echo "=== Layer 4c: real-UI activation e2e (type RED at the CODE screen) ==="
timeout 120 env CM_CODE=RED CM_EXPECT_CHAR=1 "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_red.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_red.log && echo "  PASS activation (RED -> char 1 + starter)" \
    || { echo "  FAIL activation RED (see /tmp/sg_ui_red.log)"; exit 1; }

echo
echo "=== Layer 4d: activation discrimination (MISTY -> char 10) ==="
timeout 120 env CM_CODE=MISTY CM_EXPECT_CHAR=10 "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_misty.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_misty.log && echo "  PASS activation (MISTY -> char 10 + starter)" \
    || { echo "  FAIL activation MISTY (see /tmp/sg_ui_misty.log)"; exit 1; }

echo
echo "=== Layer 4e: invalid code rejected (ZZZ -> no activation) ==="
timeout 120 env CM_CODE=ZZZ CM_EXPECT=reject "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_zzz.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_zzz.log && echo "  PASS invalid code rejected" \
    || { echo "  FAIL invalid-code reject (see /tmp/sg_ui_zzz.log)"; exit 1; }

echo
echo "=== Layer 4f: deactivation (CMDBGOFF clears preset CM char 10) ==="
timeout 120 env CM_CODE=CMDBGOFF CM_EXPECT=off CM_PRESET_CHAR=10 "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_off.log && echo "  PASS deactivation (CMDBGOFF)" \
    || { echo "  FAIL deactivation (see /tmp/sg_ui_off.log)"; exit 1; }

echo
echo "ALL AUTOMATED LAYERS GREEN (incl. real-UI activation e2e)."
echo "Remaining human-in-the-loop verify: trade refusal in-situ + full playthrough"
echo "(docs/TESTING.md)."
