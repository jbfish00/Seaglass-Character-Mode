#!/bin/sh
# Seaglass Character Mode automated regression suite.
# Runs the layers that need no human input; see docs/TESTING.md for the full
# matrix (incl. the remaining real-UI activation e2e). Exit 0 = all green.
#
# ⭐ EVERY LAYER DECLARES THE NUMBER OF ASSERTIONS IT MUST RUN, as
# CM_EXPECT_CHECKS in its environment. H.finish() turns both "ran zero
# assertions" and "ran a different number than declared" into RESULT: FAIL, so
# the greps below catch them without further plumbing
# (../game_plans/rowe_parity.md §1; proved by tools/tests/harness_guard_test.sh).
#
# Why this exists: until 2026-08-20 a layer that asserted NOTHING printed
# RESULT: PASS and was counted green here. Layer 2 was exactly that -- it ran
# 200 frames, screenshotted, and checked nothing. If you change a layer's
# assertions, update its number here; a changed tally is a regression until a
# human says otherwise.
set -e
cd "$(dirname "$0")/../.."
ROM="build/seaglass_cm.gba"
MGBA="./tools/mgba_src/build/mgba-headless"
[ -f "$ROM" ] || { echo "build first: python3 tools/inject_character_mode.py"; exit 1; }

# The mugshot renderer moves whenever the sprite art grows into it (it was
# rebased 0x08F42000 -> 0x08F60000 on 2026-07-29). Derive it from the injector
# rather than letting cm_ui_activate.lua carry a literal, the same way
# CM_TRADECHECK_STORE is derived below -- a stale address there fails as
# "mugshot template not located", which reads like a broken renderer rather
# than a moved one.
CM_MUGSHOT_ADDR=$(sed -n 's/^CM_MUGSHOT_ADDR *= *\(0x[0-9A-Fa-f]*\).*/\1/p' \
    tools/inject_character_mode.py | head -1)
[ -n "$CM_MUGSHOT_ADDR" ] || { echo "  FAIL reading CM_MUGSHOT_ADDR from the injector"; exit 1; }
export CM_MUGSHOT_ADDR
echo "  (mugshot renderer @ $CM_MUGSHOT_ADDR)"

echo "=== Layer 3: static artifact verification ==="
python3 tools/tests/verify_artifacts.py

echo
echo "=== Layer 2: boot smoke (patched ROM) ==="
timeout 45 env CM_EXPECT_CHECKS=4 "$MGBA" --script tools/mgba_scripts/boot_test.lua "$ROM" > /tmp/sg_boot.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_boot.log && echo "  PASS boot smoke" \
    || { echo "  FAIL boot smoke (see /tmp/sg_boot.log)"; exit 1; }

echo
echo "=== Layer 4a: catch gate ON (char 1 Red blocks Zigzagoon -> PC) ==="
timeout 100 env CM_EXPECT_CHECKS=1 CM_ON=1 CM_CHAR=1 "$MGBA" --script tools/mgba_scripts/cm_catch_test.lua \
    -t tools/savestates/battle_menu2.ss "$ROM" > /tmp/sg_gate_on.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_gate_on.log && echo "  PASS catch gate ON" \
    || { echo "  FAIL catch gate ON (see /tmp/sg_gate_on.log)"; exit 1; }

echo
echo "=== Layer 4b: catch gate OFF (control: mon caught to party) ==="
timeout 100 env CM_EXPECT_CHECKS=1 CM_ON=0 "$MGBA" --script tools/mgba_scripts/cm_catch_test.lua \
    -t tools/savestates/battle_menu2.ss "$ROM" > /tmp/sg_gate_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_gate_off.log && echo "  PASS catch gate OFF" \
    || { echo "  FAIL catch gate OFF (see /tmp/sg_gate_off.log)"; exit 1; }

echo
echo "=== Layer 4c: real-UI activation e2e (type RED at the CODE screen) ==="
timeout 120 env CM_EXPECT_CHECKS=8 CM_CODE=RED CM_EXPECT_CHAR=1 "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_red.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_red.log && echo "  PASS activation (RED -> char 1 + starter)" \
    || { echo "  FAIL activation RED (see /tmp/sg_ui_red.log)"; exit 1; }

echo
echo "=== Layer 4d: activation discrimination (MISTY -> char 10) ==="
timeout 120 env CM_EXPECT_CHECKS=8 CM_CODE=MISTY CM_EXPECT_CHAR=10 "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_misty.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_misty.log && echo "  PASS activation (MISTY -> char 10 + starter)" \
    || { echo "  FAIL activation MISTY (see /tmp/sg_ui_misty.log)"; exit 1; }

echo
echo "=== Layer 4e: invalid code rejected (ZZZ -> no activation) ==="
timeout 120 env CM_EXPECT_CHECKS=4 CM_CODE=ZZZ CM_EXPECT=reject "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_zzz.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_zzz.log && echo "  PASS invalid code rejected" \
    || { echo "  FAIL invalid-code reject (see /tmp/sg_ui_zzz.log)"; exit 1; }

echo
# The threshold's live proof. Layer 4e shows an UNKNOWN code is refused; this
# shows a REAL character's code is refused because they are under the threshold.
# Without it, "hidden" is only ever asserted against bytes in the ROM, never
# against the running matcher -- and a gate that poisoned nobody would still
# pass every static check that reads the same table it was written from.
# Clay is deliberately chosen: he is under the threshold on the current data AND
# would stay under it if the sibling additions overlay were ported, so this layer
# does not silently become a no-op the next time the rosters move.
echo "=== Layer 4e2: hidden character refused (CLAY is under the threshold) ==="
timeout 120 env CM_EXPECT_CHECKS=4 CM_CODE=CLAY CM_EXPECT=reject "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_hidden.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_hidden.log && echo "  PASS hidden character refused (CLAY)" \
    || { echo "  FAIL hidden character NOT refused (see /tmp/sg_ui_hidden.log)"; exit 1; }

echo
echo "=== Layer 4f: deactivation (CMDBGOFF clears preset CM char 10) ==="
timeout 120 env CM_EXPECT_CHECKS=4 CM_CODE=CMDBGOFF CM_EXPECT=off CM_PRESET_CHAR=10 "$MGBA" --script tools/mgba_scripts/cm_ui_activate.lua \
    -t tools/savestates/naming_open.ss "$ROM" > /tmp/sg_ui_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_ui_off.log && echo "  PASS deactivation (CMDBGOFF)" \
    || { echo "  FAIL deactivation (see /tmp/sg_ui_off.log)"; exit 1; }

echo
echo "=== Layer 4g: in-situ trade gate (idx2 SEASOR/Horsea, real overlay wrapper) ==="
python3 tools/tests/build_trade_testrom.py 2 > /tmp/sg_trade_build.log 2>&1 \
    || { echo "  FAIL building trade test ROM (see /tmp/sg_trade_build.log)"; exit 1; }
TRADEROM=build/seaglass_cm_tradetest.gba
# CM_TradeCheck's VAR_RESULT store moves with every shim rebuild -- derive it.
CM_TRADECHECK_STORE=$(python3 tools/tests/find_shim_store.py) || {
    echo "  FAIL locating CM_TradeCheck's store instruction"; exit 1; }
export CM_TRADECHECK_STORE
echo "  (CM_TradeCheck store @ $CM_TRADECHECK_STORE)"
trade_case() {  # name  CM_ON  CM_CHAR  EXPECT  EXPECTED_CHECKS
    log=/tmp/sg_trade_$1.log
    timeout 150 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=$5 CM_ON=$2 CM_CHAR=$3 EXPECT=$4 "$MGBA" \
        --script tools/mgba_scripts/cm_trade_test.lua \
        -t tools/savestates/mart_inside.ss "$TRADEROM" > "$log" 2>&1 || true
    grep -q "HARNESS RESULT: PASS" "$log" && echo "  PASS trade $1" \
        || { echo "  FAIL trade $1 (see $log)"; grep -a "HARNESS.*FAIL" "$log"; exit 1; }
}
trade_case RED   1 1  0 3  # Horsea OFF Red's roster   -> refuse
trade_case MISTY 1 10 1 2  # Horsea ON  Misty's roster -> allow (discrimination)
trade_case CTRL  0 1  1 2  # CM off                    -> allow (control)

echo
echo "=== Layer 5a: wild-encounter override inert with CM off ==="
timeout 60 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=3 CM_ON=0 "$MGBA" --script tools/mgba_scripts/cm_wild_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_wild_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_wild_off.log && echo "  PASS wild override inert (CM off)" \
    || { echo "  FAIL wild override inert (see /tmp/sg_wild_off.log)"; exit 1; }

echo
echo "=== Layer 5b: wild-encounter stage-fit (forced high level -> evolved stage, char 1 Red) ==="
python3 tools/tests/verify_wild_override.py > /tmp/sg_wild_stage.log 2>&1
grep -q "RESULT: PASS" /tmp/sg_wild_stage.log && echo "  PASS wild stage-fit + rate + legendary exclusion" \
    || { echo "  FAIL wild stage-fit (see /tmp/sg_wild_stage.log)"; cat /tmp/sg_wild_stage.log; exit 1; }

echo
# Layer 5b proves the pool is read correctly for char 1 -- and char 1 CANNOT
# fail: its record starts at byte 0, so it reads correctly under any stride.
# This second run is the one that actually exercises the (charId-1)*STRIDE
# arithmetic. Glacia is one of only 13 characters whose pool is disjoint from
# what the shipped 104-stride bug read, so a misaligned slice shows up as a
# species that is simply not hers. See verify_wild_override.py's CHAR_ID note.
echo "=== Layer 5b2: wild-encounter pool indexing (char 45 Glacia -- NON-first character) ==="
CM_WILD_CHAR=45 python3 tools/tests/verify_wild_override.py > /tmp/sg_wild_stage45.log 2>&1
grep -q "RESULT: PASS" /tmp/sg_wild_stage45.log && echo "  PASS wild pool indexing (char 45 reads its OWN pool)" \
    || { echo "  FAIL wild pool indexing char 45 (see /tmp/sg_wild_stage45.log)"; cat /tmp/sg_wild_stage45.log; exit 1; }

echo
# The POSITIVE assertion the legendary spec demands. Every other wild assertion
# here is "no legendary appeared", which a completely dead feature satisfies just
# as well as a correct one. This proves the roll fires, at 1%, and -- the trap
# unique to Seaglass, which derives both decisions from one wildSeed() -- that a
# legendary hit is NOT nested inside the ordinary 10% override.
echo "=== Layer 5d: 1% legendary roll fires, at rate, independently (exhaustive) ==="
python3 tools/tests/verify_legendary_roll.py > /tmp/sg_legendary.log 2>&1
grep -q "RESULT: PASS" /tmp/sg_legendary.log && echo "  PASS legendary roll fires + rate + independence" \
    || { echo "  FAIL legendary roll (see /tmp/sg_legendary.log)"; cat /tmp/sg_legendary.log; exit 1; }

echo
# Layer 5d proves the arithmetic offline. These two prove the SHIPPED SHIM does
# it, in the running ROM. They are a differential pair on one forced roll --
# identical inputs, differing only in the caught flag -- because either half
# alone is the weak assertion the spec warns about.
# 🔴 2026-08-20: these two layers were DEAD from the day they were written.
# They set breakpoints on the wild trampoline, and mGBA's headless build only
# honours setBreakpoint when MGBA_HEADLESS_DEBUGGER=1 is in the environment --
# which every other breakpoint-using layer here sets and these two did not.
# Their breakpoints never fired, so "the encounter happened" was false and the
# shim was never observed. 5e2 then reported PASS on
# "already-caught legendary NOT offered (got nil)" -- nil because NOTHING
# RAN. That is exactly the weak assertion legendary_encounters.md warns about:
# a suppression check that a completely dead feature also satisfies. With the
# variable set, the pair is a real differential: uncaught -> 145 (Zapdos),
# already-caught -> 172 (an ordinary roster mon).
echo "=== Layer 5e: legendary OFFERED when uncaught (char 3 Blue -> Zapdos, live) ==="
timeout 200 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=3 CM_CHAR=3 EXPECT_SPECIES=145 "$MGBA" --script tools/mgba_scripts/cm_legendary_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_leg_on.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_leg_on.log && echo "  PASS legendary offered when uncaught" \
    || { echo "  FAIL legendary not offered (see /tmp/sg_leg_on.log)"; exit 1; }

echo
echo "=== Layer 5e2: same roll, already caught -> legendary WITHHELD ==="
timeout 200 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=3 CM_CHAR=3 EXPECT_SPECIES=145 CM_EXPECT=caught "$MGBA" --script tools/mgba_scripts/cm_legendary_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_leg_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_leg_off.log && echo "  PASS caught legendary withheld" \
    || { echo "  FAIL caught legendary still offered (see /tmp/sg_leg_off.log)"; exit 1; }

echo
# The encounter marker (../game_plans/rowe_parity.md §3). All three runs force
# the rolled species at the wild trampoline so the marker's precondition is
# deterministic rather than waiting on a 10% override.
#
# 6b is the control that matters, and it is a DIFFERENT CHARACTER, not merely
# "mode off": a shim that ignored charId and always returned the first
# character's string would pass 6a and 6c and only fail here. This repo has
# been bitten by exactly that before -- its wild-pool test could not see a
# broken stride because it only ever ran character 1.
echo "=== Layer 6a: encounter marker names the character (char 1 Red) ==="
timeout 250 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=3 CM_CHAR=1 \
    CM_FORCE_SPECIES=1 CM_EXPECT_NAME=RED "$MGBA" \
    --script tools/mgba_scripts/cm_marker_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_marker_red.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_marker_red.log && echo "  PASS marker names RED" \
    || { echo "  FAIL marker (see /tmp/sg_marker_red.log)"; exit 1; }

echo
echo "=== Layer 6b: marker indexes by character (char 10 Misty, NOT Red) ==="
timeout 250 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=3 CM_CHAR=10 \
    CM_FORCE_SPECIES=116 CM_EXPECT_NAME=MISTY "$MGBA" \
    --script tools/mgba_scripts/cm_marker_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_marker_misty.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_marker_misty.log && echo "  PASS marker names MISTY" \
    || { echo "  FAIL marker indexing (see /tmp/sg_marker_misty.log)"; exit 1; }

echo
echo "=== Layer 6c: marker inert with CM off (vanilla intro) ==="
timeout 250 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=3 CM_ON=0 \
    CM_FORCE_SPECIES=1 CM_EXPECT_NAME= "$MGBA" \
    --script tools/mgba_scripts/cm_marker_test.lua \
    -t tools/savestates/at_8_8.ss "$ROM" > /tmp/sg_marker_off.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_marker_off.log && echo "  PASS marker inert with CM off" \
    || { echo "  FAIL marker inert (see /tmp/sg_marker_off.log)"; exit 1; }

echo
echo "=== Layer 5c: wild-encounter choke-point proof (BL 0x0822BF36 is the sole land-path caller) ==="
# Proves, on a REACHABLE land encounter, that the exact BL we retarget is
# executed and is the ONLY caller of CreateMonWithIVs for the wild mon --
# so the surf/rock-smash/fishing coverage rests on "same proven choke point"
# (+ the ROM-wide single-caller BL-scan in verify_artifacts.py), not static
# analysis alone. See docs/ROUTINE_MAP.md's wild-encounter coverage note.
timeout 60 env MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=4 "$MGBA" --script tools/mgba_scripts/prove_wild_chokepoint.lua \
    -t tools/savestates/at_8_8.ss "rom/seaglass v3.0.gba" > /tmp/sg_wild_choke.log 2>&1 || true
grep -q "HARNESS RESULT: PASS" /tmp/sg_wild_choke.log && echo "  PASS choke point empirically proven (land path)" \
    || { echo "  FAIL choke-point proof (see /tmp/sg_wild_choke.log)"; grep -a "HARNESS" /tmp/sg_wild_choke.log; exit 1; }

echo
echo "ALL AUTOMATED LAYERS GREEN (incl. real-UI activation + in-situ trade e2e + wild override)."
echo "Remaining human-in-the-loop verify: full playthrough (docs/TESTING.md)."
