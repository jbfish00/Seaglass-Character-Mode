"""The anti-vacuity guard every python/GDB test layer in this repo shares.

rowe_parity.md §1 closed this hole in the Lua harness: `H.finish()` printed
`PASSED %d` and asserted nothing, so a layer that ran ZERO assertions reported
green.  §9 Finding 2 then measured that the fix was **Lua-only**, and that the
python layers -- which are most of the layers in this repo -- still printed a
tally nobody checked.  This is that fix, for those.

Two failures are caught here, and they are different:

  * **ran nothing.**  A checker that executed no checks prints a line
    indistinguishable from one that executed all of them.  Zero is never a
    pass.

  * **ran a different number than it says.**  A check that silently stops
    firing reduces what the layer proves without changing its exit status.
    This is not hypothetical in this workspace: `wild_encounter_shim_test.py`
    printed "21/21 checks passed" while running 20, in both of its modes, for
    as long as its hand-written total existed.

⚠️ The expected count must be a **literal**, never an expression recomputed
from the same data the checks iterate (`total = len(cases) + len(marker_cases)
+ 7`).  Such a total drifts in lockstep with whatever it is meant to be
pinning, so it cannot fail -- it is a restatement, not a check.  A literal has
to be bumped deliberately, in the commit that changes the checks, which is
exactly the moment a human should be looking at it.

`CM_EXPECT_CHECKS` overrides the literal, so a runner can pin the count from
outside and so `checker_guard_test.sh` can break the guard on purpose.
"""
import os


def assert_tally(ran, expect_default, label):
    """0 if the tally is sound, 1 if it is not. Prints the reason."""
    expect = int(os.environ.get("CM_EXPECT_CHECKS", expect_default))
    if ran == 0:
        print("%s: NO CHECKS RAN -- that is a failure, not a pass. A layer "
              "that asserts nothing is not evidence." % label)
        return 1
    if ran != expect:
        print("%s: ran %d checks, expected %d. Either a check stopped running "
              "(silently reducing what this layer proves) or a check was "
              "added and the EXPECT_CHECKS literal was not bumped with it."
              % (label, ran, expect))
        return 1
    return 0


def assert_cases(ran, expect_default, label):
    """The same guard, for a NEGATIVE TEST's own case list. 0 if sound, else 1.

    ⭐ WHY A SECOND FUNCTION. The negative tests guard the checkers, and until
    2026-09-17 NOTHING guarded the negative tests -- 28 of them across the four
    repos, none with an expected-case count. Measured in Radical Red: deleting
    3 of 7 tamper cases from check_repo_selfcontained_negative_test.py took it
    from "8/8 ALL PASS" to "5/5 ALL PASS", exit 0. Every one of these files
    prints a tally it computes from what it actually ran -- several literally as
    `"%d/%d" % (passes, passes)` -- so the tally agrees with itself by
    construction and can never report a shrunken case list. That is §13.36's
    defect ("the tally was not wrong; it was measuring eight of nine and saying
    so") and §1's anti-vacuity hole, one level up: the thing that proves the
    checker can fail could itself quietly stop proving it.

    ⚠️ It reads CM_EXPECT_CASES, deliberately NOT CM_EXPECT_CHECKS. These files
    invoke the checkers as SUBPROCESSES and the environment is inherited, so
    reusing the checkers' variable would pin the parent and the child to the
    same number and break every run under the guard test.
    """
    expect = int(os.environ.get("CM_EXPECT_CASES", expect_default))
    if ran == 0:
        print("%s: NO CASES RAN -- a negative test that tampers with nothing "
              "proves nothing about the checker it is meant to guard." % label)
        return 1
    if ran != expect:
        print("%s: ran %d cases, expected %d. Either a tamper case stopped "
              "running (so the checker is no longer proven to catch it) or a "
              "case was added and the EXPECT_CASES literal was not bumped."
              % (label, ran, expect))
        return 1
    return 0
