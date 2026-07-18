-- Map the reachable extents of the mart and screenshot corners.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end
local seq = {}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
-- from (3,7): probe right extent along bottom, then up the right wall, then
-- along the top back left, screenshotting corners.
add(K.RIGHT,10)   -- find right wall at y=7
add(K.UP,8)       -- up right wall
add(K.LEFT,10)    -- along top back to left
local idx, lastAct, last = 0, 0, nil
local minx,maxx,miny,maxy = 99,0,99,0
H.onFrame(function(f)
    local x,y = pos()
    if x<minx then minx=x end; if x>maxx then maxx=x end
    if y<miny then miny=y end; if y>maxy then maxy=y end
    local cur = ("%d,%d"):format(x,y)
    if cur ~= last then H.log(("f=%d pos=(%d,%d)"):format(f,x,y)); last = cur end
    if f - lastAct >= 24 and idx < #seq then
        idx = idx + 1; lastAct = f; H.press(seq[idx], 12, 8)
    end
    if f == 260 then emu:screenshot("tools/savestates/mx_br.png") end   -- bottom-right
    if f == 520 then emu:screenshot("tools/savestates/mx_tr.png") end   -- top-right
    if f == 760 then emu:screenshot("tools/savestates/mx_tl.png")       -- top-left
        H.log(("EXTENTS x=[%d,%d] y=[%d,%d]"):format(minx,maxx,miny,maxy))
        H.finish() end
end)
