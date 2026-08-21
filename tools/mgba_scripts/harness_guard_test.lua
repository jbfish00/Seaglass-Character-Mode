-- Negative test for H.finish()'s two anti-vacuity guards.
--
-- Why this file exists: until 2026-08-20 H.finish() emitted RESULT: PASS
-- whenever #failures == 0, with the pass count printed and never tested, so a
-- layer that asserted nothing reported green and every runner here believed it
-- (../game_plans/rowe_parity.md §1). The guards that close that hole are only
-- worth anything if they can be shown to FAIL, so this fixture drives them on
-- purpose. Run it via tools/tests/harness_guard_test.sh.
--
--   CM_NEG=vacuous -> assert nothing.        Expect RESULT: FAIL.
--   CM_NEG=three   -> assert exactly 3.      Expect PASS, or FAIL under a
--                                            mismatched CM_EXPECT_CHECKS.
local H = dofile("tools/mgba_scripts/harness.lua")
if (os.getenv("CM_NEG") or "vacuous") == "three" then
    H.assertEq("one", 1, 1)
    H.assertEq("two", 2, 2)
    H.assertEq("three", 3, 3)
end
H.finish()
