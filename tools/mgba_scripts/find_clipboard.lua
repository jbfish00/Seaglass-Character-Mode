-- Find the cheat-clipboard trigger tile/facing in the Oldale mart (map 2.4).
-- Breakpoint on CM_OpenCodeEntry (0x08ED2270) fires ONLY if the clipboard entry
-- script ran AND we answered YES to the naming prompt.
--
-- ENV:
--   CM_MOVES = comma tokens L/R/U/D, one tile each (idx-gated, 24f/tile).
--   CM_FACE  = final facing tap before interacting: U/D/L/R (turn, no step).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end
local tokmap = { L=K.LEFT, R=K.RIGHT, U=K.UP, D=K.DOWN }

local moves = {}
for tok in string.gmatch(os.getenv("CM_MOVES") or "", "[^,]+") do
    if tokmap[tok] then moves[#moves+1] = tokmap[tok] end
end
local face = os.getenv("CM_FACE") or ""

local STEP = 24                     -- frames per tile
local moveEnd = 30 + #moves * STEP  -- when all moves consumed
local faceFrame = moveEnd + 12
local aFrame1  = faceFrame + 24     -- start prompt
local aFrame2  = aFrame1 + 45       -- confirm YES
local giveUp   = aFrame2 + 80

local idx, lastAct = 0, 0
local fired, fireFrame, saved = false, nil, false

H.breakpoint("CM_OpenCodeEntry", 0x08ED2270, function(f)
    if not fired then fireFrame = f end
    fired = true
    H.log("*** CM_OpenCodeEntry FIRED at frame " .. f .. " ***")
end)

H.onFrame(function(f)
    -- drive movement
    if idx < #moves and f - lastAct >= STEP and f >= 30 then
        idx = idx + 1; lastAct = f; H.press(moves[idx], 12, 8)
    end
    if f == 20 then local x,y = pos(); H.log(("START pos=(%d,%d)"):format(x,y)) end
    if f == moveEnd then
        local x,y = pos(); H.log(("AFTER-MOVE pos=(%d,%d)"):format(x,y))
        emu:screenshot("tools/savestates/fc_pos.png")
    end
    if f == faceFrame and face ~= "" and tokmap[face] then
        H.press(tokmap[face], 2, 4)   -- turn in place
    end
    if f == aFrame1 then
        local x,y = pos(); H.log(("INTERACT-A1 pos=(%d,%d) face=%s"):format(x,y,face))
        H.press(K.A, 6)
    end
    if f == aFrame1 + 24 then emu:screenshot("tools/savestates/fc_prompt.png") end
    if f == aFrame2 then H.log("CONFIRM-A2 (YES)"); H.press(K.A, 6) end

    if fired and not saved and fireFrame and f == fireFrame + 90 then
        saved = true
        emu:saveStateFile("tools/savestates/naming_open.ss")
        emu:screenshot("tools/savestates/naming_open.png")
        H.log("SAVED naming_open.ss + naming_open.png at f=" .. f)
        H.log("RESULT fired=true")
        H.finish()
    end
    if f == giveUp and not fired then
        H.log("RESULT fired=false")
        emu:screenshot("tools/savestates/fc_after.png")
        H.finish()
    end
end)
