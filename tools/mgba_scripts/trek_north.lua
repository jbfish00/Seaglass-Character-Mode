-- Trek v2: walk north with auto-battle; when UP is blocked, sweep LEFT along
-- the top edge (then RIGHT) looking for the Oldale connection. Always saves
-- trek_end state. Arrival = map change.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local ENEMY = 0x02019E78
local K = H.KEY
local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp>mx then return nil end
    return lv, hp
end
local mode="walk"
local dir=K.UP
local lastAct=0
local lastMove=0
local lastxy=nil
local sweep={K.UP, K.LEFT, K.UP, K.LEFT, K.UP, K.LEFT, K.UP, K.LEFT, K.UP,
             K.RIGHT, K.UP, K.RIGHT, K.UP}
local sweepIdx=0
local last=nil
local startMap=nil
local END=40000
H.onFrame(function(f)
    if f>END then return end
    local b=emu:read32(SB1_PTR)
    if b<0x02000000 or b>=0x02040000 then return end
    local grp,num = emu:read8(b+4), emu:read8(b+5)
    if f==30 then startMap=grp*256+num end
    local xy=string.format("%d,%d",emu:read16(b),emu:read16(b+2))
    local cur=xy.." map="..grp.."."..num
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if xy~=lastxy then lastxy=xy; lastMove=f end
    if startMap and (grp*256+num)~=startMap and (grp*256+num)~=0 then
        emu:screenshot("tools/savestates/trek_end.png")
        emu:saveStateFile("tools/savestates/oldale.ss")
        H.log("ARRIVED map "..grp.."."..num.." at f="..f)
        H.finish(); return
    end
    if f==END then
        emu:screenshot("tools/savestates/trek_end.png")
        emu:saveStateFile("tools/savestates/trek_end.ss")
        H.log("frame cap; saved trek_end"); H.finish(); return
    end
    local lv,hp = enemyLv()
    if mode=="walk" then
        if lv and hp and hp>0 then
            mode="battle"; lastAct=f; H.log("battle (lv "..lv..") f="..f)
        else
            -- stuck? advance the sweep direction (NOTE: no lastAct condition --
            -- pressing resets lastAct every ~40f so it would never fire)
            if f-lastMove>500 then
                sweepIdx = (sweepIdx % #sweep) + 1
                dir = sweep[sweepIdx]
                lastMove=f
                H.log("stuck -> dir idx "..sweepIdx)
            end
            if f-lastAct>40 then lastAct=f; H.press(dir, 16, 6) end
        end
    else
        if not lv or (hp and hp==0) then
            if f-lastAct>2200 then mode="walk"; lastAct=f; lastMove=f; H.log("resume walk f="..f) end
            if (f-lastAct)%280==0 then H.press(K.A, 12, 30) end
        else
            if f-lastAct>250 then lastAct=f; H.press(K.A, 12, 30) end
        end
    end
end)
