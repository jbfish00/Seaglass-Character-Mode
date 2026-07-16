-- From survey_end.ss (10,8 on Route 101, at the edge of the dense striped grass
-- to the east): walk INTO that grass and oscillate for many steps. Detect an
-- encounter via enemy-party or coord-freeze; save + screenshot.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local ENEMY = 0x02019E78
local K = H.KEY
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
-- from (8,8): the dense dark spiky tall grass starts ~(11,10). Go right 3,
-- down 3, then oscillate inside it.
add(K.RIGHT,3); add(K.DOWN,3)
for _=1,25 do add(K.RIGHT,1); add(K.DOWN,1); add(K.LEFT,1); add(K.UP,1) end
for _,k in ipairs(seq) do H.press(k, 16, 6) end
local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp<1 or hp>mx then return nil end
    return lv
end
local lastxy,frozenSince,saved=nil,nil,false
local END=3400
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    local xy=string.format("%d,%d", emu:read16(base), emu:read16(base+2))
    if xy~=lastxy then lastxy=xy; frozenSince=f end
    if not saved and f>150 then
        local lv=enemyLv()
        local frozen=frozenSince and (f-frozenSince)>150
        if lv or frozen then
            saved=true
            emu:saveStateFile("tools/savestates/wild_battle.ss")
            emu:screenshot("tools/savestates/wild_battle.png")
            H.log(string.format("HIT enemyLv=%s frozen=%s at %s f=%d", tostring(lv), tostring(frozen), xy, f))
        end
    end
    if f==END then if not saved then H.log("no encounter") end; H.finish() end
end)
