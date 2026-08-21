-- LIVE assertion for the wild-encounter marker (rowe_parity.md §3).
--
-- Reads the string the engine actually expanded into gDisplayedStringBattle
-- after a wild encounter, and checks it names the active character.
--
-- ⚠️ This has to be a POSITIVE observation. "The marker did not appear" is
-- satisfied equally well by a correct suppression and by the feature being
-- completely dead -- the same trap legendary_encounters.md warns about, and the
-- one that left layers 5e/5e2 dead here for weeks. So the run that matters is
-- the one that asserts the marker IS there, with the RIGHT name.
--
-- The discriminating control is a DIFFERENT CHARACTER, not merely "mode off".
-- A shim that ignored charId and always returned the first character's string
-- would pass a Red-only test and every mode-off test; only asserting that
-- char 10 says MISTY exercises the (charId-1)*STRIDE indexing. Seaglass has
-- been bitten by exactly this before -- its wild-pool test could not see a
-- broken stride because it only ever ran character 1.
--
-- Env: CM_CHAR, CM_FORCE_SPECIES (an on-roster species for that character),
--      CM_EXPECT_NAME (uppercase, or "" to expect the vanilla line),
--      CM_ON (default 1). Needs MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local CM_ON     = (os.getenv("CM_ON") or "1") ~= "0"
local CM_CHAR   = tonumber(os.getenv("CM_CHAR") or "1")
local FORCE_SP  = tonumber(os.getenv("CM_FORCE_SPECIES") or "1")
local EXPECT    = os.getenv("CM_EXPECT_NAME") or "RED"

local DISPLAYED = 0x020000CC        -- gDisplayedStringBattle, from the literal
                                    -- at 0x080870EC that the intro tail loads
local WILD_TRAMP = 0x08470208

-- Gen3 charmap, decode side only.
local CH = {}
for i = 0, 25 do
    CH[0xBB + i] = string.char(65 + i)
    CH[0xD5 + i] = string.char(97 + i)
end
CH[0x00] = " "; CH[0xAB] = "!"; CH[0xB8] = ","; CH[0xAD] = "."
local function readStr(addr, max)
    local out = {}
    for i = 0, max - 1 do
        local b = H.rd8(addr + i)
        if b == 0xFF then break end
        if b == 0xFE then out[#out + 1] = "|"
        else out[#out + 1] = CH[b] or string.format("{%02X}", b) end
    end
    return table.concat(out)
end

local forced, seen, done = false, nil, false

H.onFrame(function(f)
    if f ~= 5 then return end
    if CM_ON then
        H.setFlag(0x2B0)
        H.setVar(0x40E4, CM_CHAR)
        H.log("CM ON char=" .. CM_CHAR .. ", forcing species " .. FORCE_SP)
    else
        H.clearFlag(0x2B0)
        H.log("CM OFF (control), forcing species " .. FORCE_SP)
    end
end)

-- Force the rolled species to one that is on this character's roster, so the
-- marker's precondition is satisfied deterministically instead of waiting for
-- a 10% override to happen to fire.
emu:setBreakpoint(function()
    if forced then return end
    forced = true
    emu:writeRegister("r1", FORCE_SP)
    H.log("forced rolled species to " .. FORCE_SP)
end, WILD_TRAMP)

-- Walk the player around in grass until an encounter fires. Same driver the
-- legendary e2e uses; a savestate standing still never produces one.
local K = H.KEY
local seq = {}
local function add(k, n) for _ = 1, n do seq[#seq + 1] = k end end
add(K.RIGHT, 3); add(K.DOWN, 3)
for _ = 1, 40 do add(K.RIGHT, 1); add(K.DOWN, 1); add(K.LEFT, 1); add(K.UP, 1) end

H.onFrame(function(f)
    if f == 40 then
        for _, k in ipairs(seq) do H.press(k, 16, 6) end
    end
    if done or f < 60 then return end
    if not seen then
        local s = readStr(DISPLAYED, 60)
        if s:find("appeared") then
            seen = s
            H.log("displayed: " .. s)
        end
    end
    -- Give the intro a moment to be written, then judge. Judging the instant
    -- "appeared" shows up would race the expander mid-write.
    if (seen and f > 120) or f > 3000 then
        done = true
        H.assertTrue("wild trampoline fired (encounter happened)", forced)
        H.assertTrue("a wild intro was displayed at all", seen ~= nil)
        if seen then
            if EXPECT ~= "" then
                H.assertTrue("intro names the character (" .. EXPECT .. ")",
                             seen:find("destined for " .. EXPECT, 1, true) ~= nil)
            else
                H.assertTrue("intro is the vanilla line (no marker)",
                             seen:find("destined for", 1, true) == nil)
            end
        end
        H.finish()
    end
end)
