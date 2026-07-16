-- From nav_out.ss (starter-selection "Do you choose this POKeMON?" YES prompt):
-- confirm YES, then A-mash through the Prof. Birch rescue battle vs the wild
-- Poochyena (starter auto-uses its first move; mashing A defaults to FIGHT ->
-- first move -> through damage text). Screenshot periodically; save state.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
-- A-mash the whole thing.
H.mash(K.A, 30, 3000, 20)
local last=nil
local END=3200
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    if base>=0x02000000 and base<0x02040000 then
        local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
        if cur~=last then H.log("f="..f.." "..cur); last=cur end
    end
    if f%200==0 then emu:screenshot(string.format("tools/savestates/wb_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/after_rescue.ss"); H.log("saved after_rescue.ss"); H.finish() end
end)
