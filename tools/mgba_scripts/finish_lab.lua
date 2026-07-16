-- From after_rescue.ss (Torchic nickname keyboard): confirm the name (START =
-- OK), then A-mash through the rest of Birch's lab scene (Pokedex gift, etc.)
-- to a free overworld state. Save a clean single-Pokemon state + screenshots so
-- gPlayerParty can be located without the post-battle enemy-party noise.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
-- Clear the long post-rescue lab dialogue (Birch's thanks + Pokedex gift).
H.mash(K.A, 30, 7000, 18)
local last=nil
local END=7200
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    if base>=0x02000000 and base<0x02040000 then
        local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
        if cur~=last then H.log("f="..f.." "..cur); last=cur end
    end
    if f%250==0 then emu:screenshot(string.format("tools/savestates/fl_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/have_starter.ss"); H.log("saved have_starter.ss"); H.finish() end
end)
