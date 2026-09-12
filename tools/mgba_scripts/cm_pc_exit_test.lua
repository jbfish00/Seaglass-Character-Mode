-- LIVE PC-exit e2e on the TEST-ONLY ROM (build/seaglass_cm_pctest.gba, built by
-- tools/tests/build_pc_testrom.py).
--
-- ../game_plans/rowe_parity.md §13.31 item 2. The PC-exit hook shipped in four
-- games on static evidence alone -- no port had ever CLOSED A PC in an emulator
-- and watched the sweep run. This does. §13.20 is why it matters: four live
-- layers in three repos were found dead behind a fully green static suite.
--
-- From mart_inside.ss we drive to the mart clipboard (the same position-reactive
-- route cm_trade_test.lua and cm_egg_hatch_test.lua use) and press A. In the
-- test ROM the clipboard runs
--   giveegg 116 ; goto 0x0830E1E1
-- and everything from that goto onward is SHIPPED, unmodified: the overlay, the
-- replayed `special 0x3F` + `waitstate` that opens the storage system and waits
-- for it to close, and the `callnative CM_SweepPartyToPCNative` that runs when
-- it does. Only the entry is a test shim.
--
-- ⭐ THE ASSERTION IS A SWAP, NOT A COUNT. We latch the STARTER's personality
-- out of party slot 0 at frame 8, and afterwards require that exact 32-bit value
-- to be in the PC (enforced) or still in the party (control). A count cannot
-- tell those apart here: the egg anchor keeps the party at 2 in the control runs
-- and the sweep's compaction leaves it at 1 in the enforced run only because
-- something moved -- and "1" is also what a party that never got its egg looks
-- like. A personality that changed container cannot be produced by a dead hook.
--
-- ⚠️ THE EGG IS LOAD-BEARING (see build_pc_testrom.py): with the savestate's
-- one-mon party the never-empty rule keeps the starter for EVERY character, so
-- without the anchor every run is identical and the layer discriminates nothing.
--
-- ⭐ RED IS A STRONGER CONTROL THAN "MODE OFF": the starter is ON Red's roster
-- and OFF Misty's (measured -- layer 4h's MISTY run boxes this very mon), so the
-- RED run proves the sweep made a per-species decision keyed on the ACTIVE
-- CHARACTER rather than boxing whatever it found.
--
-- ⭐⭐ AND IT BREAKPOINTS THE STORAGE SYSTEM'S OWN HANDLER, gSpecials[0x3F],
-- passed in by the runner (read out of the BUILT ROM's table via
-- tools/character_mode/pc_hook.py, which in turn verifies the table address
-- against the literal ScrCmd_special loads -- never hardcoded here, and never
-- copied from a sibling: Lazarus's table is at 0x0828CBF4 and this one is at
-- 0x0826DD68). Retrofitted 2026-09-11 (rowe_parity.md §13.40 item 4) to match
-- the other two Lua ports; the previous version inferred "the PC opened" from
-- how long the script stayed blocked after the interaction, which is sound but
-- indirect -- it measures the WAIT, not the storage system.
--
-- ⭐ The B-mash PAUSES while the PC is open, so the open window is something
-- this layer controls rather than an accident of the mash cadence. Left
-- running, the mash backs out of the menu in the same frame it appears
-- (measured 29 frames in the sibling ports).
--
-- Env:
--   CM_ON        1/0        -- Character Mode active for this run
--   CM_CHAR      int        -- active character id when CM_ON
--   EXPECT       box|party  -- where the STARTER must end up
--   CM_PSS_ADDR  0x...     -- gSpecials[0x3F], the storage system's handler,
--                             derived from the built ROM by the runner
--   CM_SWEEP_ADDR 0x...     -- CM_SweepPartyToPCNative, derived from build/cm.elf
--                              by the runner (never hardcoded: it moves on every
--                              shim rebuild, and a stale breakpoint here would
--                              report "the PC exit never reached the sweep" on a
--                              ROM where it plainly did)
-- Needs MGBA_HEADLESS_DEBUGGER=1 for the breakpoint.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local CM_ON   = (os.getenv("CM_ON") == "1")
local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "1")
local EXPECT  = os.getenv("EXPECT") or "box"
local SWEEP   = tonumber(os.getenv("CM_SWEEP_ADDR") or "0")
local PSS     = tonumber(os.getenv("CM_PSS_ADDR") or "0")
-- The PC is opened, HELD open, then closed.
local HOLD_OPEN = 90

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
-- its personality as its first four bytes.
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

local before = {}
H.onFrame(function(f)
    if f ~= 8 then return end
    before.party = emu:read8(H.gPlayerPartyCount)
    before.starter = emu:read32(partySlot(0))
    if CM_ON then
        H.setFlag(FLAG_CHARACTER_MODE)
        H.setVar(VAR_CM_CHAR, CM_CHAR)
        H.log(("CM ON char=%d flag=%d var=%d"):format(
            CM_CHAR, H.getFlag(FLAG_CHARACTER_MODE), H.getVar(VAR_CM_CHAR)))
    else
        H.clearFlag(FLAG_CHARACTER_MODE)
        H.log("CM OFF (control)")
    end
    H.log(("start party=%d starter pers=0x%08X"):format(
        before.party, before.starter))
end)

-- Prove the SHIPPED tail was reached. The sweep is the last command before the
-- rejoin, so its entry firing means the overlay's goto landed, the replayed
-- `special 0x3F` opened the storage system, and its waitstate released -- i.e.
-- the PC actually closed. That is the whole claim this layer exists to make.
local swept, sweptParty = nil, nil
if SWEEP ~= 0 then
    H.breakpoint("sweep", SWEEP, function(fr)
        if swept == nil then
            swept = fr
            sweptParty = emu:read8(H.gPlayerPartyCount)
            H.log(("CM_SweepPartyToPCNative entered f=%d party=%d"):format(
                fr, sweptParty))
        end
    end)
end

-- ⭐ The storage system's own handler. This is what turns "the script ran" into
-- "the PC opened": if `special 0x3F` did nothing, its waitstate would release
-- at once, the sweep would still fire, and the hook would look perfectly green
-- while never having involved a PC at all.
local pssAt = nil
if PSS ~= 0 then
    H.breakpoint("pss", PSS, function(fr)
        if pssAt == nil then
            pssAt = fr
            H.log(("storage system special entered f=%d"):format(fr))
        end
    end)
end

-- Navigate to the clipboard: LEFT till x stalls, UP till y stalls, an A-up
-- probe, then face LEFT + A. Verbatim from cm_trade_test.lua's proven route.
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
local interactAt, shotOpen = nil, false
-- A no-op special releases its waitstate almost immediately; the real storage
-- system takes a fade-out, a load and a fade-in. 60 frames is comfortably above
-- the former and comfortably below the ~257 measured here from the handler.
local MIN_UI_FRAMES = 60
H.onFrame(function(f)
    -- ⚠️ STOP NAVIGATING THE MOMENT THE PC IS OPEN. The `Aup` probe's A press
    -- is what actually opens the clipboard script here -- measured: the storage
    -- handler enters at f=245 while the later `talk` press lands at f=352 --
    -- so without this the remaining A presses are delivered INSIDE the storage
    -- UI, where A dives into a box.
    if pssAt then phase = "done"; return end
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
        -- NOT necessarily the press that opens the PC; see the note above.
        H.log(("nav finished, A at (%d,%d) f=%d"):format(x, y, f)); H.press(K.A, 6)
        interactAt = f
        phase = "done"; nextAt = f + 30
    end
end)

-- ⭐ PROOF THE STORAGE UI REALLY OPENED, not just that the script ran through.
-- If `special 0x3F` were a no-op the `waitstate` would release within a frame or
-- two and the sweep would still fire -- the hook would look perfectly green
-- while never having involved a PC at all. Measured: the box view is on screen
-- for ~150 frames here, and a probe run that never presses B leaves it open
-- indefinitely, so the sweep is genuinely gated on the UI CLOSING. The
-- screenshot is durable human-checkable evidence of the same thing.
H.onFrame(function(f)
    if pssAt and f == pssAt + 45 and not shotOpen then
        shotOpen = true
        emu:screenshot("tools/savestates/pcexit_" ..
            (CM_ON and ("on_c" .. CM_CHAR) or "off") .. "_" .. EXPECT ..
            "_open.png")
    end
end)

-- Close the storage system. B backs out of its main menu, and -- the reason it
-- is B and not A -- A would DIVE INTO a box, where this script has no route
-- back out and the run would wedge exactly as mashing A through the hatch scene
-- once did (§13.22). Tapping on a cadence rather than holding, because the menu
-- ignores a held button.
local mashAt = nil
H.onFrame(function(f)
    if phase ~= "done" and not pssAt then return end
    -- ⭐ Hold the PC open for HOLD_OPEN frames after its handler runs, so the
    -- window this layer asserts on is deliberate.
    if pssAt and f < pssAt + HOLD_OPEN then emu:clearKey(K.B); return end
    if mashAt == nil then mashAt = f + 60 end
    if f >= mashAt then H.press(K.B, 4); mashAt = f + 22 end
end)

local endAt = nil
H.onFrame(function(f)
    if swept and endAt == nil then endAt = f + 90 end
    if endAt and f == endAt then
        emu:screenshot("tools/savestates/pcexit_" ..
            (CM_ON and ("on_c" .. CM_CHAR) or "off") .. "_" .. EXPECT .. ".png")
        local party = emu:read8(H.gPlayerPartyCount)
        local pers = before.starter
        local box = inStorage(pers)
        local slot = inParty(pers)
        H.log(("after: party=%d starter=0x%08X box=%s partySlot=%s"):format(
            party, pers, tostring(box), tostring(slot)))

        H.assertTrue("the savestate party had a mon to act on", pers ~= 0)
        H.assertTrue("the egg anchor was added before the PC opened",
                     sweptParty ~= nil and sweptParty == before.party + 1)
        H.assertTrue("closing the PC reached the shipped sweep", swept ~= nil)
        H.log(("storage special f=%s, sweep f=%s -- UI up for %s frames"):format(
            tostring(pssAt), tostring(swept),
            tostring(swept and pssAt and (swept - pssAt))))
        H.assertTrue("the storage system special really ran, BEFORE the sweep",
                     pssAt ~= nil and swept ~= nil and pssAt < swept)
        H.assertTrue("...and the PC stayed open long enough to be real "
                     .. "(not a no-op special)",
                     swept ~= nil and pssAt ~= nil
                     and (swept - pssAt) >= MIN_UI_FRAMES)
        if EXPECT == "box" then
            H.assertTrue("the off-roster starter's personality is in the PC",
                         box ~= nil)
            H.assertTrue("...and no longer in the party", slot == nil)
        else
            H.assertTrue("the starter's personality is still in the party",
                         slot ~= nil)
            H.assertTrue("...and not in the PC", box == nil)
        end
        H.finish()
    end
    if f == 4000 and endAt == nil then
        H.log("timeout: phase=" .. phase .. " swept=" .. tostring(swept)
              .. " pssAt=" .. tostring(pssAt))
        H.assertTrue("closing the PC reached the shipped sweep (timeout)", false)
        H.finish()
    end
end)
