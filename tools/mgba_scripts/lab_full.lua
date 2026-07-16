-- From after_rescue.ss (Birch "give a nickname?" YES/NO): decline nickname
-- (DOWN->A), then A-mash Birch's FULL speech (Pokedex + 5 Poke Balls gift --
-- what a B-escape skipped), then B-escape the aide loop and walk out to
-- Littleroot. Save have_starter2.ss. Screenshots to verify the gift text.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
H.onFrame(function(f)
    if f==80  then H.press(K.DOWN, 6, 20) end   -- cursor YES -> NO
    if f==150 then H.press(K.A, 8, 30) end      -- select NO
end)
-- A-mash the long forced speech (nickname done ~f=250).
H.mash(K.A, 300, 8000, 22)
-- After the speech, B-escape the aide loop and head out.
H.onFrame(function(f)
    if f==8100 then
        for _=1,8 do H.press(K.B, 4, 14) end
        H.press(K.LEFT, 16, 8)
        for _=1,12 do H.press(K.DOWN, 16, 8) end
    end
end)
local last=nil
local END=9200
H.onFrame(function(f)
    if f>END then return end
    local b=emu:read32(SB1_PTR)
    if b>=0x02000000 and b<0x02040000 then
        local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(b),emu:read16(b+2),emu:read8(b+4),emu:read8(b+5))
        if cur~=last then H.log("f="..f.." "..cur); last=cur end
    end
    if f%800==0 then emu:screenshot(string.format("tools/savestates/lfscr_%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/have_starter2.ss"); H.log("saved"); H.finish() end
end)
