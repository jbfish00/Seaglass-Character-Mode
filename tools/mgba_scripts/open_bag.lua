-- From wild_battle.ss (encounter just rolled): let the battle intro play, then
-- open the BAG (battle menu: right column bottom in vanilla = down+right from
-- FIGHT) and screenshot the pockets to see if we own any Poke Balls.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
-- battle intro ~600 frames, then: DOWN selects BAG row?? vanilla layout:
-- FIGHT(topleft) BAG(topright) POKEMON(bottomleft) RUN(bottomright).
-- Move RIGHT to BAG, press A.
H.onFrame(function(f)
    if f==1100 then
        emu:saveStateFile("tools/savestates/battle_menu.ss")  -- canonical: menu open
        H.press(K.RIGHT, 6, 20)
        H.press(K.A, 6, 40)
    end
end)
local END=1400
H.onFrame(function(f)
    if f>END then return end
    if f%100==0 then emu:screenshot(string.format("tools/savestates/bag_f%05d.png", f)) end
    if f==END then emu:screenshot("tools/savestates/bag_open.png"); H.finish() end
end)
