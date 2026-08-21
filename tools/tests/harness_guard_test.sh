#!/bin/bash
# Proves H.finish()'s two anti-vacuity guards actually fail (rowe_parity.md §1).
#
# A guard nobody has broken on purpose is not a guard. This drives all four
# cases and asserts the RESULT line each one must produce:
#
#   1. zero assertions, no expectation   -> FAIL  (the hole this closes)
#   2. three assertions, no expectation  -> PASS  (control: guards stay quiet)
#   3. three assertions, CM_EXPECT_CHECKS=3 -> PASS
#   4. three assertions, CM_EXPECT_CHECKS=5 -> FAIL (tally drift is caught)
#
# Case 2 is the control that matters: without it, a guard that failed
# EVERYTHING would also pass cases 1 and 4 and look correct.
set -u
cd "$(dirname "$0")/../.." || exit 1
MGBA="${MGBA:-../Seaglass-Character-Mode/tools/mgba_src/build/mgba-headless}"
ROM="${ROM:-rom/seaglass v3.0.gba}"
[ -x "$MGBA" ] || { echo "SKIP: mgba-headless not found at $MGBA"; exit 0; }
[ -f "$ROM" ]  || { echo "SKIP: ROM not found: $ROM"; exit 0; }

fail=0
check() { # <label> <want> <CM_NEG> <CM_EXPECT_CHECKS>
    local label=$1 want=$2 neg=$3 exp=$4 log got
    log=$(mktemp)
    CM_NEG="$neg" CM_EXPECT_CHECKS="$exp" timeout 60 "$MGBA" \
        --script tools/mgba_scripts/harness_guard_test.lua "$ROM" > "$log" 2>&1
    got=$(grep -oE 'RESULT: (PASS|FAIL)' "$log" | tail -1)
    if [ "$got" = "RESULT: $want" ]; then
        printf '  ok    %-38s %s\n' "$label" "$got"
    else
        printf '  FAIL  %-38s got %s, want RESULT: %s\n' "$label" "${got:-<none>}" "$want"
        fail=1
    fi
    rm -f "$log"
}
echo "harness guard negative test"
check "zero assertions is not a pass"      FAIL vacuous ""
check "control: three assertions pass"     PASS three   ""
check "matching tally passes"              PASS three   3
check "drifted tally fails"                FAIL three   5
[ $fail -eq 0 ] && echo "harness guard test: 4/4 PASS" || echo "harness guard test: FAILURES"
exit $fail
