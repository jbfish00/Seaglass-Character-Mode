-- Overworld navigation driver (mgba-headless).
--
-- Loads a savestate (pass it with -t on the command line), runs an editable
-- sequence of directional/A/B presses, screenshots along the way, and writes a
-- new savestate at the end. This is how we hand-navigate the intro -> starter
-- -> first wild battle without a human, saving a checkpoint at each milestone
-- so we never replay a segment twice.
--
-- Run:
--   ./tools/mgba_src/build/mgba-headless --script tools/mgba_scripts/nav.lua \
--     -t tools/savestates/intro_end.ss "rom/seaglass v3.0.gba" \
--     > /tmp/nav.log 2>&1
--
-- Edit MOVES, OUT_STATE, and SHOT_TAG below for each segment.

local H = dofile("tools/mgba_scripts/harness.lua")

local SHOT_DIR  = "tools/savestates/"
local SHOT_TAG  = "truck"                      -- screenshot filename prefix
local OUT_STATE = SHOT_DIR .. "truck_out.ss"  -- savestate written at the end
local SETTLE    = 60                          -- frames to let the loaded state settle
local STEP      = 16                          -- frames to hold a direction = one tile step
local GAP       = 8                           -- release gap between presses

-- Movement program. Each entry is {KEY, holdFrames?, gap?}. Overworld tile
-- steps want ~16 held frames; menu/dialogue confirms want a short A tap.
local K = H.KEY
local MOVES = {
    { K.RIGHT, STEP },
    { K.RIGHT, STEP },
    { K.DOWN, STEP },
    { K.DOWN, STEP },
    { K.DOWN, STEP },
    { K.A, 4 },
}

-- Queue after settle.
H.onFrame(function(f)
    if f == SETTLE then
        for _, m in ipairs(MOVES) do
            H.press(m[1], m[2] or STEP, m[3] or GAP)
        end
        H.log("queued " .. #MOVES .. " moves at frame " .. f)
    end
end)

-- Screenshot cadence + final state. Compute an end frame generously past the
-- whole queued program so nothing is cut off, but BOUND it so we don't spew.
local total = SETTLE
for _, m in ipairs(MOVES) do total = total + (m[2] or STEP) + (m[3] or GAP) end
local END_FRAME = total + 120

local shots = 0
H.onFrame(function(f)
    if f > END_FRAME then return end
    if f % 12 == 0 then
        local p = string.format("%s%s_f%05d.png", SHOT_DIR, SHOT_TAG, f)
        emu:screenshot(p)
        shots = shots + 1
    end
    if f == END_FRAME then
        emu:saveStateFile(OUT_STATE)
        H.log("saved " .. OUT_STATE .. " after " .. #MOVES .. " moves, " .. shots .. " shots")
        H.finish()
    end
end)
