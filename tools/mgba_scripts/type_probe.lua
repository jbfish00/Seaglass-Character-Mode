-- Minimal: navigate to R (row2,col5) and type it, screenshotting the cursor
-- along the way. No mash, no assert. Isolates the navigation/typing timing.
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
local function at(f, key) H.onFrame(function(g) if g == f then H.press(key, 8) end end) end
-- to R: DOWN,DOWN, RIGHT x5
at(40,  K.DOWN)
at(80,  K.DOWN)
at(120, K.RIGHT)
at(160, K.RIGHT)
at(200, K.RIGHT)
at(240, K.RIGHT)
at(280, K.RIGHT)
H.onFrame(function(f) if f == 310 then emu:screenshot("tools/savestates/tp_atR.png"); H.log("shot atR") end end)
at(330, K.A)   -- type R
H.onFrame(function(f) if f == 380 then emu:screenshot("tools/savestates/tp_typedR.png"); H.log("shot typedR"); H.finish() end end)
