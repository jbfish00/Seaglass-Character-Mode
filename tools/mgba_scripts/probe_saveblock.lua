-- Identify SaveBlock1 among the confirmed pointer trio and locate the player
-- coords + current map fields. In pokeemerald SaveBlock1 begins:
--   +0x00 s16 pos.x, +0x02 s16 pos.y
--   +0x04 WarpData location { s8 mapGroup, s8 mapNum, s8 warpId, s16 x, s16 y }
-- INSIDE_OF_TRUCK is (group 25, num 34) in vanilla. Dump each trio target's
-- first 32 bytes so the block whose header looks like (small coords, plausible
-- group/num) is identifiable. Then coords/map become a robust nav signal.
local H = dofile("tools/mgba_scripts/harness.lua")
local TRIO = H.SAVEBLOCK_PTRS
local function dump(base)
    local parts = {}
    for i = 0, 31 do parts[#parts+1] = string.format("%02X", emu:read8(base + i)) end
    return table.concat(parts, " ")
end
local done = false
H.onFrame(function(f)
    if done or f < 200 then return end
    done = true
    for i, p in ipairs(TRIO) do
        local base = emu:read32(p)
        H.log(string.format("trio[%d] ptr=0x%08X -> 0x%08X", i, p, base))
        if base >= 0x02000000 and base < 0x02040000 then
            H.log(string.format("  bytes: %s", dump(base)))
            H.log(string.format("  as coords: x=%d y=%d  loc: grp=%d num=%d warp=%d wx=%d wy=%d",
                emu:read16(base+0), emu:read16(base+2),
                emu:read8(base+4), emu:read8(base+5), emu:read8(base+6),
                emu:read16(base+7), emu:read16(base+9)))
        end
    end
    H.finish()
end)
