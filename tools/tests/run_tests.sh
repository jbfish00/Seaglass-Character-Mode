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
echo "=== Layer 4g: in-situ trade gate (idx2 SEASOR/Horsea, real overlay wrapper) ==="
python3 tools/tests/build_trade_testrom.py 2 > /tmp/sg_trade_build.log 2>&1 \
    || { echo "  FAIL building trade test ROM (see /tmp/sg_trade_build.log)"; exit 1; }
TRADEROM=build/seaglass_cm_tradetest.gba
trade_case() {  # name  CM_ON  CM_CHAR  EXPECT
    log=/tmp/sg_trade_$1.log
    timeout 150 env MGBA_HEADLESS_DEBUGGER=1 CM_ON=$2 CM_CHAR=$3 EXPECT=$4 "$MGBA" \
        --script tools/mgba_scripts/cm_trade_test.lua \
        -t tools/savestates/mart_inside.ss "$TRADEROM" > "$log" 2>&1 || true
    grep -q "HARNESS RESULT: PASS" "$log" && echo "  PASS trade $1" \
        || { echo "  FAIL trade $1 (see $log)"; grep -a "HARNESS.*FAIL" "$log"; exit 1; }
}
trade_case RED   1 1  0    # Horsea OFF Red's roster   -> refuse
trade_case MISTY 1 10 1    # Horsea ON  Misty's roster -> allow (discrimination)
trade_case CTRL  0 1  1    # CM off                    -> allow (control)

echo
echo "=== Layer 5a: wild-encounter override inert with CM off ==="
timeout 60 env MGBA_HEADLESS_DEBUGGER=1 CM_ON=0 "$MGBA" --script tools/mgba_scripts/cm_wild_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_wild_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_wild_off.log && echo "  PASS wild override inert (CM off)" \
    || { echo "  FAIL wild override inert (see /tmp/sg_wild_off.log)"; exit 1; }

echo
echo "=== Layer 5b: wild-encounter stage-fit (forced high level -> evolved stage, char 1 Red) ==="
python3 tools/tests/verify_wild_override.py > /tmp/sg_wild_stage.log 2>&1
grep -q "RESULT: PASS" /tmp/sg_wild_stage.log && echo "  PASS wild stage-fit + rate + legendary exclusion" \
    || { echo "  FAIL wild stage-fit (see /tmp/sg_wild_stage.log)"; cat /tmp/sg_wild_stage.log; exit 1; }

echo
echo "=== Layer 5c: wild-encounter choke-point proof (BL 0x0822BF36 is the sole land-path caller) ==="
# Proves, on a REACHABLE land encounter, that the exact BL we retarget is
# executed and is the ONLY caller of CreateMonWithIVs for the wild mon --
# so the surf/rock-smash/fishing coverage rests on "same proven choke point"
# (+ the ROM-wide single-caller BL-scan in verify_artifacts.py), not static
# analysis alone. See docs/ROUTINE_MAP.md's wild-encounter coverage note.
timeout 60 env MGBA_HEADLESS_DEBUGGER=1 "$MGBA" --script tools/mgba_scripts/prove_wild_chokepoint.lua \
    -t tools/savestates/at_8_8.ss "rom/seaglass v3.0.gba" > /tmp/sg_wild_choke.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_wild_choke.log && echo "  PASS choke point empirically proven (land path)" \
    || { echo "  FAIL choke-point proof (see /tmp/sg_wild_choke.log)"; grep -a "HARNESS" /tmp/sg_wild_choke.log; exit 1; }

echo
echo "ALL AUTOMATED LAYERS GREEN (incl. real-UI activation + in-situ trade e2e + wild override)."
echo "Remaining human-in-the-loop verify: full playthrough (docs/TESTING.md)."
