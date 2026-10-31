-- Live layer: START > "EXP RATE" (QoL, user 2026-10-29). From route101.ss (on Route 101):
-- START, UP (the cursor wraps to the bottom row), A opens the chooser over the field (x0.5 / x1 / x1.5 / x2 / x3, the
-- current rate preselected); then KEYS ("D" down, "U" up, "B" cancel, "A" choose) and the var is checked.
--   KEYS=DDA -> 2 (x2), KEYS=UA -> 4 (x0.5), KEYS=B -> unchanged (0)
-- Also: the normal menu ends with action 16, the chooser opened without fading the screen to black, and START
-- works again afterwards (the script released the player).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local VAR_EXP_RATE = 0x407C
local ACTIONS, COUNT = 0x0201D334, 0x0201D330      -- sCurrentStartMenuActions, sNumStartMenuActions
local KEYS = os.getenv("KEYS") or "DDA"
local WANT = tonumber(os.getenv("WANT") or "2")
local SHOT = os.getenv("CM_SHOT")
local lastAction, plttSum, plttBase = -1, -1, -1

local function screenSum()      -- gPlttBufferFaded is not needed: the BG palette RAM itself
    local s = 0
    for i = 0, 0x1FE, 2 do s = s + emu:read16(0x05000000 + i) end
    return s
end

H.onFrame(function(f)
    if f == 5 then H.setVar(VAR_EXP_RATE, 0) end
    if f == 15 then plttBase = screenSum() end
    if f == 20 then H.press(K.START, 6) end
    if f == 70 then
        lastAction = emu:read8(ACTIONS + emu:read8(COUNT) - 1)
        H.press(K.UP, 6)
    end
    if f == 100 then H.press(K.A, 6) end
    if f == 190 then
        plttSum = screenSum()
        if SHOT then emu:screenshot(SHOT) end
    end
    for i = 1, #KEYS do
        if f == 200 + 30 * i then
            local c = KEYS:sub(i, i)
            H.press(c == "D" and K.DOWN or c == "U" and K.UP or c == "B" and K.B or K.A, 6)
        end
    end
    if f == 395 then emu:write8(COUNT, 0) end          -- so only a rebuilt menu passes the last check
    if f == 400 then H.press(K.START, 6) end
    if f == 450 then
        H.log(("last START action %d, palette sum %d of %d, rate %d, menu rows %d"):format(lastAction, plttSum, plttBase,
            H.getVar(VAR_EXP_RATE), emu:read8(COUNT)))
        H.assertEq("the normal START menu ends with the Exp. Rate row (action 16)", lastAction, 16)
        H.assertTrue("the chooser opened over the field (palettes not faded: at least 90% of the field's)",
            plttSum * 10 >= plttBase * 9)
        H.assertEq("rate after " .. KEYS, H.getVar(VAR_EXP_RATE), WANT)
        H.assertTrue("START opens again afterwards (player released, menu rebuilt)",
            emu:read8(COUNT) > 0 and emu:read8(ACTIONS + emu:read8(COUNT) - 1) == 16)
        H.finish()
    end
end)
