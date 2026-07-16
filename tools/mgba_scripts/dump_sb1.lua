-- Dump the whole of SaveBlock1 (deref'd) as offset:hex rows to stdout, so two
-- checkpoint states can be diffed offline to localize the flags/vars arrays.
-- The flags array shows up as a contiguous region that changes at the BIT level
-- between a before/after pair of story states.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local SPAN = 0x3A00
local done=false
H.onFrame(function(f)
    if done or f<150 then return end
    done=true
    local base=emu:read32(SB1_PTR)
    console:log(string.format("SB1BASE 0x%08X", base))
    local data=emu:readRange(base, SPAN)
    local row=0
    while row<SPAN do
        local t={}
        for i=1,32 do t[#t+1]=string.format("%02X", string.byte(data,row+i) or 0) end
        console:log(string.format("SB1 %04X %s", row, table.concat(t)))
        row=row+32
    end
    console:log("SB1END")
    H.finish()
end)
