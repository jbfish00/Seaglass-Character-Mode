-- Sweep a fixed column, testing interaction in a fixed facing at each row.
-- ENV: CM_COL (column x), CM_ROWS ("2,3,4,5,6,7"), CM_DIR (U/D/L/R facing).
-- Navigates within the column (uses bottom highway to reach the column first),
-- then for each row: move to that row, turn to face CM_DIR, A + wait + A(YES).
-- Breakpoint on CM_OpenCodeEntry fires on the real trigger.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end
local COL = tonumber(os.getenv("CM_COL") or "3")
local DIRt = os.getenv("CM_DIR") or "L"
local DIR = ({U=K.UP,D=K.DOWN,L=K.LEFT,R=K.RIGHT})[DIRt]
local rows = {}
for r in string.gmatch(os.getenv("CM_ROWS") or "2,3,4,5,6,7", "[^,]+") do rows[#rows+1]=tonumber(r) end

local fired, fireFrame, saved, firedRow = false, nil, false, nil
H.breakpoint("CM_OpenCodeEntry", 0x08ED2270, function(f)
    if not fired then fireFrame = f end
    fired = true
    H.log("*** CM_OpenCodeEntry FIRED frame=" .. f .. " ***")
end)

local ri = 1
local phase = "toRow7"
local tphase = 0
local function enter(p,f) phase=p; tphase=f end

H.onFrame(function(f)
    if fired then
        if not saved and fireFrame and f >= fireFrame + 90 then
            saved = true
            emu:saveStateFile("tools/savestates/naming_open.ss")
            emu:screenshot("tools/savestates/naming_open.png")
            H.log(("SAVED naming_open.* f=%d col=%d row=%s dir=%s"):format(f,COL,tostring(firedRow),DIRt))
            H.log(("RESULT fired=true col=%d row=%s dir=%s"):format(COL,tostring(firedRow),DIRt))
            H.finish()
        end
        return
    end
    if ri > #rows then H.log("RESULT fired=false"); H.finish(); fired="done"; return end
    local x,y = pos()

    if phase == "toRow7" then
        if y < 7 then if f-tphase>=22 then H.press(K.DOWN,12,8); tphase=f end
        else enter("toCol", f) end
    elseif phase == "toCol" then
        if x < COL then if f-tphase>=22 then H.press(K.RIGHT,12,8); tphase=f end
        elseif x > COL then if f-tphase>=22 then H.press(K.LEFT,12,8); tphase=f end
        else enter("toY", f) end
    elseif phase == "toY" then
        local ty = rows[ri]
        if y > ty then if f-tphase>=22 then H.press(K.UP,12,8); tphase=f end
        elseif y < ty then if f-tphase>=22 then H.press(K.DOWN,12,8); tphase=f end
        else
            if x ~= COL then  -- got pushed off column, realign
                enter("toCol", f)
            else
                H.log(("row %d: at (%d,%d), facing %s"):format(ty,x,y,DIRt))
                enter("face", f)
            end
        end
    elseif phase == "face" then
        H.press(DIR, 2, 6); enter("a1", f+8)   -- turn in place, small delay
    elseif phase == "a1" then
        if f>=tphase then H.press(K.A,6); firedRow=rows[ri]; enter("wait1", f) end
    elseif phase == "wait1" then
        if f-tphase==20 then emu:screenshot(("tools/savestates/sd_c%d_r%d_%s.png"):format(COL,rows[ri],DIRt)) end
        if f-tphase>=40 then enter("a2", f) end
    elseif phase == "a2" then
        H.press(K.A,6); enter("wait2", f)
    elseif phase == "wait2" then
        if f-tphase>=70 then
            if not fired then
                H.log(("row %d dir %s: no trigger"):format(rows[ri],DIRt))
                H.press(K.B,6); H.press(K.B,6)
                ri = ri + 1
                enter("toRow7", f)  -- reset to highway to re-navigate cleanly
            end
        end
    end
end)
