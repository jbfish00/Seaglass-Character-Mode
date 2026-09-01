#!/bin/bash
# Proves cm_tally.assert_tally's two anti-vacuity guards actually fail.
#
# rowe_parity.md §1 hardened the LUA harness against a layer that asserts
# nothing, and §9 Finding 2 measured that the python/GDB layers -- which are
# most of the layers here -- still printed a tally nobody checked. This is the
# negative test for the guard that closed that.
#
# A guard nobody has broken on purpose is not a guard. Two halves:
#
#   1. the guard function itself, driven directly through all three branches
#   2. the real static checkers, run with a drifted CM_EXPECT_CHECKS, so the
#      wiring is proven and not just the helper
#
# The controls are the cases that matter. Without them a guard that failed
# EVERYTHING would pass every negative case and look correct.
set -u
cd "$(dirname "$0")/../.." || exit 1
fail=0
pass=0

unit() { # <label> <ran> <expect> <want-exit>
    local label=$1 ran=$2 expect=$3 want=$4 got
    CM_EXPECT_CHECKS="$expect" python3 -c '
import sys, os
sys.path.insert(0, "tools/tests")
from cm_tally import assert_tally
sys.exit(assert_tally(int(sys.argv[1]), int(sys.argv[1]), "unit"))
' "$ran" >/dev/null 2>&1
    got=$?
    if [ "$got" = "$want" ]; then printf '  ok    %-46s exit=%s\n' "$label" "$got"; pass=$((pass+1))
    else printf '  FAIL  %-46s got %s want %s\n' "$label" "$got" "$want"; fail=1; fi
}

layer() { # <label> <script> <CM_EXPECT_CHECKS or ""> <want-exit>
    local label=$1 script=$2 expect=$3 want=$4 got
    [ -f "$script" ] || { printf '  skip  %-46s (absent)\n' "$label"; return; }
    if [ -n "$expect" ]; then
        CM_EXPECT_CHECKS="$expect" timeout 1800 python3 "$script" >/dev/null 2>&1
    else
        timeout 1800 python3 "$script" >/dev/null 2>&1
    fi
    got=$?
    if [ "$got" = "$want" ]; then printf '  ok    %-46s exit=%s\n' "$label" "$got"; pass=$((pass+1))
    else printf '  FAIL  %-46s got %s want %s\n' "$label" "$got" "$want"; fail=1; fi
}

echo "checker guard negative test"
echo "-- the guard function itself --"
unit "zero checks is never a pass"        0  0   1
unit "matching tally passes (control)"    7  7   0
unit "a large matching tally passes"    128 128  0

# drift: ran != expect. Driven through the env override so the literal in each
# layer stays untouched.
CM_EXPECT_CHECKS=99999 python3 -c '
import sys; sys.path.insert(0, "tools/tests")
from cm_tally import assert_tally
sys.exit(assert_tally(7, 7, "unit"))' >/dev/null 2>&1
if [ $? -eq 1 ]; then echo "  ok    drifted tally fails                          exit=1"; pass=$((pass+1))
else echo "  FAIL  drifted tally did not fail"; fail=1; fi

echo "-- the real static layers, wired --"
layer "verify_artifacts: control"      tools/tests/verify_artifacts.py ""      0
layer "verify_artifacts: drift fails"  tools/tests/verify_artifacts.py 99999   1

[ $fail -eq 0 ] && echo "checker guard test: $pass/$pass PASS" \
                || echo "checker guard test: FAILURES"
exit $fail
