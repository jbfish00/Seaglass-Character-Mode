-- Live layer: reusable TMs (2026-10-09). From have_starter.ss, put TM06 Toxic in
-- the TM pocket's first slot, then teach it to the party lead through the real
-- bag UI (START > BAG > TMs > Use > Yes > lead mon; "learned Toxic!").
-- Afterwards the pocket must still hold TM06 with the SAME quantity
-- (EXPECT=keep, the built ROM) or a lower one (EXPECT=consumed, the base ROM;
-- the trailing A presses teach it again, so 5 -> 2 there). The base-ROM run is
-- the control that proves this driver really teaches: if the menus
-- mis-navigate, both runs see 5 and the control FAILS.
-- Quantities are decoded with the key at each read (u16 at *gSaveBlock2Ptr+0xB0):
-- the save blocks move and re-key while the menus run, so raw words can't be compared.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local TM06 = 587                 -- items 582-681 are TM01-TM100
local EXPECT = os.getenv("EXPECT") or "keep"
local SHOT = os.getenv("CM_SHOT_PREFIX")
local slot, before
local function pocket(p) return emu:read32(H.BAG_POCKETS + 8 * p) end
local function key() return emu:read16(emu:read32(H.gSaveBlock2Ptr) + 0xB0) end
local steps = {
    {30, function()
        slot = pocket(2)                       -- TMs & HMs
        emu:write16(slot, TM06)
        emu:write16(slot + 2, 5 ~ key())                   -- quantity 5
        before = emu:read16(slot + 2) ~ key()
        H.log(string.format("TM pocket slot0 = %d qty %d", emu:read16(slot), before))
    end},
    {60, function() H.press(K.START, 6, 30) end},
    {120, function() H.press(K.DOWN, 6, 20) end},
    {160, function() H.press(K.A, 6, 30) end},       -- BAG
    {260, function() H.press(K.RIGHT, 6, 20) end},
    {300, function() H.press(K.RIGHT, 6, 20) end},   -- TMs & HMs
    {380, function() H.press(K.A, 6, 30) end},       -- TM06
    {440, function() H.press(K.A, 6, 30) end},       -- Use
    {640, function() H.press(K.A, 6, 30) end},       -- "Booted up a TM" / "It contained"
    {810, function() H.press(K.A, 6, 30) end},       -- Teach Toxic? YES
    {960, function() H.press(K.A, 6, 30) end},       -- lead mon
    {1250, function() H.press(K.A, 6, 30) end},      -- "... learned Toxic!"
    {1300, function() if SHOT then emu:screenshot(SHOT .. "_learned.png") end end},
    {1500, function() H.press(K.A, 6, 30) end},
    {2000, function()
        if SHOT then emu:screenshot(SHOT .. "_bag.png") end
        -- The pocket's slot array lives in SaveBlock1, which the engine may
        -- move (ASLR-style relocation): re-read the pointer, then find TM06.
        local now, after = pocket(2), nil
        for i = 0, emu:read8(H.BAG_POCKETS + 8 * 2 + 4) - 1 do
            if emu:read16(now + 4 * i) == TM06 then after = emu:read16(now + 4 * i + 2) ~ key() end
        end
        H.log(string.format("after: pocket %08X (was %08X), TM06 qty %s", now, slot,
            after and tostring(after) or "absent"))
        H.assertTrue("the TM pocket still holds TM06", after ~= nil)
        after = after or -1
        if EXPECT == "keep" then
            H.assertEq("TM06 quantity unchanged after teaching (reusable)", after, before)
        else
            H.assertTrue("TM06 quantity went down after teaching (base ROM consumes it)", after < before)
        end
        H.finish()
    end},
}
H.onFrame(function(f) for _, s in ipairs(steps) do if s[1] == f then s[2]() end end end)
