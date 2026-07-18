-- Wild-encounter species override test (task #5). From at_8_8.ss (clean
-- overworld next to Route 101 grass), optionally turns Character Mode on for
-- a given character, walks into grass (same pattern as
-- battle_bag_oneshot.lua), and breakpoints the wild trampoline (0x08470208,
-- 0x08470218) to observe:
--   - r1/r2 at trampoline entry (0x08470208) = the vanilla roll's species/level
--   - r0 at label "1:" (0x08470218) = CM_WildMonSpeciesGated's return value
--     (species after the 10%-chance override, or unchanged)
-- Env vars: CM_ON=1, CM_CHAR=<1..170>, START_DELAY=<extra idle frames before
-- walking, shifts VCOUNT/timing so repeated runs sample different rolls>.
-- RUN WITH MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ENEMY = 0x02019E78
local FLAG_CM = 0x945

local CM_ON = (os.getenv and os.getenv("CM_ON")) == "1"
local CM_CHAR = tonumber(os.getenv and os.getenv("CM_CHAR")) or 1
local START_DELAY = tonumber(os.getenv and os.getenv("START_DELAY")) or 0

H.onFrame(function(f)
    if f == 5 then
        if CM_ON then
            H.setFlag(FLAG_CM)
            H.setVar(0x40E4, CM_CHAR)   -- VAR_CM_CHAR
            H.log("CM ON char=" .. CM_CHAR)
        else
            H.clearFlag(FLAG_CM)
            H.log("CM OFF")
        end
    end
end)

local seq = {}
local function add(k, n) for _ = 1, n do seq[#seq + 1] = k end end
add(K.RIGHT, 3); add(K.DOWN, 3)
for _ = 1, 40 do add(K.RIGHT, 1); add(K.DOWN, 1); add(K.LEFT, 1); add(K.UP, 1) end
H.onFrame(function(f)
    if f == 10 + START_DELAY then
        for _, k in ipairs(seq) do H.press(k, 16, 6) end
        H.log("walk started at f=" .. f)
    end
end)

local preSpecies, preLevel, postSpecies
emu:setBreakpoint(function()
    if preSpecies then return end   -- only the first firing (one encounter)
    preSpecies = emu:readRegister("r1")
    preLevel = emu:readRegister("r2")
    H.log(string.format("TRAMP ENTRY frame=%d species=%d level=%d", H.frame(), preSpecies, preLevel))
end, 0x08470208)

emu:setBreakpoint(function()
    if postSpecies then return end
    postSpecies = emu:readRegister("r0")
    H.log(string.format("TRAMP RESULT frame=%d species=%d", H.frame(), postSpecies))
end, 0x08470218)

local function enemyLv()
    local lv = emu:read8(ENEMY + 0x54); if lv < 1 or lv > 100 then return nil end
    local hp = emu:read16(ENEMY + 0x56); local mx = emu:read16(ENEMY + 0x58)
    if mx < 1 or mx > 999 or hp < 1 or hp > mx then return nil end
    return lv
end
local encounterAt = nil
local END = 6000 + START_DELAY
H.onFrame(function(f)
    if f > END then return end
    if not encounterAt and f > 150 and enemyLv() then
        encounterAt = f
        H.log("encounter rolled at f=" .. f .. " enemyLv=" .. tostring(enemyLv()))
    end
    if encounterAt and f == encounterAt + 50 then
        local overridden = preSpecies ~= nil and postSpecies ~= nil and preSpecies ~= postSpecies
        H.log(string.format("RESULT pre_species=%s pre_level=%s post_species=%s overridden=%s",
            tostring(preSpecies), tostring(preLevel), tostring(postSpecies), tostring(overridden)))
        H.assertTrue("trampoline fired (pre-species observed)", preSpecies ~= nil)
        H.assertTrue("trampoline result observed (post-species)", postSpecies ~= nil)
        if not CM_ON then
            H.assertTrue("CM off -> never overridden", not overridden)
        end
        H.finish()
    end
    if f == END then
        H.log("no encounter within budget")
        H.finish()
    end
end)
