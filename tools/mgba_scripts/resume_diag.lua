-- Diagnose the post-commit resume: type RED, commit, then sample gMain.callback2
-- (0x030014B8) and screenshot at intervals to see whether the naming screen
-- closed and whether the script resumed.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ROWS = { "ABCDEF .", "GHIJKL ,", "MNOPQRS ", "TUVWXYZ " }
local function findKey(ch)
    for r,row in ipairs(ROWS) do local c=row:find(ch,1,true); if c then return r-1,c-1 end end
end
local plan={}; local cr,cc=0,0
for i=1,#"RED" do local r,c=findKey(("RED"):sub(i,i))
    while cr<r do plan[#plan+1]=K.DOWN;cr=cr+1 end
    while cr>r do plan[#plan+1]=K.UP;cr=cr-1 end
    while cc<c do plan[#plan+1]=K.RIGHT;cc=cc+1 end
    while cc>c do plan[#plan+1]=K.LEFT;cc=cc-1 end
    plan[#plan+1]=K.A end
plan[#plan+1]=K.START; plan[#plan+1]=K.A
for i=1,#plan do local key=plan[i]; local w=40+(i-1)*40
    H.onFrame(function(f) if f==w then H.press(key,8) end end) end
local commit=40+(#plan-1)*40
for _,dt in ipairs({30,80,150,300,500}) do
    H.onFrame(function(f)
        if f==commit+dt then
            H.log(("+%d callback2=0x%08X"):format(dt, emu:read32(0x030014B8)))
            emu:screenshot(("tools/savestates/resume_%d.png"):format(dt))
        end
    end)
end
H.onFrame(function(f) if f==commit+520 then H.finish() end end)
