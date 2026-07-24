-- Re-capture naming_open.ss on the current build. Position-reactive walk to the
-- mart clipboard (LEFT till x stalls, UP till y stalls, an A-up probe, face LEFT,
-- A for the "Enter a Character Mode code?" prompt, A for YES) -> CM_OpenCodeEntry.
-- When that breakpoint fires, save naming_open.ss ~90 frames later (screen faded
-- in). The old fixed LEFT x3/UP x2 cadence was stale and frequently NEVER FIRED
-- (2026-07-23) -- this mirrors the proven route in cm_trade_test.lua verbatim.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local function pos()
    local s = emu:read32(0x030051B8)
    return emu:read16(s), emu:read16(s + 2)
end

local fireAt = nil
H.breakpoint("Open", 0x08ED2270, function(fr)
    if not fireAt then fireAt = fr; H.log("CM_OpenCodeEntry fired f=" .. fr) end
end)

-- position-reactive navigate to the clipboard, then interact (prompt + YES).
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
H.onFrame(function(f)
    if fireAt or f < nextAt then return end
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
        H.press(K.LEFT, 8); phase = "prompt"; nextAt = f + 30
    elseif phase == "prompt" then
        H.log(("interact at (%d,%d)"):format(x, y)); H.press(K.A, 6)
        phase = "yes"; nextAt = f + 60
    elseif phase == "yes" then
        H.press(K.A, 6); phase = "done"; nextAt = f + 100000
    end
end)

H.onFrame(function(f)
    if fireAt and f == fireAt + 90 then
        emu:screenshot("tools/savestates/naming_open.png")
        emu:saveStateFile("tools/savestates/naming_open.ss")
        H.log("saved naming_open.ss")
        H.finish()
    end
    if f == 1200 and not fireAt then
        H.log("NEVER FIRED"); emu:screenshot("tools/savestates/cap_fail.png"); H.finish()
    end
end)
