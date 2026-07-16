-- From trek_end.ss (2,2): east along y=2, probing UP twice at each of x=5..9.
-- The Oldale connection renders as open path north of the map edge there.
-- Auto-heal keeps Torchic alive through any encounters (tall grass here).
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local PARTY = 0x02019C20
local ENEMY = 0x02019E78
local K = H.KEY
local function heal()
    local mx = emu:read16(PARTY+0x58)
    if mx>0 and mx<1000 then emu:write16(PARTY+0x56, mx) end
end
local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp>mx then return nil end
    return lv, hp
end
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,3); add(K.UP,2)   -- x=5
add(K.RIGHT,1); add(K.UP,2)   -- x=6
add(K.RIGHT,1); add(K.UP,2)   -- x=7
add(K.RIGHT,1); add(K.UP,2)   -- x=8
add(K.RIGHT,1); add(K.UP,3)   -- x=9
local idx=0
local mode="walk"
local lastAct=0
local last=nil
local finished=false
local startMap=nil
local END=30000
H.onFrame(function(f)
    if finished or f>END then return end
    if f%60==0 then heal() end
    local b=emu:read32(SB1_PTR)
    if b<0x02000000 or b>=0x02040000 then return end
    local grp,num=emu:read8(b+4),emu:read8(b+5)
    if f==30 then startMap=grp*256+num end
    local cur=string.format("%d,%d map=%d.%d",emu:read16(b),emu:read16(b+2),grp,num)
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if startMap and grp~=255 and (grp*256+num)~=startMap and not (grp==0 and num==0) then
        finished=true
        emu:screenshot("tools/savestates/trek_end.png")
        emu:saveStateFile("tools/savestates/oldale.ss")
        H.log("ARRIVED map "..grp.."."..num); H.finish(); return
    end
    if f==END then
        finished=true
        emu:screenshot("tools/savestates/trek_end.png")
        emu:saveStateFile("tools/savestates/probe_end.ss")
        H.log("cap; saved probe_end"); H.finish(); return
    end
    local lv,hp=enemyLv()
    if mode=="walk" then
        if lv and hp and hp>0 then mode="battle"; lastAct=f; H.log("battle f="..f)
        elseif f-lastAct>44 and idx<#seq then
            idx=idx+1; lastAct=f; H.press(seq[idx],16,6)
        end
    else
        if not lv or (hp and hp==0) then
            if f-lastAct>2200 then mode="walk"; lastAct=f; H.log("resume f="..f) end
            if (f-lastAct)%280==0 then H.press(K.A,12,30) end
        else
            if f-lastAct>250 then lastAct=f; H.press(K.A,12,30) end
        end
    end
end)
