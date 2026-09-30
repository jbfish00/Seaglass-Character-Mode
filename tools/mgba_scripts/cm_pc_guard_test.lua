-- LIVE e2e for the PC second guard (CM_PSSLastMonGuard) on the TEST-ONLY ROM
-- build/seaglass_cm_pcguard.gba (tools/tests/build_pcguard_testrom.py).
--
-- The rule (ROWE's IsRemovingLastAllowedPartyMon): the storage system must
-- refuse to DEPOSIT the party's last alive, non-egg, ON-ROSTER mon.
--
-- Fixture, built in-game with the ROM's own constructors (never a synthesised
-- mon): from mart_inside.ss, with Character Mode OFF, press A at the clipboard
-- -> giveegg Horsea -> the real hatch -> party [Torchic, Horsea(alive)]. Then
-- turn Character Mode ON for CM_CHAR and press A again -> the SHIPPED PC script
-- -> the real storage system. Choose DEPOSIT, pick party slot 0 (Torchic),
-- DEPOSIT.
--
-- ⭐ WHY THIS FIXTURE DISCRIMINATES: with an alive Horsea beside it, VANILLA
-- lets Torchic go (CountPartyAliveNonEggMonsExcept(0) == 1). Only the guard
-- refuses, and only for a character who has Torchic but not Horsea:
--   BRENDAN (39): Torchic ON,  Horsea OFF -> refused -> Torchic stays in party
--   MISTY   (10): Torchic OFF, Horsea ON  -> allowed -> Torchic in the PC
--   CM off                                -> allowed -> Torchic in the PC
-- and the --no-guard ROM must let BRENDAN deposit (the negative control).
--
-- ⭐ ASSERT THE SWAP, NOT A COUNT: Torchic's personality is latched at frame 8
-- and looked for in the PC's box memory and in the party. Checked while the PC
-- is still open, BEFORE the exit sweep runs (which would box Horsea for
-- Brendan and muddy any count).
--
-- Env: CM_CHAR (0 = Character Mode off), EXPECT deposited|refused,
--      CM_SWEEP_ADDR, CM_PSS_ADDR, CM_GUARD_ADDR (all derived by the runner).
-- Needs MGBA_HEADLESS_DEBUGGER=1 for the breakpoints.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "0")
local EXPECT  = os.getenv("EXPECT") or "refused"
local SWEEP   = tonumber(os.getenv("CM_SWEEP_ADDR") or "0")
local PSS     = tonumber(os.getenv("CM_PSS_ADDR") or "0")
local GUARD   = tonumber(os.getenv("CM_GUARD_ADDR") or "0")
local SHOTS   = os.getenv("CM_SHOTS") or "tools/savestates"
local TAG     = (CM_CHAR == 0 and "off" or ("c" .. CM_CHAR)) .. "_" .. EXPECT

local FLAG_CHARACTER_MODE = 0x2B0
local VAR_CM_CHAR         = 0x40E4
local STORAGE_SCAN_BYTES  = 0x8600

local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end
local function partySlot(i) return H.gPlayerParty + i * H.PARTY_STRIDE end
local function inStorage(pers)
    local base = emu:read32(H.gPokemonStoragePtr)
    if base == 0 or pers == 0 then return nil end
    for off = 0, STORAGE_SCAN_BYTES - 4 do
        if emu:read32(base + off) == pers then return off end
    end
    return nil
end
local function inParty(pers)
    for i = 0, 5 do if emu:read32(partySlot(i)) == pers then return i end end
    return nil
end
local function shot(name) emu:screenshot(SHOTS .. "/pcguard_" .. TAG .. "_" .. name .. ".png") end

local torchic
H.onFrame(function(f)
    if f ~= 8 then return end
    torchic = emu:read32(partySlot(0))
    H.clearFlag(FLAG_CHARACTER_MODE)       -- the hatch must happen with CM OFF
    H.log(("start party=%d torchic=0x%08X"):format(emu:read8(H.gPlayerPartyCount), torchic))
end)

-- The hatch tail ends in the shipped sweep; with CM off it is a no-op, and its
-- entry is the "hatch finished" signal.
local hatchedAt, pssAt, guardHits = nil, nil, 0
H.breakpoint("sweep", SWEEP, function(fr)
    if hatchedAt == nil and pssAt == nil then
        hatchedAt = fr
        H.log(("hatch finished (sweep entered) f=%d party=%d"):format(
            fr, emu:read8(H.gPlayerPartyCount)))
    end
end)
H.breakpoint("pss", PSS, function(fr)
    if pssAt == nil then pssAt = fr; H.log(("storage system opened f=%d"):format(fr)) end
end)
if GUARD ~= 0 then
    H.breakpoint("guard", GUARD, function(fr)
        guardHits = guardHits + 1
        H.log(("CM_PSSLastMonGuard entered f=%d slot(r0)=%d lr=0x%08X"):format(
            fr, emu:readRegister("r0"), emu:readRegister("lr")))
    end)
end

-- Walk to the clipboard (the proven route), press A once: the hatch.
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
H.onFrame(function(f)
    if phase == "hatching" or phase == "pc" or f < nextAt then return end
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
        if hatchedAt == nil then H.press(K.LEFT, 8) end
        phase = "talk"; nextAt = f + 30
    elseif phase == "talk" then
        if hatchedAt == nil then H.press(K.A, 6) end
        phase = "hatching"; nextAt = f + 30
    end
end)

-- Through the hatch scene with B (A would open a nickname prompt path).
local mashAt = nil
H.onFrame(function(f)
    if phase ~= "hatching" or hatchedAt then return end
    if mashAt == nil then mashAt = f + 40 end
    if f >= mashAt then H.press(K.B, 4); mashAt = f + 22 end
end)

-- Second press: CM on for the character under test, then the PC.
local secondAt
H.onFrame(function(f)
    if not hatchedAt or secondAt then return end
    if f < hatchedAt + 150 then return end
    shot("0_hatched")
    if CM_CHAR ~= 0 then
        H.setFlag(FLAG_CHARACTER_MODE); H.setVar(VAR_CM_CHAR, CM_CHAR)
    end
    H.log(("party after hatch=%d; CM %s"):format(emu:read8(H.gPlayerPartyCount),
        CM_CHAR ~= 0 and ("ON char " .. CM_CHAR) or "OFF"))
    -- The clipboard is UP from the stall position: the route's `Aup` press is
    -- the one that opens it (cm_pc_exit_test.lua's note). The hatch scene
    -- leaves the player facing down, so turn up first.
    H.press(K.UP, 6); H.press(K.A, 6)
    secondAt = f; phase = "pc"
end)

-- Inside the PC: the menu is Withdraw / Deposit / Move / Move items / See ya.
-- DOWN, A = Deposit (the storage UI loads with the cursor on party slot 0);
-- A = the mon's action menu; A = STORE; A = confirm the box (or dismiss the
-- refusal). Generous waits; each step is shot.
local STEPS = {
    {60,  nil,     "1_pc_menu"},
    {10,  K.DOWN,  nil},
    {40,  K.A,     "2_deposit_mode"},
    {160, K.A,     "3_mon_menu"},
    {60,  K.A,     "4_store_menu"},       -- A = STORE
    -- Allowed: "Deposit in which BOX?" -> A confirms the default box.
    -- Refused: "That's your last POKeMON!" -> A just dismisses it.
    {90,  K.A,     "5_after_store"},
    {150, nil,     "6_result"},
}
local stepI, stepAt, checked = 1, nil, false
H.onFrame(function(f)
    if not pssAt or checked then return end
    if stepAt == nil then stepAt = pssAt end
    local s = STEPS[stepI]
    if s == nil then
        checked = true
        local box, slot = inStorage(torchic), inParty(torchic)
        H.log(("RESULT torchic box=%s partySlot=%s guardHits=%d"):format(
            tostring(box), tostring(slot), guardHits))
        H.assertTrue("the hatch left an alive second mon (party of 2)",
                     emu:read8(H.gPlayerPartyCount) >= 1 and hatchedAt ~= nil)
        H.assertTrue("the storage system opened", pssAt ~= nil)
        if EXPECT == "refused" then
            H.assertTrue("the deposit reached CM_PSSLastMonGuard", guardHits > 0)
            H.assertTrue("Torchic (the last on-roster mon) is still in the party", slot ~= nil)
            H.assertTrue("...and NOT in the PC", box == nil)
        else
            H.assertTrue("Torchic was deposited into the PC", box ~= nil)
            H.assertTrue("...and left the party", slot == nil)
        end
        H.finish()
        return
    end
    if f >= stepAt + s[1] then
        if s[3] then shot(s[3]) end
        if s[2] then H.press(s[2], 8) end
        stepI = stepI + 1; stepAt = f
    end
end)

H.onFrame(function(f)
    if f == 6000 and not checked then
        H.log(("timeout: phase=%s hatchedAt=%s pssAt=%s"):format(
            phase, tostring(hatchedAt), tostring(pssAt)))
        H.assertTrue("reached the deposit (timeout)", false)
        H.finish()
    end
end)
