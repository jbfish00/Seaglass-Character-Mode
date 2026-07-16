-- From shop.ss (~2,5): open the Oldale Mart shop (talk from (1,5) facing up),
-- buy 1 Potion, exit. Save the 1-Potion bag state for a SaveBlock1 diff that
-- locates the Items pocket + item-quantity encryption.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
H.onFrame(function(f)
    if f==60  then H.press(K.LEFT, 16, 8) end   -- to (1,5)
    if f==150 then H.press(K.UP, 6, 20) end     -- face counter
    if f==220 then H.press(K.A, 12, 30) end     -- open shop -> item list
    if f==500 then emu:screenshot("tools/savestates/bp1.png") end
    if f==560 then H.press(K.A, 12, 30) end     -- select Potion -> qty
    if f==800 then emu:screenshot("tools/savestates/bp2.png") end
    if f==860 then H.press(K.A, 12, 30) end     -- confirm qty 1 -> price YES/NO
    if f==1100 then emu:screenshot("tools/savestates/bp3.png") end
    if f==1160 then H.press(K.A, 12, 30) end    -- YES
    if f==1400 then H.press(K.A, 12, 30) end    -- "Here you are!"
    if f==1650 then H.press(K.A, 12, 30) end    -- extra advance
    if f==1900 then emu:screenshot("tools/savestates/bp4.png"); H.press(K.B, 12, 30) end  -- exit list
    if f==2100 then H.press(K.B, 12, 30) end
    if f==2400 then
        emu:screenshot("tools/savestates/bp5.png")
        emu:saveStateFile("tools/savestates/bag_potion.ss")
        H.log("saved bag_potion.ss")
        H.finish()
    end
end)
