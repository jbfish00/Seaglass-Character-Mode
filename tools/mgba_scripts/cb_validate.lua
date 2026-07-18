-- Validate the callback2 detector: opening the Bag is a separate screen and
-- MUST move gMain.callback2 off the field value. Log cb2 changes; screenshot.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local CB2 = 0x030014B8
local last=nil
H.onFrame(function(f)
    local cb = emu:read32(CB2)
    if cb~=last then H.log(("f=%d cb2=0x%08X"):format(f,cb)); last=cb end
    if f==30 then H.press(K.START,8,10) end     -- open start menu
    if f==90 then emu:screenshot("tools/savestates/cv_menu.png") end
    -- mash A/DOWN to try to open BAG (menu order unknown)
    if f==110 then H.press(K.DOWN,6,8) end
    if f==140 then H.press(K.A,6,8) end
    if f==190 then emu:screenshot("tools/savestates/cv_a1.png") end
    if f==210 then H.press(K.DOWN,6,8) end
    if f==240 then H.press(K.A,6,8) end
    if f==300 then emu:screenshot("tools/savestates/cv_a2.png") end
    if f==340 then H.finish() end
end)
