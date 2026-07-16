-- From battle_menu2.ss ("Wild Zigzagoon appeared!" stage): finish the intro
-- with spaced A presses, wait for the command menu, then RIGHT -> A to open the
-- battle BAG. Screenshots at each phase for verification.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
H.onFrame(function(f)
    if f==100 or f==350 or f==600 then H.press(K.A, 12, 30) end
    if f==900  then emu:screenshot("tools/savestates/tb_menu.png") end
    if f==950  then H.press(K.RIGHT, 12, 30) end
    if f==1050 then emu:screenshot("tools/savestates/tb_right.png") end
    if f==1100 then H.press(K.A, 12, 30) end
    if f==1400 then
        emu:screenshot("tools/savestates/tb_bag.png")
        emu:saveStateFile("tools/savestates/bag_open.ss")
        H.log("done")
        H.finish()
    end
end)
