-- Probe the untested LEFT / BOTTOM region. Navigate along the y=7 highway to
-- x=2,1,0; at each, face UP then LEFT and press A once (raises a prompt if it's
-- the clipboard; single A never confirms YES so no warp). Screenshot each.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1+H.SB1_POS_X), emu:read16(sb1+H.SB1_POS_Y),
           emu:read8(sb1+H.SB1_MAPGRP)*256+emu:read8(sb1+H.SB1_MAPNUM)
end

-- itinerary: list of {action}. Actions run sequentially with fixed spacing.
-- move: press dir. face: tap dir (turn). a: press A. shot: screenshot. log.
local steps = {}
local function mv(k) steps[#steps+1]={t="mv",k=k} end
local function face(k) steps[#steps+1]={t="face",k=k} end
local function A() steps[#steps+1]={t="a"} end
local function B() steps[#steps+1]={t="b"} end
local function shot(name) steps[#steps+1]={t="shot",n=name} end
local function lg(m) steps[#steps+1]={t="log",m=m} end

-- go left to x=2 (from x=3): 1 left
mv(K.LEFT)
for _,tile in ipairs({2,1,0}) do
    lg("at_x"..tile)
    face(K.UP);   A(); shot("lp_x"..tile.."_up");  B()
    face(K.LEFT); A(); shot("lp_x"..tile.."_left"); B()
    face(K.DOWN); A(); shot("lp_x"..tile.."_down"); B()
    if tile > 0 then mv(K.LEFT) end
end
-- also try going UP the left edge from (0,7)
mv(K.UP); A(); shot("lp_x0_up1"); B()
mv(K.UP); A(); shot("lp_x0_up2"); B()

local idx = 0
local nextAt = 30
H.onFrame(function(f)
    if f < nextAt then return end
    idx = idx + 1
    local s = steps[idx]
    if not s then
        if f > nextAt + 40 then local x,y,m=pos(); H.log(("DONE at (%d,%d) map=%d"):format(x,y,m)); H.finish() end
        return
    end
    if s.t=="mv" then H.press(s.k,12,8); nextAt=f+30
    elseif s.t=="face" then H.press(s.k,2,8); nextAt=f+16
    elseif s.t=="a" then H.press(K.A,6,8); nextAt=f+34
    elseif s.t=="b" then H.press(K.B,6,8); nextAt=f+22
    elseif s.t=="shot" then emu:screenshot("tools/savestates/"..s.n..".png"); local x,y,m=pos(); H.log(s.n.." at ("..x..","..y..") map="..m); nextAt=f+4
    elseif s.t=="log" then local x,y,m=pos(); H.log(s.m.." pos=("..x..","..y..") map="..m); nextAt=f+4
    end
end)
