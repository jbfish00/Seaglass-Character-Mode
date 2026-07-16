-- Long, print-speed-paced A-mash to clear Birch's post-rescue monologue, then
-- detect when overworld control returns (a DOWN press changes coords) and save.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
H.mash(K.A, 30, 6000, 26)         -- press ~every 52 frames (matches text print)
-- After the monologue, walk down toward the lab exit.
H.onFrame(function(f)
    if f==6100 then
        for _=1,12 do H.press(K.DOWN, 16, 8) end
    end
end)
local last=nil
local END=6700
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    if base>=0x02000000 and base<0x02040000 then
        local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
        if cur~=last then H.log("f="..f.." "..cur); last=cur end
    end
    if f%500==0 then emu:screenshot(string.format("tools/savestates/el_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/have_starter.ss"); H.log("saved"); H.finish() end
end)
