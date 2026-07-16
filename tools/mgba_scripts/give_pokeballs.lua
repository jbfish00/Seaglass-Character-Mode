-- "Give item" debug capability (ROWE debug-menu port), method adapted from
-- Lazarus's give_pokeballs.lua (same author/engine). Seaglass values, found by
-- disassembling AddBagItem @0x0814D2D0:
--   pocket descriptor table @EWRAM 0x0200B0B8, stride 8, [pocket-1]: {u32 slots*, u8 cap}
--   slot: {u16 itemId, u16 qty XOR key};  key = u16 @ (*gSaveBlock2Ptr)+0xB0 (Lazarus offset, verify)
--   Poke Ball item id = 1 (Lazarus, engine constant; verify visually)
-- Balls pocket = pocket field 2.
local H = dofile("tools/mgba_scripts/harness.lua")
local DIR = "tools/savestates/"
local POCKETS = 0x0200B0B8
local N = tonumber(os.getenv and os.getenv("BALLS")) or 20
H.onFrame(function(f)
    if f ~= 60 then return end
    local desc = POCKETS + 8 * (2 - 1)   -- Balls pocket descriptor
    local slots = emu:read32(desc)
    local cap = emu:read8(desc + 4)
    local sb2 = emu:read32(H.gSaveBlock2Ptr)
    local key = emu:read16(sb2 + 0xB0)
    H.log(string.format("Balls pocket: slots=0x%08X cap=%d key=0x%04X slot0=id%d/qty(raw)%04X",
        slots, cap, key, emu:read16(slots), emu:read16(slots + 2)))
    if slots < 0x02000000 or slots >= 0x02040000 then H.log("BAD slots ptr"); H.finish(); return end
    emu:write16(slots, 1)              -- ITEM_POKE_BALL
    emu:write16(slots + 2, N ~ key)    -- qty, encrypted
    H.log(string.format("wrote %d Poke Balls; readback id=%d qty=%d",
        N, emu:read16(slots), emu:read16(slots + 2) ~ key))
    emu:saveStateFile(DIR .. "have_balls.ss")
end)
-- Proof: open bag to the Balls pocket (overworld).
H.onFrame(function(f)
    if f == 130 then H.press(H.KEY.START, 8, 40) end
    if f == 260 then emu:screenshot(DIR .. "menu.png") end
    if f == 320 then H.press(H.KEY.DOWN, 8, 20) end   -- to BAG (guess)
    if f == 400 then H.press(H.KEY.A, 8, 60) end
    if f == 560 then emu:screenshot(DIR .. "bag.png") end
    if f == 620 then H.press(H.KEY.RIGHT, 8, 30) end  -- to Balls pocket
    if f == 760 then emu:screenshot(DIR .. "balls_proof.png"); H.finish() end
end)
