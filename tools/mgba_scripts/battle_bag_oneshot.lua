-- ONE-SHOT: from at_8_8.ss (clean overworld), walk into the tall grass to roll
-- an encounter, wait for the battle menu, then navigate RIGHT->A to the BAG —
-- all in one run, no intermediate savestate (mid-battle state loads have shown
-- broken input edges). Detects the encounter via gEnemyParty, waits for the
-- menu to be ready, then drives it.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local ENEMY = 0x02019E78
local K = H.KEY

-- Phase A: walk into grass (right 3, down 3, then oscillate) until encounter.
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,3); add(K.DOWN,3)
for _=1,25 do add(K.RIGHT,1); add(K.DOWN,1); add(K.LEFT,1); add(K.UP,1) end
for _,k in ipairs(seq) do H.press(k, 16, 6) end

local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp<1 or hp>mx then return nil end
    return lv
end

local encounterAt=nil
local menuDriven=false
local END=6000
H.onFrame(function(f)
    if f>END then return end
    if not encounterAt and f>150 and enemyLv() then
        encounterAt=f
        H.log("encounter rolled at f="..f.." enemyLv="..tostring(enemyLv()))
    end
    -- battle intro takes ~700 frames; then menu is up. Drive RIGHT then A.
    if encounterAt and not menuDriven and f==encounterAt+1500 then
        menuDriven=true
        emu:saveStateFile("tools/savestates/battle_menu2.ss")
        H.mash(K.RIGHT, f+10, f+300, 24)   -- repeated edges: battle menu drops singles
        H.mash(K.A,     f+400, f+520, 30)
        H.log("menu drive (mash) at f="..f)
    end
    if menuDriven and f==encounterAt+2400 then
        emu:screenshot("tools/savestates/bag_open.png")
        emu:saveStateFile("tools/savestates/bag_open.ss")
        H.log("bag shot saved")
        H.finish()
    end
end)
