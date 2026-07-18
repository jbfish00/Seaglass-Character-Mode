-- From start (3,7): go up to top row, then push LEFT to find the counter,
-- screenshotting the counter/clerk region. No breakpoint.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end
local seq = {}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.UP,6)          -- top (y=2)
add(K.LEFT,4)        -- push left along top
add(K.DOWN,1)        -- drop a row
add(K.LEFT,4)        -- push left again
local idx, lastAct, last = 0, 0, nil
H.onFrame(function(f)
    local x,y = pos()
    local cur = ("%d,%d"):format(x,y)
    if cur ~= last then H.log(("f=%d pos=(%d,%d)"):format(f,x,y)); last = cur end
    if f - lastAct > 18 and idx < #seq then
        idx = idx + 1; lastAct = f; H.press(seq[idx], 8, 6)
    end
    if f == 160 then emu:screenshot("tools/savestates/el_top.png") end
    if f == 320 then emu:screenshot("tools/savestates/el_left.png") end
    if f == 480 then emu:screenshot("tools/savestates/el_end.png"); H.finish() end
end)
