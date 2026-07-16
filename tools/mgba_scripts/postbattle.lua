-- Clear end-of-battle text (EXP etc.) back to the overworld; save state.
local H = dofile("tools/mgba_scripts/harness.lua")
local SB1_PTR = 0x030051B8
local K = H.KEY
H.onFrame(function(f)
    if f%300==200 and f<2400 then H.press(K.A, 12, 30) end
    if f==3000 then
        emu:screenshot("tools/savestates/postbattle.png")
        emu:saveStateFile("tools/savestates/postbattle.ss")
        local b=emu:read32(SB1_PTR)
        H.log(string.format("post: x=%d y=%d map=%d.%d",
            emu:read16(b), emu:read16(b+2), emu:read8(b+4), emu:read8(b+5)))
        H.finish()
    end
end)
