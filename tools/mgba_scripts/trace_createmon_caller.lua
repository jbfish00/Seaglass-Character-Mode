-- Breakpoint directly on CreateMonWithIVs-equivalent entry (0x081A7504,
-- confirmed via disasm: species in r1(masked u16), level in r2(masked u8),
-- writes level to mon+0x54, calls CreateBoxMon @0x081a6e44). Read its OWN lr
-- at entry to find the real caller (CreateWildMon-equivalent) -- static
-- BL-scan found only 2 callers (both script-give/daycare regions), so the
-- wild-encounter caller must be indirect; this settles it empirically.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ENEMY = 0x02019E78

local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,3); add(K.DOWN,3)
for _=1,40 do add(K.RIGHT,1); add(K.DOWN,1); add(K.LEFT,1); add(K.UP,1) end
for _,k in ipairs(seq) do H.press(k, 16, 6) end

emu:setBreakpoint(function()
    local r0 = emu:readRegister("r0")
    local lr = emu:readRegister("lr")
    H.log(string.format("CreateMonWithIVs ENTRY frame=%d lr=0x%08X r0(mon)=0x%08X r1(species-raw)=0x%08X r2(level-raw)=0x%08X r3=0x%08X",
        H.frame(), lr, r0, emu:readRegister("r1"), emu:readRegister("r2"), emu:readRegister("r3")))
end, 0x081A7504)

local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp<1 or hp>mx then return nil end
    return lv
end
local encounterAt=nil
local END=6000
H.onFrame(function(f)
    if f>END then return end
    if not encounterAt and f>150 and enemyLv() then
        encounterAt=f
        H.log("encounter rolled at f="..f.." enemyLv="..tostring(enemyLv()))
    end
    if encounterAt and f==encounterAt+50 then H.finish() end
    if f==END then H.finish() end
end)
