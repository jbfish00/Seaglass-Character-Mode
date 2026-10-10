-- Live layer: 100% catch for on-roster species (2026-10-09).
-- From battle_menu2.ss (wild Zigzagoon, ROM species 263, FULL HP -- never
-- weakened here): 20 Poke Balls in the bag, then one real throw, with the RNG
-- seeded from SEED just before it, through the battle UI. A breakpoint on the `bhi <caught>` right
-- after the hooked compare (0x080A6288) reads r3, the capture odds the game
-- decides on:
--   EXPECT=sure    -> odds 255 at the decision, and the party grows 1 -> 2
--                     (caught on the first throw at full HP)
--   EXPECT=vanilla -> odds below 255 at full HP (the Poke Ball's own maths);
--                     the throw's outcome is left to chance and not asserted
--   EXPECT=miss    -> as vanilla, and the throw fails (party stays 1): with
--                     SEED=2 the vanilla roll breaks out, the same seed the
--                     sure runs catch with -- so the guarantee is the hook's
-- Zigzagoon is on Norman's roster (char 51) and off Red's (char 1).
-- Env: CM_ON 1/0, CM_CHAR, SEED, EXPECT.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local POCKETS = 0x0200B0B8
local PARTY_COUNT = 0x02019C1D
local RNG_STATE = 0x03005438          -- Random()'s SFC32 state (0x081D931C)
local DECISION = 0x080A6288           -- bhi after `cmp r3,#254`
local CM_ON = os.getenv("CM_ON") == "1"
local EXPECT = os.getenv("EXPECT") or "sure"
local SEED = tonumber(os.getenv("SEED") or "1")
local odds = nil

H.breakpoint("odds decision", DECISION, function()
    if odds == nil then odds = emu:readRegister("r3") end
end)

H.onFrame(function(f)
    if f ~= 30 then return end
    local slots = emu:read32(POCKETS + 8)
    local key = emu:read16(emu:read32(H.gSaveBlock2Ptr) + 0xB0)
    emu:write16(slots, 1); emu:write16(slots + 2, 20 ~ key)
    if CM_ON then
        H.setFlag(0x2B0); H.setVar(0x40E4, tonumber(os.getenv("CM_CHAR") or "51"))
    else
        H.clearFlag(0x2B0)
    end
    H.log(string.format("CM %s char=%d seed=%d partyCount=%d", CM_ON and "ON" or "OFF",
        H.getVar(0x40E4), SEED, emu:read8(PARTY_COUNT)))
end)

H.onFrame(function(f)
    if f==100 or f==350 or f==600 then H.press(K.A, 12, 30) end
    if f==950  then H.press(K.RIGHT, 12, 30) end
    if f==1100 then H.press(K.A, 12, 30) end
    if f==1300 then H.press(K.RIGHT, 12, 30) end   -- ITEMS -> BALLS
    if f==1560 then H.press(K.A, 12, 40) end        -- select Poke Ball
    if f==1715 then   -- seed the shake rolls right before the throw (earlier, it changes the menus)
        for i = 0, 3 do emu:write32(RNG_STATE + 4 * i, (SEED * 0x9E3779B9 + i * 0x85EBCA6B) & 0xFFFFFFFF) end
    end
    if f==1720 then H.press(K.A, 12, 40) end        -- throw
    if f>1900 and f<4200 and f%80==0 then H.press(K.B, 8, 30) end   -- B: no nickname prompt
    if f==4400 then
        local n = emu:read8(PARTY_COUNT)
        H.log(string.format("odds at the decision=%s partyCount=%d", tostring(odds), n))
        if EXPECT == "sure" then
            H.assertEq("odds at the caught/shake decision", odds, 255)
            H.assertEq("caught on the first throw at full HP (party 1 -> 2)", n, 2)
        elseif EXPECT == "miss" then
            H.assertTrue("odds are the Poke Ball's own (below 255 at full HP)", odds ~= nil and odds < 255)
            H.assertEq("this seed's vanilla roll breaks out (party stays 1)", n, 1)
        else
            H.assertTrue("the throw reached the decision", odds ~= nil)
            H.assertTrue("odds are the Poke Ball's own (below 255 at full HP)", odds ~= nil and odds < 255)
        end
        H.finish()
    end
end)
