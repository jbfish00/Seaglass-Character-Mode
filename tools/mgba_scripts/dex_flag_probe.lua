-- Locate this ROM's Pokedex "caught"/"seen" bitmaps EMPIRICALLY, by catching a
-- Pokemon and diffing the save blocks at BIT level either side of the catch.
--
-- Why this and not static analysis: three static probes already failed and are
-- recorded in game_plans/seaglass.md so nobody repeats them -- donor
-- specials-index alignment breaks above ~0x101, there is no ascending
-- gSpeciesToNationalPokedexNum run, and there is no natDexNum field inside the
-- SpeciesInfo struct. The accessor function never needs to be found: reading the
-- bitmap directly is the same idiom onRoster() already uses (~8 instructions, no
-- ABI risk), so all we need is the base offset and the index convention.
--
-- Runs from battle_menu2.ss (wild Zigzagoon, national dex 263, species id 263 in
-- this ROM's table -- the two agree here, which is itself worth confirming) with
-- Character Mode OFF so the catch lands normally.
--
-- DUMPS BOTH SaveBlock1 AND SaveBlock2. game_plans/seaglass.md's recipe says
-- SaveBlock1, but in the pokeemerald family the CAUGHT flag lives in
-- SaveBlock2's struct Pokedex (SaveBlock1 carries only the seen1/seen2 mirrors),
-- so looking at SB1 alone could find "seen" and miss "caught" entirely.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local POCKETS = 0x0200B0B8
local ENEMY = 0x02019E78
local PC = 0x02019C1D
local SB1_PTR, SB2_PTR = 0x030051B8, 0x030051BC
local SPAN1, SPAN2 = 0x3A00, 0x1000

local before1, before2, base1, base2

local function snap(ptr, span)
    return emu:readRange(emu:read32(ptr), span)
end

-- Report every BIT that changed, not every byte: a dex flag is a single bit, and
-- a byte-level diff drowns it in playtime/RNG/party churn.
local function bitdiff(tag, old, new, base)
    local hits = 0
    for i = 1, #old do
        local a, b = string.byte(old, i), string.byte(new, i)
        if a ~= b then
            local x = a ~ b
            local nbits = 0
            for k = 0, 7 do if (x >> k) & 1 == 1 then nbits = nbits + 1 end end
            -- Single-bit 0->1 transitions are what a dex flag looks like.
            if nbits == 1 and (a & x) == 0 then
                local bit = 0
                for k = 0, 7 do if (x >> k) & 1 == 1 then bit = k end end
                local off = i - 1
                console:log(string.format(
                    "DEXBIT %s off=0x%04X bit=%d  absolute=0x%08X  "
                    .. "index_if_bitmap_base_here=%d",
                    tag, off, bit, base + off, off * 8 + bit))
                hits = hits + 1
            end
        end
    end
    console:log(string.format("DEXBIT %s single-bit-set changes: %d", tag, hits))
end

H.onFrame(function(f)
    if f ~= 30 then return end
    local slots = emu:read32(POCKETS + 8)
    local key = emu:read16(emu:read32(H.gSaveBlock2Ptr) + 0xB0)
    emu:write16(slots, 1); emu:write16(slots + 2, 20 ~ key)
    emu:write16(ENEMY + 0x56, 1)          -- weaken to 1 HP so the ball lands
    base1, base2 = emu:read32(SB1_PTR), emu:read32(SB2_PTR)
    before1, before2 = snap(SB1_PTR, SPAN1), snap(SB2_PTR, SPAN2)
    console:log(string.format("DEXBIT bases SB1=0x%08X SB2=0x%08X party=%d",
                              base1, base2, emu:read8(PC)))
end)

-- Same input cadence as cm_catch_test.lua, which is the proven one for this
-- savestate; a hand-rolled cadence silently misses the throw.
H.onFrame(function(f)
    if f==100 or f==350 or f==600 then H.press(K.A, 12, 30) end
    if f==950  then H.press(K.RIGHT, 12, 30) end
    if f==1100 then H.press(K.A, 12, 30) end
    if f==1300 then H.press(K.RIGHT, 12, 30) end
    if f==1560 then H.press(K.A, 12, 40) end
    if f==1720 then H.press(K.A, 12, 40) end
    if f>1900 and f<4200 and f%80==0 then H.press(K.A, 8, 30) end
    if f==4400 then
        local party = emu:read8(PC)
        console:log("DEXBIT after party=" .. party)
        if party < 2 then
            console:log("DEXBIT !! catch did not land -- diff is meaningless")
        end
        bitdiff("SB1", before1, snap(SB1_PTR, SPAN1), base1)
        bitdiff("SB2", before2, snap(SB2_PTR, SPAN2), base2)
        H.finish()
    end
end)
