-- Auto-sweep the mart for the cheat-clipboard trigger.
-- For each target column (ENV CM_COLS, default all), walk the open bottom row
-- (y=7, x=0..10) to that column, then walk UP until blocked, then interact
-- (A, wait, A=YES) facing UP. Breakpoint on CM_OpenCodeEntry (0x08ED2270)
-- fires only on the real trigger + YES. On fire: save naming_open.ss/png.
--
-- ENV: CM_COLS="0,1,2,..." columns to test (default 0..10)
--      CM_DIR = interact facing when at top: "U" (default). (future use)
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end

local cols = {}
local colsEnv = os.getenv("CM_COLS")
if colsEnv and colsEnv ~= "" then
    for c in string.gmatch(colsEnv, "[^,]+") do cols[#cols+1] = tonumber(c) end
else
    for c = 0, 10 do cols[#cols+1] = c end
end

local fired, fireFrame, saved = false, nil, false
local firedCol = nil
H.breakpoint("CM_OpenCodeEntry", 0x08ED2270, function(f)
    if not fired then fireFrame = f end
    fired = true
    H.log("*** CM_OpenCodeEntry FIRED frame=" .. f .. " ***")
end)

-- FSM
local ci = 1                -- current column index
local phase = "toRow"       -- toRow -> toCol -> up -> a1 -> wait1 -> a2 -> wait2 -> next
local tphase = 0            -- frame we entered current phase
local upStuckPos, upStuckAt = nil, 0
local curCol = nil

local function enter(p, f) phase = p; tphase = f end

H.onFrame(function(f)
    if fired then
        if not saved and fireFrame and f >= fireFrame + 90 then
            saved = true
            emu:saveStateFile("tools/savestates/naming_open.ss")
            emu:screenshot("tools/savestates/naming_open.png")
            H.log("SAVED naming_open.ss + naming_open.png at f=" .. f .. " col=" .. tostring(firedCol))
            H.log("RESULT fired=true col=" .. tostring(firedCol))
            H.finish()
        end
        return
    end

    if ci > #cols then
        H.log("RESULT fired=false (all columns tried)")
        H.finish(); fired = "done"; return
    end
    local x, y = pos()
    curCol = cols[ci]

    if phase == "toRow" then
        -- get to y=7 (bottom highway)
        if y < 7 then
            if f - tphase >= 22 then H.press(K.DOWN, 12, 8); tphase = f end
        else
            enter("toCol", f)
        end
    elseif phase == "toCol" then
        if x < curCol then
            if f - tphase >= 22 then H.press(K.RIGHT, 12, 8); tphase = f end
        elseif x > curCol then
            if f - tphase >= 22 then H.press(K.LEFT, 12, 8); tphase = f end
        else
            H.log(("COL %d: at (%d,%d), going up"):format(curCol, x, y))
            enter("up", f); upStuckPos = nil; upStuckAt = f
        end
    elseif phase == "up" then
        -- press up until y stops decreasing for a while
        if y ~= upStuckPos then upStuckPos = y; upStuckAt = f end
        if f - tphase >= 22 then H.press(K.UP, 12, 8); tphase = f end
        if f - upStuckAt >= 40 then
            H.log(("COL %d: stopped at (%d,%d), interacting UP"):format(curCol, x, y))
            enter("a1", f)
        end
    elseif phase == "a1" then
        H.press(K.A, 6); firedCol = curCol; enter("wait1", f)
    elseif phase == "wait1" then
        if f - tphase == 20 then emu:screenshot(("tools/savestates/sw_col%d.png"):format(curCol)) end
        if f - tphase >= 40 then enter("a2", f) end
    elseif phase == "a2" then
        H.press(K.A, 6); enter("wait2", f)
    elseif phase == "wait2" then
        if f - tphase >= 70 then
            if not fired then
                H.log(("COL %d: no trigger"):format(curCol))
                -- press B a couple times to dismiss any dialog, then next col
                H.press(K.B, 6); H.press(K.B, 6)
                ci = ci + 1
                enter("toRow", f)
            end
        end
    end
end)
