-- Walk north through Route 101 tall grass to trigger a wild encounter. Detect
-- via a valid enemy mon (gEnemyParty candidate) OR a long coord-freeze (battle
-- locks the overworld); save that state + screenshot for the catch trace.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local ENEMY = 0x02019E78
local K = H.KEY
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
-- Push north, then snake north/south through the grass rows.
add(K.UP,6)
for _=1,24 do add(K.UP,2); add(K.DOWN,2) end
for _,k in ipairs(seq) do H.press(k, 16, 6) end

local function enemyLv()
    local lv=emu:read8(ENEMY+0x54); if lv<1 or lv>100 then return nil end
    local hp=emu:read16(ENEMY+0x56); local mx=emu:read16(ENEMY+0x58)
    if mx<1 or mx>999 or hp<1 or hp>mx then return nil end
    return lv
end
local lastxy, frozenSince, saved = nil, nil, false
local END=3000
H.onFrame(function(f)
    if f>END then return end
    local base=emu:read32(SB1_PTR)
    local xy=string.format("%d,%d", emu:read16(base), emu:read16(base+2))
    if xy~=lastxy then lastxy=xy; frozenSince=f end
    if not saved and f>200 then
        local lv=enemyLv()
        local frozen = frozenSince and (f-frozenSince)>120
        if lv or frozen then
            saved=true
            emu:saveStateFile("tools/savestates/wild_battle.ss")
            emu:screenshot("tools/savestates/wild_battle.png")
            H.log(string.format("ENCOUNTER? enemyLv=%s frozen=%s at %s f=%d -> saved", tostring(lv), tostring(frozen), xy, f))
        end
    end
    if f%100==0 then emu:screenshot(string.format("tools/savestates/wg_f%05d.png", f)) end
    if f==END then if not saved then H.log("no encounter") end; H.log("end "..xy); H.finish() end
end)
