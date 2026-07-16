-- Set ONLY flag 0x74 (the intro gate: "player has a POKeMON"), walk from
-- outside_house.ss through the now-open Littleroot north exit onto Route 101
-- (map 0.16), and continue north into the tall grass to trigger the Prof. Birch
-- rescue cutscene (the starter source). A-mash the dialogue; screenshot + save.
--
-- Flags-array base pinned by bisection: SaveBlock1 + 0x157E. flag N -> byte
-- 0x157E + N/8, bit N%8. flag 0x74 -> byte 0x158C bit 4.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
local FLAGS_BASE = 0x157E
local function sb1() return emu:read32(SB1_PTR) end
local function setflag(id)
    local a = sb1() + FLAGS_BASE + math.floor(id/8)
    emu:write8(a, emu:read8(a) | (1 << (id%8)))
end

local set=false
H.onFrame(function(f)
    if f==90 and not set then
        set=true
        setflag(0x74)
        H.log(string.format("set flag 0x74 @SB1+0x%04X bit4 = 0x%02X",
            0x158C, emu:read8(sb1()+0x158C)))
        local seq={
            {K.DOWN,16},{K.RIGHT,16},{K.RIGHT,16},{K.RIGHT,16},
            {K.RIGHT,16},{K.RIGHT,16},{K.RIGHT,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.LEFT,16},{K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
        }
        for _,m in ipairs(seq) do H.press(m[1],m[2],8) end
    end
end)
-- A-mash from frame 700 onward to clear the rescue dialogue.
H.mash(K.A, 700, 2000, 22)

local last=nil
local END=2200
H.onFrame(function(f)
    if f>END then return end
    if f<90 then return end
    local base=sb1()
    if base<0x02000000 or base>=0x02040000 then return end
    local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if f%150==0 then emu:screenshot(string.format("tools/savestates/rs_f%05d.png", f)) end
    if f==END then emu:saveStateFile("tools/savestates/route101.ss"); H.log("saved route101.ss"); H.finish() end
end)
