-- For each gPlayerParty candidate, print slot levels at stride 100/104 to see
-- which is the real party array (slot0=Torchic lvl5, slots 1-5 empty=lvl0).
-- Also probe for gPlayerPartyCount (u8=1) in the words just before each base.
local H = dofile("tools/mgba_scripts/harness.lua")
local CANDS = { 0x02019C20, 0x0201ACD8, 0x0201AF30 }
local done=false
H.onFrame(function(f)
    if done or f<120 then return end
    done=true
    for _,base in ipairs(CANDS) do
        for _,stride in ipairs({100,104}) do
            local lv={}
            for s=0,5 do lv[#lv+1]=emu:read8(base+s*stride+0x54) end
            H.log(string.format("base=0x%08X stride=%d slot-levels: %d %d %d %d %d %d",
                base, stride, lv[1],lv[2],lv[3],lv[4],lv[5],lv[6]))
        end
    end
    H.finish()
end)
