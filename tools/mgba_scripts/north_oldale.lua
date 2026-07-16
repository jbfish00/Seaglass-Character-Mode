-- From free_route101.ss (11,12): east to col 14-15 (open ground, no grass),
-- then north along the east edge toward Oldale.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,4); add(K.UP,12)
for _,k in ipairs(seq) do H.press(k, 16, 6) end
local last=nil
local END=2600
H.onFrame(function(f)
    if f>END then return end
    local b=emu:read32(SB1_PTR)
    local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(b),emu:read16(b+2),emu:read8(b+4),emu:read8(b+5))
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if f==END then emu:screenshot("tools/savestates/nc_end.png"); emu:saveStateFile("tools/savestates/nav_out.ss"); H.log("saved"); H.finish() end
end)
