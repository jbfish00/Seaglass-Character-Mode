-- Breakpoint on SetMonData's entry (0x081A9CA0, CONFIRMED in ROUTINE_MAP.md)
-- during the wild-encounter window, to find the caller that drives IV/level
-- construction for the WILD mon (gEnemyParty, not gPlayerParty) -- i.e. the
-- CreateWildMon/CreateMonWithIVs-equivalent we actually want to hook.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ENEMY = 0x02019E78

local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,3); add(K.DOWN,3)
for _=1,40 do add(K.RIGHT,1); add(K.DOWN,1); add(K.LEFT,1); add(K.UP,1) end
for _,k in ipairs(seq) do H.press(k, 16, 6) end

local hits = 0
local seen = {}
emu:setBreakpoint(function()
    hits = hits + 1
    local r0 = emu:readRegister("r0")
    if r0 ~= ENEMY then return end   -- only care about writes targeting the WILD mon
    local lr = emu:readRegister("lr")
    local key = string.format("0x%08X", lr)
    if not seen[key] then
        seen[key] = 0
        H.log(string.format("SETMONDATA(enemy) frame=%d #%d lr=%s r1(field)=0x%08X r2=0x%08X r3=0x%08X",
            H.frame(), hits, key, emu:readRegister("r1"), emu:readRegister("r2"), emu:readRegister("r3")))
    end
    seen[key] = seen[key] + 1
end, 0x081A9CA0)

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
    if encounterAt and f==encounterAt+50 then
        for k,v in pairs(seen) do H.log("LRCOUNT "..k.." x"..v) end
        H.log("END totalHits(enemy)="..hits)
        H.finish()
    end
    if f==END then H.log("no encounter, hits="..hits); H.finish() end
end)
