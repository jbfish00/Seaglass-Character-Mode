-- Set flag 0x74 at a candidate flags-array base, then navigate from
-- outside_house.ss to the Route 101 north exit and check whether the gate opens
-- (map 0.9 -> Route 101). Diff of SaveBlock1 (littleroot_arrival vs
-- outside_house) put the flags bitfield at ~0x13C0, so flag 0x74 (byte 0x0E,
-- bit 4) -> SB1+0x13CE bit4. Change FLAGBASE per run to sweep candidates.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
-- RANGE MODE: set bit 4 of every byte in [LO,HI). If flag 0x74's byte is in the
-- range, the gate shows "…Good luck!" (only flag 0x74 does). Bisect on that.
-- WIDE INSTRUMENTED TEST: set bit4 across a big range, log SB1 base at set-time,
-- verify at gate-time that the pointer is stable and the write persisted.
-- 2026-07-16: static disasm of FlagSet (0x0810D254, found via the script cmd
-- table @0x0826D970 entry 0x29) proves the TRUE flags base is SB1+0x13C0, so
-- flag 0x74 = byte +0x13CE bit4. The old empirical hit (+0x158C bit4) was
-- actually var 0x4050 |= 0x10 (vars base = SB1+0x14EC) — the gate's
-- "compare var 0x4050,0 → pass if !=0" branch, not checkflag 0x74.
local LO = 0x13CE
local HI = 0x13CF
local base_at_set = nil

local function sb1() return emu:read32(SB1_PTR) end

local set=false
H.onFrame(function(f)
    if f==90 and not set then
        set=true
        local base=sb1(); base_at_set=base
        for a=base+LO, base+HI-1 do emu:write8(a, emu:read8(a) | 0x10) end
        H.log(string.format("SET bit4 across SB1(0x%08X)+0x%04X..0x%04X, sample[+0x%04X]=0x%02X",
            base, LO, HI, LO+0x2A, emu:read8(base+LO+0x2A)))
        -- navigate outside_house (5,9) -> north exit
        local seq={
            {K.DOWN,16},{K.RIGHT,16},{K.RIGHT,16},{K.RIGHT,16},
            {K.RIGHT,16},{K.RIGHT,16},{K.RIGHT,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.UP,16},{K.UP,16},{K.UP,16},{K.UP,16},
            {K.LEFT,16},{K.UP,16},{K.UP,16},{K.UP,16},
        }
        for _,m in ipairs(seq) do H.press(m[1],m[2],8) end
    end
end)

local last=nil
H.onFrame(function(f)
    if f<90 then return end
    local base=sb1()
    if base<0x02000000 or base>=0x02040000 then return end
    local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
    if cur~=last then H.log("f="..f.." "..cur); last=cur
        local g=emu:read8(base+4)
        if g~=0 and g~=1 then H.log("!!! ON ROUTE/other map "..g.."."..emu:read8(base+5).." — GATE OPENED") end
    end
    if f==470 and base_at_set then
        H.log(string.format("VERIFY gate-time SB1=0x%08X (set-time 0x%08X, %s); sample[+0x%04X]=0x%02X",
            base, base_at_set, base==base_at_set and "STABLE" or "MOVED!!", LO+0x2A, emu:read8(base+LO+0x2A)))
    end
    if f==700 then emu:screenshot("tools/savestates/gate_test.png"); H.finish() end
end)
