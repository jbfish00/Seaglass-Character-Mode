-- From after_rescue.ss (lab, post-clean-rescue): clear naming (START confirms
-- the keyboard) + Birch's speech (A), escape the aide loop (B closes without
-- re-interacting), then walk to the south door out to Littleroot. Save + shots.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
-- Phase 1: confirm the nickname keyboard a few times (START), advance prompts (A).
H.press(K.START, 6, 24); H.press(K.START, 6, 24); H.press(K.START, 6, 24)
-- Phase 2: A-mash Birch's long speech.
H.mash(K.A, 200, 4500, 22)
-- Phase 3: B-burst to break the aide loop, then walk down toward the exit.
H.onFrame(function(f)
    if f==4600 then
        for _=1,6 do H.press(K.B, 4, 14) end
        H.press(K.LEFT, 16, 8)
        for _=1,10 do H.press(K.DOWN, 16, 8) end
    end
end)
local last=nil
local END=5400
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    if base>=0x02000000 and base<0x02040000 then
        local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
        if cur~=last then H.log("f="..f.." "..cur); last=cur end
    end
    if f%400==0 then emu:screenshot(string.format("tools/savestates/lo_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/have_starter.ss"); H.log("saved"); H.finish() end
end)
