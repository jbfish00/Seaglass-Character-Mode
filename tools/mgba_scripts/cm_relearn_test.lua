-- LIVE relearner layer (QoL 2026-10-17) on build/seaglass_cm_reltest[_ctl].gba (tools/tests/build_relearn_testrom.py).
-- From mart_inside.ss drive to the clipboard (cm_egg_hatch_test.lua's route), whose test entry runs the real
-- special ChooseMonForMoveRelearner; press A on the lead. VAR_0x8005 then holds the relearnable-move count the game
-- computed. Logged as "RELEARN count=N"; the runner requires the shipped count > the control's.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local V8005 = tonumber(os.getenv("VAR_8005") or "0x020055E2")
local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
H.onFrame(function(f)
    if f == 8 then emu:write16(V8005, 0xBEEF) end         -- sentinel: the special must overwrite it
    if phase == "done" or f < nextAt then return end
    local x, y = pos()
    if phase == "left" then
        stall = (x == lastx) and stall + 1 or 0
        if stall >= 2 then phase, stall, lasty = "up", 0, -1; nextAt = f + 6; return end
        lastx = x; H.press(K.LEFT, 10, 2); nextAt = f + 20
    elseif phase == "up" then
        stall = (y == lasty) and stall + 1 or 0
        if stall >= 2 then phase = "Aup"; nextAt = f + 6; return end
        lasty = y; H.press(K.UP, 10, 2); nextAt = f + 20
    elseif phase == "Aup" then
        H.press(K.A, 6); phase = "faceL"; nextAt = f + 80
    elseif phase == "faceL" then
        H.press(K.LEFT, 8); phase = "talk"; nextAt = f + 30
    elseif phase == "talk" then
        H.press(K.A, 6); phase = "done"; nextAt = f + 30
    end
end)
local doneAt, pickAt = nil, nil
H.onFrame(function(f)
    if phase ~= "done" then return end
    doneAt = doneAt or f
    if f == doneAt + 120 then H.press(K.A, 6) end           -- pick the lead in the party menu
    if f == doneAt + 400 then
        emu:screenshot("tools/savestates/relearn_" .. (os.getenv("TAG") or "x") .. ".png")
        local n = emu:read16(V8005)
        H.log("RELEARN count=" .. n)
        H.assertTrue("ChooseMonForMoveRelearner wrote VAR_0x8005 (sentinel replaced)", n ~= 0xBEEF)
        if os.getenv("WANT") == "zero" then     -- control: the starter knows every level-up move it has reached
            H.assertEq("vanilla relearnable count (no egg moves)", n, 0)
        else
            H.assertTrue("the lead has relearnable moves (its egg moves)", n > 0 and n <= 24)
        end
        H.finish()
    end
end)
