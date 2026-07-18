-- Same breakpoint on 0x081A92FC entry, but log every hit with its own frame
-- number and a running total, plus flag any DISTINCT lr value seen for the
-- first time -- to catch the (likely rare, once-per-encounter) call whose lr
-- differs from the per-step ability-check pattern (081A94xx/081A82xx).
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
    local lr = emu:readRegister("lr")
    local key = string.format("0x%08X", lr)
    if not seen[key] then
        seen[key] = 0
        H.log(string.format("NEWLR frame=%d #%d lr=%s r0=0x%08X r1=0x%08X r2=0x%08X r3=0x%08X sp0=0x%08X",
            H.frame(), hits, key, emu:readRegister("r0"), emu:readRegister("r1"),
            emu:readRegister("r2"), emu:readRegister("r3"), emu:read32(emu:readRegister("sp"))))
    end
    seen[key] = seen[key] + 1
end, 0x081A92FC)

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
        H.log("END totalBpHits="..hits)
        H.finish()
    end
    if f==END then H.log("no encounter, hits="..hits); H.finish() end
end)
