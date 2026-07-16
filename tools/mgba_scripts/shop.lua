-- Try each direction: face LEFT+A, then UP+A, then move up a tile and UP+A.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
H.onFrame(function(f)
    if f==60  then H.press(K.LEFT,6,20) end
    if f==120 then H.press(K.A,12,30) end
    if f==350 then emu:screenshot("tools/savestates/s_left.png") end
    if f==400 then H.press(K.B,6,20) end     -- close if opened something
    if f==500 then H.press(K.UP,16,8) end    -- try to step up
    if f==600 then H.press(K.UP,6,20); local b=emu:read32(SB1_PTR); H.log(string.format("pos %d,%d",emu:read16(b),emu:read16(b+2))) end
    if f==660 then H.press(K.A,12,30) end
    if f==900 then emu:screenshot("tools/savestates/s_up.png") end
    if f==1000 then H.finish() end
end)
