#!/bin/bash
# LIVE overworld-sprite layer (2026-10-03, ../game_plans/overworld_sprites.md).
#
# From naming_open.ss, each run types a real code at the CODE screen; the
# shipped activation script's callnative sweeps the party and then refreshes the
# player's sprite (src/ow_sprite.c). tools/mgba_scripts/cm_ow_sprite_test.lua
# then reads the player out of OBJ VRAM and palette RAM against the SOURCE art
# (tools/tests/ow_sprite_env.py), leaves the Oldale Mart (no running indoors)
# and walks and runs in all four directions.
#
#   MISTY  16x32 sheet whose run frames are its walk frames (most are)
#   KRIS   16x32 sheet with real run frames
#   LUCAS  32x32 sheet with real run frames (sideways running is the case that
#          showed RR a running player's back)
#   MAY    Seaglass's own May sprite on a male player (images table asserted)
#   ZZZ    refused code: the player stays stock
# and a NEGATIVE CONTROL: a copy with GetObjectEventGraphicsInfo's entry put
# back, typing MISTY, which must FAIL.
set -u
[ -z "${BASH_VERSION:-}" ] && exec bash "$0" "$@"
cd "$(dirname "$0")/../.." || exit 1
MGBA="${MGBA_HEADLESS:-tools/mgba_src/build/mgba-headless}"
ROM=build/seaglass_cm.gba
NEG=build/seaglass_cm_ow_neg.gba
SS=tools/savestates/naming_open.ss
[ -x "$MGBA" ] || { echo "no headless mGBA at $MGBA"; exit 2; }
[ -f "$ROM" ] && [ -f "$SS" ] || { echo "build first (and have $SS)"; exit 1; }

python3 - <<'PY' || exit 1
import sys
sys.path.insert(0, "tools/character_mode")
import seaglass_ow_player as owp
d = bytearray(open("build/seaglass_cm.gba", "rb").read())
o = owp.R(owp.GET_INFO)
assert d[o:o + 8] != owp.GET_INFO_ORIG, "shipped build has no trampoline"
d[o:o + 8] = owp.GET_INFO_ORIG
open("build/seaglass_cm_ow_neg.gba", "wb").write(bytes(d))
PY

fail=0
run() {  # label name code expect checks rom want
    eval "$(python3 tools/tests/ow_sprite_env.py "$2")" || { echo "  FAIL env $2"; fail=1; return; }
    local log=/tmp/sg_ow_$1.log
    CM_CODE=$3 CM_EXPECT=$4 CM_EXPECT_CHECKS=$5 CM_SHOTS=/tmp/sg_ow_$1 timeout 240 "$MGBA" \
        --script tools/mgba_scripts/cm_ow_sprite_test.lua -t "$SS" "$6" > "$log" 2>&1
    if grep -aq "HARNESS RESULT: $7" "$log"; then echo "  PASS overworld sprite $1 (want $7)"
    else echo "  FAIL overworld sprite $1 (want $7, see $log)"; grep -a "HARNESS FAIL" "$log" | head -4; fail=1; fi
}
run misty Misty MISTY on 12 "$ROM" PASS
run kris  Kris  KRIS  on 12 "$ROM" PASS
run lucas Lucas LUCAS on 12 "$ROM" PASS
run may   May   MAY   on 3  "$ROM" PASS
run off   Misty ZZZ   off 3 "$ROM" PASS
run NEGATIVE_CONTROL_no_hook Misty MISTY on 12 "$NEG" FAIL
exit $fail
