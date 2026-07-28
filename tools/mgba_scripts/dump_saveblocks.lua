-- Dump SaveBlock1 and SaveBlock2 as hex rows for offline structural analysis.
--
-- Why offline structure rather than a gameplay diff: the encounter/catch diffs
-- could not pin the Pokedex, because every savestate in this repo is far enough
-- in that the common Route 101 species are ALREADY seen -- so the bit never
-- flips and there is nothing to find. The dex is instead identifiable by an
-- invariant that holds in any save: owned is a strict SUBSET of seen, in two
-- adjacent equal-length bitmaps.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR, SB2_PTR = 0x030051B8, 0x030051BC
local SPAN1, SPAN2 = 0x6000, 0x3000
local done = false

local function dump(tag, ptr, span)
    local base = emu:read32(ptr)
    console:log(string.format("%sBASE 0x%08X span 0x%X", tag, base, span))
    local data = emu:readRange(base, span)
    local row = 0
    while row < span do
        local t = {}
        for i = 1, 32 do t[#t + 1] = string.format("%02X", string.byte(data, row + i) or 0) end
        console:log(string.format("%s %04X %s", tag, row, table.concat(t)))
        row = row + 32
    end
end

H.onFrame(function(f)
    if done or f < 150 then return end
    done = true
    dump("SB1", SB1_PTR, SPAN1)
    dump("SB2", SB2_PTR, SPAN2)
    console:log("DUMPEND")
    H.finish()
end)
