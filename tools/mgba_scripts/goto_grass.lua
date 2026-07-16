-- From nav_out.ss (11,1 at the gate): set flag 0x74 to pass, warp to Route 101,
-- walk up into the grass, and (a) screenshot to check the clean-rescue state
-- (Birch despawned?) and (b) oscillate to trigger a wild encounter, detecting it
-- via a valid enemy mon (gEnemyParty candidate) or a long coord-freeze.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local ENEMY = 0x02019E78
local K = H.KEY
H.gSaveBlock1Ptr = 0x030051B8

local set=false
H.onFrame(function(f)
    if f==60 and not set then
        set=true
        -- 2026-07-16 correction: the gate is a coord trigger on var 0x4050
        -- (fires while ==0), NOT flag 0x74. The old H.setFlag(0x74) only
        -- worked because FLAG_BLOCK was wrong and aliased var 0x4050 |= 0x10.
        -- Set the var to 2 = the game's own post-pass value.
        H.setVar(0x4050, 2)
        H.log(string.format("var 0x4050 (SB1+0x158C) now = 0x%04X", H.getVar(0x4050)))
        local seq={}
        local function add(k,n) for _=1,n do seq[#seq+1]=k end end
        -- from have_starter.ss (7,17): proven warp path via (11,2)->(10,2)->up
        add(K.RIGHT,4); add(K.UP,15); add(K.LEFT,1); add(K.UP,3)
        add(K.UP,4)                               -- into Route 101
        -- snake WEST/north through the rescue-zone grass (covers many tiles)
        add(K.LEFT,5)
        for _=1,10 do add(K.UP,3); add(K.RIGHT,4); add(K.UP,1); add(K.LEFT,4); add(K.UP,1) end
        for _,k in ipairs(seq) do H.press(k, 16, 6) end
    end
end)
local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp<1 or hp>mx then return nil end
    return lv
end
local lastxy,frozenSince,saved=nil,nil,false
local END=4200
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    local xy=string.format("%d,%d", emu:read16(base), emu:read16(base+2))
    if xy~=lastxy then lastxy=xy; frozenSince=f end
    if not saved and f>700 then
        local lv=enemyLv()
        local frozen=frozenSince and (f-frozenSince)>150
        if lv or frozen then
            saved=true
            emu:saveStateFile("tools/savestates/wild_battle.ss")
            emu:screenshot("tools/savestates/wild_battle.png")
            H.log(string.format("ENCOUNTER? enemyLv=%s frozen=%s at %s map=%d.%d f=%d",
                tostring(lv), tostring(frozen), xy, emu:read8(base+4), emu:read8(base+5), f))
        end
    end
    if f%120==0 then emu:screenshot(string.format("tools/savestates/gg_f%05d.png", f)) end
    if f==END then if not saved then H.log("no encounter; final "..xy) end; H.finish() end
end)
