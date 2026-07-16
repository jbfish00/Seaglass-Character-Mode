-- Survey Route 101 for roaming overworld wild Pokemon (Seaglass appears to use
-- visible encounters, not vanilla random grass encounters). Walk a wide loop,
-- screenshot frequently; eyeball the shots for wild mon sprites to collide with.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
-- wander a loop: up along the west, east across the top, down the east side
add(K.UP,6); add(K.RIGHT,6); add(K.DOWN,4); add(K.LEFT,3); add(K.UP,3); add(K.RIGHT,3)
for _,k in ipairs(seq) do H.press(k, 16, 6) end
local last=nil
local END=1400
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if f%60==0 then emu:screenshot(string.format("tools/savestates/sv_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/survey_end.ss"); H.log("saved"); H.finish() end
end)
