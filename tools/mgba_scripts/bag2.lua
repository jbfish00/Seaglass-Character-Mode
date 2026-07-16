-- Battle menus drop single key edges after a state load; repeated edges land.
-- RIGHT is idempotent on the 2x2 menu (stops at BAG), so mash RIGHT, then a
-- short A mash to open the bag.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
H.mash(K.RIGHT, 60, 300, 24)
H.mash(K.A, 380, 470, 30)
local END=1000
H.onFrame(function(f)
    if f>END then return end
    if f%200==0 then emu:screenshot(string.format("tools/savestates/bag_f%05d.png", f)) end
    if f==END then emu:screenshot("tools/savestates/bag_open.png"); emu:saveStateFile("tools/savestates/bag_open.ss"); H.finish() end
end)
