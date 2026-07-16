-- Trek v3: bedroom -> downstairs -> Littleroot -> north gate -> Route 101 ->
-- top edge, probing UP at each column moving EAST (the Oldale connection was
-- not found in the westward sweep). AUTO-HEALS Torchic (gPlayerParty+0x56 =
-- maxHP) every 60 frames -- the ROWE debug-menu "heal party" equivalent --
-- so battles can never whiteout us again. Auto-battles with A.
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

-- Scripted leg: bedroom (4,2) -> stairs (7,1) -> 1F -> door -> town -> col 11
-- -> (11,2) -> (10,2) -> up through gate -> Route 101.
local leg = {}
local function add(k,n) for _=1,n do leg[#leg+1]=k end end
add(K.RIGHT,3); add(K.UP,1)              -- to stairs top (7,1) -> warps 1F
add(K.DOWN,6)                            -- 1F to door row, out
add(K.RIGHT,4)                           -- town: east toward col 11 (from ~(5,8))
add(K.UP,9)                              -- north lane to (11,2)... queue simple; coords logged
add(K.DOWN,1); add(K.LEFT,1); add(K.UP,3) -- shift col 10, through gate
add(K.UP,6); add(K.RIGHT,2); add(K.UP,4) -- into Route 101, head NE
for _,k in ipairs(leg) do H.press(k, 16, 6) end

-- After the scripted leg (~frame 2600), switch to explorer mode: probe UP,
-- then RIGHT when stuck, along the top edge (eastward bias this time).
local sweep={K.UP, K.RIGHT, K.UP, K.RIGHT, K.UP, K.RIGHT, K.UP, K.LEFT, K.UP}
local sweepIdx=0
local dir=K.UP
local mode="script"
local lastAct, lastMove, lastxy = 0, 0, nil
local last=nil
local startedRoute=false
local finished=false
local END=45000
H.onFrame(function(f)
    if finished or f>END then return end
    if f%60==0 then heal() end
    local b=emu:read32(SB1_PTR)
    if b<0x02000000 or b>=0x02040000 then return end
    local grp,num = emu:read8(b+4), emu:read8(b+5)
    local xy=string.format("%d,%d",emu:read16(b),emu:read16(b+2))
    local cur=xy.." map="..grp.."."..num
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if xy~=lastxy then lastxy=xy; lastMove=f end

    if grp==0 and num==16 then startedRoute=true end
    -- arrival: a NEW outdoor map after we were on Route 101 (0.16), excluding
    -- transition garbage (255.x / 0.0) and Littleroot (0.9)
    if startedRoute and not (grp==0 and (num==16 or num==9 or num==0)) and grp~=255 and grp~=1 then
        finished=true
        emu:screenshot("tools/savestates/trek_end.png")
        emu:saveStateFile("tools/savestates/oldale.ss")
        H.log("ARRIVED map "..grp.."."..num.." at f="..f)
        H.finish(); return
    end
    if f==END then
        finished=true
        emu:screenshot("tools/savestates/trek_end.png")
        emu:saveStateFile("tools/savestates/trek_end.ss")
        H.log("frame cap; saved trek_end"); H.finish(); return
    end

    if f>2800 and mode=="script" then mode="walk"; lastMove=f end
    local lv,hp = enemyLv()
    if mode=="walk" then
        if lv and hp and hp>0 then
            mode="battle"; lastAct=f; H.log("battle (lv "..lv..") f="..f)
        else
            if f-lastMove>500 then
                sweepIdx=(sweepIdx % #sweep)+1; dir=sweep[sweepIdx]; lastMove=f
                H.log("stuck -> dir "..sweepIdx)
            end
            if f-lastAct>40 then lastAct=f; H.press(dir, 16, 6) end
        end
    elseif mode=="battle" then
        if not lv or (hp and hp==0) then
            if f-lastAct>2200 then mode="walk"; lastAct=f; lastMove=f; H.log("resume walk f="..f) end
            if (f-lastAct)%280==0 then H.press(K.A, 12, 30) end
        else
            if f-lastAct>250 then lastAct=f; H.press(K.A, 12, 30) end
        end
    end
end)
