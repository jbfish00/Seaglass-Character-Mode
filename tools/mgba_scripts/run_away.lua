-- From bag_open.ss (battle bag, cursor CLOSE BAG): close the bag (A), back at
-- the command menu (cursor on BAG, top-right), DOWN -> RUN, A to flee. Then
-- save the free-overworld state.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
H.onFrame(function(f)
    if f==100  then H.press(K.A, 12, 30) end     -- CLOSE BAG
    if f==400  then H.press(K.DOWN, 12, 30) end  -- BAG -> RUN
    if f==550  then H.press(K.A, 12, 30) end     -- RUN
    -- "Got away safely!" textbox needs an A
    if f==900 or f==1200 then H.press(K.A, 12, 30) end
    if f==1600 then
        emu:screenshot("tools/savestates/ran.png")
        emu:saveStateFile("tools/savestates/free_route101.ss")
        local base=emu:read32(SB1_PTR)
        H.log(string.format("end x=%d y=%d map=%d.%d",
            emu:read16(base), emu:read16(base+2), emu:read8(base+4), emu:read8(base+5)))
        H.finish()
    end
end)
