-- From mart_inside.ss: try left-first then up to reach the upper-left wall
-- board (clipboard), press A, screenshot to catch our injected prompt.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end
H.onFrame(function(f)
    if f == 20 then local x,y=pos(); H.log(("start (%d,%d)"):format(x,y)) end
    if f == 420 then local x,y=pos(); H.log(("mid (%d,%d)"):format(x,y))
        emu:screenshot("tools/savestates/clip_pos.png") end
    if f == 520 then emu:screenshot("tools/savestates/clip_A.png"); H.log("shotA") end
end)
for _ = 1, 3 do H.press(K.LEFT, 8, 6) end
for _ = 1, 6 do H.press(K.UP, 8, 6) end
-- at f~=430 (after ~280 frames of movement) queue is drained; interact
H.onFrame(function(f) if f == 460 then H.press(K.A, 6) end end)
