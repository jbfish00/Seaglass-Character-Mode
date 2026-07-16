-- From bag_open.ss (battle bag, ITEMS pocket): flip through pockets with RIGHT,
-- screenshotting each, to inventory what we own (looking for Poke Balls).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
H.onFrame(function(f)
    if f==100 or f==300 or f==500 or f==700 then H.press(K.RIGHT, 12, 30) end
    if f==200 then emu:screenshot("tools/savestates/pk1.png") end
    if f==400 then emu:screenshot("tools/savestates/pk2.png") end
    if f==600 then emu:screenshot("tools/savestates/pk3.png") end
    if f==800 then emu:screenshot("tools/savestates/pk4.png") end
    if f==850 then H.log("done"); H.finish() end
end)
