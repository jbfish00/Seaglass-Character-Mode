-- Flee a wild battle from any point in the intro: spaced A's clear the intro
-- text, then DOWN (FIGHT->POKEMON), RIGHT (POKEMON->RUN), A (flee), A (clear
-- "Got away safely!"). Cursor-edge behavior makes this order idempotent.
-- Saves tools/savestates/fled.ss on the overworld.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
H.onFrame(function(f)
    if f==200 or f==500 or f==800 then H.press(K.A, 12, 30) end
    if f==1100 then H.press(K.DOWN, 12, 30) end
    if f==1200 then H.press(K.RIGHT, 12, 30) end
    if f==1300 then H.press(K.A, 12, 30) end
    if f==1700 or f==2000 then H.press(K.A, 12, 30) end
    if f==2600 then
        emu:screenshot("tools/savestates/fled.png")
        emu:saveStateFile("tools/savestates/fled.ss")
        local b=emu:read32(SB1_PTR)
        H.log(string.format("fled: x=%d y=%d map=%d.%d",
            emu:read16(b), emu:read16(b+2), emu:read8(b+4), emu:read8(b+5)))
        H.finish()
    end
end)
