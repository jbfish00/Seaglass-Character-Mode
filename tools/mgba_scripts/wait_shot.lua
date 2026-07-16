-- Load a savestate, apply NO input, screenshot periodically. Decides whether a
-- scene auto-progresses (e.g. the moving-truck auto-exit) vs. needs navigation.
local H = dofile("tools/mgba_scripts/harness.lua")
local DIR = "tools/savestates/"
local TAG = "wait"
local END_FRAME = 1200
H.onFrame(function(f)
    if f > END_FRAME then return end
    if f % 100 == 0 then emu:screenshot(string.format("%s%s_f%05d.png", DIR, TAG, f)) end
    if f == END_FRAME then H.log("wait done"); H.finish() end
end)
