-- Calibrate a full-speed detector: log gMain.callback2 (0x030014B4 + 4) whenever
-- it changes. Compare overworld vs shop-clerk (facing LEFT at (3,2)).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local CB2 = 0x030014B4 + 4
local function pos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end
local last = nil
-- walk to (3,2), face left, open shop, back out
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.UP,5); add(K.LEFT,1)   -- reach (3,2) & face left
local idx,lastAct=0,0
H.onFrame(function(f)
    local cb = emu:read32(CB2)
    if cb ~= last then
        local x,y=pos()
        H.log(("f=%d cb2=0x%08X pos=(%d,%d)"):format(f,cb,x,y))
        last = cb
    end
    if f-lastAct>=24 and idx<#seq then idx=idx+1;lastAct=f;H.press(seq[idx],12,8) end
    if f==200 then H.press(K.A,6) end        -- talk to clerk -> "Welcome!"
    if f==260 then H.press(K.A,6) end        -- advance -> buy/sell menu
    if f==320 then H.press(K.A,6) end        -- pick BUY maybe
    if f==400 then emu:screenshot("tools/savestates/cb_shop.png") end
    if f==460 then H.finish() end
end)
