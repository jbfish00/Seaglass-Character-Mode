-- Re-capture naming_open.ss on the current build: from mart_inside.ss, walk to
-- the clipboard (LEFT x3, UP x2), A (prompt), A (yes) -> CM_OpenCodeEntry. When
-- that breakpoint fires, save naming_open.ss ~90 frames later (screen faded in).
local H = dofile("tools/mgba_scripts/harness.lua")
local K = H.KEY
-- overworld movement via the queue
for _ = 1, 3 do H.press(K.LEFT, 12, 8) end
for _ = 1, 2 do H.press(K.UP, 12, 8) end
-- interact: A to raise "Enter a Character Mode code?" then A to pick YES
H.onFrame(function(f) if f == 160 then H.press(K.A, 6) end end)  -- prompt
H.onFrame(function(f) if f == 230 then H.press(K.A, 6) end end)  -- YES

local fireAt = nil
H.breakpoint("Open", 0x08ED2270, function(fr) if not fireAt then fireAt = fr; H.log("CM_OpenCodeEntry fired f="..fr) end end)
H.onFrame(function(f)
    if fireAt and f == fireAt + 90 then
        emu:screenshot("tools/savestates/naming_open.png")
        emu:saveStateFile("tools/savestates/naming_open.ss")
        H.log("saved naming_open.ss")
        H.finish()
    end
    if f == 900 and not fireAt then H.log("NEVER FIRED"); emu:screenshot("tools/savestates/cap_fail.png"); H.finish() end
end)
