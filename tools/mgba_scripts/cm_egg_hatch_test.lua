-- LIVE egg-hatch e2e on the TEST-ONLY ROM (build/seaglass_cm_eggtest.gba, built
-- by tools/tests/build_egg_testrom.py).
--
-- ../game_plans/rowe_parity.md §13.21 item 1: the hatch hook was verified
-- statically and by every pre-existing live layer, but no hatch had ever been
-- WALKED in an emulator here. This walks one.
--
-- From mart_inside.ss we drive to the mart clipboard (the same position-reactive
-- route cm_trade_test.lua uses) and press A. In the test ROM the clipboard runs
--   giveegg <species> ; setvar 0x8004,1 ; goto 0x0832EEEF
-- and everything from that goto onward is SHIPPED, unmodified: the spliced
-- tail, the replayed special EggHatch / waitstate / releaseall, and the
-- callnative into CM_SweepPartyToPCNative. So the bytes under test are the ones
-- that ship; only the entry is a test shim.
--
-- ⭐ THE ASSERTION IS A SWAP, NOT A COUNT (§13.20). We capture the EGG's
-- personality out of party slot 1 before the hatch, and afterwards require that
-- exact 32-bit value to be either in the PC (enforced) or still in the party
-- (control). A count alone also holds when neither the give nor the sweep
-- happened; a personality that moved cannot be produced by a dead feature.
--
-- ⚠️ AND A COUNT IS ACTIVELY WRONG HERE, which the first version of this layer
-- learned the hard way. On the MISTY run the sweep does fire and does box a
-- mon -- the pre-existing STARTER, which is off Misty's roster -- while keeping
-- the Horsea. So the party count is 1 in both the enforced and the
-- discriminating run, and only "which personality moved" tells them apart.
-- That also makes MISTY a stronger control than "mode off": it proves the sweep
-- made a per-species decision keyed on the ACTIVE CHARACTER, rather than
-- boxing whatever arrived last.
--
-- Env:
--   CM_ON        1/0        -- Character Mode active for this run
--   CM_CHAR      int        -- active character id when CM_ON
--   EXPECT       box|party  -- where the hatchling must end up
--   CM_SWEEP_ADDR 0x...     -- CM_SweepPartyToPCNative, derived from build/cm.elf
--                              by the runner (never hardcoded: it moves on every
--                              shim rebuild, and a stale breakpoint here would
--                              report "the tail was never reached" on a ROM
--                              where it plainly was)
-- Needs MGBA_HEADLESS_DEBUGGER=1 for the breakpoint.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local CM_ON   = (os.getenv("CM_ON") == "1")
local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "1")
local EXPECT  = os.getenv("EXPECT") or "box"
local SWEEP   = tonumber(os.getenv("CM_SWEEP_ADDR") or "0")

local FLAG_CHARACTER_MODE = 0x2B0
local VAR_CM_CHAR         = 0x40E4
local STORAGE_SCAN_BYTES  = 0x8600   -- covers struct PokemonStorage's box array

local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end

local function partySlot(i) return H.gPlayerParty + i * H.PARTY_STRIDE end

-- Byte-wise so no assumption is made about where in struct PokemonStorage the
-- box array starts or how it is strided -- only that a boxed mon still carries
-- its personality as its first four bytes, which is what makes the value a
-- usable fingerprint in the first place.
local function inStorage(pers)
    local base = emu:read32(H.gPokemonStoragePtr)
    if base == 0 then return nil end
    local b0 = pers & 0xFF
    for off = 0, STORAGE_SCAN_BYTES - 4 do
        if emu:read8(base + off) == b0
            and emu:read8(base + off + 1) == ((pers >> 8) & 0xFF)
            and emu:read8(base + off + 2) == ((pers >> 16) & 0xFF)
            and emu:read8(base + off + 3) == ((pers >> 24) & 0xFF) then
            return off
        end
    end
    return nil
end

local function inParty(pers)
    for i = 0, 5 do
        if emu:read32(partySlot(i)) == pers then return i end
    end
    return nil
end

local before, egg = {}, {}
H.onFrame(function(f)
    if f ~= 8 then return end
    before.party = emu:read8(H.gPlayerPartyCount)
    if CM_ON then
        H.setFlag(FLAG_CHARACTER_MODE)
        H.setVar(VAR_CM_CHAR, CM_CHAR)
        H.log(("CM ON char=%d flag=%d var=%d"):format(
            CM_CHAR, H.getFlag(FLAG_CHARACTER_MODE), H.getVar(VAR_CM_CHAR)))
    else
        H.clearFlag(FLAG_CHARACTER_MODE)
        H.log("CM OFF (control)")
    end
    H.log("start party=" .. before.party)
end)

-- Prove the SHIPPED tail was reached. The sweep is the last command in it, so
-- its entry firing means the goto landed, the replayed hatch ran, and the
-- waitstate released -- the whole hook, in order.
local swept = nil
if SWEEP ~= 0 then
    H.breakpoint("sweep", SWEEP, function(fr)
        if swept == nil then
            swept = fr
            H.log(("CM_SweepPartyToPCNative entered f=%d party=%d"):format(
                fr, emu:read8(H.gPlayerPartyCount)))
        end
    end)
end

-- Navigate to the clipboard: LEFT till x stalls, UP till y stalls, an A-up
-- probe, then face LEFT + A. Verbatim from cm_trade_test.lua's proven route.
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
H.onFrame(function(f)
    if phase == "done" or f < nextAt then return end
    local x, y = pos()
    if phase == "left" then
        stall = (x == lastx) and stall + 1 or 0
        if stall >= 2 then phase, stall, lasty = "up", 0, -1; nextAt = f + 6; return end
        lastx = x; H.press(K.LEFT, 10, 2); nextAt = f + 20
    elseif phase == "up" then
        stall = (y == lasty) and stall + 1 or 0
        if stall >= 2 then phase = "Aup"; nextAt = f + 6; return end
        lasty = y; H.press(K.UP, 10, 2); nextAt = f + 20
    elseif phase == "Aup" then
        H.press(K.A, 6); phase = "faceL"; nextAt = f + 80
    elseif phase == "faceL" then
        H.press(K.LEFT, 8); phase = "talk"; nextAt = f + 30
    elseif phase == "talk" then
        H.log(("interact at (%d,%d)"):format(x, y)); H.press(K.A, 6)
        phase = "done"; nextAt = f + 30
    end
end)

-- After the interaction, tap B on a cadence: B advances the "Huh?" msgbox and
-- the "hatched from the egg!" message, and -- the reason it is B and not A --
-- DECLINES the nickname prompt. Mashing A there opens the naming screen and the
-- run wedges in a keyboard it has no route out of.
local mashAt = nil
H.onFrame(function(f)
    if phase ~= "done" then return end
    if mashAt == nil then mashAt = f + 20 end
    if f >= mashAt then H.press(K.B, 4); mashAt = f + 22 end
end)

-- Latch the egg the moment it exists, before anything can hatch it.
H.onFrame(function(f)
    if egg.pers or phase ~= "done" then return end
    local n = emu:read8(H.gPlayerPartyCount)
    if n == before.party + 1 then
        local m = partySlot(before.party)
        local p = emu:read32(m)
        if p ~= 0 then
            egg.pers = p
            egg.sanity = emu:read8(m + 19)
            egg.count = n
            H.log(("egg latched f=%d slot=%d pers=0x%08X sanity=0x%02X"):format(
                f, before.party, p, egg.sanity))
        end
    end
end)

local endAt = nil
H.onFrame(function(f)
    if swept and endAt == nil then endAt = f + 90 end
    if endAt and f == endAt then
        emu:screenshot("tools/savestates/egg_" ..
            (CM_ON and ("on_c" .. CM_CHAR) or "off") .. "_" .. EXPECT .. ".png")
        local party = emu:read8(H.gPlayerPartyCount)
        local pers = egg.pers or 0
        local box = (pers ~= 0) and inStorage(pers) or nil
        local slot = (pers ~= 0) and inParty(pers) or nil
        H.log(("after: party=%d pers=0x%08X box=%s partySlot=%s"):format(
            party, pers, tostring(box), tostring(slot)))

        H.assertTrue("giveegg put an egg in the party", egg.count == before.party + 1)
        H.assertTrue("the new party member IS an egg (sanity bit 2)",
                     (egg.sanity or 0) & 0x04 ~= 0)
        H.assertTrue("the shipped hatch tail reached the sweep", swept ~= nil)
        -- ⚠️ NOT a party count. The count is the WRONG assertion here and the
        -- first version of this layer got it wrong: on the MISTY run the sweep
        -- correctly boxes the pre-existing starter (off HER roster) and keeps
        -- the hatchling, so the count lands on 1 in both the enforced and the
        -- discriminating case while the two runs differ in exactly the way that
        -- matters. Assert WHICH mon moved, not how many.
        if EXPECT == "box" then
            H.assertTrue("the hatchling's personality is in the PC", box ~= nil)
            H.assertTrue("...and no longer in the party", slot == nil)
        else
            H.assertTrue("the hatchling's personality is still in the party",
                         slot ~= nil)
            H.assertTrue("...and not in the PC", box == nil)
        end
        H.finish()
    end
    if f == 4000 and endAt == nil then
        H.log("timeout: phase=" .. phase .. " swept=" .. tostring(swept)
              .. " egg=" .. tostring(egg.pers))
        H.assertTrue("the shipped hatch tail reached the sweep (timeout)", false)
        H.finish()
    end
end)
