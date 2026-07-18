-- Explore reachable tiles in the mart, logging position each time it changes,
-- and screenshot at a few checkpoints. No breakpoint (fast).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end

-- Walk pattern: up to top, then sweep right along counter front, screenshotting.
local seq = {}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.UP,6)          -- go to top (blocked at y=3)
add(K.RIGHT,1)       -- x=4
add(K.RIGHT,1)       -- x=5
add(K.RIGHT,1)       -- x=6
add(K.RIGHT,1)       -- x=7
add(K.RIGHT,1)       -- x=8

local idx, lastAct, last = 0, 0, nil
local shots = {}
H.onFrame(function(f)
    local x,y = pos()
    local cur = ("%d,%d"):format(x,y)
    if cur ~= last then H.log(("f=%d pos=(%d,%d)"):format(f,x,y)); last = cur end
    if f - lastAct > 18 and idx < #seq then
        idx = idx + 1; lastAct = f; H.press(seq[idx], 8, 6)
    end
    -- periodic screenshots
    if f == 200 then emu:screenshot("tools/savestates/ex_200.png") end
    if f == 400 then emu:screenshot("tools/savestates/ex_400.png") end
    if f == 560 then emu:screenshot("tools/savestates/ex_560.png"); H.finish() end
end)
