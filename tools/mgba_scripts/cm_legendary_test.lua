-- LIVE positive assertion for the 1% legendary wild encounter roll.
--
-- ⚠️ Why this exists even though verify_legendary_roll.py already proves the
-- arithmetic exhaustively: that runs offline, on a re-implementation. This one
-- observes the SHIPPED SHIM, in the running ROM, actually returning a legendary.
-- The spec is explicit that a dex/flag filter is satisfied equally well by
-- correct suppression and by the feature being completely dead, so "no legendary
-- appeared" proves nothing and only a positive observation counts.
--
-- How a 1% event is made deterministic: the roll is
--     seed  = species*2654435761 + level*40503 + vcount*6151 + keys
--     lseed = seed*2246822519 + 374761393        -- the independence mix
--     hit   = lseed % 100 < 1
-- Every input is observable or controllable at the wild trampoline breakpoint,
-- which fires immediately before the shim runs: species and level are r1/r2 and
-- we can WRITE them, keys we control by holding nothing, and VCOUNT we read.
-- VCOUNT is the only slippery one -- it advances by a scanline or so between the
-- breakpoint and the shim's own read -- so we require a level that produces a
-- hit for EVERY vcount in a window around the observed one, and only then commit
-- to it. That makes the 1% event fire on demand without touching the ROM.
--
-- Env: CM_CHAR (default 3 = Blue), EXPECT_SPECIES (default 145 = Zapdos).
-- Needs MGBA_HEADLESS_DEBUGGER=1.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "3")
local EXPECT = tonumber(os.getenv("EXPECT_SPECIES") or "145")
local START_DELAY = tonumber(os.getenv("START_DELAY") or "0")

-- The 20 legendary flags, in emit_legendaries.py's order. Cleared at start so
-- the run does not depend on whatever these previously-unused flags happened to
-- hold in a savestate captured before the feature existed -- a set flag would
-- retire the legendary and the test would look like a dead feature.
local LEG_FLAGS = {0x2b6, 0x2b8, 0x2b9, 0x2ba, 0x2bb, 0x2d5, 0x2ee, 0x32a,
                   0x367, 0x38c, 0x392, 0x397, 0x3ab, 0x3af, 0x3c0, 0x3c6,
                   0x3ca, 0x3cc, 0x3d5, 0x3e9}

-- CM_EXPECT=caught SETS the flags instead of clearing them, and asserts the
-- forced roll does NOT yield the legendary -- the "offered until caught" half.
-- On its own that would be the weak assertion the spec warns about (a dead
-- feature passes it too); it is only meaningful as the pair of the uncaught run
-- above, on the same forced roll, differing in nothing but the flag.
local EXPECT_CAUGHT = (os.getenv("CM_EXPECT") == "caught")

local M32 = 0x100000000
local function u32(x) return x % M32 end
local function hits(species, level, vcount, keys)
    local seed = u32(species * 2654435761 + level * 40503 + vcount * 6151 + keys)
    return u32(seed * 2246822519 + 374761393) % 100 < 1
end

local forcedLevel, observed, fired = nil, nil, false

-- DEX_PROBE=1 also diffs the save blocks across the encounter and prints, for
-- the species we forced, the bitmap base each single-bit change would imply.
-- Two runs forcing DIFFERENT legendaries must agree on one base -- and every
-- legendary is guaranteed unseen in these savestates, which is what the earlier
-- probes lacked (they watched species the save had already seen, so no bit ever
-- flipped and there was nothing to intersect).
-- DEX_PROBE=2 widens the diff from the two save blocks to ALL OF EWRAM. The save
-- blocks were searched first and came back empty for three separate known-unseen
-- legendaries, which leaves "the dex is not in either save block" as the live
-- hypothesis -- so stop assuming where it lives and diff the whole 256 KB.
-- readRange is fine at this size; looping emu:read8 over EWRAM stalls the
-- emulator so hard the frame callback never returns (docs/TESTING.md).
local DEX_PROBE = os.getenv("DEX_PROBE") == "1" or os.getenv("DEX_PROBE") == "2"
local DEX_EWRAM = os.getenv("DEX_PROBE") == "2"
local EWRAM_BASE, EWRAM_SPAN = 0x02000000, 0x40000
local SB1_PTR, SB2_PTR = 0x030051B8, 0x030051BC
local SPAN1, SPAN2 = 0x6000, 0x3000
local dexBefore1, dexBefore2, dexBase1, dexBase2, dexDone

H.onFrame(function(f)
    if f ~= 5 then return end
    H.setFlag(0x2B0)
    H.setVar(0x40E4, CM_CHAR)
    for _, fl in ipairs(LEG_FLAGS) do
        if EXPECT_CAUGHT then H.setFlag(fl) else H.clearFlag(fl) end
    end
    H.log("CM ON char=" .. CM_CHAR .. "; all 20 legendary flags "
          .. (EXPECT_CAUGHT and "SET (already caught)" or "cleared (uncaught)"))
end)

emu:setBreakpoint(function()
    if forcedLevel then return end
    local species = emu:readRegister("r1") & 0xFFFF
    local keys = emu:read16(0x04000130)
    local vc = emu:read16(0x04000006) & 0xFF
    -- VCOUNT advances between this breakpoint and the shim's own read, by a
    -- fixed amount: the intervening code path (the trampoline veneer, then
    -- gateActive()'s FlagGet + GetVarPointer) is the same every time. So the
    -- offset is a CONSTANT to calibrate once, not a window to cover -- requiring
    -- a hit across 5 consecutive VCOUNTs was ~1e-10 per level and never found
    -- one. VC_DRIFT is that constant; run with CM_VC_DRIFT=0..7 once to find it.
    --
    -- Both r1 and r2 are ours to choose: if the roll hits, the shim returns the
    -- legendary regardless of the species that was rolled, so species is just
    -- another free variable in the seed. ~50 species x 99 levels at 1% each
    -- makes finding a forcing pair a certainty rather than a 63% gamble.
    -- CALIBRATED 2026-07-27: the drift is 0. Swept 0..7; only 0 produced the
    -- legendary (D=1..7 returned ordinary species 130/180/162/164/4), which is
    -- itself the confirmation that the model is right -- a wrong offset misses
    -- rather than accidentally hitting.
    local D = tonumber(os.getenv("CM_VC_DRIFT") or "0")
    local target = (vc + D) % 228
    for lvl = 2, 100 do
        for sp2 = species, species + 49 do
            if hits(sp2, lvl, target, keys) then
                forcedLevel = lvl
                emu:writeRegister("r1", sp2)
                emu:writeRegister("r2", lvl)
                H.log(string.format("FORCED species=%d level=%d (vcount=%d+%d=%d "
                                    .. "keys=%#x) -> legendary roll must hit",
                                    sp2, lvl, vc, D, target, keys))
                return
            end
        end
    end
    H.log("no forcing pair found this frame (unexpected); retrying next encounter")
end, 0x08470208)

emu:setBreakpoint(function()
    if observed ~= nil then return end
    observed = emu:readRegister("r0") & 0xFFFF
    fired = true
    H.log("SHIM RETURNED species=" .. observed)
    if DEX_EWRAM then
        dexBase1 = EWRAM_BASE
        dexBefore1 = emu:readRange(EWRAM_BASE, EWRAM_SPAN)
    elseif DEX_PROBE then
        dexBase1, dexBase2 = emu:read32(SB1_PTR), emu:read32(SB2_PTR)
        dexBefore1 = emu:readRange(dexBase1, SPAN1)
        dexBefore2 = emu:readRange(dexBase2, SPAN2)
    end
end, 0x08470218)

local function dexDiff(tag, old, new, base, species)
    local want = species % 8
    local wantMsb = 7 - want
    for i = 1, #old do
        local a, b = string.byte(old, i), string.byte(new, i)
        if a ~= b then
            local x = a ~ b
            local n, bit = 0, 0
            for k = 0, 7 do
                if (x >> k) & 1 == 1 then n = n + 1 bit = k end
            end
            if n == 1 and (a & x) == 0 then
                local off = i - 1
                if bit == want then
                    console:log(string.format(
                        "DEXCAND %s LSB base=0x%04X (off=0x%04X bit=%d abs=0x%08X)",
                        tag, off - (species // 8), off, bit, base + off))
                elseif bit == wantMsb then
                    console:log(string.format(
                        "DEXCAND %s MSB base=0x%04X (off=0x%04X bit=%d abs=0x%08X)",
                        tag, off - (species // 8), off, bit, base + off))
                end
            end
        end
    end
end

local seq = {}
local function add(k, n) for _ = 1, n do seq[#seq + 1] = k end end
add(K.RIGHT, 3); add(K.DOWN, 3)
for _ = 1, 40 do add(K.RIGHT, 1); add(K.DOWN, 1); add(K.LEFT, 1); add(K.UP, 1) end
H.onFrame(function(f)
    if f == 40 + START_DELAY then
        for _, k in ipairs(seq) do H.press(k, 16, 6) end
    end
    if DEX_PROBE and dexBefore1 and not dexDone and f == 1300 then
        dexDone = true
        console:log("DEXCAND ---- species " .. tostring(observed) .. " ----")
        if DEX_EWRAM then
            dexDiff("EWRAM", dexBefore1, emu:readRange(EWRAM_BASE, EWRAM_SPAN),
                    EWRAM_BASE, observed)
        else
            dexDiff("SB1", dexBefore1, emu:readRange(dexBase1, SPAN1), dexBase1, observed)
            dexDiff("SB2", dexBefore2, emu:readRange(dexBase2, SPAN2), dexBase2, observed)
        end
        console:log("DEXCAND ---- end ----")
    end
    if f == 1400 then
        H.assertTrue("wild trampoline fired (encounter happened)", fired)
        H.assertTrue("a forcing level was found and written", forcedLevel ~= nil)
        if EXPECT_CAUGHT then
            -- Same forced roll, flag set: the legendary must be withheld.
            H.assertTrue("already-caught legendary NOT offered (got "
                         .. tostring(observed) .. ")", observed ~= EXPECT)
        else
            -- THE POSITIVE ASSERTION.
            H.assertEq("shim returned the character's LEGENDARY", observed, EXPECT)
        end
        H.finish()
    end
end)
