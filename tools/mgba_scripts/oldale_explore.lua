-- To the MART door (~(13-14,8)) from (8,10): right, up, probe door columns.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local PARTY = 0x02019C20
local K = H.KEY
local seq={}
local function add(k,n) for _=1,n do seq[#seq+1]=k end end
add(K.RIGHT,5); add(K.UP,2)
add(K.RIGHT,1); add(K.UP,2)
add(K.RIGHT,1); add(K.UP,2)
local idx=0
local lastAct=0
local last=nil
local finished=false
local END=3600
H.onFrame(function(f)
    if finished or f>END then return end
    if f%60==0 then local mx=emu:read16(PARTY+0x58); if mx>0 and mx<1000 then emu:write16(PARTY+0x56,mx) end end
    local b=emu:read32(SB1_PTR)
    local grp,num=emu:read8(b+4),emu:read8(b+5)
    local cur=string.format("%d,%d map=%d.%d",emu:read16(b),emu:read16(b+2),grp,num)
    if cur~=last then H.log("f="..f.." "..cur); last=cur end
    if grp==2 then
        finished=true
        emu:saveStateFile("tools/savestates/mart_inside.ss")
        H.log("ENTERED map "..grp.."."..num); H.finish(); return
    end
    if f-lastAct>44 and idx<#seq then idx=idx+1; lastAct=f; H.press(seq[idx],16,6) end
    if f==END then
        finished=true
        emu:screenshot("tools/savestates/nc_end.png")
        emu:saveStateFile("tools/savestates/nav_out.ss")
        H.log("cap"); H.finish()
    end
end)
