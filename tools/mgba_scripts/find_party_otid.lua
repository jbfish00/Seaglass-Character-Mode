-- Locate gPlayerParty unambiguously: the player's Torchic has the player's
-- OT-ID at record+4, while gEnemyParty's wild mon has a different OT-ID. Read
-- the player's trainerId from SaveBlock2, then scan EWRAM for a plausible mon
-- whose otId matches. That record's base = gPlayerParty[0].
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local SB2_PTR = 0x030051BC
local EW0, EW1 = 0x02000000, 0x02040000
local OFF_LEVEL, OFF_HP, OFF_MAXHP = 0x54, 0x56, 0x58

local ew
local function u8(a) return string.byte(ew, a-EW0+1) or 0 end
local function u16(a) return u8(a)+u8(a+1)*256 end
local function u32(a) return u16(a)+u16(a+2)*65536 end
local function plausible(a)
    local lv=u8(a+OFF_LEVEL); if lv<1 or lv>100 then return false end
    local hp=u16(a+OFF_HP); local mx=u16(a+OFF_MAXHP)
    if mx<1 or mx>999 or hp>mx then return false end
    local pid=u32(a); if pid==0 or pid==0xFFFFFFFF then return false end
    return true
end

local done=false
H.onFrame(function(f)
    if done or f<120 then return end
    done=true
    local sb2=emu:read32(SB2_PTR)
    -- SaveBlock2: playerName[8], gender, ?, trainerId[4] @ +0x0A. +0x0A is only
    -- 2-aligned, so emu:read32 would do a rotated (wrong) read -- combine two u16.
    local otid = emu:read16(sb2+0x0A) + emu:read16(sb2+0x0C)*65536
    H.log(string.format("player OT-ID (SB2+0x0A) = 0x%08X", otid))
    ew = emu:readRange(EW0, EW1-EW0)
    local hits={}
    local a=EW0
    while a < EW1-0x60 do
        if plausible(a) and u32(a+4)==otid then
            hits[#hits+1]=a
        end
        a=a+4
    end
    H.log(string.format("records with player OT-ID: %d", #hits))
    for _,a in ipairs(hits) do
        H.log(string.format("  0x%08X lvl=%d hp=%d/%d pid=0x%08X",
            a, u8(a+OFF_LEVEL), u16(a+OFF_HP), u16(a+OFF_MAXHP), u32(a)))
    end
    -- gPlayerParty base = the lowest such address (slot 0). Count = how many
    -- consecutive slots (stride guess) are player-owned + alive.
    H.finish()
end)
