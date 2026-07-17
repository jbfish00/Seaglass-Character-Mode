-- Character Mode ENFORCEMENT test on build/seaglass_cm.gba.
-- From battle_menu2.ss (wild Zigzagoon = Nat-Dex 263, off the PoC Torchic-line
-- roster {255,256,257}): give balls, weaken to 1 HP, throw. If CM_ON=1 set the
-- CM flag/char var first. Expected: CM on -> Zigzagoon routed to PC, party count
-- stays 1; CM off -> caught to party, count 2.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local POCKETS = 0x0200B0B8
local ENEMY = 0x02019E78
local PC = 0x02019C1D
local CM_ON = (os.getenv and os.getenv("CM_ON")) == "1"

H.onFrame(function(f)
    if f ~= 30 then return end
    local slots = emu:read32(POCKETS + 8)
    local key = emu:read16(emu:read32(H.gSaveBlock2Ptr) + 0xB0)
    emu:write16(slots, 1); emu:write16(slots + 2, 20 ~ key)
    emu:write16(ENEMY + 0x56, 1)
    if CM_ON then
        local char = tonumber(os.getenv("CM_CHAR")) or 1
        H.setFlag(0x945)          -- FLAG_CHARACTER_MODE
        H.setVar(0x40E4, char)    -- VAR_CM_CHAR
        H.log(string.format("CM ON char=%d: flag0x945=%d var0x40E4=%d", char, H.getFlag(0x945), H.getVar(0x40E4)))
    else
        H.log("CM OFF (control)")
    end
    H.log("start partyCount=" .. emu:read8(PC))
end)

H.onFrame(function(f)
    if f==100 or f==350 or f==600 then H.press(K.A, 12, 30) end
    if f==950  then H.press(K.RIGHT, 12, 30) end
    if f==1100 then H.press(K.A, 12, 30) end
    if f==1300 then H.press(K.RIGHT, 12, 30) end   -- ITEMS -> BALLS
    if f==1560 then H.press(K.A, 12, 40) end        -- select Poke Ball
    if f==1720 then H.press(K.A, 12, 40) end        -- throw
    if f>1900 and f<4200 and f%80==0 then H.press(K.A, 8, 30) end
    if f==4400 then
        emu:screenshot("tools/savestates/cm_test_" .. (CM_ON and "on" or "off") .. ".png")
        H.log(string.format("RESULT CM_ON=%s partyCount=%d (expect %s)",
            tostring(CM_ON), emu:read8(PC), CM_ON and "1=blocked->PC" or "2=to party"))
        H.finish()
    end
end)
