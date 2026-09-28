-- Live proof that the engine indexes the RELOCATED dynamic multichoice
-- callback table (roster display, 2026-09-27).
--
-- Runs against build/seaglass_cm_dyntest.gba (tools/tests/build_dynmenu_testrom.py
-- <set>): the mart clipboard opens a 3-row dynmultichoice with callback set CB_SET.
-- Breakpoints sit on the instruction AFTER each of the four PC-relative loads
-- of the table base, so the loaded register is the table address the engine
-- actually used, and on callback set 1's three functions (the ROM's own
-- item-icon set, copied into the new table).
--
--   CB_SET=1  -> every load reads the NEW table, and set 1's OnInit,
--                OnSelectionChanged and OnDestroy all run
--   CB_SET=2  -> control: the reserved slot is NULL, so the loads still read
--                the new table but NO set-1 callback runs, and the menu still
--                opens and closes normally
--
-- Run: build the test ROM, then
--   MGBA_HEADLESS_DEBUGGER=1 CM_EXPECT_CHECKS=7 CB_SET=1 ./tools/mgba_src/build/mgba-headless \
--     --script tools/mgba_scripts/cm_dynmenu_table_test.lua \
--     -t tools/savestates/mart_inside.ss build/seaglass_cm_dyntest.gba
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY

local CB_SET = tonumber(os.getenv("CB_SET") or "1")
local NEW_TABLE = tonumber(os.getenv("DYN_EVENT_TABLE_ADDR") or "0x08FA4000")
local VAR_RESULT = 0x020055F0
local MULTI_B_PRESSED = 127

-- (breakpoint address, register): the instruction after each table load
local LOADS = {
    init   = { 0x081F0118, "r2" },   -- OnInit
    init2  = { 0x081F01CE, "r3" },   -- OnSelectionChanged, at init
    change = { 0x081EFFB6, "r3" },   -- OnSelectionChanged, on cursor move
    destroy= { 0x081F04DC, "r3" },   -- OnDestroy
}
local SET1 = { onInit = 0x081EFC00, onChange = 0x081EFC7C, onDestroy = 0x081EFD24 }

local seen, bad, hits = {}, {}, {}
for name, l in pairs(LOADS) do
    seen[name], bad[name] = 0, {}
    emu:setBreakpoint(function()
        local v = emu:readRegister(l[2])
        seen[name] = seen[name] + 1
        if v ~= NEW_TABLE then table.insert(bad[name], string.format("0x%08X", v)) end
    end, l[1])
end
for name, a in pairs(SET1) do
    hits[name] = 0
    emu:setBreakpoint(function() hits[name] = hits[name] + 1 end, a)
end

local function pos()
    local s = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(s), emu:read16(s + 2)
end

-- Same position-reactive route to the clipboard as cm_trade_test.lua.
-- ⚠️ MEASURED: the menu opens on the route's FIRST A (the up-facing probe,
-- frame ~245 from mart_inside.ss), not the left-facing one the trade test
-- needs -- and that second A then picked row 0 and closed it. So the menu is
-- detected by its own OnInit load, whatever phase the walk is in.
-- ⚠️ The cursor-move load (and set 1's OnSelectionChanged, via the init2
-- path) ALSO run once at init, so the move checks count only what happens
-- after the first DOWN press.
local phase, lastx, lasty, stall, nextAt = "left", -1, -1, 0, 30
local openedAt, movedAt, closedAt
local changeBase, onChangeBase = 0, 0
H.onFrame(function(f)
    if f == 8 then emu:write16(VAR_RESULT, 0x1234) end
    if seen.init > 0 and openedAt == nil then
        openedAt = f; phase = "shoot_open"; nextAt = f + 40
    end
    if f < nextAt then return end
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
        phase = "wait_open"; nextAt = f + 10
    elseif phase == "wait_open" then
        if f > 3000 then phase = "done" end
        nextAt = f + 1
    elseif phase == "shoot_open" then
        emu:screenshot(("tools/savestates/dynmenu_set%d_open.png"):format(CB_SET))
        changeBase, onChangeBase = seen.change, hits.onChange
        phase = "move"; nextAt = f + 1
    elseif phase == "move" then
        -- Closed-loop: mash DOWN until a NEW change-path load is observed
        -- (short taps get dropped under JOY_REPEAT).
        if seen.change > changeBase then
            movedAt = f; phase = "shoot_moved"; nextAt = f + 40
        elseif f - openedAt > 600 then phase = "close"; nextAt = f + 1
        else H.press(K.DOWN, 8, 8); nextAt = f + 20 end
    elseif phase == "shoot_moved" then
        emu:screenshot(("tools/savestates/dynmenu_set%d_moved.png"):format(CB_SET))
        phase = "close"; nextAt = f + 1
    elseif phase == "close" then
        if seen.destroy > 0 then
            closedAt = f; phase = "settle"; nextAt = f + 60
        elseif f > (openedAt or 0) + 1500 then phase = "done"
        else H.press(K.B, 8, 8); nextAt = f + 20 end
    elseif phase == "settle" then
        phase = "done"
    end
    if phase == "done" then
        phase = "finished"
        H.log(("set=%d opened=%s moved=%s closed=%s loads init=%d init2=%d change=%d destroy=%d")
            :format(CB_SET, tostring(openedAt), tostring(movedAt), tostring(closedAt),
                    seen.init, seen.init2, seen.change, seen.destroy))
        H.log(("set-1 callbacks: onInit=%d onChange=%d onDestroy=%d")
            :format(hits.onInit, hits.onChange, hits.onDestroy))
        H.assertTrue("OnInit load read the NEW table (" .. table.concat(bad.init, ",") .. ")",
            seen.init > 0 and #bad.init == 0 and #bad.init2 == 0)
        H.assertTrue("cursor-move load read the NEW table after a DOWN press (" .. table.concat(bad.change, ",") .. ")",
            seen.change > changeBase and #bad.change == 0)
        H.assertTrue("OnDestroy load read the NEW table (" .. table.concat(bad.destroy, ",") .. ")",
            seen.destroy > 0 and #bad.destroy == 0)
        local want = (CB_SET == 1)
        H.assertEq("set 1 OnInit ran", hits.onInit > 0, want)
        H.assertEq("set 1 OnSelectionChanged ran on a cursor move", hits.onChange > onChangeBase, want)
        H.assertEq("set 1 OnDestroy ran", hits.onDestroy > 0, want)
        H.assertEq("menu closed by B (VAR_RESULT)", emu:read16(VAR_RESULT), MULTI_B_PRESSED)
        H.finish()
    end
end)
