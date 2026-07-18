-- Full-speed flood-fill search for the cheat-clipboard trigger (no breakpoint).
-- Detector: gMain.callback2 (0x030014B8). Field/script/shop stay at
-- FIELD=0x08179791; only a genuine screen change (naming screen) moves it.
-- Drives keys DIRECTLY (no harness queue) with feedback-based movement.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local CB2 = 0x030014B8
local FIELD = 0x08179791
local function cb2() return emu:read32(CB2) end
local function rawpos()
    local sb1 = emu:read32(H.gSaveBlock1Ptr)
    return emu:read16(sb1 + H.SB1_POS_X), emu:read16(sb1 + H.SB1_POS_Y)
end

local co, resumeAt = nil, 0
local function waitf(n) coroutine.yield(n) end
-- Stable position read: player coords are only valid when idle; mid-step the
-- SaveBlock1 fields can read torn/garbage (e.g. x=14 on an 11-wide map). Wait
-- for two consecutive equal, in-range reads.
local function pos()
    local lx, ly = rawpos()
    for _ = 1, 30 do
        waitf(3)
        local x, y = rawpos()
        if x == lx and y == ly and x < 20 and y < 20 then return x, y end
        lx, ly = x, y
    end
    return lx, ly
end

local function faceDir(k) emu:addKey(k); waitf(6); emu:clearKey(k); waitf(8) end
local function tapA()     emu:addKey(K.A); waitf(6); emu:clearKey(K.A); waitf(6) end
local function tapB()     emu:addKey(K.B); waitf(6); emu:clearKey(K.B); waitf(8) end

-- Move one tile in direction k (already turned or will turn+step); returns moved?
local function stepMove(k, dx, dy)
    local ox, oy = pos()
    emu:addKey(k); waitf(18); emu:clearKey(k); waitf(12)
    local nx, ny = pos()
    return (nx == ox + dx and ny == oy + dy), nx, ny
end

local hit = false
local DIRS = { {K.UP,0,-1,"U"}, {K.RIGHT,1,0,"R"}, {K.DOWN,0,1,"D"}, {K.LEFT,-1,0,"L"} }
local OPP  = { [K.UP]=K.DOWN, [K.DOWN]=K.UP, [K.LEFT]=K.RIGHT, [K.RIGHT]=K.LEFT }
local visited = {}
local function kk(x,y) return x..","..y end

local function testTile(x, y)
    for _, d in ipairs(DIRS) do
        faceDir(d[1])          -- turn to face this wall/neighbor (no step)
        tapA(); waitf(34)      -- interact / raise "Enter a Character Mode code?"
        tapA(); waitf(42)      -- confirm YES (default cursor)
        local c = cb2()
        if c ~= FIELD then
            H.log(("*** HIT tile=(%d,%d) face=%s cb2=0x%08X ***"):format(x,y,d[4],c))
            emu:screenshot("tools/savestates/flood_hit.png")
            hit = true
            return true
        end
        tapB(); waitf(10); tapB(); waitf(10); tapB(); waitf(12)
    end
    return false
end

local function dfs(x, y)
    visited[kk(x,y)] = true
    H.log(("visit (%d,%d)"):format(x,y))
    if testTile(x, y) then return true end
    for _, d in ipairs(DIRS) do
        local nx, ny = x + d[2], y + d[3]
        if not visited[kk(nx,ny)] then
            -- turn first (so a blocked tile only turns, a walkable one steps)
            faceDir(d[1])
            local moved, px, py = stepMove(d[1], d[2], d[3])
            H.log(("try %s from (%d,%d) -> (%d,%d) moved=%s"):format(d[4],x,y,px,py,tostring(moved)))
            if moved then
                if dfs(nx, ny) then return true end
                -- return to (x,y)
                faceDir(OPP[d[1]])
                local back = false
                for _ = 1, 3 do
                    local ok, bx, by = stepMove(OPP[d[1]], -d[2], -d[3])
                    if bx == x and by == y then back = true; break end
                end
                if not back then
                    H.log(("WARN could not return to (%d,%d), now (%d,%d)"):format(x,y,select(1,pos()),select(2,pos())))
                end
            end
        end
    end
    return false
end

co = coroutine.create(function()
    waitf(20)
    local x, y = pos()
    H.log(("FLOOD start (%d,%d) cb2=0x%08X"):format(x,y,cb2()))
    if not dfs(x, y) then H.log("RESULT fired=false (flood exhausted)") end
    H.log("FLOOD done"); H.finish()
end)

H.onFrame(function(f)
    if coroutine.status(co) == "dead" or hit then return end
    if f < resumeAt then return end
    local ok, req = coroutine.resume(co, f)
    if not ok then H.log("CORO ERR: "..tostring(req)); H.finish(); hit=true; return end
    if type(req) == "number" then resumeAt = f + req end
end)
