-- Empirical choke-point proof for the wild-encounter hook (task #5), on the
-- ORIGINAL unpatched ROM. Walks into Route 101 grass (a reachable LAND
-- encounter) and arms two breakpoints:
--   BP-A: the BL instruction itself at 0x0822BF36 (the site we retarget).
--         Firing = the CPU genuinely executes that instruction on this path.
--   BP-B: CreateMonWithIVs-simple entry 0x081A7504, filtered to r0==gEnemyParty
--         (the wild mon). Records lr for EVERY enemy-mon construction.
-- Proof obligations:
--   (1) BP-A fires during the encounter (that instruction is on the land path).
--   (2) Every BP-B hit for the enemy mon has lr == 0x0822BF3B, i.e. it was
--       reached from the BL at 0x0822BF36 and NO other caller -- so there is
--       no second wild-construction path on the reachable route.
-- Env: START_DELAY shifts timing for a different roll. RUN WITH
-- MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ENEMY = 0x02019E78
local BL_SITE = 0x0822BF36
local CREATEMON = 0x081A7504
local START_DELAY = tonumber(os.getenv and os.getenv("START_DELAY")) or 0

local seq = {}
local function add(k, n) for _ = 1, n do seq[#seq + 1] = k end end
add(K.RIGHT, 3); add(K.DOWN, 3)
for _ = 1, 40 do add(K.RIGHT, 1); add(K.DOWN, 1); add(K.LEFT, 1); add(K.UP, 1) end
H.onFrame(function(f)
    if f == 10 + START_DELAY then
        for _, k in ipairs(seq) do H.press(k, 16, 6) end
    end
end)

local blFires = 0
emu:setBreakpoint(function()
    blFires = blFires + 1
    if blFires <= 3 then
        H.log(string.format("BL-A hit #%d pc=0x%08X (site 0x0822BF36)", blFires, emu:readRegister("pc")))
    end
end, BL_SITE)

local enemyLrs = {}
local enemyCreateCount = 0
emu:setBreakpoint(function()
    if emu:readRegister("r0") ~= ENEMY then return end
    enemyCreateCount = enemyCreateCount + 1
    local lr = emu:readRegister("lr")
    local key = string.format("0x%08X", lr)
    enemyLrs[key] = (enemyLrs[key] or 0) + 1
    if enemyCreateCount <= 3 then
        H.log(string.format("BP-B CreateMonWithIVs(enemy) #%d lr=%s species=%d level=%d",
            enemyCreateCount, key, emu:readRegister("r1"), emu:readRegister("r2")))
    end
end, CREATEMON)

local function enemyLv()
    local hp = emu:read16(ENEMY + 0x56); local mx = emu:read16(ENEMY + 0x58)
    if mx < 1 or mx > 999 or hp < 1 or hp > mx then return nil end
    return true
end
local encounterAt = nil
local END = 6000 + START_DELAY
H.onFrame(function(f)
    if f > END then return end
    if not encounterAt and f > 150 and enemyLv() then encounterAt = f end
    if encounterAt and f == encounterAt + 30 then
        H.log("BL-A total fires during encounter = " .. blFires)
        local distinct = 0
        for k, v in pairs(enemyLrs) do H.log("  enemy-CreateMonWithIVs lr " .. k .. " x" .. v); distinct = distinct + 1 end
        H.assertTrue("BL site 0x0822BF36 executed on land path", blFires >= 1)
        H.assertTrue("enemy CreateMonWithIVs happened", enemyCreateCount >= 1)
        H.assertEq("exactly one distinct lr for enemy construction", distinct, 1)
        H.assertTrue("that lr == 0x0822BF3B (from the BL we hooked)", enemyLrs["0x0822BF3B"] ~= nil)
        H.finish()
    end
    if f == END then H.log("no encounter"); H.assertTrue("encounter reached", false); H.finish() end
end)
