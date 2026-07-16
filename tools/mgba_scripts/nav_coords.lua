-- Coordinate-aware navigation: reads the player's live map coords + current map
-- from SaveBlock1 (trio[1]=0x030051B8, confirmed) and logs every change, so we
-- can tell exactly which presses move the player and detect the truck exit
-- (mapGroup/mapNum change away from 25/40) without eyeballing screenshots.
--
--   SaveBlock1 + 0x00 s16 pos.x
--   SaveBlock1 + 0x02 s16 pos.y
--   SaveBlock1 + 0x04 u8  mapGroup
--   SaveBlock1 + 0x05 u8  mapNum
--
-- Edit MOVES per run. Screenshots at end + a savestate for checkpointing.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local DIR = "tools/savestates/"
local TAG = "nc"
local OUT = DIR .. "nav_out.ss"
local SETTLE, STEP, GAP = 60, 16, 8
local K = H.KEY

-- EDIT THIS per run:
-- From outside_house.ss (player at (5,9), just below own house door): go east
-- along the town to the neighbor's (east) house, then up to its door to enter.
-- From nav_out.ss (10,1, blocker open): close dialogue, probe cols 12/13 UP
-- for the Route 101 connection (going around the blocker NPC + trees).
-- Test control after lab dialogue: close box, walk toward the south exit.
local MOVES = {
    { K.B, 4, 16 },
    { K.DOWN, STEP }, { K.DOWN, STEP }, { K.DOWN, STEP },
    { K.DOWN, STEP }, { K.DOWN, STEP }, { K.DOWN, STEP },
}
local WATCH = false  -- periodic screenshots to catch a cutscene playing out

local function sb1() return emu:read32(SB1_PTR) end
local function readState()
    local b = sb1()
    if b < 0x02000000 or b >= 0x02040000 then return nil end
    return {
        x = emu:read16(b + 0), y = emu:read16(b + 2),
        grp = emu:read8(b + 4), num = emu:read8(b + 5),
    }
end

local last = nil
local function fmt(s) return string.format("x=%d y=%d map=%d.%d", s.x, s.y, s.grp, s.num) end

local queued = false
H.onFrame(function(f)
    if f == SETTLE then
        for _, m in ipairs(MOVES) do H.press(m[1], m[2] or STEP, m[3] or GAP) end
        queued = true
        local s = readState()
        if s then H.log("START " .. fmt(s)); last = fmt(s) end
    end
    if queued then
        local s = readState()
        if s then
            local cur = fmt(s)
            if cur ~= last then
                H.log(string.format("f=%d %s", f, cur))
                last = cur
                if s.grp ~= 25 then H.log("!!! LEFT TRUCK -> map " .. s.grp .. "." .. s.num) end
            end
        end
    end
end)

local total = SETTLE
for _, m in ipairs(MOVES) do total = total + (m[2] or STEP) + (m[3] or GAP) end
local END_FRAME = total + (WATCH and 500 or 120)
H.onFrame(function(f)
    if f > END_FRAME then return end   -- bound: emulator keeps running past finish()
    if WATCH and f > total and f % 80 == 0 then
        emu:screenshot(string.format("%s%s_w%05d.png", DIR, TAG, f))
    end
    if f == END_FRAME then
        emu:screenshot(DIR .. TAG .. "_end.png")
        emu:saveStateFile(OUT)
        H.log("done; saved " .. OUT)
        H.finish()
    end
end)
