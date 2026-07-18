-- Stage-fitting unit test for CM_WildMonSpeciesGated (task #5), forcing the
-- ROLLED LEVEL at the wild trampoline entry breakpoint to a high value
-- (register write, not just read) so a real wild encounter -- which on
-- Route 101 only ever rolls level 2-3 -- can still exercise the "high level
-- -> evolved stage" half of the stage-fit logic. Loops until an override
-- fires (forcing the level doesn't force the 10% gate; retries across a
-- spread of START_DELAYs like cm_wild_test.lua). Env: CM_CHAR, FORCE_LEVEL,
-- START_DELAY. RUN WITH MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ENEMY = 0x02019E78
local FLAG_CM = 0x945

local CM_CHAR = tonumber(os.getenv and os.getenv("CM_CHAR")) or 1
local FORCE_LEVEL = tonumber(os.getenv and os.getenv("FORCE_LEVEL")) or 40
local START_DELAY = tonumber(os.getenv and os.getenv("START_DELAY")) or 0

H.onFrame(function(f)
    if f == 5 then
        H.setFlag(FLAG_CM)
        H.setVar(0x40E4, CM_CHAR)
        H.log("CM ON char=" .. CM_CHAR .. " forcing level=" .. FORCE_LEVEL)
    end
end)

local seq = {}
local function add(k, n) for _ = 1, n do seq[#seq + 1] = k end end
add(K.RIGHT, 3); add(K.DOWN, 3)
for _ = 1, 40 do add(K.RIGHT, 1); add(K.DOWN, 1); add(K.LEFT, 1); add(K.UP, 1) end
H.onFrame(function(f)
    if f == 10 + START_DELAY then
        for _, k in ipairs(seq) do H.press(k, 16, 6) end
    end
end)

local preSpecies, postSpecies
emu:setBreakpoint(function()
    if preSpecies then return end
    preSpecies = emu:readRegister("r1")
    emu:writeRegister("r2", FORCE_LEVEL)   -- force the level the shim will see
    H.log(string.format("TRAMP ENTRY frame=%d species=%d level(forced)=%d", H.frame(), preSpecies, FORCE_LEVEL))
end, 0x08470208)

emu:setBreakpoint(function()
    if postSpecies then return end
    postSpecies = emu:readRegister("r0")
    H.log(string.format("TRAMP RESULT frame=%d species=%d", H.frame(), postSpecies))
end, 0x08470218)

local function enemyLv()
    local hp = emu:read16(ENEMY + 0x56); local mx = emu:read16(ENEMY + 0x58)
    if mx < 1 or mx > 999 or hp < 1 or hp > mx then return nil end
    return true
end
local encounterAt = nil
local END = 6000 + START_DELAY
H.onFrame(function(f)
    if f > END then return end
    if not encounterAt and f > 150 and enemyLv() then
        encounterAt = f
    end
    if encounterAt and f == encounterAt + 50 then
        local overridden = preSpecies ~= nil and postSpecies ~= nil and preSpecies ~= postSpecies
        H.log(string.format("RESULT pre_species=%s post_species=%s overridden=%s",
            tostring(preSpecies), tostring(postSpecies), tostring(overridden)))
        H.finish()
    end
    if f == END then
        H.log("RESULT no encounter within budget")
        H.finish()
    end
end)
