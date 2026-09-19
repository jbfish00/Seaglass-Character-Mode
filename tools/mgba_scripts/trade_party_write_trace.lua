-- PROBE (not a suite layer): drive an ALLOWED in-game trade all the way through
-- the cutscene and observe WHAT WRITES gPlayerParty.
--
-- ⭐ WHY. tools/tests/check_acquisition_paths.py pins every writer of
-- gPlayerPartyCount; tools/tests/check_party_writes.py pins every mon-sized
-- COPY into gPlayerParty. Between them they are meant to make a new
-- acquisition path a failing check rather than a silent arrival. A trade is the
-- shape that defeats both in Platinum (../game_plans/rowe_parity.md, workspace
-- lesson #1): it fills the slot its partner vacated, so the COUNT never moves,
-- and if the engine writes the slot by any means other than a call with
-- r2 == 100 the COPY scan cannot see it either.
--
-- cm_trade_test.lua deliberately stops the instant CM_TradeCheck decides,
-- "before the allow path's trade cutscene ... can matter" -- so in this repo the
-- allow path's party write has never been observed. This probe observes it.
--
-- Method: the SHIPPED trade junction/wrapper on the trade test ROM (idx 2,
-- SEASOR, receives Horsea 116), CM ON as Misty (char 10) so Horsea is ON the
-- roster and the gate allows. After the decision we keep driving the scene and
-- watch plaintext fields of every party slot -- PID (+0), nickname (+8, 10
-- bytes) and level (+0x54) are NOT inside the encrypted substructs, so a slot
-- being overwritten is visible without decrypting anything.
--
-- Env: CM_CHAR (default 10), CM_WP=1 to also arm WRITE_CHANGE watchpoints on
-- each slot's PID word and report the writing PC/LR (slow: watchpoints
-- single-step). Needs MGBA_HEADLESS_DEBUGGER=1 for the breakpoint.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "10")
local WANT_WP = (os.getenv("CM_WP") == "1")
local PARTY   = H.gPlayerParty
local STRIDE  = H.PARTY_STRIDE
local SHOTS   = "tools/savestates/"

local function slotFingerprint(i)
    local base = PARTY + i * STRIDE
    local nick = {}
    for k = 0, 9 do
        local c = emu:read8(base + 8 + k)
        if c == 0xFF then break end
        nick[#nick + 1] = string.format("%02X", c)
    end
    return string.format("pid=%08X ot=%08X nick=%s lv=%d",
        emu:read32(base), emu:read32(base + 4),
        table.concat(nick, ""), emu:read8(base + 0x54))
end

local function snapshot()
    local t = {}
    for i = 0, 5 do t[i] = slotFingerprint(i) end
    t.count = emu:read8(H.gPlayerPartyCount)
    return t
end

local before, decided, ran = nil, nil, false

H.onFrame(function(f)
    if f ~= 8 then return end
    H.setFlag(0x2B0)                       -- FLAG_CHARACTER_MODE
    H.setVar(0x40E4, CM_CHAR)              -- VAR_CM_CHAR
    before = snapshot()
    H.log(("CM ON char=%d partyCount=%d"):format(CM_CHAR, before.count))
    for i = 0, 5 do H.log(("  before slot%d %s"):format(i, before[i])) end
end)

-- Prove the gate ran and allowed, exactly as cm_trade_test does -- but do NOT
-- stop here. The whole point of this probe is what happens afterwards.
local STORE = tonumber(os.getenv("CM_TRADECHECK_STORE") or "0x08ED25B6")
H.breakpoint("TradeCheck", STORE, function(fr)
    if ran then return end
    ran = true
    decided = emu:readRegister("r4")
    H.log(("CM_TradeCheck decision=%d f=%d"):format(decided, fr))
end)

-- WRITE_CHANGE watchpoints on each slot's PID word. Optional because they
-- single-step the core; the fingerprint poll below finds WHEN without them.
local wpHits, wpSeen, wpArmed = 0, {}, false
local WP_AT = tonumber(os.getenv("CM_WP_AT") or "1600")
local function armWatchpoints()
    for i = 0, 5 do
        emu:setWatchpoint(function()
            wpHits = wpHits + 1
            local pc, lr = emu:readRegister("pc"), emu:readRegister("lr")
            local key = string.format("%08X/%08X", pc, lr)
            if not wpSeen[key] then
                wpSeen[key] = true
                H.log(("WP slot%d pc=0x%08X lr=0x%08X r0=0x%08X r1=0x%08X r2=0x%08X")
                    :format(i, pc, lr, emu:readRegister("r0"),
                            emu:readRegister("r1"), emu:readRegister("r2")))
            end
        end, PARTY + i * STRIDE, 5)
    end
    H.log("watchpoints armed on all six slot PIDs")
end

-- Navigate to the mart clipboard (the proven route from cm_trade_test.lua).
local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
H.onFrame(function(f)
    if ran or f < nextAt then return end
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
        phase = "done"; nextAt = f + 100000
    end
end)

-- After the decision: drive the cutscene and poll for the party changing.
local armedAt, changedAt, changedSlots = nil, nil, {}
H.onFrame(function(f)
    if not ran then return end
    if armedAt == nil then
        armedAt = f
        H.log("decision seen; driving the trade scene from f=" .. f)
    end
    -- arm late: watchpoints single-step the core, and the party write lands
    -- ~1850 frames after the decision. CM_WP_AT trims the stepped window.
    if WANT_WP and not wpArmed and f >= armedAt + WP_AT then
        wpArmed = true; armWatchpoints()
    end

    -- the trade scene is text + animation; A advances, and unlike the egg
    -- hatch there is no naming screen to fall into on this path.
    if f > armedAt + 20 and f % 40 == 0 then H.press(K.A, 8, 20) end

    if f % 60 == 0 and changedAt == nil and before then
        local now = snapshot()
        for i = 0, 5 do
            if now[i] ~= before[i] then
                changedSlots[#changedSlots + 1] = i
                H.log(("slot%d CHANGED at f=%d"):format(i, f))
                H.log(("   before %s"):format(before[i]))
                H.log(("   after  %s"):format(now[i]))
            end
        end
        if #changedSlots > 0 then
            changedAt = f
            H.log(("partyCount %d -> %d"):format(before.count, now.count))
            emu:screenshot(SHOTS .. "trade_probe_changed.png")
        end
    end

    if f % 900 == 0 then
        emu:screenshot(SHOTS .. ("trade_probe_f%d.png"):format(f))
    end

    if f == armedAt + 5400 or (changedAt and f == changedAt + 300) then
        emu:screenshot(SHOTS .. "trade_probe_end.png")
        local now = snapshot()
        for i = 0, 5 do H.log(("  after slot%d %s"):format(i, now[i])) end
        H.log(("wpHits=%d distinct=%d"):format(wpHits, (function()
            local n = 0; for _ in pairs(wpSeen) do n = n + 1 end; return n end)()))
        H.assertEq("CM_TradeCheck allowed the trade", decided, 1)
        H.assertTrue("a party slot was overwritten by the trade",
                     changedAt ~= nil)
        H.assertEq("gPlayerPartyCount is unchanged by the trade",
                   now.count, before.count)
        H.finish()
    end
end)
