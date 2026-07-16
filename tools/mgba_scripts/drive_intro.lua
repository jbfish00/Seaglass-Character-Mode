-- Drive the Seaglass intro headlessly, capturing screenshots + a savestate.
--
-- Purpose: get from a cold boot to a controllable overworld state without a
-- human. A-mashing clears the Prof Birch speech and the moving-truck fade; this
-- script captures periodic screenshots so navigation can be eyeballed, and
-- writes a savestate at the end so subsequent runs don't replay the whole intro.
--
-- Run:
--   ./tools/mgba_src/build/mgba-headless \
--     --script tools/mgba_scripts/drive_intro.lua \
--     "rom/seaglass v3.0.gba" > /tmp/drive_intro.log 2>&1
--
-- Tunables via env-like globals set by editing below.

local H = dofile("tools/mgba_scripts/harness.lua")

local SHOT_DIR   = "tools/savestates/"
local SHOT_EVERY = 500        -- screenshot cadence (frames)
local END_FRAME  = 9000       -- stop + save state here
local STATE_PATH = SHOT_DIR .. "intro_end.ss"

-- Mash A across the whole intro to clear dialogue + confirmations.
H.mash(H.KEY.A, 30, END_FRAME, 24)

local shots = 0
H.onFrame(function(f)
    if f > END_FRAME then return end   -- bound: headless runs ~1800fps, don't spew past the goal
    if f % SHOT_EVERY == 0 then
        local path = string.format("%sintro_f%05d.png", SHOT_DIR, f)
        emu:screenshot(path)
        shots = shots + 1
        H.log("shot " .. path)
    end
    if f == END_FRAME then
        emu:saveStateFile(STATE_PATH)
        H.log("saved state " .. STATE_PATH)
        H.log("captured " .. shots .. " screenshots")
        H.finish()
    end
end)
