-- Ground truth on input: press keys and read KEYINPUT (0x04000130, active-low)
-- every frame, to verify script keys reach the emulated hardware in-battle.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
H.onFrame(function(f)
    if f==100 then emu:addKey(K.RIGHT); H.log("addKey RIGHT") end
    if f==160 then emu:clearKey(K.RIGHT); H.log("clearKey RIGHT") end
    if f==220 then emu:addKey(K.A); H.log("addKey A") end
    if f==280 then emu:clearKey(K.A); H.log("clearKey A") end
    if (f>=98 and f<=290 and f%10==0) then
        H.log(string.format("f=%d KEYINPUT=0x%04X keys=%s", f,
            emu:read16(0x04000130), tostring(emu:getKeys())))
    end
    if f==360 then emu:screenshot("tools/savestates/keyprobe.png"); H.finish() end
end)
