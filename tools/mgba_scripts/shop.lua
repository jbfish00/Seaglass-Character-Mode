-- Systematic clerk sweep from shop.ss (~2,5): try A facing UP from x=1,2,3 and
-- A facing LEFT/RIGHT beside the counter; screenshot each. Look for a shop/menu.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
local function pos() local b=emu:read32(SB1_PTR); return emu:read16(b),emu:read16(b+2) end
-- go to left wall first
H.onFrame(function(f)
    -- attempt 1: current tile, face up
    if f==60 then H.press(K.UP,6,20) end
    if f==120 then H.press(K.A,12,30) end
    if f==300 then emu:screenshot("tools/savestates/a1.png"); H.press(K.B,6,20) end
    -- move LEFT, face up
    if f==400 then H.press(K.LEFT,16,8) end
    if f==500 then H.press(K.UP,6,20) end
    if f==560 then H.press(K.A,12,30) end
    if f==740 then emu:screenshot("tools/savestates/a2.png"); local x,y=pos(); H.log("a2 "..x..","..y); H.press(K.B,6,20) end
    -- move up if possible (onto counter front), face up
    if f==840 then H.press(K.UP,16,8) end
    if f==940 then H.press(K.A,12,30) end
    if f==1120 then emu:screenshot("tools/savestates/a3.png"); local x,y=pos(); H.log("a3 "..x..","..y); H.press(K.B,6,20) end
    -- face right, A
    if f==1220 then H.press(K.RIGHT,6,20) end
    if f==1280 then H.press(K.A,12,30) end
    if f==1460 then emu:screenshot("tools/savestates/a4.png"); H.finish() end
end)
