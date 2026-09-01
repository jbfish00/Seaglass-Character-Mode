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
