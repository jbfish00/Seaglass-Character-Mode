-- Movement calibration on the CODE naming screen (from naming_open.ss).
-- Schedule presses at explicit, well-spaced frames (Lazarus-style) and
-- screenshot after each, to find timing that actually moves the cursor.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function press(f, key) H.onFrame(function(g) if g == f then H.press(key, 8) end end) end
press(40,  K.DOWN)
press(80,  K.DOWN)
press(120, K.RIGHT)
press(160, K.RIGHT)
press(200, K.RIGHT)
H.onFrame(function(f)
    if f == 60  then emu:screenshot("tools/savestates/nav_d1.png") end
    if f == 140 then emu:screenshot("tools/savestates/nav_d2r.png") end
    if f == 240 then emu:screenshot("tools/savestates/nav_end.png"); H.log("done") end
end)
