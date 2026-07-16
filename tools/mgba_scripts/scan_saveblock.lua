-- Scan SaveBlock1 for nonzero regions to locate the flags bitfield and vars
-- array. After the intro (clock set, several events fired) the flags array has
-- many bits set, so it shows up as a dense run of nonzero bytes; the vars array
-- likewise. Prints nonzero 16-byte rows with their SB1-relative offset.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local SPAN = 0x4000
local done=false
H.onFrame(function(f)
    if done or f<150 then return end
    done=true
    local base=emu:read32(SB1_PTR)
    H.log(string.format("SB1 base=0x%08X", base))
    local data=emu:readRange(base, SPAN)
    local row=0
    while row < SPAN do
        local any=false
        for i=1,16 do if string.byte(data,row+i)~=0 then any=true break end end
        if any then
            local t={}
            for i=1,16 do t[#t+1]=string.format("%02X",string.byte(data,row+i)) end
            H.log(string.format("+0x%04X: %s", row, table.concat(t," ")))
        end
        row=row+16
    end
    H.finish()
end)
