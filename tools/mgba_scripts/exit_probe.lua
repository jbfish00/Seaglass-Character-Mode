-- Find the mart exit + confirm the (14,6) warp. Press DOWN from start and log
-- map. Then from start, step around and log map/pos transitions.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pmap()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1+H.SB1_POS_X), emu:read16(sb1+H.SB1_POS_Y),
           emu:read8(sb1+H.SB1_MAPGRP), emu:read8(sb1+H.SB1_MAPNUM)
end
local last=nil
H.onFrame(function(f)
    local x,y,g,n = pmap()
    local cur=("%d,%d %d.%d"):format(x,y,g,n)
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if f==20 then H.press(K.DOWN,12,8) end
    if f==80 then emu:screenshot("tools/savestates/exit_down.png") end
    if f==120 then H.finish() end
end)
