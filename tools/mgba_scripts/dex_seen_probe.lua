-- Locate the Pokedex bitmaps by diffing the save blocks across a wild encounter
-- whose species we KNOW EXACTLY.
--
-- The catch-based probe (dex_flag_probe.lua) could not pin the convention: a
-- catch churns playtime, RNG, party and event flags, and with only one species
-- there is no way to tell a dex bit from a coincidence. This one fixes both
-- problems. The wild trampoline at 0x08470208 fires with the rolled species in
-- r1 at the moment the wild mon is created, so we snapshot there and again after
-- the battle intro has run -- the interval in which the engine sets "seen".
--
-- Run it twice with different START_DELAY values to get two different species:
-- the byte offset must move by (speciesB//8 - speciesA//8) and the bit by the
-- species modulo 8. One species can be fitted by chance; two cannot.
--
-- Needs MGBA_HEADLESS_DEBUGGER=1 (stock headless returns -1 from setBreakpoint
-- and never fires -- see docs/TESTING.md).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local SB1_PTR, SB2_PTR = 0x030051B8, 0x030051BC
local SPAN1, SPAN2 = 0x3A00, 0x1000
local START_DELAY = tonumber(os.getenv("START_DELAY") or "0")
local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "1")

local species, snapped, reported = nil, false, false
local before1, before2, base1, base2

H.onFrame(function(f)
    if f ~= 30 then return end
    H.setFlag(0x2B0)
    H.setVar(0x40E4, CM_CHAR)
    H.log("CM ON char=" .. CM_CHAR .. " START_DELAY=" .. START_DELAY)
end)

-- ⚠️ THE WHOLE POINT: force a level high enough that the CM override lands on an
-- EVOLVED pool member. The first version of this probe watched ordinary Route
-- 101 rolls (Sentret, Zigzagoon, ...) and found nothing, for a reason that reads
-- as a broken probe but is not: every savestate here is far enough in that those
-- species are ALREADY SEEN, so the dex bit never flips. Forcing char 45 Glacia
-- at level 45 yields Walrein, which no early save has seen.
local FORCE_LEVEL = tonumber(os.getenv("FORCE_LEVEL") or "0")

emu:setBreakpoint(function()
    if snapped then return end
    species = emu:readRegister("r1") & 0xFFFF
    if FORCE_LEVEL > 0 then emu:writeRegister("r2", FORCE_LEVEL) end
    base1, base2 = emu:read32(SB1_PTR), emu:read32(SB2_PTR)
    before1 = emu:readRange(base1, SPAN1)
    before2 = emu:readRange(base2, SPAN2)
    snapped = true
    console:log(string.format("DEX pre_species=%d (pre-override)", species))
end, 0x08470208)

-- The species actually CREATED -- and therefore actually marked seen -- is the
-- shim's return value, not the vanilla roll. Watching r1 at entry would expect
-- the bit for a species that never entered the battle.
emu:setBreakpoint(function()
    if species == nil then return end
    local post = emu:readRegister("r0") & 0xFFFF
    if post ~= species then
        console:log(string.format("DEX OVERRIDDEN %d -> %d", species, post))
        species = post
    end
    console:log(string.format("DEX species=%d  expect byte+%d bit%d (LSB-first) "
                              .. "or bit%d (MSB-first)",
                              species, species // 8, species % 8,
                              7 - (species % 8)))
end, 0x08470218)

local function bitdiff(tag, old, new, base)
    for i = 1, #old do
        local a, b = string.byte(old, i), string.byte(new, i)
        if a ~= b then
            local x = a ~ b
            local n = 0
            for k = 0, 7 do if (x >> k) & 1 == 1 then n = n + 1 end end
            if n == 1 and (a & x) == 0 then
                local bit = 0
                for k = 0, 7 do if (x >> k) & 1 == 1 then bit = k end end
                local off = i - 1
                -- If this IS the dex bit for `species`, the array base is here
                -- minus the species' byte index. Print that directly: it is the
                -- constant the shim would use, and two runs must agree on it.
                console:log(string.format(
                    "DEX %s off=0x%04X bit=%d | LSBfirst_base=0x%04X "
                    .. "| MSBfirst_base=0x%04X | abs=0x%08X",
                    tag, off, bit,
                    off - (species // 8), off - (species // 8),
                    base + off))
            end
        end
    end
end

-- The proven walk cadence, copied from cm_wild_test.lua. A hand-rolled one does
-- not produce an encounter on this savestate at all (tried: it just stands
-- there), which reads exactly like the breakpoint failing to fire.
local seq = {}
local function add(k, n) for _ = 1, n do seq[#seq + 1] = k end end
add(K.RIGHT, 3); add(K.DOWN, 3)
for _ = 1, 40 do add(K.RIGHT, 1); add(K.DOWN, 1); add(K.LEFT, 1); add(K.UP, 1) end
H.onFrame(function(f)
    if f == 40 + START_DELAY then
        for _, k in ipairs(seq) do H.press(k, 16, 6) end
        H.log("walk started at f=" .. f)
    end
end)

H.onFrame(function(f)
    if snapped and not reported and f > 900 then
        reported = true
        console:log("DEX ---- diff after battle intro (species " .. species .. ") ----")
        bitdiff("SB1", before1, emu:readRange(base1, SPAN1), base1)
        bitdiff("SB2", before2, emu:readRange(base2, SPAN2), base2)
        console:log("DEX done species=" .. species)
        H.finish()
    end
    if f > 1800 and not reported then
        console:log("DEX !! no encounter within budget (species=" .. tostring(species) .. ")")
        H.finish()
    end
end)
