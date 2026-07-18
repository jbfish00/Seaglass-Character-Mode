-- In-situ trade-gate e2e on the TEST-ONLY ROM (build/seaglass_cm_tradetest.gba,
-- built by tools/tests/build_trade_testrom.py). From mart_inside.ss we drive to
-- the mart clipboard (position-reactive: LEFT till blocked, UP till blocked,
-- face LEFT, A) and press A; in the test ROM the clipboard runs
--   lock ; setvar 0x8008,<idx> ; goto <junction[idx]>
-- which lands on the SHIPPED junction overlay -> the SHIPPED per-trade wrapper
-- (copyvar 0x8008->0x8004 ; callnative CM_TradeCheck ; compare VAR_RESULT ;
--  refuse-branch OR special 0x100/0x101 resume). So the bytes under test are
-- exactly what a real trade NPC runs; only the *entry* is a test shim.
--
-- CM_TradeCheck writes gSpecialVar_Result (0x800D = 0x020055F2): 0 = refuse
-- (received species off the active character's roster), 1 = allow. We seed it
-- with a sentinel, breakpoint CM_TradeCheck to PROVE it ran, then read the
-- decision it made. Needs MGBA_HEADLESS_DEBUGGER=1 (breakpoint).
--
-- Env: CM_ON (1/0), CM_CHAR (default 1), EXPECT (expected VAR_RESULT 0/1).
--   idx is baked into the test ROM (default SEASOR idx 2 -> Horsea 116, which
--   is OFF Red's roster but ON Misty's — the discriminating case).
-- We stop right after reading the decision so the allow path never enters the
-- real trade cutscene (which would need a chosen party mon); the refuse path is
-- self-terminating (message + release), so we also confirm party is unchanged.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
-- gSpecialVar_Result: empirically GetVarPointer(0x800D) -> 0x020055F0 in this
-- ROM (verified by reading r0 at CM_TradeCheck's store; the 0x020055F2 that an
-- old ROUTINE_MAP note computed is off by 2). We don't rely on this for the
-- assertion — we read the stored value straight from r4 at the store insn —
-- but keep it for the sentinel/logging.
local VAR_RESULT = 0x020055F0
local CM_ON   = (os.getenv("CM_ON") == "1")
local CM_CHAR = tonumber(os.getenv("CM_CHAR") or "1")
local EXPECT  = tonumber(os.getenv("EXPECT") or "0")

local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end

local before = {}
H.onFrame(function(f)
    if f == 8 then
        emu:write16(VAR_RESULT, 0xFFFF)          -- sentinel: defeats stale-value pass
        before.party = emu:read8(H.gPlayerPartyCount)
        if CM_ON then
            H.setFlag(0x945)                     -- FLAG_CHARACTER_MODE
            H.setVar(0x40E4, CM_CHAR)            -- VAR_CM_CHAR
            H.log(("CM ON char=%d flag=%d var=%d"):format(
                CM_CHAR, H.getFlag(0x945), H.getVar(0x40E4)))
        else
            local a = emu:read32(H.gSaveBlock1Ptr) + H.FLAG_BLOCK + math.floor(0x945/8)
            emu:write8(a, emu:read8(a) & ~(1 << (0x945 % 8)))
            H.log("CM OFF (control)")
        end
        H.log("start party=" .. before.party)
    end
end)

-- Prove CM_TradeCheck runs AND capture its decision at the instant it writes
-- VAR_RESULT. We breakpoint the store itself (0x08ED25BC: strh r4,[r0]) and read
-- the value straight from r4 — address-independent, and taken before the ALLOW
-- path's subsequent special 0x100/0x101 can overwrite VAR_RESULT.
local ran, decided = false, nil
local V8004 = 0x020055D8 + 4*2
H.breakpoint("TradeCheck", 0x08ED25BC, function(fr)
    if not ran then
        ran = true
        decided = { frame = fr, val = emu:readRegister("r4"),
                    addr = emu:readRegister("r0") }
        H.log(("CM_TradeCheck decision=%d @0x%08X f=%d [flag=%d char=%d v8004=%d]"):format(
            decided.val, decided.addr, fr, H.getFlag(0x945), H.getVar(0x40E4),
            emu:read16(V8004)))
    end
end)

-- position-reactive navigate to the clipboard, then interact. This mirrors the
-- proven route from nav_clip (LEFT till x stalls, UP till y stalls, an A-up
-- probe, then face LEFT + A) verbatim — the clipboard sits left of (0,5) and the
-- interaction only registers on the second, left-facing A.
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

-- once CM_TradeCheck has decided, settle briefly then assert and stop (before
-- the allow path's trade cutscene, which needs a chosen party mon, can matter)
local endAt = nil
H.onFrame(function(f)
    if ran and endAt == nil then endAt = f + 40 end
    if endAt and f == endAt then
        emu:screenshot("tools/savestates/trade_" ..
            (CM_ON and ("on_c" .. CM_CHAR) or "off") .. ".png")
        local party = emu:read8(H.gPlayerPartyCount)
        H.assertTrue("CM_TradeCheck ran", ran)
        if decided == nil then
            H.assertEq("CM_TradeCheck set VAR_RESULT", "unset", "0 or 1")
        else
            H.log(("decision f=%d VAR_RESULT=%d (want %d)"):format(
                decided.frame, decided.val, EXPECT))
            H.assertEq("trade VAR_RESULT", decided.val, EXPECT)
        end
        if EXPECT == 0 then
            H.assertEq("party unchanged after refusal", party, before.party)
        end
        H.finish()
    end
    if f == 1500 and not ran then
        H.assertTrue("CM_TradeCheck ran (timeout)", false); H.finish()
    end
end)
