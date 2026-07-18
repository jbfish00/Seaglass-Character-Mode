-- Full-speed unified flood-fill search for the cheat-clipboard trigger.
-- Uses H.press (proven reliable) with generous waits so the input queue never
-- backs up. Pressing a direction either STEPS (walkable neighbor) or TURNS to
-- face a wall/object (blocked). So each direction press both explores AND, when
-- blocked, lets us interaction-test (A + YES) that wall — checking callback2
-- (0x030014B8): field/script/shop stay 0x08179791, only the naming screen moves
-- it. Never press DOWN at y>=7 (nothing walkable below; the exit mat is there).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local CB2 = 0x030014B8
local FIELD = 0x08179791
local MART = 2*256 + 4    -- map 2.4
local function raw()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1+H.SB1_POS_X), emu:read16(sb1+H.SB1_POS_Y),
           emu:read8(sb1+H.SB1_MAPGRP)*256 + emu:read8(sb1+H.SB1_MAPNUM)
end
local function cb2() return emu:read32(CB2) end

local co, resumeAt = nil, 0
local function waitf(n) coroutine.yield(n) end
-- stable read: coords are torn mid-step; require two equal in-range reads.
local function pos()
    local lx,ly,lm = raw()
    for _=1,40 do
        waitf(3)
        local x,y,m = raw()
        if x==lx and y==ly and m==lm and x<24 and y<24 then return x,y,m end
        lx,ly,lm = x,y,m
    end
    return lx,ly,lm
end
local function stepPress(k) H.press(k,12,8); waitf(28) end
local function tapA() H.press(K.A,6,8); waitf(34) end
local function tapAyes() H.press(K.A,6,8); waitf(42) end
local function tapB() H.press(K.B,6,8); waitf(16) end

local hit = false
local DIRS = { {K.UP,0,-1,"U"}, {K.RIGHT,1,0,"R"}, {K.LEFT,-1,0,"L"}, {K.DOWN,0,1,"D"} }
local OPP  = { [K.UP]=K.DOWN, [K.DOWN]=K.UP, [K.LEFT]=K.RIGHT, [K.RIGHT]=K.LEFT }
local visited = {}
local function kk(x,y) return x..","..y end
local nTested = 0

local function interactTest(x,y,dirName)
    tapA()               -- start prompt (player already faces the wall)
    tapAyes()            -- confirm YES (default cursor)
    local c = cb2()
    nTested = nTested + 1
    if c ~= FIELD then
        H.log(("*** HIT tile=(%d,%d) face=%s cb2=0x%08X ***"):format(x,y,dirName,c))
        emu:screenshot("tools/savestates/flood_hit.png")
        hit = true
        return true
    end
    tapB(); tapB(); tapB()   -- dismiss any dialog/menu
    return false
end

local function dfs(x,y)
    visited[kk(x,y)] = true
    H.log(("visit (%d,%d) tested=%d"):format(x,y,nTested))
    for _,d in ipairs(DIRS) do
        if not (d[4]=="D" and y>=7) then         -- never step/probe down at bottom
            local nx,ny = x+d[2], y+d[3]
            stepPress(d[1])
            local cx,cy,cm = pos()
            if cm ~= MART then
                -- warped out unexpectedly; re-enter and bail this branch
                H.log(("WARP out at (%d,%d) dir=%s -> re-entering"):format(x,y,d[4]))
                for _=1,4 do stepPress(K.UP); local _,_,m=pos(); if m==MART then break end end
                return false
            elseif cx==x and cy==y then
                -- blocked: player now faces d -> interaction-test this wall
                if interactTest(x,y,d[4]) then return true end
            elseif cx==nx and cy==ny then
                if not visited[kk(nx,ny)] then
                    if dfs(nx,ny) then return true end
                end
                -- step back to (x,y)
                stepPress(OPP[d[1]])
                local bx,by = pos()
                if bx~=x or by~=y then
                    stepPress(OPP[d[1]])   -- one retry
                end
            else
                -- moved somewhere unexpected (2 tiles / drift); resync by
                -- pathing not attempted — just log and continue best-effort.
                H.log(("DRIFT at (%d,%d) dir=%s -> (%d,%d)"):format(x,y,d[4],cx,cy))
                -- try to get back
                stepPress(OPP[d[1]])
            end
        end
    end
    return false
end

co = coroutine.create(function()
    waitf(20)
    local x,y,m = pos()
    H.log(("FLOOD2 start (%d,%d) map=%d cb2=0x%08X"):format(x,y,m,cb2()))
    if not dfs(x,y) then H.log("RESULT fired=false (exhausted), tiles tested="..nTested) end
    H.log("FLOOD2 done"); H.finish()
end)

H.onFrame(function(f)
    if coroutine.status(co)=="dead" or hit then return end
    if f < resumeAt then return end
    local ok,req = coroutine.resume(co,f)
    if not ok then H.log("CORO ERR: "..tostring(req)); H.finish(); hit=true; return end
    if type(req)=="number" then resumeAt = f + req end
end)
