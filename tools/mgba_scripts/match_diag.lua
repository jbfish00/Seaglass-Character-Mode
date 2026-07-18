-- Diagnose CM_MatchCode: type RED, commit, and when CM_MatchCode (0x08ED22B0)
-- fires, dump the committed gStringVar2 buffer + the resulting flag/var.
-- No mash (avoid re-triggering the clipboard).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local ROWS = { "ABCDEF .", "GHIJKL ,", "MNOPQRS ", "TUVWXYZ " }
local function findKey(ch)
    for r, row in ipairs(ROWS) do local c=row:find(ch,1,true); if c then return r-1,c-1 end end
end
local plan = {}
local cr,cc = 0,0
for i=1,#"RED" do
    local r,c = findKey(("RED"):sub(i,i))
    while cr<r do plan[#plan+1]=K.DOWN; cr=cr+1 end
    while cr>r do plan[#plan+1]=K.UP; cr=cr-1 end
    while cc<c do plan[#plan+1]=K.RIGHT; cc=cc+1 end
    while cc>c do plan[#plan+1]=K.LEFT; cc=cc-1 end
    plan[#plan+1]=K.A
end
plan[#plan+1]=K.START; plan[#plan+1]=K.A
for i=1,#plan do local key=plan[i]; local w=40+(i-1)*40
    H.onFrame(function(f) if f==w then H.press(key,8) end end) end
local commit = 40+(#plan-1)*40

local fired = false
H.breakpoint("MatchCode", 0x08ED22B0, function()
    if fired then return end
    fired = true
    local s=""
    for j=0,10 do s=s..string.format("%02X ", emu:read8(0x0203AF24+j)) end
    H.log("MatchCode ENTER gStringVar2: "..s)
end)
H.onFrame(function(f)
    if f == commit + 400 then
        H.log(("post: flag=%d char=%d starter=%d fired=%s"):format(
            H.getFlag(0x945), H.getVar(0x40E4), H.getVar(0x40E5), tostring(fired)))
        H.finish()
    end
end)
