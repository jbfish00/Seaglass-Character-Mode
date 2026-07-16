-- Clear the post-rescue lab dialogue with DISCRETE A presses (H.mash appeared
-- ineffective here). Screenshot the progression; save state at the end.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
for _=1,90 do H.press(K.A, 5, 20) end   -- 90 discrete A taps
local last=nil
local END=2400
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    if base>=0x02000000 and base<0x02040000 then
        local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
        if cur~=last then H.log("f="..f.." "..cur); last=cur end
    end
    if f%300==0 then emu:screenshot(string.format("tools/savestates/f2_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/have_starter.ss"); H.log("saved"); H.finish() end
end)
