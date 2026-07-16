-- Locate the flags bitfield in SaveBlock1 and set flag 0x74 (the "player has a
-- POKeMON" gate the Littleroot north-exit NPC checks), then walk north and see
-- if the gate opens (map 0.9 -> Route 101). savestate-safe: a wrong offset just
-- fails the walk; nothing is persisted unless we choose to.
--
-- Gate logic (decoded from ROM script @0x0827DBEF):
--   checkflag 0x74 -> if set, "Are you going to catch POKeMON? Good luck!" (pass)
--   else -> "Um, um, um! ... wild POKeMON will jump out!" (block)
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY

-- pokeemerald SaveBlock1.flags candidate offsets (vanilla=0x1270; expansion
-- variants shift it). We dump a few so the real bitfield is identifiable, then
-- set flag 0x74 at CAND.
local CAND = tonumber(arg and arg[1]) or 0x1270
local FLAG = 0x74
local byteOff, bit = math.floor(FLAG/8), FLAG%8

local function sb1() return emu:read32(SB1_PTR) end
local function dump(base, off, n)
    local t = {}
    for i=0,n-1 do t[#t+1]=string.format("%02X", emu:read8(base+off+i)) end
    return table.concat(t," ")
end

local set=false
H.onFrame(function(f)
    if f==120 and not set then
        set=true
        local base=sb1()
        H.log(string.format("SB1 base=0x%08X map=%d.%d", base,
            emu:read8(base+4), emu:read8(base+5)))
        for _,o in ipairs({0x1270,0x1290,0xEE0,0x109C,0x1200,0x139C}) do
            H.log(string.format("  flags?@+0x%04X: %s", o, dump(base,o,16)))
        end
        -- set flag FLAG at CAND
        local a=base+CAND+byteOff
        local before=emu:read8(a)
        emu:write8(a, before | (1<<bit))
        H.log(string.format("SET flag 0x%X at SB1+0x%04X+0x%X (byte 0x%02X->0x%02X)",
            FLAG, CAND, byteOff, before, emu:read8(a)))
        -- now try to pass north: we assume we start at/near (10,1) or (11,2)
        H.press(K.B,4,16)
        for _=1,4 do H.press(K.UP,16,8) end
    end
end)

local last=nil
H.onFrame(function(f)
    if f<120 then return end
    local base=sb1()
    if base<0x02000000 or base>=0x02040000 then return end
    local cur=string.format("x=%d y=%d map=%d.%d", emu:read16(base),emu:read16(base+2),emu:read8(base+4),emu:read8(base+5))
    if cur~=last then H.log("f="..f.." "..cur); last=cur
        if emu:read8(base+4)~=0 and emu:read8(base+4)~=1 then H.log("!!! reached map "..emu:read8(base+4).."."..emu:read8(base+5)) end
    end
    if f==400 then emu:screenshot("tools/savestates/flagprobe.png"); H.finish() end
end)
