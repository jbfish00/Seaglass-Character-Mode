-- LIVE layer: the party-wide Exp. Share for EVERY new game, Character Mode on
-- or off (user ruling 2026-10-21; src/character_mode.c CM_NewGameExpShare,
-- hooked at NewGameInitData's last BL 0x08176F50, built 2026-10-24).
--
-- Cold boot with no save, A-mash the whole real intro (Birch speech, naming,
-- truck) exactly as drive_intro.lua does. Character Mode is never turned on.
-- Then:
--   EXPECT=granted (shipped build)              -> flag 0x20 set, item 461 in a pocket
--   EXPECT=none    (CM_NO_NEWGAME_EXPSHARE=1)   -> neither (the discriminating control)
-- Both runs also assert that NewGameInitData's hooked call ran exactly once
-- (breakpoint on the BL site, which exists in both builds) and that Character
-- Mode stayed off, so a "none" can't come from an intro that never got there.
--
-- Run (needs MGBA_HEADLESS_DEBUGGER=1 for the breakpoint):
--   MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=4 EXPECT=granted \
--     ./tools/mgba_src/build/mgba-headless --script tools/mgba_scripts/cm_newgame_expshare_test.lua \
--     build/seaglass_cm.gba > /tmp/sg_ng.log 2>&1

local H = dofile("tools/mgba_scripts/harness.lua")

local want      = os.getenv("EXPECT") or "granted"     -- granted | none
local shot      = os.getenv("SHOT") or "tools/savestates/newgame_expshare.png"
local END_FRAME = 9000
local ngRan     = 0

H.breakpoint("NewGameInitData last call", 0x08176F50, function() ngRan = ngRan + 1 end)
H.mash(H.KEY.A, 30, END_FRAME, 24)

H.onFrame(function(f)
    if f ~= END_FRAME + 60 then return end
    emu:screenshot(shot)
    local has = false
    for p = 0, 7 do
        local slots, cap = H.rd32(H.BAG_POCKETS + 8 * p), H.rd8(H.BAG_POCKETS + 8 * p + 4)
        if slots >= 0x02000000 and slots < 0x02040000 then
            for i = 0, cap - 1 do
                if H.rd16(slots + 4 * i) == 461 then has = true; H.log("Exp. Share in pocket " .. p) end
            end
        end
    end
    H.assertEq("NewGameInitData's hooked call ran once (the intro reached the new game)", ngRan, 1)
    H.assertEq("Character Mode never turned on (flag 0x2B0)", H.getFlag(0x2B0), 0)
    if want == "granted" then
        H.assertEq("party-wide Exp. Share switched on (flag 0x20)", H.getFlag(0x20), 1)
        H.assertTrue("an Exp. Share is in the bag (item 461)", has)
    else
        H.assertEq("no hook: flag 0x20 stays off", H.getFlag(0x20), 0)
        H.assertTrue("no hook: no Exp. Share in the bag", not has)
    end
    H.finish()
end)
