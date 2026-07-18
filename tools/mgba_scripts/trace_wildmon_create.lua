-- Trace CreateWildMon-equivalent: from at_8_8.ss (clean overworld near Route
-- 101 grass), arm a WRITE_CHANGE watchpoint on the whole gEnemyParty struct
-- (0x02019E78, 100 bytes) BEFORE walking into grass, then walk the same
-- pattern battle_bag_oneshot.lua used. Every write hit logs pc/lr/r0-r2 so we
-- can identify the function that first materializes the wild mon (species
-- roll + level roll already resolved by the time this writes -- this is the
-- CreateWildMon(species, level)-equivalent hook candidate).
-- RUN WITH MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local ENEMY = 0x02019E78
local K = H.KEY

local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,3); add(K.DOWN,3)
for _=1,40 do add(K.RIGHT,1); add(K.DOWN,1); add(K.LEFT,1); add(K.UP,1) end
for _,k in ipairs(seq) do H.press(k, 16, 6) end

local hits = 0
local firstPcs = {}
local armed = false
local function arm()
    -- Single-byte watchpoint on the PLAINTEXT level field (+0x54, confirmed by
    -- the existing enemyLv() readers) -- avoids the noise of the encrypted
    -- substruct-copy/nickname loops that a whole-struct watch picks up.
    local id = emu:setWatchpoint(function()
        hits = hits + 1
        local pc = emu:readRegister("pc")
        local lr = emu:readRegister("lr")
        H.log(string.format("WP level+0x54 #%d pc=0x%08X lr=0x%08X sp=0x%08X r0=0x%08X r1=0x%08X r2=0x%08X r3=0x%08X",
            hits, pc, lr, emu:readRegister("sp"), emu:readRegister("r0"), emu:readRegister("r1"),
            emu:readRegister("r2"), emu:readRegister("r3")))
        table.insert(firstPcs, pc)
    end, ENEMY + 0x54, 5)  -- WRITE_CHANGE, single byte
    H.log("watchpoint id=" .. tostring(id))
end

local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp<1 or hp>mx then return nil end
    return lv
end

local encounterAt=nil
local END=6000
H.onFrame(function(f)
    if f==1 and not armed then armed=true; arm() end
    if f>END then return end
    if not encounterAt and f>150 and enemyLv() then
        encounterAt=f
        H.log("encounter rolled at f="..f.." enemyLv="..tostring(enemyLv())..
              " species-field(box,encrypted)@+0x20="..string.format("0x%08X", emu:read32(ENEMY+0x20)))
    end
    if encounterAt and f==encounterAt+50 then
        emu:screenshot("tools/savestates/wildtrace_end.png")
        H.log(string.format("END totalWpHits=%d", hits))
        H.finish()
    end
    if f==END then
        H.log("no encounter within budget, totalWpHits="..hits)
        H.finish()
    end
end)
